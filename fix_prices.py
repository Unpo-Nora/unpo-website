import csv
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

API_URL = "https://unpo-backend.onrender.com"

# Setup session with retries
session = requests.Session()
retry = Retry(connect=5, read=5, backoff_factor=1.0)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def parse_price(val):
    val = val.strip().replace('$', '').replace('"', '').replace(',', '')
    if not val: return 0.0
    try:
        if '.' in val and len(val.split('.')[-1]) == 3:
             val = val.replace('.', '')
        return float(val)
    except Exception as e:
        print(f"Error parsing price {val}: {e}")
        return 0.0

def fix_prices():
    print("Iniciando actualizacion de precios y productos faltantes desde CATALOGO.csv...")
    
    r = session.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"}, timeout=20)
    if r.status_code != 200:
         print("Error login")
         return
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get remote products
    r_prod = session.get(f"{API_URL}/products/?limit=1000", timeout=20)
    remote_prods = {p['sku']: p for p in r_prod.json()}
    
    csv_path = 'backend/data/CATALOGO.csv'
    
    updated_count = 0
    added_count = 0
    
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        idx_sku = header.index("COD. UNPO") if header and "COD. UNPO" in header else 0
        idx_name = header.index("NOMBRE") if header and "NOMBRE" in header else 1
        idx_desc = header.index("DESCRIPCION") if header and "DESCRIPCION" in header else 2
        idx_cat = header.index("CATEGORIA") if header and "CATEGORIA" in header else 3
        idx_price = header.index("CONTADO / TRANSFERENCIA") if header and "CONTADO / TRANSFERENCIA" in header else 5
        idx_stock = header.index("Stock") if header and "Stock" in header else 6
        
        for row in reader:
            if not row or len(row) <= max(idx_sku, idx_price): continue
            
            sku_raw = row[idx_sku].strip()
            if not sku_raw: continue
            
            sku = sku_raw
            if '.' in sku: sku = sku.split('.')[0]
            try:
                 if sku.isdigit(): sku = str(int(sku))
            except: pass
            
            price_raw = row[idx_price]
            # Custom parsing for price: "18,375.00" -> 18375.0
            p_val = price_raw.strip().replace('$', '').replace('"', '').replace(',', '')
            price = 0.0
            if p_val:
                try: price = float(p_val)
                except: pass
                
            stock = 0
            if row[idx_stock].strip():
                 try: stock = int(float(row[idx_stock].strip().replace(',','')))
                 except: pass
                 
            name = row[idx_name].strip()
            if not name: name = row[idx_desc].strip().split('\\n')[0][:50]
            if not name: name = f"Producto {sku}"
            
            # Missing skus override
            if sku in ('10700084', '10700085'):
                # Add it
                if sku not in remote_prods:
                    payload = {
                        "sku": sku,
                        "name": name,
                        "description": row[idx_desc].strip(),
                        "category_id": None,
                        "is_active": True,
                        "price_wholesale": price,
                        "stock_quantity": stock,
                        "weight": 0.0,
                        "images": []
                    }
                    rp = session.post(f"{API_URL}/products/", json=payload, headers=headers, timeout=20)
                    if rp.status_code in (200, 201):
                        print(f"Added missing {sku}: {name} - Price: {price}")
                        added_count += 1
                        remote_prods[sku] = rp.json()
                    else:
                        print(f"Failed to add {sku}: {rp.text}")
            
            if sku in remote_prods:
                p = remote_prods[sku]
                if abs(float(p.get('price_wholesale', 0) or 0) - price) > 0.01:
                    payload = {
                        "sku": p['sku'],
                        "name": p['name'],
                        "description": p.get('description', ''),
                        "category_id": p.get('category_id'),
                        "is_active": p.get('is_active', True),
                        "price_wholesale": price,
                        "stock_quantity": p.get('stock_quantity', stock),
                        "weight": p.get('weight', 0.0),
                        "images": p.get('images', [])
                    }
                    rp = session.put(f"{API_URL}/products/{sku}", json=payload, headers=headers, timeout=20)
                    if rp.status_code in (200, 201):
                        print(f"Updated price {sku}: {p.get('price_wholesale', 0)} -> {price}")
                        updated_count += 1
                        
    print(f"Updated {updated_count} prices. Added {added_count} products.")
                        
if __name__ == '__main__':
    fix_prices()
