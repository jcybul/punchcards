import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.admin_service import add_user_to_merchant

add_user_to_merchant("1d720224-e256-40e6-a994-442cdd07b881","63b5195a-fa11-4b6b-8756-8f97b07d1e35")
