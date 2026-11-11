from decimal import Decimal

import httpx

from ai.schemas import ScriptDocument
from tests.test_studio import project


def sample_script():
    return ScriptDocument.model_validate(
        {
            "title": "A New Beginning",
            "shooting_script": [
                {
                    "scene_id": "scene-1",
                    "shot_number": 1,
                    "duration_seconds": 30,
                    "visual": "The studio opens at dawn",
                    "dialogue": "A new beginning",
                    "camera": "Slow dolly",
                    "audio": "Room tone",
                }
            ],
            "screenplay": "INT. STUDIO - DAWN",
            "editing_direction": ["Cut on the final word"],
            "bgm_suggestions": [
                {
                    "mood": "Hopeful",
                    "tempo_bpm": 90,
                    "instrumentation": "Piano",
                    "licensing_note": "Choose a licensed track",
                }
            ],
        }
    )


def test_generated_script_versions_saved(client, monkeypatch):
    p = project(client)
    monkeypatch.setattr("api.routes.scripts.generate_json", lambda *_: sample_script())
    url = f"/projects/{p['id']}/script"
    first = client.post(url, json={})
    second = client.post(url, json={"language": "Bengali"})
    assert first.status_code == second.status_code == 201
    assert first.json()["version"] == 1 and second.json()["version"] == 2
    assert first.json()["prompt_version"] == "script.v1"
    assert client.get(url).json()["version"] == 2
    assert len(client.get(f"/projects/{p['id']}/scripts").json()) == 2


def test_wrong_runtime_not_saved(client, monkeypatch):
    p = project(client)
    monkeypatch.setattr("api.routes.scripts.generate_json", lambda *_: sample_script())
    assert (
        client.post(f"/projects/{p['id']}/script", json={"duration_seconds": 90}).status_code == 422
    )
    assert client.get(f"/projects/{p['id']}/scripts").json() == []


def test_missing_anthropic_key_is_explicit(client, monkeypatch, settings):
    p = project(client)
    monkeypatch.setattr(
        "ai.client.get_settings",
        lambda: settings.model_copy(
            update={"anthropic_api_key": None},
        ),
    )
    response = client.post(f"/projects/{p['id']}/script", json={})
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_anthropic_forced_tool_response_validated(settings, monkeypatch):
    from pydantic import SecretStr

    from ai import client as module
    from api.schemas.studio import FeeProposal

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: settings.model_copy(
            update={
                "anthropic_api_key": SecretStr("test-provider-key"),
            }
        ),
    )
    original = httpx.Client

    def respond(request):
        import json

        body = json.loads(request.content)
        assert body["tool_choice"]["name"] == "submit_result"
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "name": "submit_result",
                        "input": {"proposed_fee": "2000", "rationale": "Test proposal"},
                    }
                ]
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kw: original(
            transport=httpx.MockTransport(respond),
            **kw,
        ),
    )
    result = module.generate_json("Propose fee", {}, FeeProposal, "test")
    assert result.proposed_fee == Decimal("2000")
