from rapidfuzz.fuzz import ratio
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from core.models import Lead, LeadIdentity
from leads.normalization import normalize_name

# All ingestion writers take this transaction-level lock BEFORE reading candidates.
# Phase 1 deliberately serializes writes; a larger deployment can partition the lock
# once geography/identity routing has been proven safe.
INGEST_LOCK_ID = 4913710201


class ReviewRequired(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def lock_ingestion(session: Session) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT set_config('lock_timeout', '5s', true)"))
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": INGEST_LOCK_ID})


def exact_matches(session: Session, identities: list[tuple[str, str]]) -> set:
    matches = set()
    for kind, value in identities:
        lead_id = session.scalar(
            select(LeadIdentity.lead_id).where(
                LeadIdentity.kind == kind, LeadIdentity.normalized_value == value
            )
        )
        if lead_id:
            matches.add(lead_id)
    return matches


def fuzzy_match(
    session: Session, name: str, city: str | None, locality: str | None, threshold: float
) -> Lead | None:
    matches = []
    # Stream to avoid materializing the full database. Revisit candidate indexing at scale.
    for lead in session.scalars(select(Lead).execution_options(yield_per=500)):
        if city and lead.city and normalize_name(city) != normalize_name(lead.city):
            continue
        if locality and lead.locality and normalize_name(locality) != normalize_name(lead.locality):
            continue
        if ratio(name, lead.normalized_business_name) >= threshold:
            matches.append(lead)
            if len(matches) > 1:
                raise ReviewRequired("ambiguous_business_name")
    return matches[0] if matches else None
