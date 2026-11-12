"""Saved customer script patterns.

Revision ID: a80b41f729ce
Revises: 6e2c557be08f
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a80b41f729ce"
down_revision = "6e2c557be08f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "client_script_patterns",
        sa.Column("client_key", sa.String(300), primary_key=True),
        sa.Column(
            "settings", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
    )


def downgrade():
    op.drop_table("client_script_patterns")
