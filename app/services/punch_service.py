# app/services/punch_service.py
# Add this import at the top
from datetime import datetime
import time
from app.models import PunchProgram, WalletDeviceReg,WalletCard, Punch, Merchant
from app.services.aps_service import notify_pass_updated 
from app.services.expiration_service import extend_card_expiration
from app.services.google_wallet_service import update_pass

from app.db import SessionLocal
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def get_device_count(card):
    with SessionLocal() as db:
        apple_devices = db.query(WalletDeviceReg).filter_by(card_id=card.id).count()
        return apple_devices or None


def get_merchant_from_card(card_id: str) -> str | None:
    """Get merchant_id from card_id using a join."""
    with SessionLocal() as db:
        result = db.query(PunchProgram.merchant_id).join(
            WalletCard, WalletCard.program_id == PunchProgram.id
        ).filter(
            WalletCard.id == card_id
        ).first()
        
        return str(result[0]) if result else None
    
# Update your punch_card function to trigger push notifications
def punch_card(card_id: str,created_by: str):
    """
    Add a punch to a wallet card and trigger push notification.
    """
 
    with SessionLocal() as db:
        card = db.get(WalletCard, card_id)
        
        if not card:
            raise NotFound(f"Card {card_id} not found")
        
        if card.status != "active":
            raise BadRequest(f"Card is not active (status: {card.status})")
        
        if card.expires_at and card.expires_at < datetime.utcnow():
            raise ValueError("Card has expired. Please get a new card.")
        
        program = db.get(PunchProgram, card.program_id)
        merchant = db.get(Merchant,program.merchant_id)
        
        # Add punch
        punch = Punch(
            wallet_card_id=card.id,
            amount=1,
            source="api",
            created_by=created_by
        )
        db.add(punch)
        
        card.current_punches += 1
        
        card.lifetime_punches = (card.lifetime_punches or 0) + 1  # Reset punches
        
        # IMPORTANT: Increment update_tag to trigger pass update
        card.update_tag = int(time.time())
        
        reward_earned = False
        if card.current_punches >= program.punches_required:
            card.reward_credits += 1
            card.current_punches = 0
            card.lifetime_rewards = (card.lifetime_rewards or 0) + 1
            reward_earned = True
            logger.info(f"Reward earned for card {card.id}")
        
        db.commit()
        db.refresh(card)
        
        
        try:
            card = extend_card_expiration(card.id, program)
        except Exception as e:
            logger.error(f"Failed to extend expiration: {e}")
        
        
        # Send push notification to all registered devices
        apple_devices = db.query(WalletDeviceReg).filter_by(card_id=card.id).count()
        
        # Check if this card has a Google Wallet pass
        has_google = card.google_object_id is not None
    
        if apple_devices > 0:
            notify_pass_updated(str(card.id))
            logger.info(f"Sent Apple push notification to {apple_devices} devices")
        
        if has_google:
            update_pass(card, program, merchant)
            logger.info("Updated Google Wallet pass")
            
        return card


# Keep your existing NotFound and BadRequest exceptions
class NotFound(Exception):
    pass

class BadRequest(Exception):
    pass