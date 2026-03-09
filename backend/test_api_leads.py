import requests
import json

BASE_URL = "http://localhost:8000"

def test_api():
    # 1. Login
    login_data = {"username": "julianv@unpo.com.ar", "password": "secure_password_123"}
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Fetch Leads NEW
    print("\n--- Fetching NEW leads ---")
    response = requests.get(f"{BASE_URL}/leads/?status=NEW&limit=10", headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Received {len(data)} leads")
        if data:
            print(f"Sample Lead: {data[0]['full_name']} - Status: {data[0]['status']}")
    else:
        print(f"Error content: {response.text}")

    # 3. Fetch Leads CONTACTED
    print("\n--- Fetching CONTACTED leads ---")
    response = requests.get(f"{BASE_URL}/leads/?status=CONTACTED&limit=10", headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Received {len(data)} leads")
    else:
        print(f"Error content: {response.text}")

if __name__ == "__main__":
    test_api()
