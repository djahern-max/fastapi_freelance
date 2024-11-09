"""add_user_email_and_name

Revision ID: 0cc9fedcbc4c
Revises: d7f7daeefa27
Create Date: 2024-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0cc9fedcbc4c'
down_revision: Union[str, None] = 'd7f7daeefa27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    
    # Create index for email
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Update existing rows with default values
    op.execute("UPDATE users SET email = username || '@example.com', full_name = username WHERE email IS NULL")
    
    # Now make the columns non-nullable
    op.alter_column('users', 'email',
               existing_type=sa.String(),
               nullable=False)
    op.alter_column('users', 'full_name',
               existing_type=sa.String(),
               nullable=False)

def downgrade() -> None:
    # First drop the index
    op.drop_index(op.f('ix_users_email'), table_name='users')
    
    # Then drop the columns
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'email')