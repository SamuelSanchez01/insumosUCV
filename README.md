# insumosUCV

Sistema web para registrar insumos donados durante la crisis del terremoto en Venezuela. Corre en Docker, se accede desde cualquier PC en la misma red local (LAN) por el puerto 8080.

---

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose](https://docs.docker.com/compose/install/) (incluido en Docker Desktop)
- Git (para clonar el repo)
- Conexión a internet la primera vez (para descargar la imagen base de Python)

---

## Instalacion

```bash
git clone git@github.com:SamuelSanchez01/insumosUCV.git
cd insumosUCV
```

### 1. Levantar el sistema

```bash
docker compose up --build -d
```

Esto construye la imagen y arranca el contenedor en segundo plano. La base de datos se crea automaticamente en `./data/inventario.db`.

### 2. Cargar los productos base

Solo la primera vez. Agrega los ~92 productos mas comunes para donaciones de desastre:

```bash
./seed_productos.sh
```

Si la app esta corriendo en otra IP (por ejemplo, en otra maquina de la LAN):

```bash
./seed_productos.sh http://192.168.1.50:8080
```

### 3. Abrir en el navegador

Desde la misma maquina donde corre Docker:

```
http://localhost:8080
```

Desde cualquier otra PC en la red local:

```
http://<IP-DE-LA-MAQUINA-SERVIDOR>:8080
```

Para ver la IP del servidor en Linux:

```bash
ip a | grep "inet " | grep -v 127
```

---

## Uso diario

### Registrar una donacion

1. Ir a la pestana **Registrar Donacion**
2. Seleccionar la **categoria** (filtra los productos)
3. Seleccionar el **producto**
4. Ingresar la cantidad por envase — usar los botones rapidos (100g, 250g, 500ml, etc.) o escribir manualmente
5. Ingresar el numero de envases/paquetes
6. El **total se calcula automaticamente**
7. Hacer click en **Registrar**

### Exportar los registros del dia

En la pestana **Registrar Donacion**, seccion **Acciones del Dia**:

```
Boton "Exportar CSV"
```

Descarga un archivo `insumos_YYYY-MM-DD.csv` con todos los registros, ordenados por categoria y producto. Compatible con Excel y LibreOffice.

### Importar registros desde un CSV

En la misma seccion **Acciones del Dia**:

```
Boton "Importar CSV"
```

Abre el explorador de archivos para elegir un `.csv`. El sistema acepta el mismo formato que genera "Exportar CSV":

```
Fecha,Categoria,Producto,Cantidad por Unidad,Unidad,Num. Unidades,Total
```

Notas sobre la importacion:

- La columna **Total** se recalcula automaticamente (Cantidad por Unidad × Num. Unidades), no se toma del archivo.
- La fila de encabezado es opcional: si la primera fila no es el encabezado, se asume que todas las filas son datos.
- La **Fecha** acepta `AAAA-MM-DD HH:MM:SS` o solo `AAAA-MM-DD`; si se deja vacia, se usa la fecha/hora actual.
- Si el **Producto** no existe todavia, se crea automaticamente con la Categoria y Unidad indicadas en esa fila.
- Si el producto ya existe, se usa su Unidad y Categoria actuales (no se modifican), aunque el archivo traiga otro valor.
- Las filas con datos invalidos (cantidad, numero de envases o fecha incorrectos) se omiten y se reportan, sin afectar al resto del archivo.
- Al finalizar, se muestra un resumen con cuantos registros se importaron y, si hubo filas con problemas, el detalle de cada una.

### Agregar un producto nuevo

1. Ir a la pestana **Productos**
2. Seleccionar categoria, escribir nombre y elegir unidad de medida
3. Click en **Crear Producto**

---

## Limpiar el inventario

El sistema **no tiene boton de limpiar** en la interfaz web (por seguridad). Para borrar todos los registros al final del dia, ejecutar en el servidor:

```bash
./limpiar_inventario.sh
```

Pedira que escribas `CONFIRMAR` antes de proceder. Se recomienda exportar el CSV primero.

---

## Administracion del contenedor

| Accion | Comando |
|---|---|
| Ver si esta corriendo | `docker ps` |
| Ver logs en vivo | `docker logs -f insumos-app-1` |
| Detener | `docker compose down` |
| Reiniciar | `docker compose restart` |
| Actualizar tras cambios | `docker compose up --build -d` |

---

## Estructura del proyecto

```
insumosUCV/
├── app.py                  # Backend Flask (API REST + SQLite)
├── templates/
│   └── index.html          # Interfaz web (Bootstrap 5)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── seed_productos.sh       # Carga productos base (ejecutar 1 vez)
├── limpiar_inventario.sh   # Borra registros del dia (requiere confirmacion)
└── data/                   # Generado automaticamente, contiene la BD
    └── inventario.db
```

---

## Categorias de productos

| Categoria | Ejemplos |
|---|---|
| Alimentos Basicos | Harina PAN, Arroz, Caraotas, Atun, Leche en polvo |
| Agua y Bebidas | Agua embotellada, Garrafa 5L/10L, Suero ORS |
| Higiene Personal | Jabon, Papel higienico, Shampoo, Toallas sanitarias |
| Salud y Medicamentos | Acetaminofen, Ibuprofeno, Vendas, Alcohol, Gasas |
| Ropa y Calzado | Camiseta, Pantalon, Cobija, Impermeable |
| Bebes y Ninos | Leche infantil, Panales S/M/G/XG, Pomada antipañal |
| Limpieza del Hogar | Cloro, Detergente, Escoba, Desinfectante |
| Otros | Velas, Linterna, Pilas, Lona impermeable, Radio |
