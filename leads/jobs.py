"""RQ entry points. HTTP ingestion is synchronous and does not require Redis."""

import logging
from uuid import uuid4

from redis import Redis
from rq import Queue

from api.schemas.leads import LeadIngest
from core.config import get_settings
from core.db import get_session_factory
from core.logging import configure_logging, request_id_context
from leads.ingestion import run_ingestion


def ingest_job(payload: dict, request_id: str | None = None) -> dict:
    settings = get_settings()
    configure_logging(settings.log_level)
    token = request_id_context.set(request_id or str(uuid4()))
    try:
        data = LeadIngest.model_validate(payload)
        result = run_ingestion(get_session_factory(), data, settings, request_id_context.get())
        return {"lead_id": str(result.lead_id), "outcome": result.outcome}
    finally:
        request_id_context.reset(token)


def enqueue_ingestion(payload: dict) -> str:
    data = LeadIngest.model_validate(payload)
    queue = Queue("leads", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue(
        ingest_job,
        data.model_dump(mode="json"),
        str(uuid4()),
        job_timeout=120,
        result_ttl=3600,
        failure_ttl=604800,
    )
    logging.getLogger(__name__).info("lead_ingestion_queued")
    return job.id
