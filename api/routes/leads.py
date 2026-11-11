import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from api.auth import require_api_key
from api.schemas.leads import (
    Channel,
    IngestResponse,
    LeadIngest,
    LeadPage,
    LeadStatus,
    LeadView,
    OptOutUpdate,
    StatusUpdate,
)
from core.config import Settings, get_settings
from core.db import get_db, get_session_factory
from core.logging import request_id_context
from core.models import Lead, LeadSource, OutreachLog
from core.models.leads import utcnow
from leads.dedup import ReviewRequired
from leads.ingestion import IngestionUnavailable, run_ingestion

router = APIRouter(prefix="/leads", tags=["leads"], dependencies=[Depends(require_api_key)])
logger = logging.getLogger(__name__)
DB = Annotated[Session, Depends(get_db)]


def find_lead(db: Session, lead_id: UUID, *, for_update: bool = False) -> Lead:
    query = select(Lead).where(Lead.id == lead_id)
    if for_update:
        query = query.with_for_update()
    lead = db.scalar(query)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    return lead


@router.post("/ingest", response_model=IngestResponse)
def ingest_lead(
    payload: LeadIngest,
    settings: Annotated[Settings, Depends(get_settings)],
    factory: Annotated[sessionmaker, Depends(get_session_factory)],
) -> IngestResponse:
    try:
        result = run_ingestion(factory, payload, settings, request_id_context.get())
    except ValueError as exc:
        raise HTTPException(422, "Invalid phone number") from exc
    except ReviewRequired as exc:
        raise HTTPException(409, {"code": exc.code, "action": "human_review_required"}) from exc
    except IngestionUnavailable as exc:
        raise HTTPException(
            503, "Ingestion unavailable; retry with the same idempotency key"
        ) from exc
    with factory() as db:
        return IngestResponse(
            outcome=result.outcome, lead=LeadView.model_validate(find_lead(db, result.lead_id))
        )


@router.get("", response_model=LeadPage)
def list_leads(
    db: DB,
    status: LeadStatus | None = None,
    channel: Channel | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LeadPage:
    query = select(Lead)
    if status:
        query = query.where(Lead.status == status)
    if channel:
        query = query.where(Lead.sources.any(LeadSource.channel == channel))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    leads = db.scalars(query.order_by(Lead.created_at.desc(), Lead.id).limit(limit).offset(offset))
    return LeadPage(
        items=[LeadView.model_validate(lead) for lead in leads],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}", response_model=LeadView)
def get_lead(lead_id: UUID, db: DB) -> Lead:
    return find_lead(db, lead_id)


@router.patch("/{lead_id}/status", response_model=LeadView)
def update_status(lead_id: UUID, payload: StatusUpdate, db: DB) -> Lead:
    lead = find_lead(db, lead_id, for_update=True)
    previous = lead.status
    if previous != payload.status:
        lead.status = payload.status
        db.add(
            OutreachLog(
                lead_id=lead_id,
                channel="system",
                direction="internal",
                status="status_changed",
                details={"previous": previous, "current": payload.status},
            )
        )
    db.commit()
    logger.info("lead_status_updated", extra={"lead_id": str(lead_id)})
    return lead


@router.patch("/{lead_id}/opt-out", response_model=LeadView)
def opt_out(lead_id: UUID, payload: OptOutUpdate, db: DB) -> Lead:
    lead = find_lead(db, lead_id, for_update=True)
    if not lead.opted_out:
        lead.opted_out = True
        lead.opted_out_at = utcnow()
        lead.opt_out_reason = payload.reason
        db.add(
            OutreachLog(
                lead_id=lead_id,
                channel="system",
                direction="internal",
                status="opted_out",
            )
        )
    db.commit()
    logger.info("lead_opted_out", extra={"lead_id": str(lead_id)})
    return lead
