from datetime import datetime, timedelta, timezone


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_and_stations(client):
    meta = client.get("/api/air/meta").json()
    assert meta["data_mode"] == "simulated"
    assert len(meta["categories"]) == 6
    st = client.get("/api/air/stations").json()["stations"]
    assert len(st) >= 20 and all(0 <= s["aqi"] <= 500 for s in st)
    assert len(st[0]["next_24h"]) == 24


def test_point_forecast_has_bands(client):
    p = client.get("/api/air/point", params={"lat": 12.95, "lon": 77.6}).json()
    assert p["coverage"] in ("good", "fair")
    assert len(p["hours"]) == 24
    assert all(h["low"] <= h["aqi"] <= h["high"] for h in p["hours"])


def test_far_point_is_flagged(client):
    p = client.get("/api/air/point", params={"lat": 22.0, "lon": 80.0}).json()
    assert p["coverage"] == "outside"


def test_grid_masks_unknown_area(client):
    g = client.get("/api/air/grid", params={"south": 12.0, "west": 75.0, "north": 13.5, "east": 76.5}).json()
    flat = [v for row in g["values"] for v in row]
    assert None in flat


def test_register_duplicate(client, auth):
    r = client.post("/api/auth/register", json={"email": "ASHA@example.com", "name": "x", "password": "longenough1"})
    assert r.status_code == 409


def test_login_wrong_password(client, auth):
    r = client.post("/api/auth/token", data={"username": "asha@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_profile_threshold(client, auth):
    me = client.get("/api/me", headers=auth).json()
    assert me["threshold"] == 100
    me = client.patch("/api/me", headers=auth, json={"custom_threshold": 140}).json()
    assert me["threshold"] == 140
    me = client.patch("/api/me", headers=auth, json={"clear_custom_threshold": True}).json()
    assert me["threshold"] == 100


def test_location_requires_consent(client, auth):
    r = client.post("/api/me/location", headers=auth, json={"lat": 12.93, "lon": 77.62}).json()
    assert r["stored"] is False
    client.patch("/api/me", headers=auth, json={"location_consent": True})
    r = client.post("/api/me/location", headers=auth, json={"lat": 12.93, "lon": 77.62}).json()
    assert r["stored"] is True and r["aqi"] is not None
    ex = client.get("/api/me/exposure", headers=auth).json()
    assert ex["pings"] == 1


def test_withdrawing_consent_deletes_history(client, auth):
    client.patch("/api/me", headers=auth, json={"location_consent": True})
    client.post("/api/me/location", headers=auth, json={"lat": 12.93, "lon": 77.62})
    client.patch("/api/me", headers=auth, json={"location_consent": False})
    client.patch("/api/me", headers=auth, json={"location_consent": True})
    assert client.get("/api/me/exposure", headers=auth).json()["pings"] == 0


def _trip_body(**kw):
    dep = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    body = {"origin": {"name": "Koramangala", "lat": 12.9352, "lon": 77.6245},
            "destination": {"name": "Hebbal", "lat": 13.0294, "lon": 77.5859},
            "depart_at": dep, "mode": "two_wheeler"}
    body.update(kw)
    return body


def test_assess_trip(client, auth):
    a = client.post("/api/trips/assess", headers=auth, json=_trip_body()).json()
    assert a["approximate_geometry"] is True
    assert len(a["routes"]) == 3
    assert sum(r["is_cleanest"] for r in a["routes"]) == 1
    assert a["departure_scan"]
    for r in a["routes"]:
        assert r["dose_ug"] > 0 and r["strip"]
    assert a["verdict"] in ("go", "caution", "reconsider")


def test_car_dose_lower_than_cycling(client, auth):
    car = client.post("/api/trips/assess", headers=auth, json=_trip_body(mode="driving")).json()
    cyc = client.post("/api/trips/assess", headers=auth, json=_trip_body(mode="cycling")).json()
    best = lambda a: min(r["dose_ug"] for r in a["routes"])
    assert best(car) < best(cyc)


def test_bad_mode_rejected(client, auth):
    assert client.post("/api/trips/assess", headers=auth, json=_trip_body(mode="teleport")).status_code == 422


def test_trip_crud_and_alert_check(client, auth):
    r = client.post("/api/trips", headers=auth, json=_trip_body(label="Gym", repeat_weekdays=[0, 2, 4]))
    assert r.status_code == 201
    tid = r.json()["id"]
    assert any(t["id"] == tid for t in client.get("/api/trips", headers=auth).json())
    client.post("/api/alerts/check-now", headers=auth)
    alerts = client.get("/api/alerts", headers=auth).json()
    assert "unread" in alerts
    assert client.delete(f"/api/trips/{tid}", headers=auth).status_code == 204


def test_alert_fires_above_threshold(client, auth):
    client.patch("/api/me", headers=auth, json={"location_consent": True, "custom_threshold": 50})
    client.post("/api/me/location", headers=auth, json={"lat": 12.9172, "lon": 77.6229})
    created = client.post("/api/alerts/check-now", headers=auth).json()["created"]
    assert any(a["kind"] == "location_breach" for a in created)
    # Cooldown: the same place does not alert twice in a row.
    again = client.post("/api/alerts/check-now", headers=auth).json()["created"]
    assert not any(a["kind"] == "location_breach" for a in again)
    client.patch("/api/me", headers=auth, json={"clear_custom_threshold": True})


def test_places_offline(client):
    res = client.get("/api/air/places", params={"q": "silk board"}).json()
    assert res and res[0]["source"] == "offline"


def test_here_gives_personal_advice(client, auth):
    r = client.get("/api/me/here", headers=auth, params={"lat": 12.95, "lon": 77.6}).json()
    adv = r["advice"]
    assert adv["threshold"] == 100
    assert adv["level"] in ("ok", "caution", "avoid")
    assert adv["cleanest_hour"]["aqi"] <= max(h["aqi"] for h in r["hours"][:12])


def test_here_has_insights(client, auth):
    r = client.get("/api/me/here", headers=auth, params={"lat": 12.95, "lon": 77.6}).json()
    assert r["budget"]["budget_ug"] == 270
    assert r["home"]["windows"]["action"] in ("open", "brief", "closed")
    assert r["explain"]["trend"] in ("up", "down", "flat")


def test_language_switch_translates_advice(client, auth):
    assert client.patch("/api/me", headers=auth, json={"language": "kn"}).json()["language"] == "kn"
    r = client.get("/api/me/here", headers=auth, params={"lat": 12.95, "lon": 77.6}).json()
    assert "ಗಾಳಿ" in r["advice"]["headline"]
    assert client.patch("/api/me", headers=auth, json={"language": "xx"}).status_code == 422
    client.patch("/api/me", headers=auth, json={"language": "en"})


def test_daily_brief_in_hindi(client, auth):
    client.patch("/api/me", headers=auth, json={"language": "hi", "home_lat": 12.93, "home_lon": 77.62})
    created = client.post("/api/alerts/brief-now", headers=auth).json()["created"]
    assert created and created[0]["kind"] == "daily_brief"
    assert "आज की हवा" in created[0]["title"] and "सिगरेट" in created[0]["body"]
    client.patch("/api/me", headers=auth, json={"language": "en"})


def test_one_time_trip_alert_check_does_not_crash(client, auth):
    r = client.post("/api/trips", headers=auth, json=_trip_body(label="Once"))
    assert r.status_code == 201
    assert client.post("/api/alerts/check-now", headers=auth).status_code == 200
    client.delete(f"/api/trips/{r.json()['id']}", headers=auth)


def test_trip_has_cigarettes(client, auth):
    a = client.post("/api/trips/assess", headers=auth, json=_trip_body()).json()
    assert all(r["cigarettes"] >= 0 for r in a["routes"])


def test_timestamps_carry_utc_offset(client, auth):
    client.post("/api/alerts/brief-now", headers=auth)
    alerts = client.get("/api/alerts", headers=auth).json()["alerts"]
    assert alerts and alerts[0]["created_at"].endswith(("+00:00", "Z"))
