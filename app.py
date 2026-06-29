from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import csv
import io
import os
from datetime import datetime

app = Flask(__name__)
DB_PATH = "/data/inventario.db"


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # Concurrency + durability for the LAN multi-client setup:
    # WAL lets readers and the writer work at the same time (no reader/writer blocking),
    # busy_timeout makes a second writer wait instead of failing with "database is locked",
    # synchronous=NORMAL keeps committed data durable across an app/container crash.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    try:
        cantidad = float(data.get("cantidad_por_unidad", 0))
        num      = int(data.get("num_unidades", 0))
        pid      = int(data.get("producto_id", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Datos invalidos"}), 400
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



if __name__ == "__main__":
    init_db()
    # Prefer a production WSGI server (waitress) for the multi-client LAN setup;
    # fall back to Flask's dev server if waitress is not installed.
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8080, threads=8)
    except ImportError:
        app.run(host="0.0.0.0", port=8080, debug=False)
