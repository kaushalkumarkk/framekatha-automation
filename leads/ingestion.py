import hashlib
import json
import logging
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from api.schemas.leads import LeadIngest
from core.config import Settings
from core.models import DeadLetter, Lead, LeadIdentity, LeadSource
from core.models.leads import utcnow
from leads.dedup import ReviewRequired, exact_matches, fuzzy_match, lock_ingestion
from leads.normalization import normalize_email, normalize_name, normalize_phone

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    lead_id: UUID
    outcome: str


class IngestionUnavailable(Exception):
    pass


def ingest(session: Session, payload: LeadIngest, settings: Settings) -> IngestResult:
    """Caller owns the transaction. All candidate reads happen after acquiring the lock."""
    identities = []
    if payload.phone:
        identities.append(("phone", normalize_phone(payload.phone, settings.default_phone_region)))
    if payload.email:
        identities.append(("email", normalize_email(str(payload.email))))
    raw = payload.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    lock_ingestion(session)

    by_key = None
    by_external = None
    if payload.idempotency_key:
        by_key = session.scalar(
            select(LeadSource).where(LeadSource.idempotency_key == payload.idempotency_key)
        )
        if by_key and by_key.request_hash != digest:
            raise ReviewRequired("idempotency_payload_mismatch")
    if payload.external_id:
        by_external = session.scalar(
            select(LeadSource).where(
                LeadSource.channel == payload.channel, LeadSource.external_id == payload.external_id
            )
        )
    if by_key and by_external and by_key.lead_id != by_external.lead_id:
        raise ReviewRequired("source_reference_conflict")
    source = by_key or by_external
    matches = exact_matches(session, identities)
    if source:
        matches.add(source.lead_id)
    if len(matches) > 1:
        raise ReviewRequired("conflicting_contact_identities")

    lead = (
        session.get(Lead, next(iter(matches)))
        if matches
        else fuzzy_match(
            session,
            normalize_name(payload.business_name),
            payload.city,
            payload.locality,
            settings.fuzzy_name_threshold,
        )
    )
    outcome = "merged" if lead else "created"
    if lead is None:
        lead = Lead(
            business_name=payload.business_name,
            normalized_business_name=normalize_name(payload.business_name),
        )
        session.add(lead)
        session.flush()

    # Existing primary values win; alternate contacts are retained as identities.
    values = {
        "primary_phone": next((v for k, v in identities if k == "phone"), None),
        "primary_email": next((v for k, v in identities if k == "email"), None),
        "website": str(payload.website) if payload.website else None,
        "city": payload.city,
        "locality": payload.locality,
    }
    for field, value in values.items():
        if value and not getattr(lead, field):
            setattr(lead, field, value)
    if payload.opted_out:
        lead.opted_out = True
        lead.opted_out_at = lead.opted_out_at or utcnow()
        lead.opt_out_reason = lead.opt_out_reason or payload.opt_out_reason
    lead.updated_at = utcnow()

    existing = {(identity.kind, identity.normalized_value) for identity in lead.identities}
    for kind, value in identities:
        if (kind, value) not in existing:
            session.add(LeadIdentity(lead_id=lead.id, kind=kind, normalized_value=value))

    if source:
        # A source's first idempotency key remains immutable. Subsequent event keys
        # get their own source reference to retain replay protection for every key.
        if payload.idempotency_key and source.idempotency_key != payload.idempotency_key:
            source = None
        else:
            source.last_seen_at = utcnow()
            source.hit_count += 1
            if not payload.idempotency_key:
                source.raw_payload = raw
                source.source_url = (
                    str(payload.source_url) if payload.source_url else source.source_url
                )
    if source is None:
        # The same listing can have multiple event references, but its unique
        # channel/external reference stays on the original row.
        session.add(
            LeadSource(
                lead_id=lead.id,
                channel=payload.channel,
                external_id=payload.external_id if by_external is None else None,
                source_url=str(payload.source_url) if payload.source_url else None,
                idempotency_key=payload.idempotency_key,
                request_hash=digest,
                raw_payload=raw,
            )
        )
    session.flush()
    return IngestResult(lead.id, outcome)


def persist_dead_letter(
    factory: sessionmaker, payload: LeadIngest, request_id: str, code: str, attempts: int
) -> None:
    with factory.begin() as session:
        session.add(
            DeadLetter(
                job_type="lead_ingest",
                request_id=request_id,
                payload=payload.model_dump(mode="json"),
                error_code=code,
                error_message=code,
                attempt_count=attempts,
            )
        )
    logger.warning("ingestion_dead_lettered", extra={"error_code": code})


def transient_database_error(error: DBAPIError) -> bool:
    sqlstate = getattr(error.orig, "sqlstate", None)
    return bool(
        error.connection_invalidated
        or sqlstate in {"40001", "40P01", "55P03"}
        or (sqlstate and sqlstate.startswith("08"))
    )


def run_ingestion(
    factory: sessionmaker, payload: LeadIngest, settings: Settings, request_id: str
) -> IngestResult:
    for attempt in range(1, settings.ingest_max_attempts + 1):
        try:
            with factory.begin() as session:
                result = ingest(session, payload, settings)
            logger.info(
                "lead_ingested",
                extra={
                    "lead_id": str(result.lead_id),
                    "outcome": result.outcome,
                },
            )
            return result
        except ReviewRequired as exc:
            try:
                persist_dead_letter(factory, payload, request_id, exc.code, attempt)
            except DBAPIError as storage_error:
                logger.error("dead_letter_storage_unavailable")
                raise IngestionUnavailable from storage_error
            raise
        except DBAPIError as exc:
            # Connection establishment errors may have no SQLSTATE.
            retryable = transient_database_error(exc) or (
                isinstance(exc, OperationalError) and not getattr(exc.orig, "sqlstate", None)
            )
            logger.warning("ingestion_database_failure", extra={"attempt": attempt})
            if retryable and attempt < settings.ingest_max_attempts:
                time.sleep(settings.retry_base_seconds * 2 ** (attempt - 1))
                continue
            try:
                persist_dead_letter(factory, payload, request_id, "database_failure", attempt)
            except DBAPIError:
                # An unavailable database cannot durably store a dead letter.
                logger.error("dead_letter_storage_unavailable")
            raise IngestionUnavailable from exc
        except ValueError:
            # Invalid phone input belongs to the API's 422 validation path.
            raise
        except Exception as exc:
            logger.error("ingestion_unexpected_failure")
            try:
                persist_dead_letter(factory, payload, request_id, "unexpected_failure", attempt)
            except DBAPIError:
                logger.error("dead_letter_storage_unavailable")
            raise IngestionUnavailable from exc
    raise IngestionUnavailable  # pragma: no cover
