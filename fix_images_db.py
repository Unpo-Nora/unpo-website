import os
import requests
import re
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

API_URL = "https://unpo-backend.onrender.com"

session = requests.Session()
retry = Retry(connect=5, read=5, backoff_factor=1.0)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def fix_images():
    print("Iniciando reemplazo de array de imagenes (filtrando formatos no soportados)...")
    
    r = session.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"}, timeout=20)
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    images_dir = os.path.join("backend", "data", "images")
    if not os.path.exists(images_dir):
        print("El directorio de imágenes no existe.")
        return
        
    sku_images = {}
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    
    for filename in os.listdir(images_dir):
        if filename.startswith('.'): continue
        if not filename.lower().endswith(valid_exts): continue
        
        # El formato es SKU.jpg o SKU_1.jpg
        # Extraemos la parte numerica del principio antes de cualquier '_' o '.'
        match = re.search(r"^(\d+)", filename)
        if match:
            # We must be careful!
            # 20300053_1.jpg -> sku 20300053
            # 20300053.jpg -> sku 20300053
            sku = match.group(1)
            # Ensure the characters after the digits are dot or understore
            rest = filename[len(sku):]
            if rest.startswith('.') or rest.startswith('_'):
                if sku not in sku_images:
                    sku_images[sku] = []
                sku_images[sku].append(f"/static/images/{filename}")
            
    # Remove duplicates and sort
    for sku in sku_images:
        sku_images[sku] = sorted(list(set(sku_images[sku])), key=lambda x: (len(x), x))
        
    print(f"Archivos encontrados para {len(sku_images)} SKUs.")

    r_prod = session.get(f"{API_URL}/products/?limit=1000", timeout=30)
    prod_products = {p['sku']: p for p in r_prod.json()}
    
    updated = 0
    for sku, p in prod_products.items():
        images = sku_images.get(sku, [])
        
        # If the API has different images, update it
        if set(p.get('images', [])) != set(images):
            payload = p.copy()
            payload['images'] = images
            
            rp = session.put(f"{API_URL}/products/{sku}", json=payload, headers=headers, timeout=20)
            if rp.status_code in (200, 201):
                print(f"[{updated+1}] Corregido {sku}: {p.get('images')} -> {images}")
                updated += 1
            else:
                print(f"Error {sku}: {rp.text}")
                
    print(f"Finalizado. {updated} productos corregidos.")

if __name__ == "__main__":
    fix_images()
