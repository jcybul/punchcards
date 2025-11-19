import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.admin_service import add_user_to_merchant

add_user_to_merchant("9a4a527e-300d-44ea-8b62-e06fd48b90ca","a00eccc3-6b39-473d-9779-5fd210891935")
