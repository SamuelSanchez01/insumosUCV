#!/bin/bash
# Uso: ./seed_productos.sh [URL]
# Ejemplo en otra maquina: ./seed_productos.sh http://192.168.1.50:8080
BASE="${1:-http://localhost:8080}"

ok=0
exist=0
fail=0

crear() {
  local nombre="$1" unidad="$2" categoria="$3"
  local json
  json=$(printf '{"nombre":"%s","unidad":"%s","categoria":"%s"}' "$nombre" "$unidad" "$categoria")
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/productos" \
    -H "Content-Type: application/json" -d "$json")
  if [ "$code" = "200" ]; then
    printf "  OK      %-35s %-12s %s\n" "$nombre" "($unidad)" "$categoria"
    ((ok++))
  elif [ "$code" = "409" ]; then
    printf "  EXISTE  %-35s ya registrado\n" "$nombre"
    ((exist++))
  else
    printf "  ERROR   %-35s HTTP %s\n" "$nombre" "$code"
    ((fail++))
  fi
}

# Esperar a que la app este lista
printf "Conectando a %s" "$BASE"
for i in $(seq 1 15); do
  if curl -sf "$BASE/" -o /dev/null 2>/dev/null; then
    echo " — listo."
    break
  fi
  printf "."
  sleep 1
  if [ "$i" -eq 15 ]; then
    echo ""
    echo "ERROR: No se pudo conectar a $BASE"
    exit 1
  fi
done

echo ""
echo "============================================================"
echo "  CARGANDO PRODUCTOS BASE — Donaciones Terremoto Venezuela"
echo "============================================================"
echo ""

echo ">> Alimentos Basicos"
crear "Harina PAN"               "kg"       "Alimentos Basicos"
crear "Arroz"                    "kg"       "Alimentos Basicos"
crear "Pasta / Fideos"           "g"        "Alimentos Basicos"
crear "Caraotas negras"          "kg"       "Alimentos Basicos"
crear "Lentejas"                 "g"        "Alimentos Basicos"
crear "Atun enlatado"            "g"        "Alimentos Basicos"
crear "Sardinas enlatadas"       "g"        "Alimentos Basicos"
crear "Leche en polvo"           "g"        "Alimentos Basicos"
crear "Aceite vegetal"           "ml"       "Alimentos Basicos"
crear "Azucar"                   "kg"       "Alimentos Basicos"
crear "Sal refinada"             "g"        "Alimentos Basicos"
crear "Cafe soluble"             "g"        "Alimentos Basicos"
crear "Avena en hojuelas"        "g"        "Alimentos Basicos"
crear "Conservas de carne"       "g"        "Alimentos Basicos"
crear "Mayonesa"                 "g"        "Alimentos Basicos"

echo ""
echo ">> Agua y Bebidas"
crear "Agua embotellada 1.5L"    "ml"       "Agua y Bebidas"
crear "Agua en garrafa 5L"       "L"        "Agua y Bebidas"
crear "Agua en garrafa 10L"      "L"        "Agua y Bebidas"
crear "Suero oral ORS"           "ml"       "Agua y Bebidas"
crear "Bebida rehidratante"      "ml"       "Agua y Bebidas"
crear "Jugos en polvo"           "g"        "Agua y Bebidas"
crear "Tabletas purif. de agua"  "unidades" "Agua y Bebidas"
crear "Te / Infusion"            "g"        "Agua y Bebidas"

echo ""
echo ">> Higiene Personal"
crear "Jabon de bano"            "g"        "Higiene Personal"
crear "Papel higienico"          "unidades" "Higiene Personal"
crear "Pasta dental"             "g"        "Higiene Personal"
crear "Cepillo de dientes"       "unidades" "Higiene Personal"
crear "Shampoo"                  "ml"       "Higiene Personal"
crear "Toallitas humedas"        "unidades" "Higiene Personal"
crear "Desodorante"              "unidades" "Higiene Personal"
crear "Toallas sanitarias"       "unidades" "Higiene Personal"
crear "Gel antibacterial"        "ml"       "Higiene Personal"
crear "Algodon"                  "g"        "Higiene Personal"
crear "Afeitadoras desechables"  "unidades" "Higiene Personal"
crear "Toalla de bano"           "unidades" "Higiene Personal"

echo ""
echo ">> Salud y Medicamentos"
crear "Acetaminofen 500mg"       "unidades" "Salud y Medicamentos"
crear "Ibuprofeno 400mg"         "unidades" "Salud y Medicamentos"
crear "Venda elastica"           "unidades" "Salud y Medicamentos"
crear "Gasas esteriles"          "unidades" "Salud y Medicamentos"
crear "Alcohol antiseptico"      "ml"       "Salud y Medicamentos"
crear "Agua oxigenada"           "ml"       "Salud y Medicamentos"
crear "Antiacidos"               "unidades" "Salud y Medicamentos"
crear "Antidiarreicos"           "unidades" "Salud y Medicamentos"
crear "Antihistaminicos"         "unidades" "Salud y Medicamentos"
crear "Antigripal"               "unidades" "Salud y Medicamentos"
crear "Vitaminas multivitaminico" "unidades" "Salud y Medicamentos"
crear "Pomada antiseptica"       "g"        "Salud y Medicamentos"
crear "Suero fisiologico"        "ml"       "Salud y Medicamentos"
crear "Guantes desechables"      "unidades" "Salud y Medicamentos"
crear "Tapabocas / Mascarillas"  "unidades" "Salud y Medicamentos"

echo ""
echo ">> Ropa y Calzado"
crear "Camiseta adulto"          "unidades" "Ropa y Calzado"
crear "Pantalon adulto"          "unidades" "Ropa y Calzado"
crear "Ropa interior adulto"     "unidades" "Ropa y Calzado"
crear "Calcetines / Medias"      "unidades" "Ropa y Calzado"
crear "Zapatos adulto (par)"     "unidades" "Ropa y Calzado"
crear "Chancletas / Sandalias"   "unidades" "Ropa y Calzado"
crear "Cobija / Frazada"         "unidades" "Ropa y Calzado"
crear "Toalla de bano"           "unidades" "Ropa y Calzado"
crear "Impermeable / Capa lluvia" "unidades" "Ropa y Calzado"

echo ""
echo ">> Bebes y Ninos"
crear "Leche infantil en polvo"  "g"        "Bebes y Ninos"
crear "Panales talla S"          "unidades" "Bebes y Ninos"
crear "Panales talla M"          "unidades" "Bebes y Ninos"
crear "Panales talla G"          "unidades" "Bebes y Ninos"
crear "Panales talla XG"         "unidades" "Bebes y Ninos"
crear "Toallitas para bebe"      "unidades" "Bebes y Ninos"
crear "Jabon pediatrico"         "ml"       "Bebes y Ninos"
crear "Pomada antipañal"         "g"        "Bebes y Ninos"
crear "Comida para bebe"         "g"        "Bebes y Ninos"
crear "Tetero / Biberon"         "unidades" "Bebes y Ninos"
crear "Vitaminas infantiles"     "unidades" "Bebes y Ninos"
crear "Cobija de bebe"           "unidades" "Bebes y Ninos"
crear "Suero fisiologico bebe"   "ml"       "Bebes y Ninos"

echo ""
echo ">> Limpieza del Hogar"
crear "Cloro / Hipoclorito"      "ml"       "Limpieza del Hogar"
crear "Detergente en polvo"      "g"        "Limpieza del Hogar"
crear "Jabon de lavar ropa"      "g"        "Limpieza del Hogar"
crear "Desinfectante multiusos"  "ml"       "Limpieza del Hogar"
crear "Escoba"                   "unidades" "Limpieza del Hogar"
crear "Trapeador"                "unidades" "Limpieza del Hogar"
crear "Esponjas de cocina"       "unidades" "Limpieza del Hogar"
crear "Bolsas de basura"         "unidades" "Limpieza del Hogar"
crear "Guantes de limpieza"      "unidades" "Limpieza del Hogar"
crear "Cepillo multiusos"        "unidades" "Limpieza del Hogar"

echo ""
echo ">> Otros"
crear "Velas de emergencia"      "unidades" "Otros"
crear "Linterna LED"             "unidades" "Otros"
crear "Pilas AA"                 "unidades" "Otros"
crear "Pilas AAA"                "unidades" "Otros"
crear "Fosforos / Encendedor"    "unidades" "Otros"
crear "Lona impermeable"         "unidades" "Otros"
crear "Cinta adhesiva"           "unidades" "Otros"
crear "Radio portatil"           "unidades" "Otros"
crear "Bolsas de basura grandes" "unidades" "Otros"
crear "Utensilios desechables"   "unidades" "Otros"

echo ""
echo "============================================================"
printf "  Creados: %d" "$ok"
[ "$exist" -gt 0 ] && printf "  |  Ya existian: %d" "$exist"
[ "$fail"  -gt 0 ] && printf "  |  Errores: %d" "$fail"
echo ""
echo "============================================================"
