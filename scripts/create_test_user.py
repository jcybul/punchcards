import os, requests
from dotenv import load_dotenv
load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env")

email = "testuser@example.com"
password = "TempPass123!"

url = f"{SUPABASE_URL}/auth/v1/admin/users"
headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

resp = requests.post(url, headers=headers, json={
    "email": email,
    "password": password,
    "email_confirm": True   # mark confirmed so you can log in immediately
})
resp.raise_for_status()



user = resp.json()
print("✅ Created test user")
print("ID:", user["id"])
print("Email:", user["email"])
