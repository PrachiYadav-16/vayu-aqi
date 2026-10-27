# Testing

## Automated tests

`cd backend && pytest -q` runs 36 tests in about 10 seconds against a throwaway SQLite database with
routing and geocoding forced offline.

| File | Covers |
|---|---|
| `tests/test_core.py` | CPCB breakpoints and band gaps, dominant pollutant, PM2.5 inverse, categories, thresholds, advice levels, IDW, interpolation staying inside a city, polyline decoding |
| `tests/test_model.py` | NumPy GRU output equals PyTorch output; simulator determinism |
| `tests/test_api.py` | Health, stations, personal advice, point forecasts and intervals, out-of-coverage flag, map grid masking, register/login errors, auth guard, threshold updates, location consent and deletion, trip assessment, car vs cycle dose, mode validation, trip CRUD, alert firing and cooldown, offline place search |

CI runs the backend tests and a frontend type-check and build on every push (`.github/workflows/ci.yml`).

## End-to-end check

The full path location capture → forecaster → route advisory → dashboard was exercised in a headless
Chromium session: sign in, Air now with geolocation, Plan a trip from Koramangala to Electronic City,
Saved trips, Alerts, My exposure and Settings, on a 1440 px desktop and a 390 px phone viewport. The only
console errors were map tiles and web fonts that the test machine could not download.

## Load test

`locust -f locustfile.py --host http://localhost:8000 --headless -u 30 -r 10 -t 60s`

Single uvicorn worker, SQLite, 2 CPU cores, 30 concurrent users:

| Endpoint | Requests | Failures | Median | 95th pct |
|---|---|---|---|---|
| GET /api/air/stations | 274 | 0 | 7 ms | 21 ms |
| GET /api/me/here | 258 | 0 | 10 ms | 21 ms |
| GET /api/air/grid | 102 | 0 | 10 ms | 32 ms |
| POST /api/trips/assess | 44 | 0 | 340 ms | 380 ms |
| POST /api/auth/register | 30 | 0 | 2.4 s | 3.2 s |

Findings:

* Forecasts are cached per observation hour, so reads stay in single-digit milliseconds.
* Route assessment is the heaviest read (interpolating about 70 points per route for 24 hours, three routes,
  17 departure times) and stays under 400 ms.
* Sign-up is slow under a burst because bcrypt is deliberately expensive and the 30 sign-ups arrived within
  3 seconds on 2 cores. In production run several workers (`uvicorn --workers 4` or gunicorn).
