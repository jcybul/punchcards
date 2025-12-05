import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.admin_service import add_user_to_merchant

add_user_to_merchant("fe9e6d32-b44d-4657-88db-493922843273","b5c6d91d-99ed-4f30-9194-052351975052")
