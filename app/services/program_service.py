from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session,joinedload

from app.db import engine
from app.models import PunchProgram, WalletCard,Merchant, Redemption, MerchantUser
from app.apple_passes import build_pkpass
from app.exceptions import NotFound
from app.db import SessionLocal


def get_program(program_id):
    with Session(engine) as session:
        result = session.query(PunchProgram, Merchant).join(Merchant).filter(PunchProgram.id == program_id).first()
        
        if not result:
            raise NotFound(f"failed to find program with id {program_id}")
        
        program, merchant = result
        return {
            "id": str(program.id),
            "merchant_id": str(program.merchant_id),
            "merchant_name": merchant.name,
            "merchant_logo_url": merchant.wallet_logo_url,
            "filled_icon": program.wallet_filled_icon_url,
            "empty_icon": program.wallet_empty_icon_url,
            "brand_color": merchant.wallet_brand_color,
            "wallet_logo_url": merchant.wallet_logo_url,
            "description": "placeholder",
            "name": program.name,
            "punches_required": program.punches_required,
            
            }
        
def get_merchant_programs(merchant_id: str) -> list[dict]:
    """
    Get all punch programs for a merchant.
    
    Args:
        merchant_id: UUID of the merchant
        
    Returns:
        List of programs with details
        
    Raises:
        NotFound: If merchant doesn't exist
    """
    with Session(engine) as session:
        merchant = session.get(Merchant, merchant_id)
        if not merchant:
            raise NotFound(f"Merchant {merchant_id} not found")
        
        programs = session.query(PunchProgram).filter(
            PunchProgram.merchant_id == merchant_id
        ).order_by(PunchProgram.created_at.desc()).all()
        
        result = []
        for program in programs:
            active_count = session.scalar(
            select(func.count(WalletCard.id))
            .where(
                WalletCard.program_id == program.id,
                WalletCard.status == "active"
            )
        )
            redemption_count = session.scalar(
            select(func.count(Redemption.id))
            .join(WalletCard, WalletCard.id == Redemption.wallet_card_id)
            .where(WalletCard.program_id == program.id)
            ) or 0
            result.append({
                     "id": str(program.id),
                    "merchant_id": str(program.merchant_id),
                    "merchant_name": merchant.name,
                    "merchant_logo_url": merchant.wallet_logo_url,
                    "filled_icon": program.wallet_filled_icon_url,
                    "empty_icon": program.wallet_empty_icon_url,
                    "brand_color": merchant.wallet_brand_color,
                    "wallet_logo_url": merchant.wallet_logo_url,
                    "description": "placeholder",
                    "name": program.name,
                    "punches_required": program.punches_required,
                    "active_cards": active_count or 0,
                    "total_redepmtions": redemption_count or 0,
                    "created_at": program.created_at.isoformat()
            })
        
        return result
            

def get_create_program_pass(program_id,user_id):
    with Session(engine) as session:
        ## get the program
        program = session.query(PunchProgram).filter(PunchProgram.id == program_id).first()
        
        if not program:
            return f"failed to find program with id {program_id}"
        merchant = session.query(Merchant).filter(Merchant.id == program.merchant_id).first()
        
        ## get the wallet pass if exist wit the user id and program id 
        
        wallet_pass = session.query(WalletCard).filter(
                    (WalletCard.program_id == program.id) & (WalletCard.user_id == user_id)
                ).first()        
        if not wallet_pass:
            new_pass = WalletCard(
                program_id=program.id,
                user_id=user_id,
                current_punches=0,
                reward_credits=0,
                status="active",
            )
            session.add(new_pass)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                new_pass = session.query(WalletCard).filter(
                    (WalletCard.program_id == program.id) & (WalletCard.user_id == user_id)
                ).first()
                if new_pass is None:
                    return "failed to create wallet card"
            session.commit()
            return build_pkpass(new_pass, program,merchant)
        else:
            return build_pkpass(wallet_pass,program,merchant)
        
        
def get_user_programs(user_id):
    """
    Get all punch programs with merchant details for a merchant user.
    
    Returns:
        dict: Merchants grouped with their programs
    """
    from app.db import SessionLocal
    from app.models import PunchProgram, Merchant, MerchantUser
    from uuid import UUID
    
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, AttributeError):
        return {}
    
    with SessionLocal() as db:
        merchant_ids = db.query(MerchantUser.merchant_id).filter(
            MerchantUser.user_id == user_uuid
        ).all()
        
        if not merchant_ids:
            return {}
        
        merchant_id_list = [m[0] for m in merchant_ids]
        programs = db.query(PunchProgram).filter(
            PunchProgram.merchant_id.in_(merchant_id_list)
        ).all()
        
        merchants = db.query(Merchant).filter(
            Merchant.id.in_(merchant_id_list)
        ).all()
        
        merchant_lookup = {str(m.id): m for m in merchants}
        
        merchants_dict = {}
        
        for program in programs:
            merchant_id = str(program.merchant_id)
            merchant = merchant_lookup.get(merchant_id)
            active_count = db.scalar(
            select(func.count(WalletCard.id))
            .where(
                WalletCard.program_id == program.id,
                WalletCard.status == "active"
            )
        )
            redemption_count = db.scalar(
            select(func.count(Redemption.id))
            .join(WalletCard, WalletCard.id == Redemption.wallet_card_id)
            .where(WalletCard.program_id == program.id)
            ) or 0
            
            
            if not merchant:
                continue
            
            if merchant_id not in merchants_dict:
                merchants_dict[merchant_id] = {
                    'merchant_info': {
                        'id': merchant_id,
                        'name': merchant.name,
                        'brand_color': merchant.wallet_brand_color,
                        'logo_url': merchant.wallet_logo_url
                    },
                    'programs': []
                }
            
            merchants_dict[merchant_id]['programs'].append({
                'id': str(program.id),
                'name': program.name,
                'punches_required': program.punches_required,
                "active_cards": active_count or 0,
                "total_redepmtions": redemption_count or 0,
                'status': program.active ,
                'created_at': program.created_at.isoformat() if program.created_at else None
            })
        
        return merchants_dict