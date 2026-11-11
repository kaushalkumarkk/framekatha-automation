import secrets
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import require_api_key, session_token
from api.schemas.leads import StrictInput
from core.config import Settings, get_settings
from core.db import get_db
from core.models import (
    DeadLetter,
    FeedbackReview,
    Invoice,
    Lead,
    Project,
    ScraperRun,
    ScriptVersion,
    SuspensionNotice,
    Talent,
    TalentSelection,
)
from core.models.leads import utcnow

router = APIRouter(tags=["workspace"])
DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


class LoginInput(StrictInput):
    api_key: SecretStr


@router.post("/auth/session")
def login(payload: LoginInput, request: Request, response: Response, settings: Config):
    if not secrets.compare_digest(
        payload.api_key.get_secret_value().encode(), settings.api_key.get_secret_value().encode()
    ):
        raise HTTPException(401, "Incorrect studio access key")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin login is not allowed")
    response.set_cookie(
        "fk_session",
        session_token(settings),
        httponly=True,
        samesite="strict",
        secure=settings.app_env == "production",
        max_age=settings.browser_session_hours * 3600,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True}


@router.delete("/auth/session")
def logout(response: Response):
    response.delete_cookie("fk_session")
    return {"authenticated": False}


@router.get("/auth/session", dependencies=[Depends(require_api_key)])
def session_status():
    return {"authenticated": True}


@router.get("/studio/overview", dependencies=[Depends(require_api_key)])
def overview(db: DB):
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions))

    projects = list(db.scalars(select(Project).order_by(Project.created_at.desc()).limit(6)))
    activity = []
    for model, title, category in (
        (Lead, "Lead added", "lead"),
        (Project, "Project created", "project"),
        (Talent, "Talent added", "talent"),
        (ScriptVersion, "Script draft saved", "script"),
    ):
        for row in db.scalars(select(model).order_by(model.created_at.desc()).limit(5)):
            activity.append(
                {
                    "id": str(row.id),
                    "title": title,
                    "name": getattr(row, "business_name", getattr(row, "name", "Draft")),
                    "category": category,
                    "created_at": row.created_at,
                }
            )
    activity.sort(key=lambda item: item["created_at"].replace(tzinfo=UTC), reverse=True)
    return {
        "counts": {
            "leads": count(Lead),
            "projects": count(Project),
            "talent": count(Talent),
            "scripts": count(ScriptVersion),
            "paused": count(Project, Project.work_paused.is_(True)),
            "pending_approvals": count(TalentSelection, TalentSelection.status == "sent")
            + count(FeedbackReview, FeedbackReview.status == "pending")
            + count(SuspensionNotice, SuspensionNotice.status == "draft"),
            "dead_letters": count(DeadLetter, DeadLetter.status == "pending"),
            "unpaid_invoices": count(Invoice, Invoice.status == "unpaid"),
            "scraper_runs": count(ScraperRun),
        },
        "projects": projects,
        "activity": activity[:8],
    }


@router.get("/studio/integrations", dependencies=[Depends(require_api_key)])
def integrations(settings: Config):
    return {
        "anthropic": {
            "configured": bool(settings.anthropic_api_key),
            "model": settings.anthropic_model,
        },
        "news": {"configured": bool(settings.news_api_key)},
        "scrapers": {
            "config_file": settings.scraper_config,
            "delay_seconds": settings.scraper_delay_seconds,
            "proxy_configured": bool(settings.scraper_proxy),
        },
        "resolve": {"mode": "editing_workstation", "requires": "DaVinci Resolve Studio"},
    }


@router.get("/studio/dead-letters", dependencies=[Depends(require_api_key)])
def failures(db: DB):
    return [
        {
            "id": row.id,
            "job_type": row.job_type,
            "request_id": row.request_id,
            "error_code": row.error_code,
            "attempt_count": row.attempt_count,
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in db.scalars(select(DeadLetter).order_by(DeadLetter.created_at.desc()).limit(100))
    ]


@router.post("/studio/dead-letters/{failure_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve_failure(failure_id: str, db: DB):
    from uuid import UUID

    try:
        identity = UUID(failure_id)
    except ValueError:
        raise HTTPException(422, "Invalid failure ID") from None
    failure = db.get(DeadLetter, identity, with_for_update=True)
    if failure is None:
        raise HTTPException(404, "Failure not found")
    failure.status, failure.resolved_at = "resolved", utcnow()
    db.commit()
    return {"id": failure.id, "status": failure.status}
