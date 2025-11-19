# app/services/google_wallet_service.py
"""
Google Wallet pass generation using direct HTTP requests
Avoids googleapiclient.discovery issues on Cloud Run
"""

from datetime import datetime, timezone
import os
import re
import json
import time
import logging
import jwt
import requests
from google.oauth2 import service_account
import google.auth.transport.requests
from app.services.expiration_service import calculate_expiration_date
from app.services.utils_functions_service import ensure_naive_utc

logger = logging.getLogger(__name__)

# Configuration
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_WALLET_SERVICE_ACCOUNT_FILE")
ISSUER_ID = os.environ.get("GOOGLE_WALLET_ISSUER_ID")
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]
BASE_URL = "https://walletobjects.googleapis.com/walletobjects/v1"

_credentials = None


def normalize_id(value: str) -> str:
    """Sanitize object/class IDs for Google Wallet (lowercase + allowed chars only)."""
    return re.sub(r"[^a-z0-9._-]", "", str(value).lower())


def get_credentials():
    """Get authenticated credentials (singleton)."""
    global _credentials
    
    if _credentials is None:
        if not ISSUER_ID:
            logger.error("GOOGLE_WALLET_ISSUER_ID not set")
            return None
            
        if not SERVICE_ACCOUNT_FILE:
            logger.error("GOOGLE_WALLET_SERVICE_ACCOUNT_FILE not set")
            return None
            
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.error(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
            return None
        
        try:
            _credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, 
                scopes=SCOPES
            )
            logger.info("Google Wallet credentials loaded")
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None
    
    return _credentials


def get_access_token():
    """Get a fresh access token."""
    credentials = get_credentials()
    if not credentials:
        return None
    
    try:
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token
    except Exception as e:
        logger.error(f"Failed to refresh access token: {e}")
        return None


def make_api_request(method, endpoint, data=None):
    """Make an authenticated request to Google Wallet API."""
    token = get_access_token()
    if not token:
        logger.error("No access token available")
        return None
    
    url = f"{BASE_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            logger.error(f"Unsupported method: {method}")
            return None
        
        if response.status_code in (200, 201):
            return response.json()
        elif response.status_code == 409:
            return {"status": "exists", "response": response.json()}
        else:
            logger.error(f"API request failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API request exception: {e}")
        return None


def create_loyalty_class(program, merchant):
    """Create or update a Loyalty Class."""
    class_id = f"{ISSUER_ID}.{normalize_id(program.id)}"
    
    background_color = merchant.wallet_brand_color or "#111111"
    
    loyalty_class = {
        "id": class_id,
        "issuerName": merchant.name,
        "programName": program.name,
        "hexBackgroundColor": background_color,
        "textModulesData": [] ,
        "reviewStatus": "UNDER_REVIEW",
        
        "programLogo": {
            "sourceUri": {
                "uri": merchant.wallet_logo_url or "https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg"
            },
            "contentDescription": {
                "defaultValue": {"language": "en-US", "value": f"{merchant.name} logo"}
            },
        },
        
        "heroImage": {
            "sourceUri": {
                "uri": merchant.wallet_logo_url or "https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg"
            },
            "contentDescription": {
                "defaultValue": {"language": "en-US", "value": f"{program.name} rewards"}
            },
        },
        
        "localizedIssuerName": {
            "defaultValue": {"language": "en-US", "value": merchant.name}
        },
        "localizedProgramName": {
            "defaultValue": {"language": "en-US", "value": program.name}
        },
        
        "accountNameLabel": "Member",
        "accountIdLabel": "Card ID",
        "rewardsTier": program.name,
        "rewardsTierLabel": "Program",
        "multipleDevicesAndHoldersAllowedStatus": "MULTIPLE_HOLDERS",
    }
    
    # Add optional fields if available
    if hasattr(program, 'google_program_details') and program.google_program_details:
        loyalty_class["programDetails"] = {
            "defaultValue": {"language": "en-US", "value": program.google_program_details}
        }
        
    if program.expiration_enabled:
        expiration_type_text = {
            'rolling': 'Rolling expiration - extends with activity',
            'fixed': 'Fixed expiration from card creation',
            'hybrid': 'Extends with activity up to maximum'
        }.get(program.expiration_type, 'Cards expire after inactivity')
        
        loyalty_class["textModulesData"].append({
            "header": "Card Expiration",
            "body": f"{program.expiration_months} months. {expiration_type_text}",
            "id": "expiration_policy"
        })
    
    # Try to create
    result = make_api_request("POST", "loyaltyClass", loyalty_class)
    
    if result and result.get("status") == "exists":
        # Already exists, try to update (without reviewStatus)
        logger.info(f"Class {class_id} exists, updating...")
        loyalty_class_update = {k: v for k, v in loyalty_class.items() if k != "reviewStatus"}
        result = make_api_request("PATCH", f"loyaltyClass/{class_id}", loyalty_class_update)
    
    if result:
        logger.info(f" Loyalty class ready: {class_id}")
    else:
        logger.error(f"Failed to create/update class: {class_id}")
    
    return result


def create_or_update_loyalty_object(card, program, merchant):
    """Create or update a Loyalty Object (individual user pass)."""
    class_id = f"{ISSUER_ID}.{normalize_id(program.id)}"
    object_id = f"{ISSUER_ID}.{normalize_id(card.id)}"
    
    # Ensure class exists
    create_loyalty_class(program, merchant)
    
    # Calculate progress
    punches = card.current_punches or 0
    required = program.punches_required
    progress_text = f"{punches} of {required}"
    progress_percentage = int((punches / required) * 100) if required > 0 else 0
    
    # Visual progress bar
    filled = int((punches / required) * 10) if required > 0 else 0
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty
    
    # Status text
    if punches >= required:
        status_text = "Complete! Redeem your reward"
    elif punches > 0:
        remaining = required - punches
        status_text = f"{remaining} more punch{'es' if remaining > 1 else ''} to go!"
    else:
        status_text = "Start collecting punches"
    
    loyalty_object = {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE",
        "hasUsers": True,
        "hasLinkedDevice": True,
        
        "accountName": f"{merchant.name} Member",
        "accountId": str(card.id)[:8].upper(),
        
        "loyaltyPoints": {
            "label": "Punches",
            "balance": {"int": punches},
        },
        
        "barcode": {
            "type": "QR_CODE",
            "value": str(card.id),
            "alternateText": str(card.id)[:8].upper()
        },
        
        "textModulesData": [
            {
                "header": "Progress",
                "body": f"{progress_bar}\n{progress_text} ({progress_percentage}%)",
                "id": "progress"
            },
            {
                "header": "Status",
                "body": status_text,
                "id": "status"
            },
            {
                "header": "How to Earn",
                "body": f"Make a purchase and scan this QR code. Earn {required} punches to get a reward!",
                "id": "howto"
            }
        ],
        
        "infoModuleData": {
            "labelValueRows": [
                {
                    "columns": [
                        {"label": "Punches", "value": progress_text},
                        {"label": "Goal", "value": f"{required} total"}
                    ]
                }
            ]
        }
    }
    
    # Add rewards if available
    if card.reward_credits and card.reward_credits > 0:
        loyalty_object["secondaryLoyaltyPoints"] = {
            "label": "Rewards Available",
            "balance": {"int": card.reward_credits}
        }
        loyalty_object["textModulesData"].insert(1, {
            "header": "Rewards",
            "body": f"You have {card.reward_credits} reward{'s' if card.reward_credits > 1 else ''} ready to redeem!",
            "id": "rewards"
        })
        
    if card.expires_at:
        now = datetime.utcnow()
        expires_at_utc = ensure_naive_utc(card.expires_at)
        
        loyalty_object["validTimeInterval"] = {
            "start": {
                "date": card.created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            },
            "end": {
                "date": card.expires_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        }
        
        # Calculate days remaining
        days_remaining = (expires_at_utc - now).days
        
        # Add expiration info to text modules
        if days_remaining <= 0:
            # Expired
            loyalty_object["state"] = "EXPIRED"
            expiration_text = "EXPIRED"
            expiration_header = "Card Status"
        elif days_remaining <= 7:
            # Expiring very soon - urgent
            expiration_text = f"Expires in {days_remaining} day{'s' if days_remaining != 1 else ''}"
            expiration_header = "URGENT"
        elif days_remaining <= 30:
            # Expiring soon
            expiration_text = f"Expires in {days_remaining} days"
            expiration_header = "Valid Until"
        else:
            # Normal expiration display
            expiration_text = card.expires_at.strftime("%b %d, %Y")
            expiration_header = "Valid Until"
        
        # Add expiration module
        loyalty_object["textModulesData"].append({
            "header": expiration_header,
            "body": expiration_text,
            "id": "expiration"
        })
        
        if days_remaining > 0:
            loyalty_object["infoModuleData"]["labelValueRows"].append({
                "columns": [
                    {"label": "Expires", "value": card.expires_at.strftime("%b %d, %Y")}
                ]
            })
    
    result = make_api_request("POST", "loyaltyObject", loyalty_object)
    
    if result and result.get("status") == "exists":
        # Already exists, update it
        logger.info(f"Object {object_id} exists, updating...")
        result = make_api_request("PATCH", f"loyaltyObject/{object_id}", loyalty_object)
    
    if result:
        logger.info(f"Loyalty object ready: {object_id}")
    else:
        logger.error(f"Failed to create/update object: {object_id}")
    
    return result


def get_save_url(card, program):
    """Generate JWT-signed Save to Google Wallet URL."""
    if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
        # Fallback to simple URL
        import urllib.parse
        object_id = f"{ISSUER_ID}.{normalize_id(card.id)}"
        return f"https://pay.google.com/gp/v/save/{urllib.parse.quote(object_id)}"
    
    try:
        service_account_info = json.load(open(SERVICE_ACCOUNT_FILE))
        issuer_email = service_account_info["client_email"]
        private_key = service_account_info["private_key"]
        
        class_id = f"{ISSUER_ID}.{normalize_id(program.id)}"
        object_id = f"{ISSUER_ID}.{normalize_id(card.id)}"

        payload = {
            "iss": issuer_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "payload": {"loyaltyObjects": [{"id": object_id, "classId": class_id}]},
        }

        token = jwt.encode(payload, private_key, algorithm="RS256")
        return f"https://pay.google.com/gp/v/save/{token}"
    except Exception as e:
        logger.error(f"Failed to create JWT save URL: {e}")
        import urllib.parse
        object_id = f"{ISSUER_ID}.{normalize_id(card.id)}"
        return f"https://pay.google.com/gp/v/save/{urllib.parse.quote(object_id)}"


def update_pass(card, program, merchant):
    """Update Google Wallet pass after punch/redemption."""
    try:
        result = create_or_update_loyalty_object(card, program, merchant)
        if result:
            logger.info(f"Google Wallet pass updated for card {card.id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to update Google Wallet pass: {e}")
        return False


def get_or_create_google(program_id: str, user_id: str):
    """Get or create Google Wallet pass."""
    from flask import jsonify
    from uuid import UUID
    from app.db import SessionLocal
    from app.models import WalletCard, PunchProgram, Merchant
    
    try:
        program_uuid = UUID(program_id)
        user_uuid = UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid UUID format"}), 400
    
    with SessionLocal() as db:
        card = db.query(WalletCard).filter_by(
            user_id=user_uuid,
            program_id=program_uuid
        ).first()
        
        if not card:
            card = WalletCard(
                program_id=program.id,
                user_id=user_id,
                current_punches=0,
                reward_credits=0,
                status="active",
                lifetime_punches=0,
                lifetime_rewards=0,
                expiration_notified=False
                )
            card.expires_at = calculate_expiration_date(program, card)

            db.add(card)
            db.commit()
            db.refresh(card)
        
        program = db.get(PunchProgram, program_uuid)
        if not program:
            return jsonify({"error": "Program not found"}), 404
            
        merchant = db.get(Merchant, program.merchant_id)
        if not merchant:
            return jsonify({"error": "Merchant not found"}), 404
        
        result = create_or_update_loyalty_object(card, program, merchant)
        
        if not result:
            return jsonify({"error": "Failed to create Google Wallet pass"}), 500
        
        save_url = get_save_url(card, program)
        
        if not card.google_object_id:
            card.google_object_id = f"{ISSUER_ID}.{normalize_id(card.id)}"
            db.commit()
        
        return jsonify({
            "success": True,
            "save_url": save_url,
            "card_id": str(card.id),
            "google_object_id": card.google_object_id,
            "current_punches": card.current_punches,
            "reward_credits": card.reward_credits
        })
        
        
