"""add project ratings

Revision ID: 926418035ba0
Revises: 8cac531048c6
Create Date: 2025-01-05 16:20:13.252932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '926418035ba0'
down_revision: Union[str, None] = '8cac531048c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
