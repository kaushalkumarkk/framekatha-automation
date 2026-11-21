from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from api.schemas.agency import QC_ITEMS, BrandStrategy, ContentCalendar, LeadIntelligence
from core.models import AgencyDocument, Invoice, Project
from tests.test_scripts import sample_script
from tests.test_studio import project


def onboard(client, name="Salon Brand"):
    response = client.post(
        "/clients",
        json={
            "name": name,
            "business_category": "Salon",
            "target_audience": "Local residents",
            "business_location": "Kolkata",
            "brand_objectives": ["More bookings"],
            "monthly_budget": "50000",
            "kpis": ["Bookings"],
            "approved_facts": ["Open Sundays"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def lead(client, **kwargs):
    response = client.post(
        "/leads/ingest",
        json={
            "business_name": "A New Salon",
            "channel": "manual",
            **kwargs,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["lead"]


def approve(client, doc_id):
    for stage in ("director", "client"):
        response = client.post(
            f"/agency/documents/{doc_id}/review",
            json={
                "stage": stage,
                "decision": "approved",
                "reviewed_by": f"QA {stage}",
                "note": "Reviewed the complete draft",
            },
        )
        assert response.status_code == 200, response.text


def strategy():
    return BrandStrategy(
        positioning="Local premium salon",
        audience_personas=["Residents"],
        competitor_analysis=["Research needed"],
        usp="Open Sundays",
        content_opportunities=["Reels"],
        marketing_funnel=["Awareness"],
        advertising_strategy="Test locally",
        monthly_objectives=["Bookings"],
        assumptions=["Budget subject to review"],
    )


def test_client_ids_isolate_brand_knowledge_in_scripts(client, monkeypatch):
    first, second = onboard(client), onboard(client)
    assert first["id"] != second["id"]
    p = project(client)
    assert client.put(f"/projects/{p['id']}/client/{first['id']}").status_code == 200
    captured = []

    def generate(_prompt, brief, *_args):
        captured.append(brief)
        return sample_script()

    monkeypatch.setattr("api.routes.scripts.generate_json", generate)
    assert client.post(f"/projects/{p['id']}/script", json={}).status_code == 201
    assert captured[-1]["brand_knowledge"]["approved_facts"] == ["Open Sundays"]
    other = project(client)
    assert client.post(f"/projects/{other['id']}/script", json={}).status_code == 201
    assert "brand_knowledge" not in captured[-1]


@pytest.mark.parametrize(
    "score,classification",
    [
        (0, "low_priority"),
        (39, "low_priority"),
        (40, "potential"),
        (59, "potential"),
        (60, "warm"),
        (79, "warm"),
        (80, "hot"),
        (100, "hot"),
    ],
)
def test_lead_intelligence_thresholds_and_prediction_flag(
    client, monkeypatch, score, classification
):
    record = lead(client)
    monkeypatch.setattr(
        "api.routes.agency.generate_json",
        lambda *_: LeadIntelligence(
            score=score,
            rationale="No website supplied",
            opportunities=["Website"],
            evidence_gaps=["No advertising account data"],
            estimated_monthly_budget="10000",
        ),
    )
    result = client.post(f"/leads/{record['id']}/intelligence").json()
    assert result["profile"]["intelligence"]["classification"] == classification
    assert result["profile"]["intelligence"]["budget_is_prediction"]
    assert result["notification_required"] == (score >= 80)
    assert result["sent"] is False


@pytest.mark.parametrize("stop", ["responded", "declined", "opt_out", "won", "archived"])
def test_followups_stop_after_response_decline_optout_or_closed_status(client, monkeypatch, stop):
    monkeypatch.setattr("api.routes.agency.studio_today", lambda: date(2026, 11, 21))
    record = lead(client)
    url = f"/leads/{record['id']}"
    assert (
        client.put(
            url + "/sales",
            json={"assigned_to": "Sales", "industry": "Salon", "follow_up_start": "2026-11-19"},
        ).status_code
        == 200
    )
    due = client.get("/sales/follow-ups").json()
    assert len(due) == 1 and due[0]["milestone"] == 3
    event = {"event_id": "event-1", "event": stop}
    if stop == "opt_out":
        client.patch(url + "/opt-out", json={"reason": "Unsubscribe"})
    elif stop in {"won", "archived"}:
        client.patch(url + "/status", json={"status": stop})
    else:
        assert client.post(url + "/sales-events", json=event).status_code == 200
        assert client.post(url + "/sales-events", json=event).status_code == 200
        event["note"] = "Changed event"
        assert client.post(url + "/sales-events", json=event).status_code == 409
    assert client.get("/sales/follow-ups").json() == []


def test_scheduler_returns_latest_only_and_suppresses_completed(client, monkeypatch):
    monkeypatch.setattr("api.routes.agency.studio_today", lambda: date(2026, 11, 21))
    record = lead(client)
    url = f"/leads/{record['id']}"
    client.put(url + "/sales", json={"follow_up_start": "2026-11-01"})
    assert [x["milestone"] for x in client.get("/sales/follow-ups").json()] == [14]
    payload = {"event_id": "complete-14", "event": "follow_up_completed", "milestone": 14}
    assert client.post(url + "/sales-events", json=payload).status_code == 200
    assert client.get("/sales/follow-ups").json() == []
    assert (
        client.post(
            url + "/sales-events", json={"event_id": "bad", "event": "responded", "milestone": 1}
        ).status_code
        == 422
    )


def test_document_approval_order_versioning_handoff_and_pause(client, monkeypatch, factory):
    p = project(client)
    brand = onboard(client)
    url = f"/projects/{p['id']}/documents/brand_strategy"
    assert client.post(url, json={}).status_code == 409
    client.put(f"/projects/{p['id']}/client/{brand['id']}")
    monkeypatch.setattr("api.routes.agency.generate_json", lambda *_: strategy())
    doc = client.post(url, json={})
    assert doc.status_code == 201, doc.text
    doc = doc.json()
    review = f"/agency/documents/{doc['id']}/review"
    assert (
        client.post(
            review,
            json={
                "stage": "client",
                "decision": "approved",
                "reviewed_by": "Client",
                "note": "Too early",
            },
        ).status_code
        == 409
    )
    handoff = f"/agency/documents/{doc['id']}/handoff"
    assert client.get(handoff).status_code == 409
    approve(client, doc["id"])
    assert client.get(handoff).json()["sent"] is False
    with factory.begin() as db:
        db.get(Project, UUID(p["id"])).work_paused = True
    assert client.get(handoff).status_code == 409
    newer = client.post(url, json={}).json()
    assert newer["version"] == 2 and newer["status"] == "draft"
    assert client.get(handoff).status_code == 409
    with factory() as db:
        docs = list(db.scalars(select(AgencyDocument).order_by(AgencyDocument.version)))
        assert len(docs[0].reviews) == 2 and not docs[1].reviews


def test_calendar_rejects_wrong_count_date_and_outside_window(client, monkeypatch):
    p, brand = project(client), onboard(client)
    client.put(f"/projects/{p['id']}/client/{brand['id']}")
    url = f"/projects/{p['id']}/documents/content_calendar"
    monkeypatch.setattr(
        "api.routes.agency.generate_json",
        lambda *_: ContentCalendar(
            start_date=date(2026, 12, 1),
            items=[
                {
                    "day": "2026-12-01",
                    "content_type": "Reel",
                    "topic": "Tour",
                    "channel": "Instagram",
                    "objective": "Awareness",
                    "production_notes": "Film",
                }
            ],
        ),
    )
    assert client.post(url, json={"start_date": "2026-12-01"}).status_code == 422
    assert (
        client.post(url, json={"start_date": "2026-12-02", "deliverable_count": 1}).status_code
        == 422
    )
    result = client.post(url, json={"start_date": "2026-12-01", "deliverable_count": 1})
    assert result.status_code == 201 and result.json()["version"] == 1
    with pytest.raises(ValueError):
        ContentCalendar.model_validate(
            {
                "start_date": "2026-12-01",
                "items": [
                    {
                        "day": "2026-12-31",
                        "content_type": "Reel",
                        "topic": "Tour",
                        "channel": "Instagram",
                        "objective": "Awareness",
                        "production_notes": "Film",
                    }
                ],
            }
        )


def test_script_approvals_qc_and_new_script_invalidates_production(client):
    p = project(client)
    prefix = f"/projects/{p['id']}"
    script = client.post(prefix + "/scripts/import", json=sample_script().model_dump()).json()
    assert client.get(prefix + "/production-brief").status_code == 409
    doc = client.post(prefix + f"/scripts/{script['id']}/submit-review").json()
    approve(client, doc["id"])
    assert client.get(prefix + "/production-brief").json()["approved_script_id"] == script["id"]
    assert client.put(prefix + "/production", json={"stage": "ready"}).status_code == 422
    ready = {
        "stage": "ready",
        "backup_primary_verified": True,
        "backup_secondary_verified": True,
        "final_approved_by": "Editor",
        "qc": dict.fromkeys(QC_ITEMS, True),
    }
    assert client.put(prefix + "/production", json=ready).status_code == 200
    client.post(prefix + "/scripts/import", json=sample_script().model_dump())
    assert client.get(prefix + "/production-brief").status_code == 409
    assert client.put(prefix + "/production", json=ready).status_code == 409


def test_expenses_idempotent_profit_calculation_and_currency_separation(client, factory):
    p, usd = project(client), project(client, currency="USD")
    prefix = f"/projects/{p['id']}"
    expense = {
        "external_id": "receipt-1",
        "category": "production",
        "description": "Crew",
        "amount": "1500.50",
        "incurred_on": "2026-11-21",
        "recorded_by": "Accounts",
    }
    first = client.post(prefix + "/expenses", json=expense)
    assert first.status_code == 201, first.text
    assert client.post(prefix + "/expenses", json=expense).json()["id"] == first.json()["id"]
    assert client.post(prefix + "/expenses", json={**expense, "amount": "1600"}).status_code == 409
    assert client.post(f"/projects/{usd['id']}/expenses", json=expense).status_code == 409
    with factory.begin() as db:
        for status, amount in [("paid", "5000"), ("unpaid", "2000"), ("cancelled", "1000")]:
            db.add(
                Invoice(
                    project_id=UUID(p["id"]),
                    external_id=status,
                    client_name="Client",
                    amount=Decimal(amount),
                    currency="INR",
                    due_date=date(2026, 1, 1),
                    status=status,
                )
            )
    report = client.get(prefix + "/profitability").json()
    assert Decimal(report["realized_margin"]) == Decimal("3499.50")
    assert Decimal(report["outstanding"]) == Decimal("2000")
    assert report["overdue_invoices"] == ["unpaid"]
    bi = client.get("/studio/business-intelligence").json()
    assert set(bi["finance_by_currency"]) == {"INR", "USD"}


def test_marketing_upsert_ratios_no_invented_roas_and_zero_denominators(client):
    p = project(client)
    prefix = f"/projects/{p['id']}"
    payload = {
        "platform": "meta",
        "campaign_id": "campaign-1",
        "day": "2026-11-01",
        "metrics": {
            "impressions": 1000,
            "reach": 500,
            "clicks": 50,
            "leads": 10,
            "conversions": 5,
            "spend": "100.00",
        },
    }
    first = client.put(prefix + "/marketing-metrics", json=payload)
    assert first.status_code == 200, first.text
    assert (
        client.put(prefix + "/marketing-metrics", json=payload).json()["id"] == first.json()["id"]
    )
    url = prefix + "/marketing-report?start=2026-11-01&end=2026-11-30"
    report = client.get(url).json()
    assert len(report["records"]) == 1
    assert Decimal(report["ctr_percent"]) == 5
    assert Decimal(report["cpc"]) == 2
    assert Decimal(report["cost_per_lead"]) == 10
    assert report["roas"] is None
    payload["metrics"]["attributed_revenue"] = "500"
    client.put(prefix + "/marketing-metrics", json=payload)
    assert Decimal(client.get(url).json()["roas"]) == 5
    report = client.get(prefix + "/marketing-report?start=2026-12-01&end=2026-12-30").json()
    assert report["roas"] is None and report["ctr_percent"] is None
    assert (
        client.get(prefix + "/marketing-report?start=2026-12-30&end=2026-12-01").status_code == 422
    )


def test_agency_routes_require_auth(client):
    client.headers.clear()
    for path in ("/clients", "/sales/follow-ups", "/studio/business-intelligence"):
        assert client.get(path).status_code == 401


def test_human_document_import_validates_and_starts_fresh_review(client):
    p = project(client)
    url = f"/projects/{p['id']}/documents/brand_strategy/import"
    first = client.post(url, json={"output": strategy().model_dump()})
    assert first.status_code == 201
    approve(client, first.json()["id"])
    second = client.post(url, json={"output": strategy().model_dump()}).json()
    assert second["version"] == 2 and second["status"] == "draft"
    assert client.post(url, json={"output": {"unexpected": "field"}}).status_code == 422
    assert client.get("/studio/business-intelligence").json()["pending_document_reviews"] == 1


def test_outreach_draft_review_and_optout_gate(client, monkeypatch):
    from api.schemas.agency import OutreachDraft

    record = lead(client)
    prefix = f"/leads/{record['id']}"
    monkeypatch.setattr(
        "api.routes.agency.generate_json",
        lambda *_: OutreachDraft(
            subject="Salon reel ideas",
            message="May we share a portfolio?",
            proposed_services=["Reel production"],
            claims_to_verify=[],
        ),
    )
    first = client.post(prefix + "/outreach-draft")
    assert first.status_code == 201
    draft = first.json()
    assert draft["direction"] == "internal" and draft["details"]["sent"] is False
    review = prefix + f"/outreach/{draft['id']}/review"
    payload = {
        "stage": "director",
        "decision": "approved",
        "reviewed_by": "Sales head",
        "note": "Checked the proposal",
    }
    assert client.post(review, json=payload).json()["status"] == "outreach_approved"
    assert client.post(review, json=payload).status_code == 409
    second = client.post(prefix + "/outreach-draft").json()
    client.patch(prefix + "/opt-out", json={})
    assert client.post(prefix + "/outreach-draft").status_code == 409
    assert client.post(prefix + f"/outreach/{second['id']}/review", json=payload).status_code == 409


def test_monthly_report_requires_period_and_uses_recorded_metrics(client, monkeypatch):
    from api.schemas.agency import MonthlyReport

    p = project(client)
    captured = []

    def generate(_prompt, brief, *_args):
        captured.append(brief)
        return MonthlyReport(
            summary="No data",
            content_published="Not available",
            reach_and_engagement="Not available",
            ad_performance="Not available",
            leads_generated="Not available",
            campaign_insights=[],
            next_month_recommendations=["Import data"],
            missing_data=["Campaign metrics"],
        )

    monkeypatch.setattr("api.routes.agency.generate_json", generate)
    url = f"/projects/{p['id']}/documents/monthly_report"
    assert client.post(url, json={}).status_code == 422
    result = client.post(url, json={"start_date": "2026-11-01", "end_date": "2026-11-30"})
    assert result.status_code == 201
    assert captured[0]["performance"]["records"] == []
    assert result.json()["status"] == "draft"


def test_recorded_financial_data_prevents_currency_change(client):
    p = project(client)
    prefix = f"/projects/{p['id']}"
    client.post(
        prefix + "/expenses",
        json={
            "external_id": "cost-1",
            "category": "production",
            "description": "Rental",
            "amount": "10",
            "incurred_on": "2026-11-21",
            "recorded_by": "Accounts",
        },
    )
    # ProjectInput does not accept database-generated/read-only fields.
    from api.schemas.studio import ProjectInput

    payload = {key: value for key, value in p.items() if key in ProjectInput.model_fields}
    payload["currency"] = "USD"
    assert client.put(prefix, json=payload).status_code == 409
