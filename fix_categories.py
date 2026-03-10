import csv
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

API_URL = "https://unpo-backend.onrender.com"
session = requests.Session()
retry = Retry(connect=5, read=5, backoff_factor=1.0)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def fix_categories():
    print("Iniciando asignación de categorías desde CATALOGO.csv...")
    
    r = session.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"}, timeout=20)
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Fetch existing categories
    cats_resp = session.get(f"{API_URL}/products/categories")
    categories = cats_resp.json()
    cat_map_by_name = {c['name'].strip().upper(): c['id'] for c in categories}
    
    # 2. Get remote products
    r_prod = session.get(f"{API_URL}/products/?limit=1000", timeout=20)
    remote_prods = {p['sku']: p for p in r_prod.json()}
    
    csv_path = 'backend/data/CATALOGO.csv'
    
    updated_count = 0
    created_cats = set()
    
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        idx_sku = header.index("COD. UNPO") if header and "COD. UNPO" in header else 0
        idx_cat = header.index("CATEGORIA") if header and "CATEGORIA" in header else 3
        
        for row in reader:
            if not row or len(row) <= max(idx_sku, idx_cat): continue
            
            sku_raw = row[idx_sku].strip()
            if not sku_raw: continue
            
            sku = sku_raw
            if '.' in sku: sku = sku.split('.')[0]
            try:
                 if sku.isdigit(): sku = str(int(sku))
            except: pass
            
            cat_name = row[idx_cat].strip().upper()
            if not cat_name: cat_name = "GENERAL"
            
            # Map GENERAL to General to avoid ALL CAPS if it's the first time
            if cat_name == "GENERAL": pretty_cat = "General"
            else: pretty_cat = cat_name.title()
            
            # If category doesn't exist remotely, create it
            if cat_name not in cat_map_by_name:
                if cat_name not in created_cats:
                    # Let's hope there's a POST endpoint for categories
                    print(f"La categoría {pretty_cat} no existe. Intentando crear...")
                    payload = {"name": pretty_cat}
                    rc = session.post(f"{API_URL}/products/categories", json=payload, headers=headers)
                    if rc.status_code in (200, 201):
                        new_cat = rc.json()
                        cat_map_by_name[cat_name] = new_cat['id']
                    else:
                        print(f"Error creando categoría {pretty_cat}: {rc.text}")
                        # fallback
                        continue
                else:
                    # We already tried creating it and it failed or is pending
                    pass
                
            cat_id = cat_map_by_name.get(cat_name)
            
            if sku in remote_prods and cat_id:
                p = remote_prods[sku]
                if p.get('category_id') != cat_id:
                    payload = {
                        "sku": p['sku'],
                        "name": p['name'],
                        "description": p.get('description', ''),
                        "category_id": cat_id,
                        "is_active": p.get('is_active', True),
                        "price_wholesale": p.get('price_wholesale', 0),
                        "stock_quantity": p.get('stock_quantity', 0),
                        "weight": p.get('weight', 0.0),
                        "images": p.get('images', [])
                    }
                    rp = session.put(f"{API_URL}/products/{sku}", json=payload, headers=headers, timeout=20)
                    if rp.status_code in (200, 201):
                        updated_count += 1
                        
    print(f"Finalizado. {updated_count} productos actualizados con su categoría correcta.")

if __name__ == '__main__':
    fix_categories()
