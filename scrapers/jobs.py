import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from redis import Redis
from rq import Queue

from core.config import get_settings
from core.db import get_session_factory
from core.logging import configure_logging, request_id_context
from core.models import DeadLetter, ScraperRun
from core.models.leads import utcnow
from leads.ingestion import run_ingestion
from scrapers.acres99 import Acres99Scraper
from scrapers.base import ScrapingBlocked
from scrapers.magicbricks import MagicBricksScraper
from scrapers.maps import MapsScraper
from scrapers.radar import RadarScraper

SCRAPERS = {
    "maps": MapsScraper,
    "magicbricks": MagicBricksScraper,
    "acres99": Acres99Scraper,
    "radar": RadarScraper,
}
logger = logging.getLogger(__name__)


def execute_run(run_id: str):
    settings = get_settings()
    configure_logging(settings.log_level)
    token = request_id_context.set(str(uuid4()))
    factory = get_session_factory()
    try:
        with factory.begin() as db:
            run = db.get(ScraperRun, UUID(run_id), with_for_update=True)
            if run is None or run.status not in {"queued", "failed"}:
                return
            run.status = "running"
            channel = run.channel
        try:
            config = yaml.safe_load(Path(settings.scraper_config).read_text()) or {}
            rows = SCRAPERS[channel](settings).collect(config)
            ingested, rejected = 0, 0
            for row in rows:
                try:
                    run_ingestion(factory, row, settings, request_id_context.get())
                    ingested += 1
                except Exception:
                    rejected += 1
                    logger.warning("scraper_row_rejected")
            with factory.begin() as db:
                run = db.get(ScraperRun, UUID(run_id))
                run.status = "succeeded" if not rejected else "partial"
                run.ingested, run.rejected = ingested, rejected
                run.finished_at = utcnow()
            logger.info("scraper_completed")
        except Exception as error:
            code = "scraping_blocked" if isinstance(error, ScrapingBlocked) else "scraper_failed"
            with factory.begin() as db:
                run = db.get(ScraperRun, UUID(run_id))
                run.status = "blocked" if isinstance(error, ScrapingBlocked) else "failed"
                run.error_code, run.finished_at = code, utcnow()
                db.add(
                    DeadLetter(
                        job_type="scraper",
                        request_id=request_id_context.get(),
                        payload={"run_id": run_id, "channel": channel},
                        error_code=code,
                        error_message=code,
                        attempt_count=1,
                    )
                )
            logger.warning("scraper_failed", extra={"error_code": code})
            raise
    finally:
        request_id_context.reset(token)


def queue_run(channel: str, scheduled_at: datetime | None = None) -> UUID:
    if channel not in SCRAPERS:
        raise ValueError("Unsupported scraper channel")
    if scheduled_at and (scheduled_at.tzinfo is None or scheduled_at <= datetime.now(UTC)):
        raise ValueError("Schedule must be a future timezone-aware datetime")
    factory = get_session_factory()
    with factory.begin() as db:
        run = ScraperRun(channel=channel, scheduled_at=scheduled_at)
        db.add(run)
        db.flush()
        run_id = run.id
    try:
        queue = Queue("scrapers", connection=Redis.from_url(get_settings().redis_url))
        kwargs = {"job_timeout": 1800, "failure_ttl": 604800, "job_id": str(run_id)}
        if scheduled_at:
            job = queue.enqueue_at(scheduled_at, execute_run, str(run_id), **kwargs)
        else:
            job = queue.enqueue(execute_run, str(run_id), **kwargs)
        with factory.begin() as db:
            db.get(ScraperRun, run_id).job_id = job.id
        return run_id
    except Exception:
        with factory.begin() as db:
            run = db.get(ScraperRun, run_id)
            run.status, run.error_code = "failed", "queue_unavailable"
            db.add(
                DeadLetter(
                    job_type="scraper_queue",
                    request_id=request_id_context.get(),
                    payload={"run_id": str(run_id), "channel": channel},
                    error_code="queue_unavailable",
                    error_message="Redis queue unavailable",
                    attempt_count=1,
                )
            )
        raise
