import json
import logging

from sqlalchemy import func, select

from core.logging import JsonFormatter
from core.models import DeadLetter, OutreachLog


def create(client, **fields):
    response = client.post(
        "/leads/ingest",
        json={
            "business_name": "Frame Katha Studio",
            "channel": "maps",
            **fields,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["lead"]


def test_authentication(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 200
    client.headers.pop("X-API-Key")
    assert client.get("/leads").status_code == 401
    assert client.get("/health/ready").status_code == 401
    client.headers["X-API-Key"] = "incorrect"
    assert client.post("/leads/ingest", json={}).status_code == 401


def test_get_filter_pagination_status_and_audit(client, factory):
    lead = create(client, external_id="a")
    create(client, external_id="b")
    create(client, business_name="Bengal Estates", channel="manual")
    lead_id = lead["id"]
    assert client.get(f"/leads/{lead_id}").json()["id"] == lead_id
    assert client.get("/leads?channel=maps").json()["total"] == 1
    assert client.get("/leads?channel=manual").json()["total"] == 1
    assert client.get("/leads?limit=1").json()["total"] == 2
    assert len(client.get("/leads?limit=1").json()["items"]) == 1
    assert len(client.get("/leads?offset=2").json()["items"]) == 0
    updated = client.patch(f"/leads/{lead_id}/status", json={"status": "qualified"})
    assert updated.json()["status"] == "qualified"
    assert client.get("/leads?status=qualified").json()["total"] == 1
    assert client.patch(f"/leads/{lead_id}/status", json={"status": "invalid"}).status_code == 422
    assert client.get("/leads?limit=101").status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OutreachLog)) == 1


def test_opt_out_remains_set(client):
    lead_id = create(client)["id"]
    response = client.patch(f"/leads/{lead_id}/opt-out", json={"reason": "Unsubscribe"})
    assert response.json()["opted_out"] is True
    assert response.json()["opt_out_reason"] == "Unsubscribe"
    assert create(client, opted_out=False)["opted_out"] is True
    assert client.patch(f"/leads/{lead_id}/opt-out", json={"opted_out": False}).status_code == 422


def test_validation_and_not_found(client):
    assert client.get("/leads/00000000-0000-0000-0000-000000000000").status_code == 404
    assert (
        client.post(
            "/leads/ingest",
            json={
                "business_name": "Test",
                "channel": "manual",
                "phone": "12345",
            },
        ).status_code
        == 422
    )
    response = client.post(
        "/leads/ingest",
        json={
            "business_name": "Test",
            "channel": "manual",
            "email": "private-invalid-email",
        },
    )
    assert response.status_code == 422
    assert "private-invalid-email" not in response.text


def test_conflict_response_and_dead_letter(client, factory):
    create(client, business_name="Lotus Films", phone="9876543210")
    create(client, business_name="Bengal Estates", email="hello@example.com")
    response = client.post(
        "/leads/ingest",
        json={
            "business_name": "Conflicting Business",
            "channel": "manual",
            "phone": "9876543210",
            "email": "hello@example.com",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["action"] == "human_review_required"
    with factory() as session:
        failure = session.scalar(select(DeadLetter))
        assert failure.request_id == response.headers["X-Request-ID"]


def test_structured_logs_redact_input(client, capsys):
    create(client, email="private-contact@example.com", metadata={"secret": "private-secret"})
    output = capsys.readouterr().err
    assert "private-contact" not in output
    assert "private-secret" not in output
    record = logging.LogRecord("test", logging.INFO, "", 0, "lead_ingested", (), None)
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["event"] == "lead_ingested"
    assert "timestamp" in parsed
