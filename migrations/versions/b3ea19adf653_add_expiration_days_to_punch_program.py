"""add expiration days to punch program

Revision ID: b3ea19adf653
Revises: bce6dd91f428
Create Date: 2025-11-27 10:58:41.399804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b3ea19adf653'
down_revision: Union[str, None] = 'bce6dd91f428'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new column
    op.add_column('punch_programs', sa.Column('expiration_extension_days', sa.Integer(), nullable=True))
    
    # Drop old column if it exists
    try:
        op.drop_column('punch_programs', 'expiration_extension_months')
    except:
        pass
    
    # Drop the old index (not constraint)
    try:
        op.drop_index('uq_wallet_cards_user_program', table_name='wallet_cards')
    except:
        pass
    
    # Create the partial unique index (only for active cards)
    op.execute("""
        CREATE UNIQUE INDEX uq_wallet_cards_user_program 
        ON wallet_cards(user_id, program_id) 
        WHERE status = 'active'
    """)


def downgrade() -> None:
    # Drop the partial index
    op.drop_index('uq_wallet_cards_user_program', table_name='wallet_cards')
    
    # Recreate old non-partial index
    op.execute("""
        CREATE UNIQUE INDEX uq_wallet_cards_user_program 
        ON wallet_cards(user_id, program_id)
    """)
    
    # Restore old column
    op.add_column('punch_programs', sa.Column('expiration_extension_months', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_column('punch_programs', 'expiration_extension_days')