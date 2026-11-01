from tests.factories import auth_headers


def test_get_and_update_profile(client, db):
    _, h = auth_headers(db, client, "asha@example.com", full_name="Asha Rao")
    p = client.get("/api/profile", headers=h).json()
    assert p["full_name"] == "Asha Rao" and p["open_to_remote"] is True

    res = client.put(
        "/api/profile",
        json={
            "full_name": "Asha R",
            "headline": "Backend engineer",
            "current_location": "Pune",
            "preferred_locations": ["Pune", "pune", " Bengaluru "],
            "open_to_remote": False,
            "years_experience": 2.5,
            "phone": "+91 98765 43210",
        },
        headers=h,
    )
    assert res.status_code == 200, res.text
    p = res.json()
    assert p["full_name"] == "Asha R"
    assert p["preferred_locations"] == ["Pune", "Bengaluru"]
    assert p["years_experience"] == 2.5
    assert client.get("/api/auth/me", headers=h).json()["full_name"] == "Asha R"


def test_profile_validation_and_roles(client, db):
    _, h = auth_headers(db, client, "asha@example.com")
    assert client.put("/api/profile", json={"phone": "call me"}, headers=h).status_code == 422
    assert client.put("/api/profile", json={"years_experience": -1}, headers=h).status_code == 422
    assert client.put("/api/profile", json={"phone": ""}, headers=h).json()["phone"] is None
    _, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    assert client.get("/api/profile", headers=rh).status_code == 403
