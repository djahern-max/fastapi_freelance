"""project_showcase_update

Revision ID: 8cac531048c6
Revises: 4a3964a61154
Create Date: 2025-01-05 15:51:17.982047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8cac531048c6'
down_revision: Union[str, None] = '4a3964a61154'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
