"""add_donations_table

Revision ID: 162e7238f720
Revises: 487913ada978
Create Date: [auto-generated date]

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "162e7238f720"
down_revision = "487913ada978"
branch_labels = None
depends_on = None


def upgrade():
    # Only create the donations table
    op.create_table(
        "donations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("stripe_session_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="check_positive_amount"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_session_id"),
    )
    op.create_index(op.f("ix_donations_id"), "donations", ["id"], unique=False)


def downgrade():
    # Only drop the donations table
    op.drop_index(op.f("ix_donations_id"), table_name="donations")
    op.drop_table("donations")
