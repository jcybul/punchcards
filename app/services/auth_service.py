# app/services/auth_service.py
from __future__ import annotations

from datetime import datetime
import os
import functools
from typing import Iterable, Optional

import jwt
from flask import request, g, abort
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.exceptions import NotFound
from app.models import Profile, MerchantUser, WalletCard, PunchProgram, Merchant

# ──────────────────────────────────────────────────────────────────────────────
# Config
# Get this from Supabase: Project Settings → API → JWT Secret
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    # Don't crash import in dev, but fail fast when first used
    pass
# ──────────────────────────────────────────────────────────────────────────────
# Low-level JWT utilities

def _bearer_token() -> Optional[str]:
    """Return the raw Bearer token string or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

def decode_supabase_jwt(token: str) -> Optional[dict]:
    """Decode a Supabase access token (HS256). Returns payload dict or None."""
    if not SUPABASE_JWT_SECRET:
        raise RuntimeError("Missing SUPABASE_JWT_SECRET env var")
    try:
        # Supabase uses HS256; often no aud claim
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.PyJWTError:
        return None


def current_user_id() -> Optional[str]:
    """Extract auth.users.id (UUID as string) from the request Bearer token."""
    tok = _bearer_token()
    if not tok:
        return None
    payload = decode_supabase_jwt(tok)
    return payload.get("sub") if payload else None


def get_user_info(user_id: str) -> dict:
    """
    Get user profile and role information.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        dict with user profile and merchant info (if applicable)
        
    Raises:
        NotFound: If user profile doesn't exist
    """
    with SessionLocal() as db:
        profile = db.get(Profile, user_id)
        
        if not profile:
            raise NotFound(f"User profile {user_id} not found")
        
        # Check if user is staff at any merchant
        merchant_user = db.scalar(
            select(MerchantUser)
            .where(MerchantUser.user_id == user_id)
            .limit(1)
        )
        
        # Build result
        result = {
            "id": str(profile.id),
            "platform_role": profile.platform_role,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "birthdate": profile.birthdate.isoformat() if profile.birthdate else None
        }
        
        # Add merchant info if they're staff
        if merchant_user:
            result["merchant_id"] = str(merchant_user.merchant_id)
            result["merchant_role"] = merchant_user.role
        
        return result

# ──────────────────────────────────────────────────────────────────────────────
# Decorators

def require_auth(fn):
    """Attach g.user_id (auth.users.id) or abort 401."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        uid = current_user_id()
        if not uid:
            abort(401, description="Unauthorized")
        g.user_id = uid
        return fn(*args, **kwargs)
    return wrapper


def require_platform_role(*allowed_roles: str):
    """
    Gate by platform role stored in profiles.platform_role (e.g., 'admin', 'user').
    Usage:
        @require_auth
        @require_platform_role('admin')
        def admin_only(): ...
    """
    if not allowed_roles:
        allowed_roles = ("admin",)

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            uid = getattr(g, "user_id", None)
            if not uid:
                abort(401, description="Unauthorized")
            with Session(engine) as s:
                prof = s.get(Profile, uid)
                role = prof.platform_role if prof else "user"
                if role not in allowed_roles:
                    abort(403, description="Forbidden")
            return fn(*args, **kwargs)
        return wrapper
    return deco


def require_merchant_role(merchant_id: str, allowed: Iterable[str] = ("owner", "manager", "staff")):
    """
    Inline check you can call inside routes to assert the caller has a role
    on a given merchant. Example:

        @bp.post('/programs')
        @require_auth
        def create_program():
            require_merchant_role(merchant_id, allowed=('owner','manager'))
            ...
    """
    uid = getattr(g, "user_id", None)
    if not uid:
        abort(401, description="Unauthorized")
    with Session(engine) as s:
        row = s.execute(
            select(MerchantUser.role).where(
                MerchantUser.merchant_id == merchant_id,
                MerchantUser.user_id == uid,
            )
        ).first()
        
        if not row or row[0] not in tuple(allowed):
            abort(403, description="Forbidden")


def require_card_owner_or_merchant_staff(card_id: str):
    """
    Allow if caller owns the card OR is staff on the card's merchant.
    Use this on read endpoints like GET /cards/:id or history.
    """
    uid = getattr(g, "user_id", None)
    if not uid:
        abort(401, description="Unauthorized")

    with Session(engine) as s:
        # Join card → program → merchant
        q = (
            select(WalletCard.user_id, Merchant.id.label("merchant_id"))
            .join(PunchProgram, PunchProgram.id == WalletCard.program_id)
            .join(Merchant, Merchant.id == PunchProgram.merchant_id)
            .where(WalletCard.id == card_id)
        )
        row = s.execute(q).first()
        if not row:
            abort(404, description="Card not found")

        card_owner_id, merchant_id = row
        if str(card_owner_id) == str(uid):
            return  # owner is allowed

        # else must be staff on that merchant
        staff = s.execute(
            select(MerchantUser.id).where(
                MerchantUser.merchant_id == merchant_id,
                MerchantUser.user_id == uid,
                MerchantUser.role.in_(("staff", "manager", "owner")),
            )
        ).first()
        if not staff:
            abort(403, description="Forbidden")

def verify_cron_token(f):
    @functools.wraps(f)
    def cron_wrapper(*args, **kwargs):
        token = request.headers.get('X-Cron-Token')
        expected_token = os.getenv('CRON_TOKEN')
        if not token or token != expected_token:
            return {'error': 'Unauthorized Missing cron token or token is incorrect'}, 403
        
        return f(*args, **kwargs)
    return cron_wrapper

# ──────────────────────────────────────────────────────────────────────────────
# Convenience helpers for routes

def user_required_merchant_id_from_card(card_id: str) -> str:
    """
    Resolve the merchant_id for a given card (useful to then call require_merchant_role).
    """
    with Session(engine) as s:
        q = (
            select(Merchant.id)
            .join(PunchProgram, PunchProgram.merchant_id == Merchant.id)
            .join(WalletCard, WalletCard.program_id == PunchProgram.id)
            .where(WalletCard.id == card_id)
        )
        row = s.execute(q).first()
        if not row:
            abort(404, description="Card not found")
        return str(row[0])


def update_profile(user_id, first_name, last_name, birth_date=None):
    """Update user profile."""
    with SessionLocal() as db:
        profile = db.query(Profile).get(user_id)
        if profile:
            profile.first_name = first_name
            profile.last_name = last_name
        if birth_date:
            profile.birthdate = datetime.fromisoformat(birth_date)           
            db.commit()
            db.refresh(profile)
        return profile