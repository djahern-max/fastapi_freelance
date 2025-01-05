"""add project ratingsV2

Revision ID: 923ce3d1becb
Revises: 926418035ba0
Create Date: 2025-01-05 16:23:38.634687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '923ce3d1becb'
down_revision: Union[str, None] = '926418035ba0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
