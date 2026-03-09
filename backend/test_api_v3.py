import requests
import json

BASE_URL = "http://localhost:8000"

def test_api():
    # 1. Login to get token
    login_data = {"username": "julianv@unpo.com.ar", "password": "secure_password_123"}
    print(f"Logging in with {login_data['username']}...")
    try:
        response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
        if response.status_code != 200:
            print(f"Login failed ({response.status_code}): {response.text}")
            return
    except Exception as e:
        print(f"Connection error: {e}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Fetch Leads
    print("\n--- Fetching leads from /leads/ ---")
    try:
        response = requests.get(f"{BASE_URL}/leads/", headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Received {len(data)} leads")
            if data:
                print(f"Sample Lead Status: {data[0].get('status')}")
                print(f"Sample Lead ID: {data[0].get('id')}")
        else:
            print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    test_api()
