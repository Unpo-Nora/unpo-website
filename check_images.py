import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

API_URL = "https://unpo-backend.onrender.com"

session = requests.Session()
retry = Retry(connect=5, read=5, backoff_factor=1.0)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def check():
    r = session.get(f"{API_URL}/products/?limit=1000", timeout=20)
    items = r.json()
    broken = [p for p in items if p['images']]
    ast = [p for p in items if p['sku']=='10300074']
    if ast:
        print('Astronaut 10300074 images:', ast[0].get('images'))
    print('Sample broken carousels:', [(p['sku'], p['images']) for p in broken[:3]])
    
if __name__ == '__main__':
    check()
