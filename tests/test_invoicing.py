from datetime import timedelta

import pytest
from sqlalchemy import func, select

from core.models import SuspensionNotice
from invoicing.service import studio_today
from tests.test_studio import project


@pytest.mark.parametrize(
    "days,action,milestone",
    [
        (-1, "none", None),
        (0, "none", None),
        (1, "gentle_reminder", 1),
        (4, "gentle_reminder", 1),
        (5, "follow_up", 5),
        (10, "final_reminder", 10),
        (15, "pause_work_and_review_notice", 15),
        (20, "pause_work_and_review_notice", 15),
    ],
)
def test_overdue_milestones(client, days, action, milestone):
    p = project(client)
    response = client.post(
        "/invoices/evaluate",
        json={
            "project_id": p["id"],
            "external_id": "INV-TEST",
            "amount": "25000",
            "due_date": (studio_today() - timedelta(days=days)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["action"] == action and result["milestone"] == milestone
    assert result["work_paused"] == (days >= 15)
    assert not result["sent"]


def test_day15_notice_idempotent_and_never_sent(client, factory):
    p = project(client)
    payload = {
        "project_id": p["id"],
        "external_id": "INV-15",
        "amount": "25000",
        "due_date": (studio_today() - timedelta(days=15)).isoformat(),
    }
    first = client.post("/invoices/evaluate", json=payload).json()
    second = client.post("/invoices/evaluate", json=payload).json()
    assert first["notice"]["id"] == second["notice"]["id"]
    assert first["notice"]["status"] == "draft"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(SuspensionNotice)) == 1
    approved = client.post(
        f"/invoices/notices/{first['notice']['id']}/review",
        json={
            "decision": "approved",
            "reviewed_by": "Studio Owner",
        },
    ).json()
    assert approved["notice"]["status"] == "approved" and not approved["sent"]


def test_payment_requires_manual_resume_and_blocks_unpaid_resume(client):
    p = project(client)
    result = client.post(
        "/invoices/evaluate",
        json={
            "project_id": p["id"],
            "external_id": "INV-15",
            "amount": "25000",
            "due_date": (studio_today() - timedelta(days=15)).isoformat(),
        },
    ).json()
    resume = {"reviewed_by": "Owner", "note": "Payment verified"}
    assert client.post(f"/projects/{p['id']}/resume", json=resume).status_code == 409
    paid = client.patch(
        f"/invoices/{result['invoice']['id']}/status", json={"status": "paid"}
    ).json()
    assert paid["work_paused"] and paid["action"] == "none"
    assert (
        client.post(f"/projects/{p['id']}/resume", json=resume).json()["project"]["work_paused"]
        is False
    )


def test_disputed_invoice_routes_to_human(client):
    p = project(client)
    response = client.post(
        "/invoices/evaluate",
        json={
            "project_id": p["id"],
            "external_id": "INV-DISPUTE",
            "amount": "25000",
            "due_date": (studio_today() - timedelta(days=15)).isoformat(),
            "status": "disputed",
        },
    )
    assert response.json()["action"] == "human_review"
    assert response.json()["notice"] is None
