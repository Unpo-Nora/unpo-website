import difflib
import json

products_file = 'backend/all_products.txt'
products = []
with open(products_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            sku, name = line.split(' - ', 1)
            products.append({"sku": sku, "name": name})

product_names = [p['name'] for p in products]

queries = [
    "HUMIDIFICADOR PIPE MADERA CLARO 500 ML",
    "HUMIDIFICADOR PIPE MADERA OSCURO 500 ML",
    "DISPENSER DE DETERGENTE BLANCO",
    "DISPENSER DE DETERGENTE NEGRO",
    "HUMIDIFICADOR MADERA CLARO 550 ML",
    "HUMIDIFICADOR MADERA OSCURO 550 ML",
    "HUMIDIFICADOR LUNA 130 ML", # maybe 120 ML
    "HUMIDIFICADOR PELOTA MADERA CLARO 150 ML", # maybe Humidificador en forma de pelota
    "HUMIDIFICADOR LONG NECK MADERA OSCURO 550 ML",
    "HUMIDIFICADOR VIDRIO EFECTO FUEGO ARTIFICIAL 120 ML",
    "HUMIDIFICADOR BUBBLE MADERA CLARO 130 ML",
    "HUMIDIFICADOR LUNA 120 ML",
    "HUMIDIFICADOR EFECTO VOLCAN 300 ML", # HUMIDIFICADOR VOLCANO 300 ML
    "HUMIDIFICADOR VIDRIO EFECTO PINTURA 120 ML",
    "HUMIDIFICADOR JUPITER 120 ML",
    "ORGANIZADOR DE 16 COMPARTIMENTOS LAVABLE",
    "SET UTENSILIOS DE COCINA x12 NEGRO",
    "ORGANIZADOR DE ACRILICO CON MANIJA 35x10CM",
    "ORGANIZADOR DE ACRILICO CON MANIJA 29x15CM",
    "HIELERA CUBETA DE SILICONA BLANCA",
    "SET X3 RECIPIENTES HERMETICOS DE PLASTICO",
    "HUMIDIFICADOR LONG NECK MADERA CLARO 500 ML"
]

results = {}
for q in queries:
    matches = difflib.get_close_matches(q, product_names, n=1, cutoff=0.3)
    if matches:
        best_match = matches[0]
        matched_sku = next(p['sku'] for p in products if p['name'] == best_match)
        results[q] = {"sku": matched_sku, "matched_name": best_match}
    else:
        # try word match
        best_match = None
        max_overlap = 0
        q_words = set(q.lower().split())
        for p in product_names:
            p_words = set(p.lower().split())
            overlap = len(q_words & p_words)
            if overlap > max_overlap:
                max_overlap = overlap
                best_match = p
        
        if best_match:
            matched_sku = next(p['sku'] for p in products if p['name'] == best_match)
            results[q] = {"sku": matched_sku, "matched_name": best_match}
        else:
            results[q] = {"sku": "UNKNOWN", "matched_name": "UNKNOWN"}

print(json.dumps(results, indent=2))
