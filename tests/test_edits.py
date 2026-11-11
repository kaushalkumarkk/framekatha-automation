from tests.test_studio import project, talent


def test_project_and_talent_can_be_edited(client):
    p = project(client)
    update = {
        key: p[key]
        for key in (
            "name",
            "client_name",
            "requirement",
            "required_skills",
            "min_fee",
            "max_fee",
            "currency",
            "shoot_date",
            "location",
            "call_time",
            "cinematographer",
        )
    }
    update["location"] = "Updated studio"
    result = client.put(f"/projects/{p['id']}", json=update)
    assert result.status_code == 200 and result.json()["location"] == "Updated studio"
    t = talent(client)
    result = client.put(
        f"/talent/{t['id']}",
        json={
            "name": t["name"],
            "email": t["email"],
            "skills": t["skills"],
            "fee_rate": "6000",
            "available": False,
        },
    )
    assert result.status_code == 200 and not result.json()["available"]
    assert client.post(f"/projects/{p['id']}/match").json()["matches"] == []


def test_submitted_casting_protects_project_fee_range(client):
    p, t = project(client), talent(client)
    prefix = f"/projects/{p['id']}"
    client.post(prefix + "/selections", json={"talent_id": t["id"], "proposed_fee": "5000"})
    client.post(prefix + "/send-to-client")
    update = {
        key: p[key]
        for key in (
            "name",
            "client_name",
            "requirement",
            "required_skills",
            "min_fee",
            "max_fee",
            "currency",
            "shoot_date",
            "location",
            "call_time",
            "cinematographer",
        )
    }
    update["max_fee"] = "12000"
    assert client.put(prefix, json=update).status_code == 409
