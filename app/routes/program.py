from flask import Blueprint, abort, jsonify, request
from app.exceptions import NotFound
from app.services.program_service import get_program, get_merchant_programs, get_user_programs, get_total_punches_for_program
from app.services.auth_service import require_auth, require_merchant_role, current_user_id
import logging
from ..db import engine

bp = Blueprint("program", __name__)
logger = logging.getLogger(__name__)


@bp.get("/get_program")
def get_profile():
    
    program_id = request.args.get('program_id')
    try:
        program = get_program(program_id)
        logger.info(program)
        return jsonify(program), 200
    except NotFound as e:
        abort(404, description=str(e))

@bp.get("/merchant_user_programs")
@require_auth
def get_user_programs_():
    user_id = current_user_id()
    
    if not user_id:
        return jsonify({"error": "Failed to fetch user"}), 500 
    
    try:
        programs = get_user_programs(user_id)
        
        return jsonify({
            "success": True,
            "programs": programs
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user programs: {e}") 
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Error while getting user programs"
        }), 500


@bp.route("/merchant/<merchant_id>/programs")
@require_auth
def merchant_programs(merchant_id: str):
    require_merchant_role(merchant_id, allowed=('owner', 'manager', 'staff'))
    try:
        programs = get_merchant_programs(merchant_id)
        return jsonify({
            "programs": programs,
            "count": len(programs)
        }), 200
    except NotFound as e:
        abort(404, description=str(e))

