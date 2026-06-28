#!/usr/bin/env python3
"""
insumos-mcp - MCP server to bulk-import CSV data into an insumosUCV instance.

It talks to the app's REST API over the LAN (default http://localhost:8080), so an
admin can run it from any machine that can reach the acopio server, and every write
goes through the app's own validation and unique-product-name constraint.

Tools:
  get_status            - check connectivity + current counts
  list_productos        - list the product catalog (optionally filtered by category)
  import_productos_csv  - bulk-create products from a CSV (catalog / master list)
  import_registros_csv  - bulk-create donation records from a CSV (e.g. migrate Excel)
  export_registros_csv  - pull the app's CSV export (handy backup before importing)

Config (env):
  INSUMOS_BASE_URL  base URL of the running app   (default: http://localhost:8080)
  INSUMOS_TIMEOUT   per-request timeout, seconds   (default: 30)

Requires Python 3.10+.
"""

import csv
import io
import os
import re
import unicodedata
from datetime import datetime

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("INSUMOS_BASE_URL", "http://localhost:8080").rstrip("/")
TIMEOUT = float(os.environ.get("INSUMOS_TIMEOUT", "30"))
MAX_ERRORS = 50  # cap how many per-row errors we report back

mcp = FastMCP("insumos")


# ------------------------------ HTTP helpers ------------------------------

def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


def _safe_err(resp: httpx.Response) -> str:
    try:
        return resp.json().get("error", f"HTTP {resp.status_code}")
    except Exception:
        return f"HTTP {resp.status_code}"


# ------------------------------ parsing helpers ------------------------------

def _norm(s: str) -> str:
    """Lowercase, strip accents, collapse non-alphanumerics to single spaces."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Normalized column aliases (Spanish/English, accent-insensitive).
_ALIASES = {
    "nombre":    {"nombre", "producto", "product", "name", "articulo", "item",
                  "descripcion", "insumo"},
    "unidad":    {"unidad", "unit", "medida", "unidad de medida", "um", "u m"},
    "categoria": {"categoria", "category", "cat", "modulo", "grupo", "rubro"},
    "cantidad":  {"cantidad por unidad", "cantidad", "cantidad por envase", "cant",
                  "cant por envase", "contenido", "cantidad por paquete",
                  "cantidad envase"},
    "num":       {"num unidades", "numero de envases", "envases", "numero de paquetes",
                  "paquetes", "cantidad de envases", "numero", "num", "n envases",
                  "cantidad recibida", "numero de unidades", "nro envases",
                  "nro de envases"},
    "fecha":     {"fecha", "date", "fecha y hora", "timestamp", "fecha hora"},
    "total":     {"total", "total recibido", "cantidad total"},
}


def _row_get(norm_row: dict, field: str):
    for alias in _ALIASES[field]:
        val = norm_row.get(alias)
        if val:
            return val
    return None


def _parse_number(raw) -> float:
    """Parse a number tolerating Spanish (1.234,56) and English (1,234.56) formats."""
    if raw is None:
        raise ValueError("numero vacio")
    s = str(raw).strip().replace(" ", "")
    if not s:
        raise ValueError("numero vacio")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,56  (es)
        else:
            s = s.replace(",", "")                       # 1,234.56  (en)
    elif "," in s:
        s = s.replace(",", ".")                          # 1,5 -> 1.5
    return float(s)


_FECHA_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
    "%d-%m-%Y", "%m/%d/%Y",
)


def _normalize_fecha(raw):
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).strip()
    for fmt in _FECHA_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return s  # pass through; the optional app patch stores whatever string we send


def _read_csv(path, csv_text):
    """Return (rows, delimiter, fieldnames). Each row is a dict keyed by NORMALIZED header."""
    if (path is None) == (csv_text is None):
        raise ValueError("Especifica exactamente uno: 'path' o 'csv_text'.")
    if path is not None:
        with open(os.path.expanduser(path), "r", encoding="utf-8-sig", newline="") as f:
            text = f.read()
    else:
        text = csv_text.lstrip("﻿")

    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        delim = ";" if sample.count(";") >= sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    for raw in reader:
        norm_row = {}
        for k, v in raw.items():
            if k is None:
                continue
            norm_row[_norm(k)] = (v or "").strip()
        if any(norm_row.values()):
            rows.append(norm_row)
    return rows, delim, (reader.fieldnames or [])


def _fetch_product_map(c: httpx.Client) -> dict:
    r = c.get("/api/productos")
    r.raise_for_status()
    return {_norm(p["nombre"]): p for p in r.json()}


# --------------------------------- tools ---------------------------------

@mcp.tool()
def get_status() -> dict:
    """Comprueba la conexion con la app insumosUCV y devuelve los conteos actuales
    (productos y registros). Usalo para verificar la URL antes de importar."""
    try:
        with _client() as c:
            prods = c.get("/api/productos"); prods.raise_for_status()
            regs = c.get("/api/registros"); regs.raise_for_status()
    except Exception as e:
        return {"ok": False, "base_url": BASE_URL, "error": f"No se pudo conectar: {e}"}
    return {"ok": True, "base_url": BASE_URL,
            "productos": len(prods.json()), "registros": len(regs.json())}


@mcp.tool()
def list_productos(categoria: str | None = None) -> dict:
    """Lista el catalogo de productos actual (id, nombre, unidad, categoria).
    Opcionalmente filtra por categoria (sin distinguir acentos/mayusculas)."""
    try:
        with _client() as c:
            r = c.get("/api/productos"); r.raise_for_status()
            items = r.json()
    except Exception as e:
        return {"ok": False, "error": f"No se pudo conectar: {e}"}
    if categoria:
        cn = _norm(categoria)
        items = [p for p in items if _norm(p.get("categoria", "")) == cn]
    return {"ok": True, "count": len(items), "productos": items}


@mcp.tool()
def import_productos_csv(path: str | None = None, csv_text: str | None = None,
                         default_unidad: str | None = None,
                         default_categoria: str = "Otros",
                         dry_run: bool = False) -> dict:
    """Importa un catalogo de productos desde un CSV (lista maestra / migracion de Excel).

    Columnas reconocidas (acentos/mayusculas y alias flexibles):
      nombre|producto  (requerido), unidad|medida, categoria|modulo.
    Las filas cuyo nombre ya existe se omiten sin error (constraint UNIQUE del backend),
    asi que el import es idempotente: puedes correrlo varias veces.

    Args:
      path: ruta a un archivo .csv en la maquina del admin, O
      csv_text: el contenido CSV en linea (usa solo UNO de los dos).
      default_unidad: unidad a usar si la fila no trae columna de unidad.
      default_categoria: categoria por defecto (def. 'Otros').
      dry_run: si True, valida y reporta que pasaria SIN escribir nada.
    """
    try:
        rows, delim, _ = _read_csv(path, csv_text)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        with _client() as c:
            existing = {k for k in _fetch_product_map(c)}
    except Exception as e:
        return {"ok": False, "error": f"No se pudo conectar: {e}"}

    created = skipped = 0
    errors = []
    with _client() as c:
        for i, row in enumerate(rows, start=2):  # row 1 = header
            nombre = _row_get(row, "nombre")
            if not nombre:
                errors.append({"fila": i, "error": "falta 'nombre'"}); continue
            unidad = _row_get(row, "unidad") or default_unidad
            if not unidad:
                errors.append({"fila": i, "nombre": nombre,
                               "error": "falta 'unidad' y no hay default_unidad"}); continue
            categoria = _row_get(row, "categoria") or default_categoria
            if _norm(nombre) in existing:
                skipped += 1; continue
            if dry_run:
                created += 1; existing.add(_norm(nombre)); continue
            try:
                resp = c.post("/api/productos",
                              json={"nombre": nombre, "unidad": unidad, "categoria": categoria})
            except Exception as e:
                errors.append({"fila": i, "nombre": nombre, "error": f"conexion: {e}"}); continue
            if resp.status_code == 200:
                created += 1; existing.add(_norm(nombre))
            elif resp.status_code == 409:
                skipped += 1
            elif len(errors) < MAX_ERRORS:
                errors.append({"fila": i, "nombre": nombre, "error": _safe_err(resp)})

    return {"ok": True, "dry_run": dry_run, "filas": len(rows), "delimitador": delim,
            "creados": created, "omitidos_existentes": skipped,
            "errores": len(errors), "detalle_errores": errors[:MAX_ERRORS]}


@mcp.tool()
def import_registros_csv(path: str | None = None, csv_text: str | None = None,
                         create_missing_productos: bool = True,
                         default_unidad: str = "unidades",
                         default_categoria: str = "Otros",
                         dry_run: bool = False) -> dict:
    """Importa registros de donaciones desde un CSV (migrar planillas/Excel, o re-importar
    el CSV que exporta la propia app).

    ADVERTENCIA: este import NO es idempotente. Los registros no tienen clave unica, asi que
    correr el mismo archivo dos veces DUPLICA las donaciones. Usa dry_run=True primero y, ante
    la duda, exporta un respaldo con export_registros_csv antes de importar.

    Columnas reconocidas (alias flexibles, sin acentos/mayusculas):
      producto|nombre              (requerido)
      cantidad por unidad|cantidad (requerido; numero, acepta coma decimal)
      num unidades|envases         (requerido; entero)
      fecha                        (opcional; ver NOTA)
      unidad, categoria            (opcionales; se usan para crear el producto si falta)
    La columna 'total' se ignora: el backend la recalcula (cantidad x envases).

    Si el producto no existe y create_missing_productos=True, se crea automaticamente
    (con unidad/categoria de la fila o los defaults).

    NOTA sobre 'fecha': el POST /api/registros del backend actual fija la fecha al momento
    de importar e ignora la fecha enviada. Para preservar fechas historicas aplica el parche
    opcional del README (3 lineas en app.py). Este importador ya envia la fecha siempre, asi
    que funcionara en cuanto el parche este aplicado.

    Args:
      path / csv_text: archivo .csv o contenido en linea (usa solo UNO).
      create_missing_productos: crea productos ausentes (def. True).
      default_unidad / default_categoria: para los productos que haya que crear.
      dry_run: si True, valida y reporta SIN escribir nada.
    """
    try:
        rows, delim, _ = _read_csv(path, csv_text)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        with _client() as c:
            prod_map = _fetch_product_map(c)
    except Exception as e:
        return {"ok": False, "error": f"No se pudo conectar: {e}"}

    imported = prod_created = 0
    errors = []
    with _client() as c:
        for i, row in enumerate(rows, start=2):
            nombre = _row_get(row, "nombre")
            if not nombre:
                errors.append({"fila": i, "error": "falta 'producto'"}); continue
            try:
                cantidad = _parse_number(_row_get(row, "cantidad"))
                num = int(round(_parse_number(_row_get(row, "num"))))
            except Exception as e:
                errors.append({"fila": i, "producto": nombre,
                               "error": f"numero invalido: {e}"}); continue
            if cantidad <= 0 or num <= 0:
                errors.append({"fila": i, "producto": nombre,
                               "error": "cantidad y num. envases deben ser > 0"}); continue
            fecha = _normalize_fecha(_row_get(row, "fecha"))

            key = _norm(nombre)
            prod = prod_map.get(key)
            if prod is None:
                if not create_missing_productos:
                    errors.append({"fila": i, "producto": nombre,
                                   "error": "producto no existe (create_missing_productos=False)"})
                    continue
                unidad = _row_get(row, "unidad") or default_unidad
                categoria = _row_get(row, "categoria") or default_categoria
                if dry_run:
                    prod_map[key] = {"id": -1, "unidad": unidad, "categoria": categoria}
                    prod_created += 1
                    prod = prod_map[key]
                else:
                    try:
                        cr = c.post("/api/productos",
                                    json={"nombre": nombre, "unidad": unidad, "categoria": categoria})
                    except Exception as e:
                        errors.append({"fila": i, "producto": nombre, "error": f"conexion: {e}"}); continue
                    if cr.status_code not in (200, 409):
                        errors.append({"fila": i, "producto": nombre,
                                       "error": f"no se pudo crear producto: {_safe_err(cr)}"}); continue
                    prod_map = _fetch_product_map(c)  # refresh to learn the new id
                    prod = prod_map.get(key)
                    if prod is None:
                        errors.append({"fila": i, "producto": nombre,
                                       "error": "producto creado pero no encontrado"}); continue
                    if cr.status_code == 200:
                        prod_created += 1

            if dry_run:
                imported += 1; continue
            payload = {"producto_id": prod["id"],
                       "cantidad_por_unidad": cantidad, "num_unidades": num}
            if fecha:
                payload["fecha"] = fecha
            try:
                resp = c.post("/api/registros", json=payload)
            except Exception as e:
                errors.append({"fila": i, "producto": nombre, "error": f"conexion: {e}"}); continue
            if resp.status_code == 200:
                imported += 1
            elif len(errors) < MAX_ERRORS:
                errors.append({"fila": i, "producto": nombre, "error": _safe_err(resp)})

    return {"ok": True, "dry_run": dry_run, "filas": len(rows), "delimitador": delim,
            "registros_importados": imported, "productos_creados": prod_created,
            "errores": len(errors), "detalle_errores": errors[:MAX_ERRORS],
            "nota_fecha": ("El backend fija la fecha al importar salvo que se aplique el "
                           "parche opcional (ver README).")}


@mcp.tool()
def export_registros_csv(path: str | None = None) -> dict:
    """Descarga el CSV que genera la app (GET /api/export). Util como respaldo antes de
    importar. Si 'path' se indica, guarda el archivo ahi; si no, devuelve el contenido."""
    try:
        with _client() as c:
            r = c.get("/api/export"); r.raise_for_status()
            content = r.content.decode("utf-8-sig")
    except Exception as e:
        return {"ok": False, "error": f"No se pudo conectar: {e}"}
    if path:
        p = os.path.expanduser(path)
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            f.write(content)
        return {"ok": True, "guardado_en": p, "bytes": len(content)}
    return {"ok": True, "csv": content}


if __name__ == "__main__":
    mcp.run()
