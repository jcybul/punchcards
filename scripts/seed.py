# scripts/seed.py
from __future__ import annotations
import os, uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import engine
from app.models import Merchant, PunchProgram, WalletCard
from dotenv import load_dotenv
load_dotenv()

AUTH_USER_ID = os.getenv("AUTH_USER")

def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except Exception:
        raise SystemExit("❌ AUTH_USER_ID must be a valid UUID from Supabase Auth → Users")

def get_or_create(session: Session, model, defaults: dict | None = None, **lookup):
    """Utility to avoid duplicate inserts when reseeding."""
    inst = session.execute(select(model).filter_by(**lookup)).scalar_one_or_none()
    if inst:
        return inst, False
    params = {**lookup, **(defaults or {})}
    inst = model(**params)
    session.add(inst)
    try:
        session.flush()
        return inst, True
    except IntegrityError:
        session.rollback()
        inst = session.execute(select(model).filter_by(**lookup)).scalar_one()
        return inst, False

def seed():
    if not AUTH_USER_ID:
        raise SystemExit("❌ Set AUTH_USER_ID in your .env (Supabase Auth user UUID).")

    user_id = _uuid(AUTH_USER_ID)

    with Session(engine) as session:
        # Merchant
        merchant, created_m = get_or_create(
            session,
            Merchant,
            contact_email="owner@sample.coffee",
            defaults={
                "name": "Sample Coffee",
                "wallet_brand_color": "#222222",
            },
        )

        # Program
        program, created_p = get_or_create(
            session,
            PunchProgram,
            merchant_id=merchant.id,
            name="Buy 9 get 1",
            defaults={"punches_required": 10, "active": True},
        )

        # WalletCard tied to Supabase Auth user
        card, created_c = get_or_create(
            session,
            WalletCard,
            program_id=program.id,
            user_id=user_id,
            defaults={
                "current_punches": 0,
                "reward_credits": 0,
                "status": "active",
            },
        )

        session.commit()

        print("✅ Seed complete")
        print(f"  merchant_id: {merchant.id} ({'created' if created_m else 'existing'})")
        print(f"  program_id : {program.id} ({'created' if created_p else 'existing'})")
        print(f"  card_id    : {card.id} ({'created' if created_c else 'existing'})")
        print(f"  auth_user  : {user_id}")

if __name__ == "__main__":
    seed()
