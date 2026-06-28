#!/bin/bash
set -e

echo "========================================"
echo "  LIMPIAR INVENTARIO DE INSUMOS"
echo "========================================"
echo ""
echo "ADVERTENCIA: Esta accion eliminara TODOS"
echo "los registros del inventario."
echo ""
read -p "Escriba CONFIRMAR para continuar: " resp

if [ "$resp" != "CONFIRMAR" ]; then
  echo "Operacion cancelada."
  exit 0
fi

echo ""
echo "Limpiando..."

docker exec insumos-app-1 python3 -c "
import sqlite3
conn = sqlite3.connect('/data/inventario.db')
n = conn.execute('DELETE FROM registros').rowcount
conn.commit()
conn.close()
print(f'Listo. {n} registros eliminados.')
"
