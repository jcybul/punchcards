from flask import Blueprint, abort, jsonify, request
from sqlalchemy import text

from app.services.auth_service import current_user_id, require_auth, get_user_info
from app.services.user_service import get_user_cards
from app.exceptions import NotFound

from ..db import engine

bp = Blueprint("user", __name__)

@bp.get("/profile")
@require_auth
def get_profile():
    user_id = current_user_id()
    
    try:
        profile = get_user_info(user_id)
        return jsonify(profile), 200
    except NotFound as e:
        abort(404, description=str(e))

@bp.route("/cards")
@require_auth
def get_cards():
    user_id = current_user_id()
    cards = get_user_cards(user_id)
    
    
    return jsonify({
        "cards": cards,
        "count": len(cards)
    }), 200
    
    
    
    
    
    


