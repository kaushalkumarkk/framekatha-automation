from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import require_api_key
from api.schemas.studio import (
    ApprovalInput,
    NegotiateInput,
    ProjectInput,
    SelectionInput,
    TalentInput,
)
from core.config import Settings, get_settings
from core.db import get_db
from core.models import Negotiation, Project, Talent, TalentSelection
from core.models.leads import utcnow
from talent.callsheet import call_sheet_pdf
from talent.service import entity, import_talent, match_talent, negotiate

router = APIRouter(tags=["studio"], dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_db)]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectInput, db: DB):
    project = Project(**payload.model_dump())
    if project.client_email:
        project.client_email = str(project.client_email)
    db.add(project)
    db.commit()
    return project


@router.get("/projects")
def projects(db: DB):
    return list(db.scalars(select(Project).order_by(Project.created_at.desc()).limit(200)))


@router.get("/projects/{project_id}")
def project_detail(project_id: UUID, db: DB):
    return entity(db, Project, project_id)


@router.post("/talent/import")
def add_talent(payload: TalentInput, db: DB, settings: Annotated[Settings, Depends(get_settings)]):
    talent = import_talent(db, payload, settings.default_phone_region)
    db.commit()
    return talent


@router.get("/talent")
def talents(db: DB, database: str | None = None):
    query = select(Talent).order_by(Talent.name).limit(200)
    if database is not None:
        if database not in {"A", "B"}:
            raise HTTPException(422, "database must be A or B")
        query = query.where(Talent.has_portfolio.is_(database == "A"))
    return list(db.scalars(query))


@router.get("/talent/{talent_id}")
def talent_detail(talent_id: UUID, db: DB):
    return entity(db, Talent, talent_id)


@router.post("/talent/{talent_id}/negotiate")
def talent_negotiate(talent_id: UUID, payload: NegotiateInput, db: DB):
    result = negotiate(
        db, entity(db, Talent, talent_id), entity(db, Project, payload.project_id), payload
    )
    db.commit()
    return result


@router.get("/talent/{talent_id}/negotiations")
def negotiations(talent_id: UUID, db: DB):
    entity(db, Talent, talent_id)
    return list(db.scalars(select(Negotiation).where(Negotiation.talent_id == talent_id)))


@router.post("/projects/{project_id}/match")
def match(project_id: UUID, db: DB):
    return {"matches": match_talent(db, entity(db, Project, project_id))}


@router.post("/projects/{project_id}/selections", status_code=201)
def select_talent(project_id: UUID, payload: SelectionInput, db: DB):
    project = db.get(Project, project_id, with_for_update=True)
    if project is None:
        raise HTTPException(404, "Project not found")
    talent = entity(db, Talent, payload.talent_id)
    if talent.currency != project.currency:
        raise HTTPException(409, "Talent and project currencies differ")
    if not project.min_fee <= payload.proposed_fee <= project.max_fee:
        raise HTTPException(422, "Fee is outside project limits")
    if not talent.available or (
        project.shoot_date and project.shoot_date.isoformat() in talent.unavailable_dates
    ):
        raise HTTPException(409, "Talent is unavailable for the shoot")
    existing = db.scalar(
        select(TalentSelection).where(
            TalentSelection.project_id == project_id,
            TalentSelection.talent_id == payload.talent_id,
        )
    )
    if existing:
        raise HTTPException(
            409, "Talent is already selected; approval records cannot be overwritten"
        )
    selection = TalentSelection(project_id=project_id, **payload.model_dump())
    db.add(selection)
    db.commit()
    return selection


@router.get("/projects/{project_id}/selections")
def selections(project_id: UUID, db: DB):
    entity(db, Project, project_id)
    return [
        {"selection": selection, "talent": talent}
        for selection, talent in db.execute(
            select(TalentSelection, Talent)
            .join(Talent)
            .where(TalentSelection.project_id == project_id)
        )
    ]


@router.post("/projects/{project_id}/send-to-client")
def send_to_client(project_id: UUID, db: DB):
    project = db.get(Project, project_id, with_for_update=True)
    if not project:
        raise HTTPException(404, "Project not found")
    rows = list(
        db.execute(
            select(TalentSelection, Talent)
            .join(Talent)
            .where(
                TalentSelection.project_id == project_id,
                TalentSelection.status == "proposed",
            )
        )
    )
    if not rows:
        raise HTTPException(409, "No proposed talent to submit")
    packet = []
    for selection, talent in rows:
        selection.status, selection.sent_at = "sent", utcnow()
        packet.append(
            {
                "selection_id": selection.id,
                "name": talent.name,
                "portfolio_url": talent.portfolio_url,
                "skills": talent.skills,
                "proposed_fee": selection.proposed_fee,
                "currency": project.currency,
            }
        )
    project.status = "awaiting_client"
    db.commit()
    return {
        "project_id": project_id,
        "client_email": project.client_email,
        "talent": packet,
        "action": "n8n_send_client_packet",
        "sent_by_service": False,
    }


@router.post("/projects/{project_id}/client-approval")
def record_approval(project_id: UUID, payload: ApprovalInput, db: DB):
    project = db.get(Project, project_id, with_for_update=True)
    if project is None:
        raise HTTPException(404, "Project not found")
    selection = entity(db, TalentSelection, payload.selection_id)
    if selection.project_id != project_id:
        raise HTTPException(404, "Selection not found for this project")
    if selection.status != "sent":
        raise HTTPException(409, "Only submitted selections can receive a client decision")
    selection.status = payload.decision
    selection.approved_by, selection.approval_note = payload.approved_by, payload.note
    selection.decision_at = utcnow()
    db.flush()
    pending = db.scalar(
        select(TalentSelection.id).where(
            TalentSelection.project_id == project_id,
            TalentSelection.status.in_(["proposed", "sent"]),
        )
    )
    project.status = "awaiting_client" if pending else "casting_reviewed"
    db.commit()
    return selection


@router.get("/projects/{project_id}/call-sheet")
def call_sheet(project_id: UUID, db: DB):
    project = entity(db, Project, project_id)
    approved = list(
        db.execute(
            select(TalentSelection, Talent)
            .join(Talent)
            .where(
                TalentSelection.project_id == project_id,
                TalentSelection.status == "approved",
            )
        )
    )
    if not approved:
        raise HTTPException(
            409, "Client-approved talent is required before generating a call sheet"
        )
    if not all((project.shoot_date, project.location, project.call_time, project.cinematographer)):
        raise HTTPException(422, "Set shoot date, location, call time and cinematographer first")
    return Response(
        call_sheet_pdf(project, approved),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="call-sheet.pdf"'},
    )
