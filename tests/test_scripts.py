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


def test_customer_pattern_reused_overridden_and_replaced(client, monkeypatch):
    first = project(client)
    second = project(client, client_name="  EXAMPLE   CLIENT  ")
    other = project(client, client_name="Another client")
    prefix = f"/projects/{first['id']}"
    pattern = {
        "language": "Hindi",
        "duration_seconds": 45,
        "topic": "Salon launch",
        "character_count": 2,
        "shoot_setting": "indoor",
        "pattern_instructions": "Problem, demonstration, then call to action",
        "customer_challenges": "Customers do not know the new service",
        "agreement_notes": "No discount promises",
    }
    assert client.put(prefix + "/script-pattern", json=pattern).status_code == 200
    assert client.get(f"/projects/{second['id']}/script-pattern").json()["topic"] == "Salon launch"
    assert client.get(f"/projects/{other['id']}/script-pattern").json()["topic"] is None
    briefs = []

    def generate(_prompt, brief, *_args):
        briefs.append(brief.copy())
        document = sample_script()
        document.shooting_script[0].duration_seconds = brief["duration_seconds"]
        return document

    monkeypatch.setattr("api.routes.scripts.generate_json", generate)
    result = client.post(prefix + "/script", json={})
    assert result.status_code == 201
    assert briefs[-1]["duration_seconds"] == 45
    assert briefs[-1]["character_count"] == 2
    override = client.post(prefix + "/script", json={"language": "Bengali", "topic": None})
    assert override.status_code == 201
    assert briefs[-1]["language"] == "Bengali" and briefs[-1]["topic"] is None
    assert client.get(prefix + "/script-pattern").json()["language"] == "Hindi"
    assert client.put(prefix + "/script-pattern", json={"topic": "New pattern"}).status_code == 200
    assert client.post(prefix + "/script", json={}).status_code == 201
    assert briefs[-1]["duration_seconds"] == 30
    assert briefs[-1]["pattern_instructions"] is None
    versions = client.get(prefix + "/scripts").json()
    assert versions[-1]["brief"]["topic"] == "Salon launch"
    assert versions[-1]["brief"]["duration_seconds"] == 45


def test_pattern_validation_and_missing_project(client):
    from uuid import uuid4

    prefix = f"/projects/{project(client)['id']}"
    for data in ({"character_count": -1}, {"shoot_setting": "roof"}, {"language": " "}):
        assert client.put(prefix + "/script-pattern", json=data).status_code == 422
    assert client.get(f"/projects/{uuid4()}/script-pattern").status_code == 404


def test_import_script_is_versioned_and_validated_without_ai(client, monkeypatch):
    def unexpected(*_):
        raise AssertionError("Import must not call the provider")

    monkeypatch.setattr("api.routes.scripts.generate_json", unexpected)
    prefix = f"/projects/{project(client)['id']}"
    document = sample_script().model_dump()
    imported = client.post(prefix + "/scripts/import", json=document)
    assert imported.status_code == 201
    assert imported.json()["prompt_version"] == "import.v1"
    assert client.post(prefix + "/scripts/import", json=document).json()["version"] == 2
    document["shooting_script"].append(document["shooting_script"][0].copy())
    assert client.post(prefix + "/scripts/import", json=document).status_code == 422
    assert len(client.get(prefix + "/scripts").json()) == 2
