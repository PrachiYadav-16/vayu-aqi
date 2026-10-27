# API reference

Base URL `http://localhost:8000`. Interactive docs with request/response schemas are at `/docs`
(Swagger) and `/redoc`. Endpoints marked **auth** need `Authorization: Bearer <token>`.

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, name, password, sensitivity[]}` | `{access_token}` |
| POST | `/api/auth/token` | form: `username`, `password` | `{access_token}` |

## Air quality (public)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/air/meta` | Categories, data mode (`live`/`simulated`), latest reading time, model version and test metrics |
| GET | `/api/air/stations?hour=0..24` | All stations with AQI now (`hour=0`) or forecast, plus each station's next 24 h |
| GET | `/api/air/stations/{id}` | Point forecast at a station |
| GET | `/api/air/point?lat=&lon=` | Point forecast anywhere (see below) |
| GET | `/api/air/grid?south=&west=&north=&east=&hour=&cells=` | Interpolated surface for the map; `null` where no station is near |
| GET | `/api/air/places?q=&lat=&lon=` | Place search (Google, Nominatim or offline list) |

Point forecast response:

```json
{
  "current_aqi": 67, "category": "satisfactory", "dominant_pollutant": "pm10",
  "pollutants": {"pm25": 31.2, "pm10": 67.4, "no2": 24.1, "o3": 7.0, "co": 0.85, "so2": 8.0},
  "sub_indices": {"pm25": 52, "pm10": 67},
  "hours": [{"ts": "2026-10-28T01:00:00+00:00", "aqi": 83, "low": 59, "high": 113, "category": "satisfactory"}],
  "nearest_station_km": 2.01, "coverage": "good", "method": "kriging", "model_version": "gru-20261027-1913"
}
```

`low` and `high` are the 10th and 90th percentile. `coverage` is `good` (station within 8 km), `fair`
(within 45 km) or `outside`.

## Me (auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/me` | Profile with computed `threshold` |
| PATCH | `/api/me` | Any of `name, sensitivity, custom_threshold, clear_custom_threshold, home_lat, home_lon, location_consent, notify_push, notify_trip_advisories, quiet_start_hour, quiet_end_hour`. Setting `location_consent` to false deletes location history |
| GET | `/api/me/sensitivity-groups` | Groups and their thresholds |
| GET | `/api/me/here?lat=&lon=` | Point forecast plus personal advice: level, actions, next breach, cleanest hour |
| POST | `/api/me/location` | `{lat, lon, accuracy_m}`; ignored without consent; at most one point per 10 min |
| DELETE | `/api/me/location` | Delete location history |
| GET | `/api/me/exposure?days=14` | Daily average/peak AQI and minutes above threshold |
| POST | `/api/me/devices` | `{token, platform}` register an FCM token |
| DELETE | `/api/me/devices/{token}` | Unregister |

## Trips (auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/trips/modes` | `walking, cycling, two_wheeler, auto, bus, driving` |
| POST | `/api/trips/assess` | `{origin:{name,lat,lon}, destination:{...}, depart_at, mode}` |
| GET | `/api/trips` | Saved trips with their last assessment |
| POST | `/api/trips` | Assess body plus `label`, `repeat_weekdays` (0 = Monday) |
| DELETE | `/api/trips/{id}` | |

Assessment response (trimmed):

```json
{
  "verdict": "caution", "threshold": 100, "headline": "Moderate air, above your alert level of 100.",
  "routes": [{
    "id": 0, "summary": "Hosur Road", "provider": "osrm", "distance_km": 13.4, "duration_min": 34,
    "avg_aqi": 118, "peak_aqi": 141, "dose_ug": 38.2, "minutes_above_threshold": 21,
    "is_fastest": true, "is_cleanest": false,
    "geometry": [[12.935, 77.624]], "strip": [{"minute": 0, "lat": 12.935, "lon": 77.624, "aqi": 104}]
  }],
  "recommended_route_id": 1,
  "departure_scan": [{"shift_min": -60, "depart_at": "...", "dose_ug": 33.1, "avg_aqi": 101, "peak_aqi": 120}],
  "suggestions": [{"type": "departure", "shift_min": 90, "dose_reduction_pct": 24, "text": "Leave 1 h 30 min later: 24% less pollution inhaled on the same route."}]
}
```

## Alerts (auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/alerts?limit=50` | `{unread, alerts[]}` newest first |
| POST | `/api/alerts/{id}/read` | |
| POST | `/api/alerts/read-all` | |
| POST | `/api/alerts/check-now` | Run this user's alert rules immediately |

## Ops

`GET /api/health` returns `{"status": "ok"}`.
