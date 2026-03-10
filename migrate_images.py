import os
import requests
import re

API_URL = "https://unpo-backend.onrender.com"

def sync_images_from_fs():
    print("Iniciando sincronización de imágenes desde el disco...")
    
    r = requests.post(f"{API_URL}/auth/login", data={"username": "admin@unpo.com.ar", "password": "admin"})
    if r.status_code != 200:
        print("Error al iniciar sesión:", r.text)
        return
        
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Agrupar imagenes por SKU
    images_dir = os.path.join("backend", "data", "images")
    if not os.path.exists(images_dir):
        print("El directorio de imágenes no existe.")
        return
        
    sku_images = {}
    for filename in os.listdir(images_dir):
        if filename.startswith('.'): continue
        
        # El formato es SKU.jpg o SKU_1.jpg
        # Extraemos la parte numerica del principio
        match = re.match(r"^(\d+)", filename)
        if match:
            sku = match.group(1)
            if sku not in sku_images:
                sku_images[sku] = []
            sku_images[sku].append(f"/static/images/{filename}")
            
    # Casos especiales en las imagenes: UNPO1.jpg
    
    print(f"Archivos encontrados para {len(sku_images)} SKUs.")

    # 2. Obtener productos de prod
    r_prod = requests.get(f"{API_URL}/products/?limit=1000")
    if r_prod.status_code != 200:
        print("Error al obtener productos")
        return
        
    prod_products = {p['sku']: p for p in r_prod.json()}
    
    # 3. Actualizar productos
    updated = 0
    for sku, images in sku_images.items():
        if sku not in prod_products:
            print(f"SKU {sku} tiene imágenes pero no existe en BD.")
            continue
            
        p = prod_products[sku]
        
        # Sort images so the main one (without _X) goes first, then _1, _2
        # e.g., 20600041.jpeg, 20600041_1.jpeg
        images.sort(key=lambda x: (len(x), x))
        
        # We only update if the images list is different
        if p.get('images') == images:
            continue
            
        payload = {
            "sku": p['sku'],
            "name": p['name'],
            "description": p.get('description', ''),
            "category_id": p.get('category_id'),
            "is_active": p.get('is_active', True),
            "price_wholesale": p.get('price_wholesale', 0),
            "stock_quantity": p.get('stock_quantity', 0),
            "weight": p.get('weight', 0),
            "images": images
        }
        
        r = requests.put(f"{API_URL}/products/{sku}", json=payload, headers=headers)
        if r.status_code in (200, 201):
            print(f"[{updated+1}] Actualizado {sku} con {len(images)} imágenes.")
            updated += 1
        else:
            print(f"Error {sku}: {r.text}")
            
    print(f"Finalizado. {updated} productos actualizados con imágenes.")

if __name__ == "__main__":
    sync_images_from_fs()
