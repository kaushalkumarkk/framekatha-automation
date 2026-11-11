from unittest.mock import Mock

from api.schemas.leads import LeadIngest
from leads import jobs


def test_enqueue_validates_and_targets_leads_queue(settings, monkeypatch):
    queue = Mock()
    queue.enqueue.return_value.id = "job-id"
    constructor = Mock(return_value=queue)
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    monkeypatch.setattr(jobs, "Queue", constructor)
    result = jobs.enqueue_ingestion({"business_name": "Frame Katha", "channel": "manual"})
    assert result == "job-id"
    assert constructor.call_args.args == ("leads",)
    args = queue.enqueue.call_args.args
    assert args[0] is jobs.ingest_job
    assert LeadIngest.model_validate(args[1]).business_name == "Frame Katha"
    assert queue.enqueue.call_args.kwargs["job_timeout"] == 120


def test_worker_uses_same_ingestion_pipeline(factory, settings, monkeypatch):
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    monkeypatch.setattr(jobs, "get_session_factory", lambda: factory)
    first = jobs.ingest_job({"business_name": "Frame Katha", "channel": "manual"})
    second = jobs.ingest_job({"business_name": "Frame Katha", "channel": "maps"})
    assert first["lead_id"] == second["lead_id"]
    assert second["outcome"] == "merged"
