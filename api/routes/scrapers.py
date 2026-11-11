from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import require_api_key
from core.db import get_db
from core.models import ScraperRun
from scrapers.jobs import queue_run

router = APIRouter(prefix="/scrapers", tags=["scrapers"], dependencies=[Depends(require_api_key)])


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["maps", "magicbricks", "acres99", "radar"]
    scheduled_at: datetime | None = None


@router.post("/runs", status_code=202)
def start_run(payload: RunInput):
    try:
        run_id = queue_run(payload.channel, payload.scheduled_at)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except Exception:
        raise HTTPException(503, "Queue unavailable; inspect scraper run status") from None
    return {"run_id": run_id, "status": "queued"}


@router.get("/runs")
def runs(db: Annotated[Session, Depends(get_db)]):
    return list(db.scalars(select(ScraperRun).order_by(ScraperRun.created_at.desc()).limit(100)))
