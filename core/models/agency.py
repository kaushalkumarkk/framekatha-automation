"""Agency operations added from the 2026–2027 blueprint."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.models.leads import JSON_VALUE, utcnow


class ClientProfile(Base):
    __tablename__ = "client_profiles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(300))
    # Explicit client IDs avoid combining brands that happen to share a name.
    onboarding: Mapped[dict] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectClient(Base):
    __tablename__ = "project_clients"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("client_profiles.id"), index=True)


class SalesProfile(Base):
    __tablename__ = "sales_profiles"
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), primary_key=True)
    assigned_to: Mapped[str | None] = mapped_column(String(300))
    industry: Mapped[str | None] = mapped_column(String(300))
    follow_up_start: Mapped[date | None] = mapped_column(Date)
    stopped_reason: Mapped[str | None] = mapped_column(String(30))
    intelligence: Mapped[dict | None] = mapped_column(JSON_VALUE)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgencyDocument(Base):
    __tablename__ = "agency_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "version", name="uq_agency_document_version"),
        CheckConstraint(
            "status IN ('draft','director_approved','approved','rejected')",
            name="ck_agency_document_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    brief: Mapped[dict] = mapped_column(JSON_VALUE)
    output: Mapped[dict] = mapped_column(JSON_VALUE)
    reviews: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductionTracker(Base):
    __tablename__ = "production_trackers"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    details: Mapped[dict] = mapped_column(JSON_VALUE)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectExpense(Base):
    __tablename__ = "project_expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expense_positive"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(1000))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    incurred_on: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    __table_args__ = (
        UniqueConstraint("project_id", "platform", "campaign_id", "day", name="uq_campaign_day"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    platform: Mapped[str] = mapped_column(String(80))
    campaign_id: Mapped[str] = mapped_column(String(200))
    day: Mapped[date] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSON_VALUE)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
