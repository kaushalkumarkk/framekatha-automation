from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from api.schemas.leads import LeadIngest
from core.models import DeadLetter, Lead, LeadIdentity, LeadSource
from leads.dedup import ReviewRequired
from leads.ingestion import IngestionUnavailable, run_ingestion


def ingest(factory, settings, **fields):
    return run_ingestion(
        factory,
        LeadIngest(
            **{
                "business_name": "Frame Katha Studio",
                "channel": "manual",
                **fields,
            }
        ),
        settings,
        "test-request",
    )


def count(factory, model):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_duplicate_phone_merges_and_preserves_sources(factory, settings):
    first = ingest(factory, settings, phone="9876543210", channel="maps", external_id="a")
    second = ingest(factory, settings, phone="+91 98765 43210", channel="manual")
    assert first.outcome == "created"
    assert second.outcome == "merged"
    assert first.lead_id == second.lead_id
    assert count(factory, Lead) == 1
    assert count(factory, LeadSource) == 2
    assert count(factory, LeadIdentity) == 1


def test_exact_email_case_insensitive(factory, settings):
    first = ingest(factory, settings, email="Hello@Example.com")
    second = ingest(factory, settings, business_name="Renamed Business", email="hello@example.COM")
    assert first.lead_id == second.lead_id


def test_shared_email_domain_does_not_merge(factory, settings):
    first = ingest(factory, settings, email="one@example.com", business_name="Lotus Films")
    second = ingest(factory, settings, email="two@example.com", business_name="Bengal Estates")
    assert first.lead_id != second.lead_id


def test_fuzzy_names_merge(factory, settings):
    first = ingest(factory, settings, business_name="Frame Katha Studios")
    second = ingest(factory, settings, business_name="Frame Katha Studio")
    assert first.lead_id == second.lead_id


def test_threshold_configurable(factory, settings):
    first = ingest(factory, settings, business_name="Frame Katha Studios")
    settings.fuzzy_name_threshold = 100
    second = ingest(factory, settings)
    assert first.lead_id != second.lead_id


def test_location_disambiguates(factory, settings):
    first = ingest(factory, settings, city="Kolkata", locality="Garia")
    second = ingest(factory, settings, city="Kolkata", locality="Newtown")
    assert first.lead_id != second.lead_id


def test_merge_fills_missing_fields_retains_contacts_and_optout(factory, settings):
    first = ingest(
        factory,
        settings,
        email="first@example.com",
        opted_out=True,
        opt_out_reason="Requested removal",
    )
    ingest(
        factory,
        settings,
        email="second@example.com",
        phone="9876543210",
        website="https://example.com",
        city="Kolkata",
    )
    third = ingest(
        factory,
        settings,
        business_name="New Business Name",
        email="second@example.com",
        opted_out=False,
    )
    assert third.lead_id == first.lead_id
    with factory() as session:
        lead = session.get(Lead, first.lead_id)
        assert lead.primary_email == "first@example.com"
        assert lead.primary_phone == "+919876543210"
        assert lead.city == "Kolkata"
        assert lead.website == "https://example.com/"
        assert lead.business_name == "Frame Katha Studio"
        assert lead.opted_out and lead.opted_out_at
        assert lead.opt_out_reason == "Requested removal"
        assert len(lead.identities) == 3


def test_conflicting_identities_rollback_and_dead_letter(factory, settings):
    ingest(factory, settings, phone="9876543210", business_name="Lotus Films")
    ingest(factory, settings, email="hello@example.com", business_name="Bengal Estates")
    with pytest.raises(ReviewRequired, match="conflicting_contact_identities"):
        ingest(factory, settings, phone="9876543210", email="hello@example.com")
    assert count(factory, Lead) == 2
    assert count(factory, LeadSource) == 2
    assert count(factory, DeadLetter) == 1


def test_ambiguous_name_goes_to_review(factory, settings):
    ingest(factory, settings, city="Kolkata", locality="Garia")
    ingest(factory, settings, city="Kolkata", locality="Newtown")
    with pytest.raises(ReviewRequired, match="ambiguous_business_name"):
        ingest(factory, settings)
    assert count(factory, Lead) == 2
    assert count(factory, DeadLetter) == 1


def test_idempotency_and_listing_replay(factory, settings):
    first = ingest(factory, settings, idempotency_key="event-1", external_id="listing-1")
    second = ingest(factory, settings, idempotency_key="event-1", external_id="listing-1")
    assert first.lead_id == second.lead_id
    assert count(factory, LeadSource) == 1
    with factory() as session:
        assert session.scalar(select(LeadSource)).hit_count == 2
    with pytest.raises(ReviewRequired, match="idempotency_payload_mismatch"):
        ingest(
            factory, settings, idempotency_key="event-1", external_id="listing-1", city="Kolkata"
        )


def test_multiple_event_keys_for_same_listing(factory, settings):
    for key in ("event-1", "event-2", "event-2", "event-1"):
        ingest(factory, settings, idempotency_key=key, external_id="listing-1")
    assert count(factory, Lead) == 1
    assert count(factory, LeadSource) == 2


def test_source_repeat_updates_hit_count(factory, settings):
    ingest(factory, settings, external_id="listing-1")
    ingest(factory, settings, external_id="listing-1", city="Kolkata")
    assert count(factory, LeadSource) == 1
    with factory() as session:
        source = session.scalar(select(LeadSource))
        assert source.hit_count == 2
        assert source.raw_payload["city"] == "Kolkata"


def test_transient_failure_retries_then_succeeds(factory, settings, monkeypatch):
    import leads.ingestion as module

    original = module.ingest
    attempts = []

    def flaky(*args):
        attempts.append(True)
        if len(attempts) < 3:
            raise OperationalError("redacted", {}, OSError("test connection failure"))
        return original(*args)

    monkeypatch.setattr(module, "ingest", flaky)
    result = ingest(factory, settings)
    assert result.outcome == "created"
    assert len(attempts) == 3
    assert count(factory, DeadLetter) == 0


def test_exhausted_retries_dead_letter(factory, settings, monkeypatch):
    import leads.ingestion as module

    def fail(*args):
        raise OperationalError("redacted", {}, OSError("test connection failure"))

    monkeypatch.setattr(module, "ingest", fail)
    with pytest.raises(IngestionUnavailable):
        ingest(factory, settings)
    with factory() as session:
        failure = session.scalar(select(DeadLetter))
        assert failure.attempt_count == 3
        assert failure.error_code == "database_failure"
    assert count(factory, Lead) == 0


def test_unexpected_failure_rolls_back_and_dead_letters(factory, settings, monkeypatch):
    import leads.ingestion as module

    def fail(session, *_):
        session.add(Lead(business_name="Unsaved", normalized_business_name="unsaved"))
        session.flush()
        raise RuntimeError("private exception details")

    monkeypatch.setattr(module, "ingest", fail)
    with pytest.raises(IngestionUnavailable):
        ingest(factory, settings)
    assert count(factory, Lead) == 0
    with factory() as session:
        failure = session.scalar(select(DeadLetter))
        assert failure.error_code == "unexpected_failure"
        assert "private" not in failure.error_message


def test_listing_cannot_steal_another_leads_contact(factory, settings):
    ingest(factory, settings, business_name="Lotus Films", external_id="listing-1")
    ingest(factory, settings, business_name="Bengal Estates", phone="9876543210")
    with pytest.raises(ReviewRequired, match="conflicting_contact_identities"):
        ingest(factory, settings, external_id="listing-1", phone="9876543210")
    assert count(factory, Lead) == 2
    assert count(factory, LeadSource) == 2


@pytest.mark.postgres
def test_concurrent_phone_ingestion_creates_one_master(factory, settings, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL concurrency tests")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda number: ingest(
                    factory, settings, phone="9876543210", external_id=str(number)
                ),
                range(12),
            )
        )
    assert len({result.lead_id for result in results}) == 1
    assert count(factory, Lead) == 1
    assert count(factory, LeadSource) == 12


@pytest.mark.postgres
def test_concurrent_fuzzy_ingestion_creates_one_master(factory, settings, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL concurrency tests")
    names = ["Frame Katha Studio", "Frame Katha Studios"] * 6
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda name: ingest(factory, settings, business_name=name), names))
    assert len({result.lead_id for result in results}) == 1
    assert count(factory, Lead) == 1
