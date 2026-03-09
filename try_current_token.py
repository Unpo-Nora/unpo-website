import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("META_PAGE_ACCESS_TOKEN")
page_id = "260721673799066"

url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
payload = {
    'subscribed_fields': 'leadgen',
    'access_token': token
}

print(f"Probando token actual de .env que termina en {token[-10:]}...")
resp = requests.post(url, data=payload)
print(resp.json())
