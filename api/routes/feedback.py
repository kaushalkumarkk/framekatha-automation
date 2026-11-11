from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.feedback import FeedbackInput, ReviewInput, parse_feedback
from api.auth import require_api_key
from core.db import get_db
from core.models import FeedbackReview, Project
from core.models.leads import utcnow
from talent.service import entity

router = APIRouter(tags=["edit feedback"], dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_db)]


@router.post("/projects/{project_id}/feedback", status_code=201)
def feedback(project_id: UUID, payload: FeedbackInput, db: DB):
    entity(db, Project, project_id)
    result = parse_feedback(payload.text)
    review = FeedbackReview(
        project_id=project_id,
        text=payload.text,
        operations=[op.model_dump() for op in result.operations],
    )
    db.add(review)
    db.commit()
    return {
        "review": review,
        "clarification_needed": result.clarification_needed,
        "requires_human_review": True,
        "applied": False,
    }


@router.get("/projects/{project_id}/feedback")
def feedback_history(project_id: UUID, db: DB):
    entity(db, Project, project_id)
    return list(
        db.scalars(
            select(FeedbackReview)
            .where(
                FeedbackReview.project_id == project_id,
            )
            .order_by(FeedbackReview.created_at.desc())
        )
    )


@router.post("/feedback/{review_id}/review")
def review_feedback(review_id: UUID, payload: ReviewInput, db: DB):
    review = db.get(FeedbackReview, review_id, with_for_update=True)
    if review is None:
        raise HTTPException(404, "Feedback review not found")
    if review.status != "pending":
        raise HTTPException(409, "Feedback already reviewed")
    review.status, review.reviewed_by = payload.decision, payload.reviewed_by
    review.reviewed_at = utcnow()
    db.commit()
    return {"review": review, "applied": False}
