# app/services/expiration_service.py
"""
Handle card expiration logic.
"""
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import WalletCard, PunchProgram, WalletDeviceReg
from app.services.aps_service import send_push_notification
from app.services.google_wallet_service import create_generic_object

import logging

logger = logging.getLogger(__name__)


def calculate_expiration_date(program: PunchProgram, card: WalletCard = None) -> datetime | None:
    """
    Calculate expiration date based on program settings.
    
    Args:
        program: PunchProgram with expiration settings
        card: WalletCard (optional, for hybrid type)
    
    Returns:
        datetime of expiration or None if expiration disabled
    """
    if not program.expiration_enabled:
        return None
    
    now = datetime.utcnow()
    
    if program.expiration_type == 'fixed':
        if card:
            base_date = card.created_at
        else:
            base_date = now
        
        return base_date + timedelta(days=30 * program.expiration_months)
    
    elif program.expiration_type == 'rolling':
        # Rolling: X months from now (last activity)
        return now + timedelta(days=program.expiration_extension_days)
    
    elif program.expiration_type == 'hybrid':
        # Hybrid: X months from now, but capped at max from creation
        new_expiration = now + timedelta(days=program.expiration_extension_days)
        
        if card and program.expiration_max_months:
            max_expiration = card.created_at + timedelta(days=30 * program.expiration_max_months)
            return min(new_expiration, max_expiration)
        
        return new_expiration
    
    logger.warning(f"Unknown expiration type: {program.expiration_type}, defaulting to rolling")
    return now + timedelta(days=program.expiration_extension_days)


def extend_card_expiration(card_id: str, program: PunchProgram) -> WalletCard:
    """
    Extend card expiration based on program settings.
    Called when card is punched or redeemed.
    """
    with SessionLocal() as db:
        card = db.get(WalletCard, card_id)
        
        if not card:
            raise ValueError(f"Card {card_id} not found")
        
        if not program.expiration_enabled:
            logger.debug(f"Expiration disabled for program {program.id}")
            return card
        
        # Update last activity
        card.last_activity_at = datetime.utcnow()
        
        # Calculate new expiration
        if program.expiration_type in ['rolling', 'hybrid']:
            old_expiration = card.expires_at
            card.expires_at = calculate_expiration_date(program, card)
            
            # Reset notification flag if we extended significantly
            if old_expiration and card.expires_at and card.expires_at > old_expiration + timedelta(days=7):
                card.expiration_notified = False
            
            logger.info(f"Extended card {card_id} expiration to {card.expires_at}")
                
        db.commit()
        db.refresh(card)
        
        return card


def send_expiration_warnings():
    """
    Send warnings to users about expiring cards.
    Run this daily via cron job at 9 AM.
    
    Returns:
        Number of warnings sent
    """
    with SessionLocal() as db:
        now = datetime.utcnow()
        
        # Get all programs with expiration enabled
        programs = db.query(PunchProgram).filter(
            PunchProgram.expiration_enabled == True,
            PunchProgram.active == True
        ).all()
        
        warnings_sent = 0
        
        for program in programs:
            warning_date = now + timedelta(days=program.expiration_warning_days)
            
            # Get cards that will expire soon and haven't been notified
            expiring_cards = db.query(WalletCard).filter(
                WalletCard.program_id == program.id,
                WalletCard.expires_at <= warning_date,
                WalletCard.expires_at > now,
                WalletCard.expiration_notified == False,
                WalletCard.status == 'active'
            ).all()
            
            for card in expiring_cards:
                days_left = (card.expires_at - now).days
                
                # Get merchant info
                from app.models import Merchant
                merchant = db.get(Merchant, program.merchant_id)
                
                # Send push notification via APNs
                message = f"Your {merchant.name} punch card expires in {days_left} days. Visit soon to keep your rewards!"
                
                # Get device registrations
                registrations = db.query(WalletDeviceReg).filter_by(
                    card_id=card.id
                ).all()
                
                for reg in registrations:
                    if reg.push_token:
                        try:
                            send_push_notification(card.id)
                            logger.info(f"Sent expiration warning for card {card.id}")
                        except Exception as e:
                            logger.error(f"Failed to send expiration warning: {e}")
                
                # Mark as notified
                card.expiration_notified = True
                warnings_sent += 1
        
        db.commit()
        
        logger.info(f"Sent {warnings_sent} expiration warnings")
        return warnings_sent


def process_expired_cards():
    """
    Deactivate expired cards and update both Apple and Google passes.
    """
    with SessionLocal() as db:
        now = datetime.utcnow()
        
        # Get expired cards that are still active
        expired_cards = db.query(WalletCard).filter(
            WalletCard.expires_at <= now,
            WalletCard.status == 'active'
        ).all()
        
        for card in expired_cards:
            # Get program and merchant info
            program = db.get(PunchProgram, card.program_id)
            from app.models import Merchant
            merchant = db.get(Merchant, program.merchant_id)
            
            # Deactivate card
            old_status = card.status
            card.status = 'expired'
            
            logger.info(f"Expired card {card.id} (was {old_status})")
            
            if card.google_object_id:
                try:
                    create_generic_object(card, program, merchant)
                    logger.info(f"Marked Google Wallet pass as expired for card {card.id}")
                except Exception as e:
                    logger.error(f"Failed to update Google Wallet pass: {e}")
            
            
            registrations = db.query(WalletDeviceReg).filter_by(
                card_id=card.id
            ).all()
            
            for reg in registrations:
                if reg.push_token:
                    try:
                        send_push_notification(card.id)
                    except Exception as e:
                        logger.error(f"Failed to send expired notification: {e}")
        
        db.commit()
        
        logger.info(f"Processed {len(expired_cards)} expired cards")
        return len(expired_cards)


def get_expiration_stats(merchant_id: str = None) -> dict:
    """
    Get expiration statistics for merchant dashboard.
    """
    with SessionLocal() as db:
        query = db.query(WalletCard)
        
        if merchant_id:
            query = query.join(PunchProgram).filter(
                PunchProgram.merchant_id == merchant_id
            )
        
        now = datetime.utcnow()
        
        # Count cards by expiration status
        active_cards = query.filter(
            WalletCard.status == 'active',
            WalletCard.expires_at > now
        ).count()
        
        expiring_soon = query.filter(
            WalletCard.status == 'active',
            WalletCard.expires_at <= now + timedelta(days=30),
            WalletCard.expires_at > now
        ).count()
        
        expired_cards = query.filter(
            WalletCard.status == 'expired'
        ).count()
        
        return {
            "active_cards": active_cards,
            "expiring_soon": expiring_soon,
            "expired_cards": expired_cards
        }