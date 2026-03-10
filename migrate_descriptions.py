import csv
import requests

API_URL = "https://unpo-backend.onrender.com"

def migrate_descriptions():
    print("Iniciando migración de descripciones desde CATALOGO.csv...")
    
    # 1. Login
    r = requests.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"})
    if r.status_code != 200:
        print("Error al iniciar sesión:", r.text)
        return
        
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Extract mappings from CSV
    print("Leyendo CATALOGO.csv local...")
    sku_desc = {}
    csv_path = 'backend/data/CATALOGO.csv'
    
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        # We need SKU and DESCRIPCION
        idx_sku = header.index("COD. UNPO") if header and "COD. UNPO" in header else 0
        idx_desc = header.index("DESCRIPCION") if header and "DESCRIPCION" in header else 2
        
        for row in reader:
            if not row or len(row) <= max(idx_sku, idx_desc): continue
            
            sku_raw = row[idx_sku].strip()
            if not sku_raw: continue
            
            # Normalize SKU
            sku = sku_raw
            if '.' in sku: sku = sku.split('.')[0]
            try:
                 if sku.isdigit(): sku = str(int(sku))
            except: pass
            
            desc = row[idx_desc].strip()
            if desc:
                sku_desc[sku] = desc

    print(f"Encontrados {len(sku_desc)} productos con descripción en catálogo.")
    
    # 3. Update production API
    processed = 0
    updated = 0
    
    # Fetch all production products first to ensure we don't overwrite other data
    r_prod = requests.get(f"{API_URL}/products/?limit=1000")
    if r_prod.status_code != 200:
        print("Error al obtener productos de producción")
        return
        
    prod_products = {p['sku']: p for p in r_prod.json()}
    
    for sku, desc in sku_desc.items():
        if sku not in prod_products:
            continue
            
        p = prod_products[sku]
        
        # Only update if description is empty or different
        if p.get('description') == desc:
            continue
            
        payload = {
            "sku": p['sku'],
            "name": p['name'],
            "description": desc,
            "category_id": p.get('category_id'),
            "is_active": p.get('is_active', True),
            "price_wholesale": p.get('price_wholesale', 0),
            "stock_quantity": p.get('stock_quantity', 0),
            "weight": p.get('weight', 0),
            "images": p.get('images', [])
        }
        
        r = requests.put(f"{API_URL}/products/{sku}", json=payload, headers=headers)
        if r.status_code in (200, 201):
            print(f"[{processed+1}/{len(sku_desc)}] Descripción sincronizada para {sku}")
            updated += 1
        else:
            print(f"[{processed+1}/{len(sku_desc)}] Error {sku}: {r.text}")
            
        processed += 1
            
    print(f"Migración completada. {updated} productos actualizados.")

if __name__ == "__main__":
    migrate_descriptions()
