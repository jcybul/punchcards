# app/routes/passes.py
import json
from flask import Blueprint, send_file, abort, request, Response, jsonify
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import WalletCard, PunchProgram
from app.apple_passes import build_pkpass 
from app.services.program_service import get_create_program_pass
from app.services.auth_service import require_auth, current_user_id, require_merchant_role
from app.services.punch_service import punch_card, NotFound, BadRequest, get_merchant_from_card
from app.services.google_wallet_service import get_or_create_google
import logging
import time


bp = Blueprint("passes", __name__)
logger = logging.getLogger(__name__)


@bp.route("/punch_card")
@require_auth
def punch():
    """
    Punch a card. Requires staff authorization for the merchant.
    """
    card_id = request.args.get("card_id")
    
    if not card_id:
        abort(400, description="card_id required")
    
    # Get the merchant from the card
    merchant_id = get_merchant_from_card(card_id)
    
    if not merchant_id:
        abort(404, description="Card not found")
    
    # Check if user has permission for this merchant
    require_merchant_role(merchant_id, allowed=('owner', 'manager', 'staff'))
    
    # If we get here, user is authorized - proceed with punch
    try:
        staff_user_id = current_user_id()
        card = punch_card(card_id, created_by=staff_user_id)
        
    except NotFound as e:
        abort(404, description=str(e))
    except BadRequest as e:
        abort(400, description=str(e))

    return jsonify({
        "card_id": str(card.id),
        "current_punches": card.current_punches,
        "reward_credits": card.reward_credits,
        "update_tag": card.update_tag,
        "status": card.status,
        "punched_by": staff_user_id,
        "expiration": card.expires_at
    })
    
@bp.route("/apple/get_or_create/")
@require_auth
def get_or_create_user_pass():
    
    program_id = request.args.get('program_id')
    user_id = current_user_id()
    
    if not program_id or not user_id:
        return Response(
            json.dumps({"error": "Missing required parameters: program_id and user_id."}),
            status=400,
            mimetype='application/json'
        )
    
    # 3. Call the core logic function
    logger.info(f"Getting pass for user {user_id} ")
    pass_result = get_create_program_pass(program_id, user_id)
    
    if isinstance(pass_result, bytes):
        # SUCCESS: Function returned the binary pkpass content
        
        # Apple Wallet passes MUST be served with this specific MIME type
        # The filename suggestion is typically included in the headers
        return Response(
            pass_result, 
            mimetype='application/vnd.apple.pkpass', 
            headers={
                'Content-Disposition': f'attachment; filename="loyalty_card_{program_id}_{user_id}.pkpass"'
            }
        )
    else:
        # ERROR: Function returned a string error message
        # Use HTTP 404 if the program wasn't found, otherwise 400 for a general failure
        status_code = 404 if "failed to find program" in pass_result else 400
        
        return Response(
            json.dumps({"error": pass_result}),
            status=status_code,
            mimetype='application/json'
        )
    
@bp.route("/google/get_or_create/")
@require_auth
def get_or_create_google_pass():
    """
    Generate or get a Google Wallet pass for a user and program.
    Returns a 'Save to Google Wallet' URL.
    """
    
    program_id = request.args.get('program_id')
    user_id = current_user_id()
    
    if not program_id or not user_id:
        return Response(
            json.dumps({"error": "Missing required parameters: program_id and user_id."}),
            status=400,
            mimetype='application/json'
        )
    
    # 3. Call the core logic function
    logger.info(f"Getting pass for user {user_id} ")
    pass_result = get_or_create_google(program_id, user_id)
    
    return pass_result
    

    
    