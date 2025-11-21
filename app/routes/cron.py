# app/cron.py
from flask import Blueprint, jsonify
from app.services.expiration_service import send_expiration_warnings, process_expired_cards
from app.services.auth_service import verify_cron_token
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('cron', __name__)

@bp.get("/cron/send-expiration-warnings")
@verify_cron_token
def cron_send_warnings():
    """Called by Cloud Scheduler daily at 9 AM"""
    try:
        count = send_expiration_warnings()
        return jsonify({"success": True, "warnings_sent": count})
    except Exception as e:
        logger.error(f"Cron failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.get("/cron/process-expired-cards")
@verify_cron_token
def cron_process_expired():
    """Called by Cloud Scheduler daily at midnight"""
    try:
        count = process_expired_cards()
        return jsonify({"success": True, "cards_processed": count})
    except Exception as e:
        logger.error(f"Cron failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    
    