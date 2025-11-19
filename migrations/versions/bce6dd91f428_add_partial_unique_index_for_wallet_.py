"""add partial unique index for wallet cards

Revision ID: bce6dd91f428
Revises: 414e1a985da3
Create Date: 2025-11-19 10:46:56.858452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bce6dd91f428'
down_revision: Union[str, None] = '414e1a985da3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_wallet_cards_user_program", "wallet_cards", type_="unique")
    
    op.execute("""
        CREATE UNIQUE INDEX uq_wallet_cards_user_program 
        ON wallet_cards(user_id, program_id) 
        WHERE status = 'active'
    """)

def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS uq_wallet_cards_user_program
    """)
    
    op.create_unique_constraint(
        "uq_wallet_cards_user_program",
        "wallet_cards",
        ["user_id", "program_id"]
    )