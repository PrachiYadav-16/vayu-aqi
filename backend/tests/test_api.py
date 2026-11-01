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


def test_mask_advice_does_not_crash(client, auth):
    """Regression: a variable named `t` in the departure scan shadowed the translator."""
    client.patch("/api/me", headers=auth, json={"custom_threshold": 50})
    for mode in ("cycling", "walking", "two_wheeler"):
        r = client.post("/api/trips/assess", headers=auth, json=_trip_body(mode=mode))
        assert r.status_code == 200, r.text
        assert any(s["type"] == "mask" for s in r.json()["suggestions"])
    client.patch("/api/me", headers=auth, json={"clear_custom_threshold": True})


def test_meta_reports_data_source(client):
    m = client.get("/api/air/meta").json()
    assert m["data_source"] == "simulated" and m["data_mode"] == "simulated"


def _new_user(client, email):
    r = client.post("/api/auth/register", json={"email": email, "name": "T", "password": "long-enough-1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_login_is_throttled_after_repeated_failures(client):
    _new_user(client, "throttle@example.com")
    codes = [client.post("/api/auth/token", data={"username": "throttle@example.com", "password": "wrong-pass"}).status_code
             for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429
    # Other accounts are unaffected.
    ok = client.post("/api/auth/token", data={"username": "asha@example.com", "password": "breathe-easy-1"})
    assert ok.status_code == 200


def test_saving_a_past_one_time_trip_is_rejected(client, auth):
    past = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    r = client.post("/api/trips", headers=auth, json=_trip_body(depart_at=past, label="old"))
    assert r.status_code == 422
    # A repeating trip may use any time of day as its template.
    r = client.post("/api/trips", headers=auth, json=_trip_body(depart_at=past, label="daily", repeat_weekdays=[0, 1]))
    assert r.status_code == 201
    client.delete(f"/api/trips/{r.json()['id']}", headers=auth)


def test_saved_trip_carries_its_assessment(client, auth):
    r = client.post("/api/trips", headers=auth, json=_trip_body(label="with verdict"))
    assert r.status_code == 201
    a = r.json()["last_assessment"]
    assert a and a["routes"] and "checked_at" in a and "geometry" not in a["routes"][0]
    client.delete(f"/api/trips/{r.json()['id']}", headers=auth)


def test_check_now_reports_counts(client, auth):
    r = client.post("/api/alerts/check-now", headers=auth).json()
    assert {"created", "trips", "trips_due"} <= r.keys()


def test_brief_now_uses_passed_position_when_no_home(client):
    h = _new_user(client, "brief@example.com")
    assert client.post("/api/alerts/brief-now", headers=h).json()["created"] == []
    r = client.post("/api/alerts/brief-now?lat=12.97&lon=77.59", headers=h).json()
    assert len(r["created"]) == 1 and r["created"][0]["kind"] == "daily_brief"


def test_pm25_share_keeps_doses_honest(client):
    p = client.get("/api/air/point", params={"lat": 12.97, "lon": 77.59}).json()
    assert 0.1 <= p["pm25_share"] <= 1.0
    assert all("pm25" in h for h in p["hours"])


def test_delete_account_removes_everything(client):
    h = _new_user(client, "leaving@example.com")
    client.patch("/api/me", headers=h, json={"location_consent": True})
    client.post("/api/me/location", headers=h, json={"lat": 12.97, "lon": 77.59})
    client.post("/api/trips", headers=h, json=_trip_body(label="bye"))
    assert client.delete("/api/me", headers=h).status_code == 204
    assert client.get("/api/me", headers=h).status_code == 401
    r = client.post("/api/auth/token", data={"username": "leaving@example.com", "password": "long-enough-1"})
    assert r.status_code == 401


def test_input_edge_cases(client, auth):
    assert client.post("/api/auth/register", json={"email": "blank@example.com", "name": "   ",
                                                  "password": "long-enough-1"}).status_code == 422
    assert client.patch("/api/me", headers=auth, json={"name": None}).status_code == 200
    assert client.patch("/api/me", headers=auth, json={"name": "  "}).status_code == 422
    assert client.patch("/api/me", headers=auth, json={"location_consent": None}).status_code == 200
    assert client.get("/api/does-not-exist").status_code in (404, 405)


def test_assess_rejects_trips_it_cannot_judge(client, auth):
    far = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assert client.post("/api/trips/assess", headers=auth, json=_trip_body(depart_at=far)).status_code == 422
    jaipur = {"name": "Jaipur", "lat": 26.91, "lon": 75.79}
    jaipur2 = {"name": "Jaipur 2", "lat": 26.95, "lon": 75.84}
    r = client.post("/api/trips/assess", headers=auth, json=_trip_body(origin=jaipur, destination=jaipur2))
    assert r.status_code == 422 and "outside" in r.json()["detail"]
    delhi = {"name": "Delhi", "lat": 28.61, "lon": 77.21}
    assert client.post("/api/trips/assess", headers=auth, json=_trip_body(destination=delhi)).status_code == 422
    same = _trip_body()
    same["destination"] = same["origin"]
    assert client.post("/api/trips/assess", headers=auth, json=same).status_code == 422
    # Naive times are read as IST.
    r = client.post("/api/trips/assess", headers=auth, json=_trip_body(
        depart_at=(datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%S")))
    assert r.status_code == 200 and r.json()["depart_at"].endswith("+05:30")
