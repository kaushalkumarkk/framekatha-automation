from tests.test_studio import project, talent


def test_frontend_and_assets_are_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Frame Katha" in response.text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/style.css").status_code == 200


def test_browser_session_login_cookie_and_logout(client, settings):
    client.headers.pop("X-API-Key")
    assert client.get("/auth/session").status_code == 401
    assert client.post("/auth/session", json={"api_key": "incorrect"}).status_code == 401
    result = client.post("/auth/session", json={"api_key": settings.api_key.get_secret_value()})
    assert result.status_code == 200
    cookie = result.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert settings.api_key.get_secret_value() not in cookie
    assert client.get("/studio/overview").status_code == 200
    assert (
        client.post(
            "/leads/ingest",
            json={
                "business_name": "Blocked",
                "channel": "manual",
            },
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert client.delete("/auth/session").status_code == 200
    assert client.get("/auth/session").status_code == 401


def test_forged_or_expired_browser_sessions_rejected(client, settings):
    from api.auth import valid_session

    client.headers.pop("X-API-Key")
    client.cookies.set("fk_session", "99999999999.forged.invalid")
    assert client.get("/studio/overview").status_code == 401
    assert not valid_session("bad.token", settings)


def test_overview_uses_real_counts_and_integrations_hide_secrets(client, settings):
    assert client.get("/studio/overview").json()["counts"]["projects"] == 0
    project(client)
    talent(client)
    data = client.get("/studio/overview").json()
    assert data["counts"]["projects"] == 1
    assert data["counts"]["talent"] == 1
    assert len(data["activity"]) == 2
    response = client.get("/studio/integrations")
    assert settings.api_key.get_secret_value() not in response.text
    assert "anthropic" in response.json()
