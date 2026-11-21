"""Client onboarding, sales intelligence, reviews, production and profitability.

Revision ID: c73d91a402bf
Revises: a80b41f729ce
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c73d91a402bf"
down_revision = "a80b41f729ce"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def identity():
    return sa.Column("id", sa.Uuid(), primary_key=True)


def timestamp(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table(
        "client_profiles",
        identity(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("onboarding", JSON, nullable=False),
        timestamp(),
        timestamp("updated_at"),
    )
    op.create_table(
        "project_clients",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("client_profiles.id"), nullable=False),
    )
    op.create_index("ix_project_clients_client_id", "project_clients", ["client_id"])
    op.create_table(
        "sales_profiles",
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("leads.id"), primary_key=True),
        sa.Column("assigned_to", sa.String(300)),
        sa.Column("industry", sa.String(300)),
        sa.Column("follow_up_start", sa.Date()),
        sa.Column("stopped_reason", sa.String(30)),
        sa.Column("intelligence", JSON),
        timestamp("updated_at"),
    )
    op.create_table(
        "agency_documents",
        identity(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("brief", JSON, nullable=False),
        sa.Column("output", JSON, nullable=False),
        sa.Column("reviews", JSON, nullable=False),
        timestamp(),
        sa.UniqueConstraint("project_id", "kind", "version", name="uq_agency_document_version"),
        sa.CheckConstraint(
            "status IN ('draft','director_approved','approved','rejected')",
            name="ck_agency_document_status",
        ),
    )
    op.create_index("ix_agency_documents_project_id", "agency_documents", ["project_id"])
    op.create_table(
        "production_trackers",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("details", JSON, nullable=False),
        timestamp("updated_at"),
    )
    op.create_table(
        "project_expenses",
        identity(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("recorded_by", sa.String(300), nullable=False),
        timestamp(),
        sa.CheckConstraint("amount > 0", name="ck_expense_positive"),
    )
    op.create_index("ix_project_expenses_project_id", "project_expenses", ["project_id"])
    op.create_table(
        "campaign_metrics",
        identity(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("campaign_id", sa.String(200), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metrics", JSON, nullable=False),
        timestamp("updated_at"),
        sa.UniqueConstraint("project_id", "platform", "campaign_id", "day", name="uq_campaign_day"),
    )
    op.create_index("ix_campaign_metrics_project_id", "campaign_metrics", ["project_id"])


def downgrade():
    for table in (
        "campaign_metrics",
        "project_expenses",
        "production_trackers",
        "agency_documents",
        "sales_profiles",
        "project_clients",
        "client_profiles",
    ):
        op.drop_table(table)
