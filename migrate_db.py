import requests
import json
import csv
import os

API_URL = "https://unpo-backend.onrender.com"

def migrate():
    print("Iniciando migración desde CSVs locales (sin pandas)...")
    
    # 1. Setup admin
    print("Verificando admin...")
    try:
        requests.get(f"{API_URL}/auth/setup-admin")
    except Exception as e:
        print("Setup error:", e)
        
    # 2. Login
    print("Iniciando sesión como admin...")
    r = requests.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"})
    if r.status_code != 200:
        print("Error al iniciar sesión:", r.text)
        return
        
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Read CSV
    print("Leyendo catálogo CSV local...")
    csv_mayorista = "backend/data/MAYORISTA.csv"
    
    if not os.path.exists(csv_mayorista):
        print("Error: No se encontró MAYORISTA.csv")
        return
        
    # Crear categorías remotas básicas (cache)
    remote_cats = {}
    print("Sincronizando categorías...")
    r_cats = requests.get(f"{API_URL}/products/categories", headers=headers)
    if r_cats.status_code == 200:
       for c in r_cats.json():
           remote_cats[c['name']] = c['id']

    # Procesar archivo CSV mayorista
    # Saltamos las primeras 3 lineas
    with open(csv_mayorista, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for _ in range(3):
            next(reader, None)
            
        header = next(reader, None)
        if not header:
            print("CSV vacío")
            return
            
        # Encontrar indices de columnas
        try:
            idx_sku = header.index("COD. UNPO")
        except:
            idx_sku = 0
            
        try:
            idx_name = header.index("DESCRIPCION")
        except:
            idx_name = 1
            
        try:
            idx_cat = header.index("CATEGORIA")
        except:
            idx_cat = 2
            
        try:
            idx_stock = header.index("UNIDADES")
        except:
            idx_stock = 17
            
        try:
            idx_peso = header.index("KG")
        except:
            idx_peso = 3
            
        try:
            idx_precio = header.index("PRECIO SIN IVA")
        except:
            idx_precio = 9
            
        processed = 0
        for i, row in enumerate(reader):
            if not row or len(row) <= max(idx_sku, idx_name): continue
            
            sku_raw = row[idx_sku].strip()
            if not sku_raw: continue
            
            # Normalize SKU
            sku = sku_raw
            if '.' in sku: sku = sku.split('.')[0]
            try:
                 if sku.isdigit(): sku = str(int(sku))
            except: pass
            
            name = row[idx_name].strip()
            if not name: name = f"Producto {sku}"
            
            cat_name = row[idx_cat].strip() if len(row) > idx_cat else "General"
            if not cat_name: cat_name = "General"
            
            # Stock
            stock_val = 0
            if len(row) > idx_stock:
                raw_stock = row[idx_stock].strip()
                if raw_stock:
                    try:
                        val = raw_stock.replace('.', '').replace(',', '.')
                        stock_val = int(float(val))
                    except: pass
                    
            # Pricing
            price_val = 0.0
            if len(row) > idx_precio:
                 raw_price = row[idx_precio].strip().replace('$', '')
                 if raw_price:
                     try:
                         if '.' in raw_price and ',' in raw_price:
                             if raw_price.find(',') < raw_price.find('.'): raw_price = raw_price.replace(',', '')
                             else: raw_price = raw_price.replace('.', '').replace(',', '.')
                         elif ',' in raw_price: raw_price = raw_price.replace(',', '.')
                         elif '.' in raw_price and len(raw_price.split('.')[-1]) == 3: raw_price = raw_price.replace('.', '')
                         price_val = float(raw_price)
                     except: pass
                     
            # Weight
            weight_val = 0.0
            if len(row) > idx_peso:
                 raw_peso = row[idx_peso].strip()
                 if raw_peso:
                     try:
                         weight_val = float(raw_peso.replace(',', '.'))
                     except: pass
                     
            # Override for specific product mentioned in backend code
            if sku == "20800064":
                name = "PELUCHE KOALA NARIZ NEGRA"
                price_val = 17138.43
                
            payload = {
                "sku": sku,
                "name": name,
                "description": "",
                "category_id": None, 
                "is_active": True,
                "price_wholesale": price_val,
                "stock_quantity": stock_val,
                "weight": weight_val,
                "images": []
            }
            
            r = requests.post(f"{API_URL}/products/", json=payload, headers=headers)
            if r.status_code in (200, 201):
                print(f"[{processed+1}] OK: {sku}")
                processed += 1
            elif "already exists" in r.text.lower():
                r2 = requests.put(f"{API_URL}/products/{sku}", json=payload, headers=headers)
                print(f"[{processed+1}] UPDATED: {sku}")
                processed += 1
            else:
                print(f"[{processed+1}] ERROR {sku}: {r.text}")

if __name__ == "__main__":
    migrate()
