# app/routes/wallet_service.py
"""
Apple Wallet Web Service endpoints (required for live pass updates).
See: https://developer.apple.com/documentation/walletpasses/adding_a_web_service_to_update_passes
"""
from flask import Blueprint, request, jsonify, abort
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import SessionLocal
from app.models import WalletCard, WalletDeviceReg, PunchProgram, Merchant
from app.apple_passes import build_pkpass
import os
import logging
bp = Blueprint("wallet_service", __name__, url_prefix="/v1")
logger = logging.getLogger(__name__)

PASS_TYPE_ID = os.environ["PASS_TYPE_ID"]

def _verify_auth_token(serial_number: str) -> WalletCard | None:
    """
    Verify the Authorization header matches the card's auth_token.
    Returns the WalletCard if valid, None otherwise.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("ApplePass "):
        return None
    
    token = auth_header.replace("ApplePass ", "")
    
    with SessionLocal() as db:
        card = db.scalar(
            select(WalletCard).where(
                WalletCard.id == serial_number,
                WalletCard.auth_token == token
            )
        )
        return card


@bp.route("/devices/<device_library_id>/registrations/<pass_type_id>/<serial_number>", methods=["POST"])
def register_device(device_library_id: str, pass_type_id: str, serial_number: str):
    """
    Called when user adds pass to Apple Wallet.
    Stores device token so we can send push notifications.
    """
    if pass_type_id != PASS_TYPE_ID:
        abort(404)
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("ApplePass "):
        abort(401)
    
    token = auth_header.replace("ApplePass ", "")
    
    data = request.get_json()
    push_token = data.get("pushToken")
    
    if not push_token:
        abort(400)
    
    with SessionLocal() as db:
        # Verify card exists and token matches
        card = db.scalar(
            select(WalletCard).where(
                WalletCard.id == serial_number,
                WalletCard.auth_token == token
            )
        )
        
        if not card:
            abort(401)
        
        # Check if registration already exists
        existing = db.scalar(
            select(WalletDeviceReg).where(
                WalletDeviceReg.card_id == card.id,
                WalletDeviceReg.device_library_id == device_library_id
            )
        )
        
        if existing:
            # Update push token
            existing.push_token = push_token
            db.commit()
            return "", 200  # <-- ADDED return statement
        else:
            # Create new registration
            reg = WalletDeviceReg(
                card_id=card.id,
                device_library_id=device_library_id,
                push_token=push_token
            )
            db.add(reg)
            db.commit()
            return "", 201

@bp.route("/devices/<device_library_id>/registrations/<pass_type_id>", methods=["GET"])
def get_registrations(device_library_id: str, pass_type_id: str):
    """
    Returns list of pass serial numbers registered to this device.
    
    CRITICAL FIX: When passes are grouped, we need to return ALL passes
    so Apple Wallet updates all of them together.
    """
    if pass_type_id != PASS_TYPE_ID:
        abort(404)
    
    passes_updated_since = request.args.get("passesUpdatedSince")
    
    with SessionLocal() as db:
        query = (
            select(WalletCard.id, WalletCard.update_tag, PunchProgram.name)
            .join(WalletDeviceReg, WalletDeviceReg.card_id == WalletCard.id)
            .join(PunchProgram, PunchProgram.id == WalletCard.program_id)
            .where(WalletDeviceReg.device_library_id == device_library_id)
        )
        
        all_results = db.execute(query).all()
        
        if not all_results:
            return "", 204
        
        if passes_updated_since:
            cutoff = int(passes_updated_since)
            
            updated_cards = [
                (card_id, update_tag, program_name) 
                for card_id, update_tag, program_name in all_results 
                if update_tag > cutoff
            ]
            
            
            if not updated_cards:
                return "", 204
            

            results = all_results
        else:
            results = all_results
        
        serial_numbers = [str(card_id) for card_id, _, _ in results]
        last_updated = max(update_tag for _, update_tag, _ in results)
        
        response_data = {
            "serialNumbers": serial_numbers,
            "lastUpdated": str(last_updated)
        }
        
        logger.info(f"Returning {len(serial_numbers)} pass(es) for update:")
        for sn in serial_numbers:
            logger.info(f"  - {sn}")
        logger.info(f"Last updated: {last_updated}")
        
        return jsonify(response_data), 200


@bp.route("/devices/<device_library_id>/registrations/<pass_type_id>/<serial_number>", methods=["DELETE"])
def unregister_device(device_library_id: str, pass_type_id: str, serial_number: str):
    """
    Called when user removes pass from Apple Wallet.
    """
    if pass_type_id != PASS_TYPE_ID:
        abort(404)
    
    card = _verify_auth_token(serial_number)
    if not card:
        abort(401)
    
    with SessionLocal() as db:
        reg = db.scalar(
            select(WalletDeviceReg).where(
                WalletDeviceReg.card_id == card.id,
                WalletDeviceReg.device_library_id == device_library_id
            )
        )
        
        if reg:
            db.delete(reg)
            db.commit()
    
    return "", 200


@bp.route("/passes/<pass_type_id>/<serial_number>", methods=["GET"])
def get_latest_pass(pass_type_id: str, serial_number: str):
    """
    Returns the latest .pkpass file.
    Called by Apple Wallet when it detects an update is available.
    """
    if pass_type_id != PASS_TYPE_ID:
        abort(404)
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("ApplePass "):
        abort(401)
    
    token = auth_header.replace("ApplePass ", "")
    
    with SessionLocal() as db:
        card = db.scalar(
            select(WalletCard).where(
                WalletCard.id == serial_number,
                WalletCard.auth_token == token
            )
        )
        
        if not card:
            abort(401)
        
        program = db.get(PunchProgram, card.program_id)
        if not program:
            abort(404)
            
        merchant = db.get(Merchant,program.merchant_id)
        if not merchant:
            abort(404)
        
        pkpass_bytes = build_pkpass(card, program, merchant)
        
        return pkpass_bytes, 200, {
            "Content-Type": "application/vnd.apple.pkpass",
            "Last-Modified": str(card.update_tag)
        }

@bp.route("/log", methods=["POST"])
def log_messages():
    """
    Apple Wallet can POST error logs here for debugging.
    """
    logs = request.get_json()
    
    logger.info(f"Apple Wallet logs: {logs}")
    
    return "", 200

