from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.feedback import ReviewInput
from api.auth import require_api_key
from api.schemas.leads import Name, StrictInput
from api.schemas.studio import Money
from core.db import get_db
from core.models import Invoice, Project, SuspensionNotice
from core.models.leads import utcnow
from invoicing.service import evaluate, studio_today
from leads.dedup import lock_ingestion
from talent.service import entity

router = APIRouter(tags=["invoicing"], dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_db)]
InvoiceStatus = Literal["unpaid", "paid", "cancelled", "disputed"]


class InvoiceInput(StrictInput):
    project_id: UUID
    external_id: str = Field(min_length=1, max_length=200)
    amount: Money
    due_date: date
    status: InvoiceStatus = "unpaid"


class InvoiceUpdate(StrictInput):
    status: InvoiceStatus


class ResumeInput(StrictInput):
    reviewed_by: Name
    note: str = Field(min_length=1, max_length=2000)


@router.post("/invoices/evaluate")
def evaluate_invoice(payload: InvoiceInput, db: DB):
    # Global identity lock before project lock keeps concurrent external-ID imports safe.
    lock_ingestion(db)
    project = db.get(Project, payload.project_id, with_for_update=True)
    if project is None:
        raise HTTPException(404, "Project not found")
    invoice = db.scalar(select(Invoice).where(Invoice.external_id == payload.external_id))
    if invoice:
        if invoice.status in {"paid", "cancelled"} and payload.status != invoice.status:
            raise HTTPException(409, "A settled invoice cannot be reopened by ingestion")
        if (
            invoice.project_id != payload.project_id
            or invoice.amount != payload.amount
            or invoice.due_date != payload.due_date
        ):
            raise HTTPException(409, "Invoice reference already belongs to different invoice data")
        invoice.status = payload.status
    else:
        invoice = Invoice(
            **payload.model_dump(), client_name=project.client_name, currency=project.currency
        )
        db.add(invoice)
        db.flush()
    result = evaluate(db, invoice, project)
    db.commit()
    return result


@router.get("/invoices")
def invoices(db: DB):
    return list(db.scalars(select(Invoice).order_by(Invoice.created_at.desc()).limit(200)))


@router.post("/invoices/{invoice_id}/evaluate")
def reevaluate(invoice_id: UUID, db: DB):
    invoice = entity(db, Invoice, invoice_id)
    project = db.get(Project, invoice.project_id, with_for_update=True)
    result = evaluate(db, invoice, project)
    db.commit()
    return result


@router.patch("/invoices/{invoice_id}/status")
def invoice_status(invoice_id: UUID, payload: InvoiceUpdate, db: DB):
    invoice = entity(db, Invoice, invoice_id)
    project = db.get(Project, invoice.project_id, with_for_update=True)
    db.refresh(invoice)
    invoice.status = payload.status
    result = evaluate(db, invoice, project)
    db.commit()
    return result


@router.get("/invoices/notices")
def notices(db: DB):
    return list(db.scalars(select(SuspensionNotice).order_by(SuspensionNotice.created_at.desc())))


@router.post("/invoices/notices/{notice_id}/review")
def review_notice(notice_id: UUID, payload: ReviewInput, db: DB):
    notice = db.get(SuspensionNotice, notice_id, with_for_update=True)
    if notice is None:
        raise HTTPException(404, "Notice not found")
    if notice.status != "draft":
        raise HTTPException(409, "Notice already reviewed")
    invoice = entity(db, Invoice, notice.invoice_id)
    if payload.decision == "approved" and invoice.status != "unpaid":
        raise HTTPException(409, "Only an unpaid invoice notice can be approved")
    notice.status, notice.approved_by = payload.decision, payload.reviewed_by
    notice.reviewed_at = utcnow()
    db.commit()
    return {"notice": notice, "sent": False}


@router.post("/projects/{project_id}/resume")
def resume_project(project_id: UUID, payload: ResumeInput, db: DB):
    project = db.get(Project, project_id, with_for_update=True)
    if project is None:
        raise HTTPException(404, "Project not found")
    unresolved = db.scalars(
        select(Invoice).where(
            Invoice.project_id == project_id,
            Invoice.status.in_(["unpaid", "disputed"]),
        )
    )
    if any((studio_today() - invoice.due_date).days >= 15 for invoice in unresolved):
        raise HTTPException(409, "Resolve overdue invoices before resuming work")
    project.work_paused = False
    db.commit()
    return {"project": project, "reviewed_by": payload.reviewed_by, "note": payload.note}
