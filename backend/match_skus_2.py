import difflib
import json

products_file = 'backend/all_products.txt'
products = []
with open(products_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                sku, name = parts
                products.append({"sku": sku, "name": name})

product_names = [p['name'] for p in products]

queries = [
    "JARRA DE VIDRIO TEXTURIZADO",
    "SET x6 VASOS DE VIDRIO PARA LICUADO",
    "LUNCHERA BOX REDONDA CON CUBIERTO (VERDE Y ROSA)",
    "LUNCHERA PLASTICA CON COMPARTIMENTOS Y CUBIERTOS",
    "PICADOR ELECTRICO RECARGABLE USB 300ML",
    "SET x3 RECIPIENTES HERMETICOS DE VIDRIO",
    "SET x12 UTENSILIOS DE COCINA DE SILICONA VERDE",
    "LUNCHERA BOX REDONDA CON CUBIERTO (2VERDE Y 2 AZUL CON AMARILLO)",
    "LUNCHERA PLASTICA CON COMPARTIMENTOS Y CUBIERTOS CELESTE",
    "ORGANIZADOR DE 6 COMPARTIMENTOS LAVABLE",
    "PIZARRA LED CON BASE DE MADERA",
    "SET x12 UTENSILIOS DE COCINA DE SILICONA ROJO",
    "SET DE ALIMENTACION PARA BEBE DE SILICONA ROSA",
    "SET DE ALIMENTACION PARA BEBE DE SILICONA CELESTE",
    "REJILLAS PARA VAJILLA (5 NEGRAS y 5 GRIS)",
    "SET DE ALIMENTACION PARA BEBE DE SILICONA"
]

results = {}
for q in queries:
    matches = difflib.get_close_matches(q, product_names, n=1, cutoff=0.3)
    if matches:
        best_match = matches[0]
        matched_sku = next(p['sku'] for p in products if p['name'] == best_match)
        results[q] = {"sku": matched_sku, "matched_name": best_match}
    else:
        results[q] = {"sku": "UNKNOWN", "matched_name": "UNKNOWN"}

print(json.dumps(results, indent=2))
