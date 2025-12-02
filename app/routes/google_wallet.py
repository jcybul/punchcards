# app/routes/google_wallet.py
"""
Google Wallet pass endpoints
"""
from flask import Blueprint, jsonify, request
from app.db import SessionLocal
from app.models import WalletCard, PunchProgram, Merchant
from app.services import google_wallet_service
from uuid import UUID
import logging
from app.services.auth_service import get_user_info

logger = logging.getLogger(__name__)

bp = Blueprint("google_wallet", __name__, url_prefix="/api/google-wallet")


@bp.route("/pass/<program_id>/", methods=["GET"])
def generate_google_pass(program_id: str, user_id: str):
    """
    Generate or get a Google Wallet pass for a user and program.
    Returns a 'Save to Google Wallet' URL.
    """
    try:
        program_uuid = UUID(program_id)
        user_uuid = UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid UUID format"}), 400
    
    with SessionLocal() as db:
        # Get or create card
        card = db.query(WalletCard).filter_by(
            user_id=user_uuid,
            program_id=program_uuid
        ).first()
        
        if not card:
            # Create new card
            card = WalletCard(
                user_id=user_uuid,
                program_id=program_uuid,
                current_punches=0,
                reward_credits=0,
                status='active'
            )
            db.add(card)
            db.commit()
            db.refresh(card)
            logger.info(f"Created new card {card.id} for user {user_id}")
        
        # Get program and merchant
        program = db.get(PunchProgram, program_uuid)
        if not program:
            return jsonify({"error": "Program not found"}), 404
            
        merchant = db.get(Merchant, program.merchant_id)
        if not merchant:
            return jsonify({"error": "Merchant not found"}), 404
        
        # Create/update the Google Wallet pass
        result = google_wallet_service.create_or_update_loyalty_object(
            card, program, merchant
        )
        
        if not result:
            return jsonify({
                "error": "Failed to create Google Wallet pass",
                "note": "Google Wallet may not be configured"
            }), 500
        
        # Generate save URL
        save_url = google_wallet_service.get_save_url(card,program)
        
        # Update card with Google object ID
        if not card.google_object_id:
            card.google_object_id = f"{google_wallet_service.ISSUER_ID}.{card.id}"
            db.commit()
        
        return jsonify({
            "success": True,
            "save_url": save_url,
            "card_id": str(card.id),
            "object_id": card.google_object_id
        })


@bp.route("/update/<card_id>", methods=["POST"])
def update_google_pass(card_id: str):
    """
    Manually trigger an update to a Google Wallet pass.
    (Usually called automatically after punching)
    """
    try:
        card_uuid = UUID(card_id)
    except ValueError:
        return jsonify({"error": "Invalid card ID"}), 400
    
    with SessionLocal() as db:
        card = db.get(WalletCard, card_uuid)
        if not card:
            return jsonify({"error": "Card not found"}), 404
        
        program = db.get(PunchProgram, card.program_id)
        if not program:
            return jsonify({"error": "Program not found"}), 404
            
        merchant = db.get(Merchant, program.merchant_id)
        if not merchant:
            return jsonify({"error": "Merchant not found"}), 404
        
        # Update the pass in Google Wallet
        success = google_wallet_service.update_pass(card, program, merchant)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Google Wallet pass updated"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to update Google Wallet pass"
            }), 500
            
@bp.route("/test-google-wallet-config", methods=["GET"])
def test_config():
    import os
    return {
        "GOOGLE_WALLET_ISSUER_ID": os.getenv("GOOGLE_WALLET_ISSUER_ID"),
        "GOOGLE_WALLET_SERVICE_ACCOUNT_FILE": os.getenv("GOOGLE_WALLET_SERVICE_ACCOUNT_FILE"),
        "file_exists": os.path.exists(os.getenv("GOOGLE_WALLET_SERVICE_ACCOUNT_FILE", ""))
    }
    
