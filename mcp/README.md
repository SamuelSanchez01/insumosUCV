# insumos-mcp

Servidor **MCP** (Model Context Protocol) para que un administrador importe datos CSV en
una instancia de **insumosUCV** en marcha: catalogo de productos y registros de donaciones.
Pensado, por ejemplo, para **migrar planillas de Excel** de otras carpas hacia el sistema.

Se conecta a la **API REST** de la app por la LAN (por defecto `http://localhost:8080`), asi
que puede ejecutarse desde cualquier maquina que alcance al servidor del acopio. Cada
escritura pasa por la validacion de la propia app, incluida la restriccion de nombre unico de
producto, de modo que no escribe nunca directo sobre el archivo SQLite.

## Que es un MCP y como se usa

Un servidor MCP expone "herramientas" que un asistente compatible (Claude Code, Claude
Desktop) puede invocar. Una vez configurado, el administrador escribe en lenguaje natural
("importa este CSV de productos") y el asistente llama a la herramienta correspondiente.

## Herramientas

| Herramienta | Que hace |
|---|---|
| `get_status` | Verifica la conexion y devuelve los conteos actuales (productos, registros). |
| `list_productos` | Lista el catalogo (opcionalmente filtrado por categoria). |
| `import_productos_csv` | Crea productos en lote desde un CSV (lista maestra). Idempotente. |
| `import_registros_csv` | Crea registros de donaciones en lote desde un CSV. |
| `export_registros_csv` | Descarga el CSV que exporta la app (respaldo antes de importar). |

Todos los importadores aceptan `dry_run=True`: validan y reportan que pasaria **sin escribir
nada**. Conviene correr siempre un `dry_run` antes del import real.

## Requisitos

- **Python 3.10 o superior**.
- Una instancia de insumosUCV corriendo y alcanzable (por LAN o en la misma maquina).

## Instalacion

```bash
cd mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuracion del cliente

`INSUMOS_BASE_URL` apunta a la app. Cambialo si corre en otra IP de la LAN
(por ejemplo `http://192.168.1.50:8080`).

**Claude Code (CLI):**
```bash
claude mcp add insumos \
  -e INSUMOS_BASE_URL=http://localhost:8080 \
  -- /ruta/a/mcp/.venv/bin/python /ruta/a/mcp/server.py
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "insumos": {
      "command": "/ruta/a/mcp/.venv/bin/python",
      "args": ["/ruta/a/mcp/server.py"],
      "env": { "INSUMOS_BASE_URL": "http://localhost:8080" }
    }
  }
}
```

Usa la ruta absoluta al Python del entorno virtual (`.venv/bin/python`) para que las
dependencias esten disponibles.

Variables de entorno:

| Variable | Por defecto | Descripcion |
|---|---|---|
| `INSUMOS_BASE_URL` | `http://localhost:8080` | URL base de la app. |
| `INSUMOS_TIMEOUT` | `30` | Tiempo limite por peticion, en segundos. |

## Formatos de CSV

Los encabezados son **flexibles**: no distinguen acentos ni mayusculas y aceptan varios
alias. El **delimitador** se detecta solo (`,`, `;` o tabulador, util con Excel en espanol).
Los numeros aceptan coma decimal (`1,5`) y separador de miles.

**Productos** (`samples/productos.csv`):

```
nombre,unidad,categoria
Aceite de cocina,ml,Alimentos Basicos
Acetaminofen 500mg,unidades,Salud y Medicamentos
```

- `nombre` (requerido), `unidad`, `categoria`.
- Los nombres ya existentes se omiten sin error (el import puede correrse varias veces).

**Registros** (`samples/registros.csv`), mismo formato que exporta la app:

```
Fecha,Categoria,Producto,Cantidad por Unidad,Unidad,Num. Unidades,Total
2026-06-25 09:30:00,Salud y Medicamentos,Acetaminofen 500mg,40,unidades,3,120
```

- `producto` (requerido), `cantidad por unidad` (requerido), `num unidades` (requerido).
- `fecha` opcional (ver nota mas abajo).
- `unidad` y `categoria` se usan para crear el producto si todavia no existe.
- `total` se ignora: el backend lo recalcula como `cantidad x envases`.

> **Cuidado:** a diferencia del import de productos (que omite repetidos por nombre unico),
> el import de **registros NO es idempotente**: correr el mismo archivo dos veces duplica las
> donaciones. Corre `dry_run=True` primero y, ante la duda, exporta un respaldo con
> `export_registros_csv` antes de importar.

Alias reconocidos por columna: `producto` tambien acepta `nombre`, `articulo`, `item`;
`cantidad por unidad` acepta `cantidad`, `cantidad por envase`, `contenido`;
`num unidades` acepta `envases`, `paquetes`, `numero de envases`.

## Ejemplos de uso (en lenguaje natural)

- "Verifica la conexion con insumos." (llama a `get_status`)
- "Importa el catalogo de `~/carpa-medicinas/productos.csv`, primero en dry-run."
- "Ahora si, importalo de verdad."
- "Importa las donaciones de `~/excel-export.csv` y crea los productos que falten."
- "Exporta los registros actuales a `~/respaldo.csv` antes de empezar."

## Nota sobre la `fecha` (preservar fechas historicas)

El endpoint `POST /api/registros` del backend **actual** fija `fecha = ahora()` e **ignora**
la fecha enviada. El importador ya envia la `fecha` del CSV en cada peticion, asi que para
preservar fechas historicas basta con este cambio **opcional y retrocompatible** en `app.py`
(funcion `create_registro`):

```diff
     total = round(cantidad * num, 4)
-    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
+    fecha = (str(data.get("fecha") or "").strip()
+             or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
```

Sin ese cambio, los registros importados quedan con la fecha del momento del import y todo lo
demas funciona igual. Es una mejora separada al backend; no es necesaria para usar el resto
del importador.

## Prueba de humo (al desplegar)

Antes de confiar en el importador en la maquina real del acopio, corre esta lista corta.
Toma un par de minutos y cubre lo que no se puede verificar fuera del entorno real
(Docker real, la LAN, y el cliente MCP de verdad).

1. **App arriba:** `docker compose up --build -d` y abre `http://localhost:8080`
   (o `http://IP-DEL-SERVIDOR:8080` desde otra PC de la LAN).
2. **Conexion del MCP:** en Claude, pide *"verifica la conexion con insumos"*. `get_status`
   debe devolver `ok: true` con la URL correcta. Si falla, revisa `INSUMOS_BASE_URL`
   (IP y puerto), sobre todo si el MCP corre en una maquina distinta al servidor.
3. **Dry-run primero:** *"importa `samples/productos.csv` en dry-run"*. Reporta `creados`
   sin escribir nada.
4. **Import real chico:** *"ahora importalo de verdad"* y confirma que los productos
   aparecen en la pestana **Productos** de la web.
5. **Registros:** *"importa `samples/registros.csv`"* y confirma que aparecen en la web con
   el **Total** recalculado.
6. **Idempotencia:** vuelve a importar `samples/productos.csv`: debe dar `omitidos_existentes`
   y **no** duplicar. (Recuerda: el import de **registros** si duplica, ver aviso arriba.)
7. **Respaldo:** *"exporta los registros a `~/respaldo.csv`"* y confirma que se descarga.
8. **Limpieza:** borra los datos de prueba desde la web (o con `limpiar_inventario.sh` para
   los registros) antes del uso real.

## Solucion de problemas

- **"No se pudo conectar"**: revisa que la app este corriendo y que `INSUMOS_BASE_URL`
  apunte a la IP y puerto correctos. Prueba `get_status` primero.
- **Filas con error**: cada importador devuelve `detalle_errores` con el numero de fila y el
  motivo (por ejemplo numero invalido o falta de columna). El resto de las filas si se importa.
- **Numeros mal interpretados**: confirma el separador decimal. El importador maneja `1,5` y
  `1.5`, pero un CSV con miles y decimales mezclados de forma ambigua puede requerir limpieza.

## Como funciona (resumen tecnico)

`server.py` usa FastMCP (paquete `mcp`) y `httpx`. Cada herramienta abre un cliente HTTP
contra `INSUMOS_BASE_URL`, normaliza los encabezados del CSV (sin acentos ni mayusculas),
mapea los productos por nombre y hace POST a `/api/productos` y `/api/registros`. No accede al
archivo de base de datos: toda escritura pasa por la API y su validacion.
