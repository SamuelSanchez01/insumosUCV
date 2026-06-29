from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import csv
import io
import os
from datetime import datetime

app = Flask(__name__)
DB_PATH = "/data/inventario.db"

# Encabezado esperado del CSV (igual al que genera /api/export)
CSV_HEADER_ESPERADO = ["fecha", "categoria", "producto", "cantidad por unidad", "unidad", "num. unidades", "total"]
CSV_COLUMNAS_MINIMAS = 6  # Fecha, Categoria, Producto, Cantidad por Unidad, Unidad, Num. Unidades (el Total se recalcula)


def normalizar_fecha(valor):
    """Acepta 'YYYY-MM-DD HH:MM:SS' o 'YYYY-MM-DD'. Devuelve None si es invalida."""
    valor = (valor or "").strip()
    if not valor:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS productos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT NOT NULL,
            unidad    TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'Otros'
        );
        CREATE TABLE IF NOT EXISTS registros (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id         INTEGER NOT NULL,
            cantidad_por_unidad REAL    NOT NULL,
            num_unidades        INTEGER NOT NULL,
            total               REAL    NOT NULL,
            fecha               TEXT    NOT NULL,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );
    """)
    # Migration: add categoria to existing DBs that don't have it yet
    try:
        conn.execute("ALTER TABLE productos ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Otros'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Si hay duplicados de nombre en BDs existentes, conserva solo el primero
    conn.execute("""
        DELETE FROM productos WHERE id NOT IN (
            SELECT MIN(id) FROM productos GROUP BY nombre
        )
    """)
    # Unique index on nombre (safe to run multiple times)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)")
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/productos", methods=["GET"])
def get_productos():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM productos ORDER BY categoria, nombre"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/productos", methods=["POST"])
def create_producto():
    data = request.json
    nombre    = data.get("nombre", "").strip()
    unidad    = data.get("unidad", "").strip()
    categoria = data.get("categoria", "Otros").strip()
    if not nombre or not unidad:
        return jsonify({"error": "Faltan datos"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO productos (nombre, unidad, categoria) VALUES (?, ?, ?)",
            (nombre, unidad, categoria),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"Ya existe un producto llamado \"{nombre}\""}), 409
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/productos/<int:pid>", methods=["DELETE"])
def delete_producto(pid):
    conn = get_db()
    conn.execute("DELETE FROM productos WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/registros", methods=["GET"])
def get_registros():
    conn = get_db()
    rows = conn.execute("""
        SELECT r.id, r.fecha, r.cantidad_por_unidad, r.num_unidades, r.total,
               p.nombre, p.unidad, p.categoria
        FROM registros r
        JOIN productos p ON r.producto_id = p.id
        ORDER BY r.fecha DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/registros", methods=["POST"])
def create_registro():
    data = request.json
    cantidad = float(data.get("cantidad_por_unidad", 0))
    num      = int(data.get("num_unidades", 0))
    pid      = int(data.get("producto_id", 0))
    if cantidad <= 0 or num <= 0 or pid <= 0:
        return jsonify({"error": "Datos invalidos"}), 400
    total = round(cantidad * num, 4)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute(
        "INSERT INTO registros (producto_id, cantidad_por_unidad, num_unidades, total, fecha) VALUES (?, ?, ?, ?, ?)",
        (pid, cantidad, num, total, fecha),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/registros/<int:rid>", methods=["DELETE"])
def delete_registro(rid):
    conn = get_db()
    conn.execute("DELETE FROM registros WHERE id = ?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/export")
def export_csv():
    conn = get_db()
    rows = conn.execute("""
        SELECT r.fecha, p.categoria, p.nombre, r.cantidad_por_unidad, p.unidad,
               r.num_unidades, r.total
        FROM registros r
        JOIN productos p ON r.producto_id = p.id
        ORDER BY p.categoria, p.nombre, r.fecha
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Categoria", "Producto", "Cantidad por Unidad", "Unidad", "Num. Unidades", "Total"])
    for r in rows:
        writer.writerow(list(r))

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"insumos_{fecha_hoy}.csv",
    )


@app.route("/api/import", methods=["POST"])
def import_csv():
    archivo = request.files.get("file")
    if archivo is None or archivo.filename == "":
        return jsonify({"error": "No se recibio ningun archivo"}), 400
    if not archivo.filename.lower().endswith(".csv"):
        return jsonify({"error": "El archivo debe ser un .csv"}), 400

    crudo = archivo.read()
    try:
        # utf-8-sig absorbe el BOM que agrega /api/export (y el que agrega Excel al guardar)
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "No se pudo leer el archivo. Debe estar en formato de texto UTF-8."}), 400

    try:
        filas = list(csv.reader(io.StringIO(texto)))
    except csv.Error:
        return jsonify({"error": "El archivo no tiene un formato CSV valido"}), 400

    # Quita filas completamente vacias (comunes al final del archivo)
    filas = [f for f in filas if any(c.strip() for c in f)]
    if not filas:
        return jsonify({"error": "El archivo esta vacio"}), 400

    # Si la primera fila es el encabezado esperado, se omite; si no, se asume que ya son datos
    primera = [c.strip().lower() for c in filas[0]]
    if primera == CSV_HEADER_ESPERADO:
        filas_datos = filas[1:]
        offset = 2  # numero de fila real en el archivo (1 = encabezado)
    else:
        filas_datos = filas
        offset = 1

    conn = get_db()
    productos_existentes = {
        p["nombre"].strip().lower(): dict(p)
        for p in conn.execute("SELECT * FROM productos").fetchall()
    }

    insertados = 0
    productos_creados = 0
    errores = []
    avisos = []

    for i, fila in enumerate(filas_datos):
        num_fila = i + offset
        if len(fila) < CSV_COLUMNAS_MINIMAS:
            errores.append(f"Fila {num_fila}: tiene menos columnas de las esperadas")
            continue

        fecha_raw, categoria, nombre, cant_raw, unidad, num_raw = (c.strip() for c in fila[:6])

        if not nombre:
            errores.append(f"Fila {num_fila}: falta el nombre del producto")
            continue

        try:
            cantidad = float(cant_raw.replace(",", "."))
        except ValueError:
            errores.append(f"Fila {num_fila} (\"{nombre}\"): \"Cantidad por Unidad\" invalida")
            continue

        try:
            num = int(float(num_raw))
        except ValueError:
            errores.append(f"Fila {num_fila} (\"{nombre}\"): \"Num. Unidades\" invalida")
            continue

        if cantidad <= 0 or num <= 0:
            errores.append(f"Fila {num_fila} (\"{nombre}\"): la cantidad y el numero de envases deben ser mayores que 0")
            continue

        fecha = normalizar_fecha(fecha_raw)
        if fecha is None:
            errores.append(f"Fila {num_fila} (\"{nombre}\"): fecha invalida \"{fecha_raw}\" (use AAAA-MM-DD)")
            continue

        clave = nombre.lower()
        prod = productos_existentes.get(clave)
        if prod is None:
            unidad_final = unidad or "unidades"
            categoria_final = categoria or "Otros"
            try:
                conn.execute(
                    "INSERT INTO productos (nombre, unidad, categoria) VALUES (?, ?, ?)",
                    (nombre, unidad_final, categoria_final),
                )
                productos_creados += 1
            except sqlite3.IntegrityError:
                pass
            prod = dict(conn.execute("SELECT * FROM productos WHERE nombre = ?", (nombre,)).fetchone())
            productos_existentes[clave] = prod
        elif unidad and unidad != prod["unidad"]:
            avisos.append(
                f"Fila {num_fila} (\"{nombre}\"): el producto ya existe con unidad \"{prod['unidad']}\"; "
                f"se ignoro la unidad \"{unidad}\" del archivo"
            )

        total = round(cantidad * num, 4)
        conn.execute(
            "INSERT INTO registros (producto_id, cantidad_por_unidad, num_unidades, total, fecha) VALUES (?, ?, ?, ?, ?)",
            (prod["id"], cantidad, num, total, fecha),
        )
        insertados += 1

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "insertados": insertados,
        "productos_creados": productos_creados,
        "filas_total": len(filas_datos),
        "errores": errores,
        "avisos": avisos,
    })


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080, debug=False)
