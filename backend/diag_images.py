import http.client
import json

def check_images():
    conn = http.client.HTTPConnection("localhost", 8000)
    
    # 1. Probar API de productos para ver qué devuelve
    print("--- Verificando respuesta de la API ---")
    conn.request("GET", "/products/?limit=5")
    res = conn.getresponse()
    if res.status == 200:
        data = json.loads(res.read().decode())
        for p in data:
            print(f"SKU: {p['sku']}, Images: {p.get('images', [])}")
    else:
        print(f"Error API: {res.status} {res.reason}")

    # 2. Probar acceso directo a una imagen conocida
    # Según psql: 10200003 -> /static/images/010200003.PNG
    test_url = "/static/images/010200003.PNG"
    print(f"\n--- Probando acceso a {test_url} ---")
    conn.request("GET", test_url)
    res = conn.getresponse()
    print(f"Resultado: {res.status} {res.reason}")
    if res.status == 200:
        print("¡ÉXITO! La imagen es accesible internamente.")
    else:
        print("FALLÓ el acceso a la imagen.")
    
    conn.close()

if __name__ == "__main__":
    check_images()
