import time
from app.models import Merchant, PunchProgram, WalletDeviceReg
from app.services.aps_service import notify_pass_updated
from app.db import SessionLocal
from app.models import WalletCard, Punch, Redemption
from sqlalchemy import select
from app.services.aps_service import notify_pass_updated
from app.services.google_wallet_service import update_pass

import logging

logger = logging.getLogger(__name__)



def redeem_reward(card_id: str, redeemed_by: str, location_id: str = None, value_cents: int = 0) -> dict:
    """
    Redeem one reward from a card.
    
    Args:
        card_id: UUID of the wallet card
        redeemed_by: UUID of staff member processing redemption
        location_id: Optional location where redeemed
        value_cents: Optional monetary value of reward
        
    Returns:
        dict with redemption details
        
    Raises:
        CardNotFound: If card doesn't exist
        CardNotActive: If card is not active
        InsufficientRewards: If card has no rewards available
    """
    with SessionLocal() as db:
        card = db.get(WalletCard, card_id)
        
        if not card:
            raise CardNotFound(f"Card {card_id} not found")
        
        if card.status != "active":
            raise CardNotActive(f"Card is not active (status: {card.status})")
        
        if card.reward_credits < 1:
            raise InsufficientRewards(f"Card has no rewards available (credits: {card.reward_credits})")
        program = db.get(PunchProgram, card.program_id)
        merchant = db.get(Merchant,program.merchant_id)
        
        # Create redemption record
        redemption = Redemption(
            wallet_card_id=card.id,
            created_by=redeemed_by
        )
        db.add(redemption)
        
        # Deduct reward credit
        card.reward_credits -= 1
        card.update_tag = int(time.time())
        
        db.commit()
        db.refresh(card)
        db.refresh(redemption)
        
        # Send push notification to update pass
        apple_devices = db.query(WalletDeviceReg).filter_by(card_id=card.id).count()
        
        # Check if this card has a Google Wallet pass
        has_google = card.google_object_id is not None
    
        if apple_devices > 0:
            notify_pass_updated(str(card.id))
            logger.info(f"Sent Apple push notification to {apple_devices} devices")
        
        if has_google:
            update_pass(card, program, merchant)
            logger.info("Updated Google Wallet pass")
        
        
        return {
            "success": True,
            "redemption_id": str(redemption.id),
            "card_id": str(card.id),
            "reward_credits": card.reward_credits,
            "current_punches": card.current_punches,
            "redeemed_at": redemption.created_at.isoformat(),
            "redeemed_by": redeemed_by
        }
        
        
class InsufficientRewards(Exception):
    """Raised when card has no rewards to redeem"""
    pass

class CardNotFound(Exception):
    """Raised when card doesn't exist"""
    pass

class CardNotActive(Exception):
    """Raised when card is not active"""
    pass