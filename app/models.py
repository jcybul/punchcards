# app/models.py  (only the changed bits)
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Text, Integer, Boolean, DateTime, Numeric, UniqueConstraint, Date
from sqlalchemy.dialects.postgresql import UUID
from secrets import token_hex
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    wallet_brand_color: Mapped[str] = mapped_column(Text, default="#111111")
    wallet_logo_url: Mapped[str | None] = mapped_column(Text)
    wallet_strip_color: Mapped[str] = mapped_column(Text, default="#6E463A",nullable=True)
    wallet_foreground_color: Mapped[str] = mapped_column(Text, default="#FFFFFF", nullable=True) 

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Location(Base):
    __tablename__ = "locations"
    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PunchProgram(Base):
    __tablename__ = "punch_programs"
    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    punches_required: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_after_days: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    wallet_filled_icon_url: Mapped[str | None] = mapped_column(Text)
    wallet_empty_icon_url: Mapped[str | None] = mapped_column(Text)
    google_program_details: Mapped[str | None] = mapped_column(Text)
    google_terms_conditions: Mapped[str | None] = mapped_column(Text)  
    google_website_url: Mapped[str | None] = mapped_column(Text)      
    google_help_url: Mapped[str | None] = mapped_column(Text) 
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WalletCard(Base):
    __tablename__ = "wallet_cards"
    id: Mapped[uuid.UUID] = uuid_pk()
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("punch_programs.id", ondelete="CASCADE"), nullable=False
    )
    # Supabase Auth user (auth.users.id). No FK across schemas.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    current_punches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    apple_pass_id: Mapped[str | None] = mapped_column(Text)
    google_object_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active", nullable=False)

    # NEW: per-pass auth + update tag (for PassKit web service & caching)
    auth_token: Mapped[str | None] = mapped_column(Text, default=lambda: token_hex(32))
    update_tag: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # enforce one card per (user, program)
        UniqueConstraint("user_id", "program_id", name="uq_wallet_cards_user_program"),
    )
class Punch(Base):
    __tablename__ = "punches"
    id: Mapped[uuid.UUID] = uuid_pk()
    wallet_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Redemption(Base):
    __tablename__ = "redemptions"
    id: Mapped[uuid.UUID] = uuid_pk()
    wallet_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False)
    value_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WalletDeviceReg(Base):
    __tablename__ = "wallet_device_regs"
    id: Mapped[uuid.UUID] = uuid_pk()

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallet_cards.id", ondelete="CASCADE"), nullable=False
    )
    device_library_id: Mapped[str] = mapped_column(Text, nullable=False)  # Apple deviceLibraryIdentifier
    push_token: Mapped[str] = mapped_column(Text, nullable=False)         # APNs device token

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # one registration per (card, device)
        UniqueConstraint("card_id", "device_library_id", name="uq_card_device"),
    )
    
# NEW: profiles (global role for platform-wide admin)
# app/models.py (Profile only)
from sqlalchemy import Text, Date, DateTime

class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    first_name: Mapped[str | None] = mapped_column(Text)
    last_name:  Mapped[str | None] = mapped_column(Text)
    birthdate:  Mapped[datetime | None] = mapped_column(Date)  # or DateTime if you prefer
    platform_role: Mapped[str] = mapped_column(Text, default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# NEW: merchant_users (per-merchant roles)
class MerchantUser(Base):
    __tablename__ = "merchant_users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Supabase Auth user id (auth.users.id). We keep this as a UUID column (no FK to cross schema).
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # 'owner' | 'manager' | 'staff'
    role: Mapped[str] = mapped_column(Text, nullable=False, default="staff")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", name="uq_merchant_user"),
    )