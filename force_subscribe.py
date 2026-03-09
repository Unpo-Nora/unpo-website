import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("META_PAGE_ACCESS_TOKEN")
page_id = "260721673799066"  # ID exacto de la página UNPO

if not token:
    print("Error: META_PAGE_ACCESS_TOKEN no encontrado en .env")
    exit(1)

print(f"⏳ Intentando forzar la suscripción de la App a la página UNPO ({page_id})...")

url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
payload = {
    'subscribed_fields': 'leadgen',
    'access_token': token
}

sub_resp = requests.post(url, data=payload)
print("✅ Respuesta de suscripción:", sub_resp.json())
