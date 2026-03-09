import requests
import os
from dotenv import load_dotenv

load_dotenv()
sys_user_token = os.getenv("META_PAGE_ACCESS_TOKEN")
page_id = "260721673799066"  # ID de la página UNPO

if not sys_user_token:
    print("Error: META_PAGE_ACCESS_TOKEN no encontrado en .env")
    exit(1)

print(f"Buscando el Page Access Token para la página {page_id} usando tu token de System User...")

url = f"https://graph.facebook.com/v19.0/{page_id}?fields=access_token&access_token={sys_user_token}"
resp = requests.get(url)
data = resp.json()

if 'access_token' in data:
    page_token = data['access_token']
    print("\n✅ ¡ÉXITO! Se encontró el Token de Página Definitivo.")
    print("==================================================")
    print(page_token)
    print("==================================================\n")
    print("⏳ Suscribiendo la aplicación a los webhooks de esta página...")
    
    sub_url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    sub_payload = {
        'subscribed_fields': 'leadgen',
        'access_token': page_token
    }
    sub_resp = requests.post(sub_url, data=sub_payload)
    print("Respuesta de suscripción:", sub_resp.json())
else:
    print("❌ Error: No se pudo obtener el token de página. Facebook devolvió:")
    print(data)
