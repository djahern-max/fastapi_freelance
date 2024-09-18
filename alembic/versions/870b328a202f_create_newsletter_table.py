"""Create newsletter table

Revision ID: 870b328a202f
Revises: 2e9d15015d4d
Create Date: 2024-09-18 08:11:23.187297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '870b328a202f'
down_revision: Union[str, None] = '2e9d15015d4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the 'newsletter' table
    op.create_table(
        'newsletter',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    )

def downgrade() -> None:
    # Drop the 'newsletter' table if downgraded
    op.drop_table('newsletter')


