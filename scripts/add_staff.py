import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.admin_service import add_user_to_merchant

add_user_to_merchant("1c86b348-f792-4503-ac40-f5ae5cd008ec","a00eccc3-6b39-473d-9779-5fd210891935")
