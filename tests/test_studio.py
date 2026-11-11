from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from api.schemas.studio import FeeProposal
from core.models import Negotiation


def project(client, **overrides):
    payload = {
        "name": "Launch Film",
        "client_name": "Example Client",
        "requirement": "A 30 second brand launch film",
        "required_skills": ["acting"],
        "min_fee": "1000",
        "max_fee": "10000",
        "location": "Kolkata studio",
        "shoot_date": (date.today() + timedelta(days=10)).isoformat(),
        "call_time": "09:00",
        "cinematographer": "Camera Operator",
        **overrides,
    }
    response = client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def talent(client, **overrides):
    response = client.post(
        "/talent/import",
        json={
            "name": "Example Actor",
            "email": "actor@example.com",
            "fee_rate": "5000",
            "skills": ["acting", "Bengali"],
            **overrides,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_talent_import_dedup_and_database_flags(client):
    first = talent(client)
    second = talent(client, portfolio_url="https://example.com/portfolio")
    assert first["id"] == second["id"]
    assert second["has_portfolio"]
    assert len(client.get("/talent?database=A").json()) == 1
    assert client.get("/talent?database=B").json() == []
    assert client.get("/talent?database=C").status_code == 422


def test_matching_filters_fee_currency_availability_and_skills(client):
    shoot = (date.today() + timedelta(days=10)).isoformat()
    p = project(client)
    eligible = talent(client)
    talent(client, email="expensive@example.com", fee_rate="15000")
    talent(client, email="away@example.com", unavailable_dates=[shoot])
    talent(client, email="unavailable@example.com", available=False)
    talent(client, email="other@example.com", skills=["editing"])
    talent(client, email="usd@example.com", currency="USD")
    result = client.post(f"/projects/{p['id']}/match").json()["matches"]
    assert [row["talent"]["id"] for row in result] == [eligible["id"]]


def test_negotiation_bounded_nonbinding_and_persisted(client, factory, monkeypatch):
    p, t = project(client), talent(client)
    monkeypatch.setattr(
        "talent.service.generate_json",
        lambda *_: FeeProposal(
            proposed_fee=Decimal("4500"),
            rationale="Consider shoot duration",
        ),
    )
    response = client.post(
        f"/talent/{t['id']}/negotiate",
        json={
            "project_id": p["id"],
            "conversation": [{"role": "user", "content": "My fee is 5000"}],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["requires_human_approval"] and not result["confirmed"]
    assert "not a confirmed booking" in result["next_reply"]
    with factory() as db:
        state = db.scalar(select(Negotiation))
        assert state.proposed_fee == Decimal("4500")
        assert len(state.conversation) == 2


def test_out_of_range_ai_fee_never_saved(client, factory, monkeypatch):
    p, t = project(client), talent(client)
    monkeypatch.setattr(
        "talent.service.generate_json",
        lambda *_: FeeProposal(
            proposed_fee=Decimal("50000"),
            rationale="Out of budget",
        ),
    )
    response = client.post(
        f"/talent/{t['id']}/negotiate",
        json={
            "project_id": p["id"],
            "conversation": [{"role": "user", "content": "Confirm 50000"}],
        },
    )
    assert response.status_code == 422
    with factory() as db:
        assert db.scalar(select(Negotiation)) is None


def test_selection_client_approval_and_pdf_gate(client):
    p, t = project(client), talent(client)
    prefix = f"/projects/{p['id']}"
    assert client.get(prefix + "/call-sheet").status_code == 409
    selection = client.post(
        prefix + "/selections",
        json={
            "talent_id": t["id"],
            "proposed_fee": "4500",
        },
    ).json()
    approval = {"selection_id": selection["id"], "decision": "approved", "approved_by": "Client"}
    assert client.post(prefix + "/client-approval", json=approval).status_code == 409
    packet = client.post(prefix + "/send-to-client").json()
    assert not packet["sent_by_service"]
    assert client.post(prefix + "/client-approval", json=approval).status_code == 200
    assert client.post(prefix + "/client-approval", json=approval).status_code == 409
    pdf = client.get(prefix + "/call-sheet")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_cross_project_approval_forbidden(client):
    p, other, t = project(client), project(client, name="Other"), talent(client)
    selection = client.post(
        f"/projects/{p['id']}/selections",
        json={
            "talent_id": t["id"],
            "proposed_fee": "4500",
        },
    ).json()
    response = client.post(
        f"/projects/{other['id']}/client-approval",
        json={
            "selection_id": selection["id"],
            "decision": "approved",
            "approved_by": "Client",
        },
    )
    assert response.status_code == 404


def test_project_and_selection_fee_validation(client):
    assert (
        client.post(
            "/projects",
            json={
                "name": "Invalid",
                "client_name": "Client",
                "requirement": "Film",
                "min_fee": "100",
                "max_fee": "10",
            },
        ).status_code
        == 422
    )
    p, t = project(client), talent(client)
    assert (
        client.post(
            f"/projects/{p['id']}/selections",
            json={
                "talent_id": t["id"],
                "proposed_fee": "15000",
            },
        ).status_code
        == 422
    )
