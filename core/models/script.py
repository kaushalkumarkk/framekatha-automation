from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.models.leads import JSON_VALUE, utcnow


class ClientScriptPattern(Base):
    __tablename__ = "client_script_patterns"
    client_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON_VALUE)


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_project_script_version"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(String(80))
    brief: Mapped[dict] = mapped_column(JSON_VALUE)
    output: Mapped[dict] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
