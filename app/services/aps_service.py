# app/services/apns_service.py
"""
Send push notifications to Apple devices when passes are updated.
Uses HTTP/2 APNs provider API.
"""
import os
import json
import jwt
import time
import httpx
from datetime import datetime, timedelta
from sqlalchemy import select
from app.models import WalletDeviceReg
from app.db import SessionLocal
import logging

# APNs configuration
APNS_KEY_ID = os.getenv("APNS_KEY_ID")  # Your APNs key ID (e.g., "ABC123DEFG")
APNS_TEAM_ID = os.getenv("APPLE_TEAM_ID")  # Your Apple Team ID
APNS_KEY_PATH = os.getenv("APNS_KEY_PATH") 
APNS_USE_SANDBOX = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"

# APNs endpoints
APNS_PRODUCTION_URL = "https://api.push.apple.com"
APNS_SANDBOX_URL = "https://api.sandbox.push.apple.com"

APNS_URL = APNS_SANDBOX_URL if APNS_USE_SANDBOX else APNS_PRODUCTION_URL

logger = logging.getLogger(__name__)


def _generate_apns_token() -> str:
    """
    Generate a JWT token for APNs authentication.
    Token is valid for 1 hour.
    """
    if not APNS_KEY_PATH or not os.path.exists(APNS_KEY_PATH):
        raise ValueError("APNs key file not found")
    
    with open(APNS_KEY_PATH, 'r') as f:
        key = f.read()
    
    headers = {
        "alg": "ES256",
        "kid": APNS_KEY_ID
    }
    
    payload = {
        "iss": APNS_TEAM_ID,
        "iat": int(time.time())
    }
    
    token = jwt.encode(payload, key, algorithm="ES256", headers=headers)
    return token


def send_push_notification(card_id: str) -> dict:
    """
    Send push notification to all devices registered for this card.
    This tells Apple Wallet to fetch the updated pass.
    
    Returns dict with success/failure counts.
    """
    if not APNS_KEY_ID or not APNS_TEAM_ID or not APNS_KEY_PATH:
        print("APNs not configured - skipping push notifications")
        return {"sent": 0, "failed": 0, "error": "APNs not configured"}

    print(APNS_KEY_ID,APNS_KEY_PATH,APNS_SANDBOX_URL)
    
    with SessionLocal() as db:
        # Get all device registrations for this card
        registrations = db.scalars(
            select(WalletDeviceReg).where(WalletDeviceReg.card_id == card_id)
        ).all()
        
        if not registrations:
            return {"sent": 0, "failed": 0, "error": "No devices registered"}
        
        # Generate auth token
        try:
            auth_token = _generate_apns_token()
        except Exception as e:
            logger.error(f"Failed to generate APNs token: {e}")
            return {"sent": 0, "failed": len(registrations), "error": str(e)}
        
        # Send notification to each device
        sent = 0
        failed = 0
        
        # Empty payload - this is a "content-available" notification
        # Apple Wallet will fetch the updated pass automatically
        payload = {}
        
        headers = {
            "authorization": f"bearer {auth_token}",
            "apns-topic": os.getenv("PASS_TYPE_ID"),  # Your pass type ID
            "apns-push-type": "background",
            "apns-priority": "5"
        }
        
        with httpx.Client(http2=True) as client:
            for reg in registrations:
                url = f"{APNS_URL}/3/device/{reg.push_token}"
                
                try:
                    response = client.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        sent += 1
                        logger.info(f"Push notification sent to device {reg.device_library_id}")
                    elif response.status_code == 410: 
                        failed += 1
                        logger.error(f"Token expired for device {reg.device_library_id}, removing...")
                        # Remove expired registration
                        with SessionLocal() as cleanup_db:
                            cleanup_db.delete(reg)
                            cleanup_db.commit()
                    else:
                        failed += 1
                        logger.error(f"APNs error: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to send push to device {reg.device_library_id}: {e}")
        
        return {"sent": sent, "failed": failed}


def notify_pass_updated(card_id: str):
    """
    Convenience function to send push notification after updating a pass.
    Call this after incrementing update_tag.
    """
    try:
        result = send_push_notification(card_id)
        logger.info(f"Push notification result for card {card_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return {"sent": 0, "failed": 0, "error": str(e)}

