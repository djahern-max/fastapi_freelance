"""make_user_id_nullable

Revision ID: cb318ddec2fc
Revises: <previous_revision_id>
Create Date: <auto_generated_date>
"""

from alembic import op
import sqlalchemy as sa

# These two lines are important!
revision = "cb318ddec2fc"
down_revision = "162e7238f720"  # Update this line to point to the previous head


def upgrade():
    op.alter_column("donations", "user_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("donations", "user_id", existing_type=sa.Integer(), nullable=False)
