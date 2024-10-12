"""Add user_id to Video model

Revision ID: f7abe4c1f84c
Revises: 483e42237fd5
Create Date: 2024-10-12 06:08:27.831077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7abe4c1f84c'
down_revision: Union[str, None] = '483e42237fd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add the column as nullable first
    op.add_column('videos', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Add the foreign key constraint
    op.create_foreign_key(None, 'videos', 'users', ['user_id'], ['id'])
    
    # Here you would update existing rows with a default user_id if needed
    # This is just an example, adjust as necessary for your use case
    op.execute("UPDATE videos SET user_id = (SELECT id FROM users LIMIT 1)")
    
    # Now make the column non-nullable
    op.alter_column('videos', 'user_id', nullable=False)

def downgrade():
    op.drop_constraint(None, 'videos', type_='foreignkey')
    op.drop_column('videos', 'user_id')
