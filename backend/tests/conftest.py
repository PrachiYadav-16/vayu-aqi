import os
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="vayu-test-")
os.environ["VAYU_DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ["VAYU_RUN_SCHEDULER"] = "false"
os.environ["VAYU_OPEN_METEO"] = "false"  # tests run offline on simulated data
os.environ["VAYU_OSRM_URL"] = "http://127.0.0.1:9"  # unreachable: forces the offline router
os.environ["VAYU_NOMINATIM_URL"] = "http://127.0.0.1:9"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.db import init_db
    from app.ingest.pipeline import backfill_simulated, ensure_stations
    from app.main import app

    init_db()
    ensure_stations()
    backfill_simulated(days=4)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/register", json={
        "email": "asha@example.com", "name": "Asha", "password": "breathe-easy-1", "sensitivity": ["asthma"],
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
