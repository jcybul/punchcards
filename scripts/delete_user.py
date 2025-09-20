import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

user_id = "fceeb437-791d-48a0-aec9-4ee63031f360"

url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
headers = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
}

resp = requests.delete(url, headers=headers)
if resp.status_code == 200:
    print("✅ User deleted")
else:
    print("❌ Failed:", resp.text)