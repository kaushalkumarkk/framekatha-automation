from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from ai.feedback import EditOperation, FeedbackOperations
from resolve.adapter import assemble
from resolve.ingest import FolderIngestor
from resolve.plan import build_plan
from tests.test_scripts import sample_script
from tests.test_studio import project


def test_script_matching_and_unmatched_visual_shots(tmp_path):
    script = sample_script().model_dump()
    script["shooting_script"].append(
        {
            "scene_id": "visual-only",
            "dialogue": "",
            "duration_seconds": 3,
        }
    )
    transcript = {
        "media_path": str(tmp_path / "clip.mov"),
        "segments": [
            {"start": 2, "end": 5, "text": "A new beginning"},
        ],
    }
    plan = build_plan(script, [transcript])
    assert plan["requires_editor_review"]
    assert len(plan["clips"]) == 1
    assert plan["clips"][0]["start_seconds"] == 2
    assert plan["unmatched_shots"][0]["scene_id"] == "visual-only"


def test_ingest_ledger_prevents_reprocessing_and_retries(tmp_path):
    media, output = tmp_path / "media", tmp_path / "output"
    media.mkdir()
    path = media / "clip.mov"
    path.write_bytes(b"fixture")
    transcriber = Mock(return_value={"media_path": str(path), "segments": []})
    worker = FolderIngestor(media, output, stable_seconds=0, transcriber=transcriber)
    assert len(worker.scan()) == 1
    assert worker.scan() == []
    assert transcriber.call_count == 1
    assert len(worker.transcripts()) == 1
    worker.close()
    failing = Mock(side_effect=RuntimeError("transcription failed"))
    path.write_bytes(b"changed fixture")
    worker = FolderIngestor(media, output, stable_seconds=0, transcriber=failing)
    for _ in range(5):
        worker.scan()
    assert failing.call_count == 3
    assert worker.ledger.execute("SELECT status FROM media").fetchone()[0] == "dead_letter"
    worker.close()


def test_resolve_adapter_queues_without_starting_render(tmp_path):
    media = tmp_path / "clip.mov"
    media.write_bytes(b"fixture")
    plan = {
        "kind": "rough_assembly",
        "duration_seconds": 3,
        "clips": [
            {
                "media_path": str(media),
                "start_seconds": 2,
                "end_seconds": 5,
                "record_seconds": 0,
            }
        ],
    }
    resolve = Mock()
    project = resolve.GetProjectManager.return_value.GetCurrentProject.return_value
    pool = project.GetMediaPool.return_value
    timeline = pool.CreateEmptyTimeline.return_value
    timeline.GetStartFrame.return_value = 86400
    pool.ImportMedia.return_value = [Mock()]
    pool.ImportMedia.return_value[0].GetClipProperty.return_value = "24"
    pool.AppendToTimeline.return_value = [Mock()]
    project.AddRenderJob.return_value = "render-id"
    result = assemble(plan, "Rough cut", render_directory=tmp_path / "renders", resolve=resolve)
    clip = pool.AppendToTimeline.call_args.args[0][0]
    assert clip["startFrame"] == 48 and clip["endFrame"] == 119
    assert clip["recordFrame"] == 86400
    assert result["render_job_id"] == "render-id" and not result["render_started"]
    project.StartRendering.assert_not_called()


def test_missing_media_cannot_mutate_resolve():
    resolve = Mock()
    with pytest.raises(ValueError, match="missing"):
        assemble(
            {
                "kind": "rough_assembly",
                "clips": [
                    {
                        "media_path": "/missing/clip.mov",
                        "start_seconds": 0,
                        "end_seconds": 2,
                    }
                ],
            },
            "Missing",
            resolve=resolve,
        )
    resolve.GetProjectManager.assert_not_called()


def test_invalid_trim_rejected():
    with pytest.raises(ValidationError):
        EditOperation(
            operation="trim", scene_id="scene-1", start_seconds=5, end_seconds=2, reason="Invalid"
        )


def test_feedback_is_review_only_even_after_approval(client, monkeypatch):
    p = project(client)
    monkeypatch.setattr(
        "api.routes.feedback.parse_feedback",
        lambda _: FeedbackOperations(
            operations=[
                EditOperation(operation="remove", scene_id="scene-1", reason="Client request")
            ],
        ),
    )
    response = client.post(f"/projects/{p['id']}/feedback", json={"text": "Remove scene-1"})
    assert response.status_code == 201
    result = response.json()
    assert not result["applied"] and result["requires_human_review"]
    review_id = result["review"]["id"]
    approved = client.post(
        f"/feedback/{review_id}/review",
        json={
            "decision": "approved",
            "reviewed_by": "Human Editor",
        },
    )
    assert approved.status_code == 200
    assert not approved.json()["applied"]
    assert approved.json()["review"]["status"] == "approved"


def test_dialogue_matches_consecutive_segments_without_cutting_words(tmp_path):
    script = sample_script().model_dump()
    script["shooting_script"][0].update(
        dialogue="Welcome to our studio a new beginning", duration_seconds=2
    )
    transcript = {
        "media_path": str(tmp_path / "clip.mov"),
        "segments": [
            {"start": 0, "end": 2, "text": "Welcome to our studio"},
            {"start": 2.2, "end": 5, "text": "A new beginning!"},
        ],
    }
    result = build_plan(script, [transcript])
    assert result["clips"][0]["match_score"] == 100
    assert result["clips"][0]["end_seconds"] == 5
    assert result["duration_seconds"] == 5
    assert result["warnings"][0]["scene_id"] == "scene-1"
    # The same dialogue cannot reuse the selected media range in another shot.
    script["shooting_script"].append(script["shooting_script"][0].copy())
    result = build_plan(script, [transcript])
    assert len(result["clips"]) == 1 and len(result["unmatched_shots"]) == 1


def test_matching_does_not_bridge_separate_takes_or_invalid_ranges(tmp_path):
    script = sample_script().model_dump()
    script["shooting_script"][0]["dialogue"] = "Welcome to our studio a new beginning"
    transcript = {
        "media_path": str(tmp_path / "clip.mov"),
        "segments": [
            {"start": 0, "end": 2, "text": "Welcome to our studio"},
            {"start": 8, "end": 10, "text": "A new beginning"},
            {"start": 12, "end": float("inf"), "text": "Welcome to our studio a new beginning"},
        ],
    }
    result = build_plan(script, [transcript], threshold=95)
    assert not result["clips"]
    assert len(result["unmatched_shots"]) == 1
