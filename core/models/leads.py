import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','qualified','contacted','won','lost','archived')",
            name="ck_lead_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(300))
    normalized_business_name: Mapped[str] = mapped_column(String(300), index=True)
    primary_phone: Mapped[str | None] = mapped_column(String(20))
    primary_email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(2048))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    locality: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="new", server_default="new")
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opt_out_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    identities: Mapped[list["LeadIdentity"]] = relationship(back_populates="lead")
    sources: Mapped[list["LeadSource"]] = relationship(back_populates="lead")


class LeadIdentity(Base):
    __tablename__ = "lead_identities"
    __table_args__ = (
        UniqueConstraint("kind", "normalized_value", name="uq_lead_identity"),
        CheckConstraint("kind IN ('phone','email')", name="ck_identity_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    normalized_value: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lead: Mapped[Lead] = relationship(back_populates="identities")


class LeadSource(Base):
    __tablename__ = "lead_sources"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_source_channel_external"),
        UniqueConstraint("idempotency_key", name="uq_source_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    channel: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    hit_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lead: Mapped[Lead] = relationship(back_populates="sources")


class OutreachLog(Base):
    __tablename__ = "outreach_logs"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound','internal')", name="ck_direction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    channel: Mapped[str] = mapped_column(String(80))
    direction: Mapped[str] = mapped_column(String(12))
    template_id: Mapped[str | None] = mapped_column(String(200))
    provider_message_id: Mapped[str | None] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    __table_args__ = (Index("ix_dead_letter_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    error_code: Mapped[str] = mapped_column(String(80))
    error_message: Mapped[str] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
