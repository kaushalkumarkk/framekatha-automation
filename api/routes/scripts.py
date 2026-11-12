from importlib.resources import files
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.client import generate_json
from ai.schemas import ScriptDocument, ScriptPattern, ScriptRequest
from api.auth import require_api_key
from core.db import get_db
from core.models import ClientScriptPattern, Project, ScriptVersion
from talent.service import entity

router = APIRouter(tags=["scripts"], dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_db)]


def client_key(project: Project) -> str:
    return " ".join(project.client_name.casefold().split())


def pattern_for(db: Session, project: Project) -> ScriptPattern:
    saved = db.get(ClientScriptPattern, client_key(project))
    return ScriptPattern.model_validate(saved.settings if saved else {})


@router.get("/projects/{project_id}/script-pattern")
def script_pattern(project_id: UUID, db: DB):
    project = entity(db, Project, project_id)
    return pattern_for(db, project)


@router.put("/projects/{project_id}/script-pattern")
def save_script_pattern(project_id: UUID, payload: ScriptPattern, db: DB):
    project = entity(db, Project, project_id)
    key = client_key(project)
    saved = db.get(ClientScriptPattern, key)
    if saved is None:
        saved = ClientScriptPattern(client_key=key)
        db.add(saved)
    saved.settings = payload.model_dump(mode="json")
    db.commit()
    return payload


def store_script(db: Session, project: Project, result: ScriptDocument, brief: dict, source: str):
    db.refresh(project, with_for_update=True)
    version = (
        db.scalar(
            select(func.max(ScriptVersion.version)).where(
                ScriptVersion.project_id == project.id,
            )
        )
        or 0
    ) + 1
    script = ScriptVersion(
        project_id=project.id,
        version=version,
        prompt_version=source,
        brief=brief,
        output=result.model_dump(mode="json"),
    )
    db.add(script)
    db.commit()
    return script


@router.post("/projects/{project_id}/scripts/import", status_code=201)
def import_script(project_id: UUID, payload: ScriptDocument, db: DB):
    project = entity(db, Project, project_id)
    return store_script(db, project, payload, {"source": "imported"}, "import.v1")


@router.post("/projects/{project_id}/script", status_code=201)
def create_script(project_id: UUID, payload: ScriptRequest, db: DB):
    project = entity(db, Project, project_id)
    # Only explicit request fields override the saved customer pattern.
    brief = pattern_for(db, project).model_dump()
    brief.update(payload.model_dump(exclude_unset=True))
    brief["requirement"] = payload.requirement or project.requirement
    brief["project_name"] = project.name
    result = generate_json(
        files("ai").joinpath("prompts/script.v1.txt").read_text(),
        brief,
        ScriptDocument,
        "script_generation",
    )
    runtime = sum(shot.duration_seconds for shot in result.shooting_script)
    duration = brief["duration_seconds"]
    if abs(runtime - duration) > max(3, duration * 0.15):
        raise HTTPException(422, "Generated script runtime differs from the brief; regenerate")
    return store_script(db, project, result, brief, "script.v1")


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
