from importlib.resources import files
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.client import generate_json
from ai.schemas import ScriptDocument, ScriptRequest
from api.auth import require_api_key
from core.db import get_db
from core.models import Project, ScriptVersion
from talent.service import entity

router = APIRouter(tags=["scripts"], dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_db)]


@router.post("/projects/{project_id}/script", status_code=201)
def create_script(project_id: UUID, payload: ScriptRequest, db: DB):
    project = entity(db, Project, project_id)
    brief = payload.model_dump()
    brief["requirement"] = payload.requirement or project.requirement
    brief["project_name"] = project.name
    result = generate_json(
        files("ai").joinpath("prompts/script.v1.txt").read_text(),
        brief,
        ScriptDocument,
        "script_generation",
    )
    runtime = sum(shot.duration_seconds for shot in result.shooting_script)
    if abs(runtime - payload.duration_seconds) > max(3, payload.duration_seconds * 0.15):
        raise HTTPException(422, "Generated script runtime differs from the brief; regenerate")
    db.refresh(project, with_for_update=True)
    version = (
        db.scalar(
            select(func.max(ScriptVersion.version)).where(
                ScriptVersion.project_id == project_id,
            )
        )
        or 0
    ) + 1
    script = ScriptVersion(
        project_id=project_id,
        version=version,
        prompt_version="script.v1",
        brief=brief,
        output=result.model_dump(mode="json"),
    )
    db.add(script)
    db.commit()
    return script


@router.get("/projects/{project_id}/scripts")
def scripts(project_id: UUID, db: DB):
    entity(db, Project, project_id)
    return list(
        db.scalars(
            select(ScriptVersion)
            .where(
                ScriptVersion.project_id == project_id,
            )
            .order_by(ScriptVersion.version.desc())
        )
    )


@router.get("/projects/{project_id}/script")
def latest_script(project_id: UUID, db: DB):
    entity(db, Project, project_id)
    script = db.scalar(
        select(ScriptVersion)
        .where(
            ScriptVersion.project_id == project_id,
        )
        .order_by(ScriptVersion.version.desc())
        .limit(1)
    )
    if script is None:
        raise HTTPException(404, "No script generated for this project")
    return script
