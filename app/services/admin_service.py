import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import MerchantUser, Merchant, Profile
from sqlalchemy import select
import os, requests
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def create_user(email,password):
    if not SUPABASE_URL or not KEY:
        raise SystemExit("❌ Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env")

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



def add_user_to_merchant(user_id: str, merchant_id: str, role="staff"):
    """
    Add a user as staff for a merchant.
    
    Args:
        user_id: UUID of the user
        merchant_id: UUID of the merchant
        role: 'owner', 'manager', or 'staff' (default: staff)
    """
    valid_roles = ['owner', 'manager', 'staff']
    if role not in valid_roles:
        print(f" Invalid role. Must be one of: {valid_roles}")
        return False
    
    with SessionLocal() as db:
        # Check if user exists
        user = db.query(Profile).filter(Profile.id == user_id).first()
        if not user:
            print(f" User {user_id} not found")
            return False
        
        # Check if merchant exists
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            print(f"Merchant {merchant_id} not found")
            return False
        
        # Check if user is already assigned to this merchant
        existing = db.query(MerchantUser).filter(
            MerchantUser.user_id == user_id,
            MerchantUser.merchant_id == merchant_id
        ).first()
        
        if existing:
            print(f"⚠️  User already has role '{existing.role}' for {merchant.name}")
            # Optionally update role
            existing.role = role
            db.commit()
            print(f" Updated role to '{role}'")
            return True
        
        # Create new merchant user assignment
        merchant_user = MerchantUser(
            user_id=user_id,
            merchant_id=merchant_id,
            role=role
        )
        db.add(merchant_user)
        db.commit()
        
        user_name = f"{user.first_name} {user.last_name}" if user.first_name else user_id
        print(f"Added {user_name} as '{role}' for {merchant.name}")
        return True
            
        
