from app.db import SessionLocal
from app.models import WalletCard, PunchProgram, Merchant

def get_user_cards(user_id: str) -> list[dict]:
    """
    Get all wallet cards for a user with merchant and program details.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        List of wallet card details
    """
    with SessionLocal() as db:
        cards = db.query(WalletCard).filter(WalletCard.user_id == user_id).all()
        
        if not cards:
            return []
        result = []
        for card in cards:
            program = db.query(PunchProgram).filter(PunchProgram.id == card.program_id).first()
            if not program:
                continue 
            
            merchant = db.query(Merchant).filter(Merchant.id == program.merchant_id).first()
            if not merchant:
                continue  
            # Build card data
            result.append({
                "id": str(card.id),
                "merchant_name": merchant.name,
                "merchant_logo_url": merchant.wallet_logo_url,
                "program_name": program.name,
                "program_id": str(program.id),
                "current_punches": card.current_punches,
                "punches_required": program.punches_required,
                "reward_credits": card.reward_credits,
                "status": card.status,
                "created_at": card.created_at.isoformat(),
                "wallet_brand_color": merchant.wallet_brand_color
            })
        
        return result