import json
from flask import Blueprint, send_file, abort, request, Response, jsonify
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import WalletCard, PunchProgram
from app.apple_passes import build_pkpass 
from app.services.program_service import get_create_program_pass
from app.services.auth_service import require_auth, current_user_id, require_merchant_role
from app.services.punch_service import punch_card, NotFound, BadRequest, get_merchant_from_card
import logging
from app.services.reedemption_service import redeem_reward, CardNotActive,CardNotFound,InsufficientRewards

bp = Blueprint("redemptions", __name__)
logger = logging.getLogger(__name__)


@bp.route("/redeem_reward")
@require_auth
def redeem():
    """
    Redeem a reward. Requires staff authorization for the merchant.
    Staff scans card QR code and this deducts one reward credit.
    """
    card_id = request.args.get("card_id")
    staff_id = request.args.get("staff_id")
    
    if not card_id:
        return jsonify({"error": "Card not required", "message": str(e)}), 400
    
    # Get merchant from card for authorization
    merchant_id = get_merchant_from_card(card_id)

    if not merchant_id:
        return jsonify({"error": "Card not found", "message": str(e)}), 404

    
    # Check staff authorization
    require_merchant_role(merchant_id, allowed=('owner', 'manager', 'staff'))
    
    try:
        # Redeem the reward
        staff_user_id = current_user_id()
        result = redeem_reward(
            card_id=card_id,
            redeemed_by=staff_id
        )
        
        return jsonify(result), 200
        
    except CardNotFound as e:
        return jsonify({"error": "Card not found", "message": str(e)}), 404
    except CardNotActive as e:
        return jsonify({"error": "Card not active", "message": str(e)}), 400
    except InsufficientRewards as e:
        return jsonify({"error": "Insufficient rewards", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "message": str(e)}), 500