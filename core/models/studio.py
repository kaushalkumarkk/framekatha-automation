from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.models.leads import JSON_VALUE, utcnow


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("min_fee >= 0 AND max_fee >= min_fee", name="ck_project_fee_range"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(300))
    client_name: Mapped[str] = mapped_column(String(300))
    client_email: Mapped[str | None] = mapped_column(String(320))
    requirement: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    min_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    max_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    shoot_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(500))
    call_time: Mapped[str | None] = mapped_column(String(5))
    cinematographer: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="planning")
    work_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Talent(Base):
    __tablename__ = "talent"
    __table_args__ = (
        CheckConstraint("fee_rate >= 0 AND followers >= 0", name="ck_talent_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(2048), unique=True)
    has_portfolio: Mapped[bool] = mapped_column(Boolean, default=False)
    skills: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    followers: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    unavailable_dates: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Negotiation(Base):
    __tablename__ = "negotiations"
    __table_args__ = (UniqueConstraint("project_id", "talent_id", name="uq_negotiation_pair"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    talent_id: Mapped[UUID] = mapped_column(ForeignKey("talent.id"), index=True)
    conversation: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    proposed_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default="human_review_required")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TalentSelection(Base):
    __tablename__ = "talent_selections"
    __table_args__ = (UniqueConstraint("project_id", "talent_id", name="uq_selection_pair"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    talent_id: Mapped[UUID] = mapped_column(ForeignKey("talent.id"), index=True)
    proposed_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(300))
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(Text)
