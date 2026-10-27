"""Ingestion: fetch, fuse and store one hourly reading per station."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select

from app.aqi.naqi import compute_aqi
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import simulator
from app.ingest.sources import (
    OpenAQClient,
    OpenWeatherClient,
    TomTomTrafficClient,
    WAQIClient,
    any_pollutant_source,
)
from app.ingest.stations import SEED_STATIONS
from app.models import Station
from app.store.timeseries import get_store

log = logging.getLogger(__name__)
POLLUTANTS = ("pm25", "pm10", "no2", "o3", "co", "so2")


def ensure_stations() -> None:
    source = "cpcb" if any_pollutant_source() else "simulated"
    with SessionLocal() as db:
        existing = {s.id for s in db.scalars(select(Station)).all()}
        for sid, name, city, lat, lon, _ in SEED_STATIONS:
            if sid not in existing:
                db.add(Station(id=sid, name=name, city=city, lat=lat, lon=lon, source=source))
        db.commit()


def _with_aqi(row: dict) -> dict:
    aqi, _, _ = compute_aqi({p: row.get(p) for p in POLLUTANTS})
    row["aqi"] = aqi
    return row


def frame_to_rows(frame: simulator.SimFrame) -> list[dict]:
    rows = []
    fields = ("pm25", "pm10", "no2", "o3", "co", "so2", "temp", "humidity", "wind_speed", "wind_dir", "traffic")
    arrays = {f: getattr(frame, f) for f in fields}
    for t, ts in enumerate(frame.times):
        for s, sid in enumerate(frame.station_ids):
            row = {"station_id": sid, "ts": ts}
            for f in fields:
                row[f] = float(arrays[f][t, s])
            rows.append(_with_aqi(row))
    return rows


def backfill_simulated(days: int = 30, until: datetime | None = None) -> int:
    until = until or datetime.now(timezone.utc)
    frame = simulator.simulate(until=until, since=until - timedelta(days=days))
    return get_store().write(frame_to_rows(frame))


def ingest_live(now: datetime | None = None) -> dict:
    """Run one ingestion pass. Uses real sources when configured, otherwise the simulator."""
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    settings = get_settings()
    store = get_store()

    if not any_pollutant_source():
        if not settings.simulate_when_offline:
            return {"mode": "disabled", "written": 0}
        last = store.latest_ts()
        since = (last + timedelta(hours=1)) if last else now - timedelta(days=30)
        if since > now:
            return {"mode": "simulated", "written": 0}
        frame = simulator.simulate(until=now, since=since)
        return {"mode": "simulated", "written": store.write(frame_to_rows(frame))}

    openaq, waqi, owm, tomtom = OpenAQClient(), WAQIClient(), OpenWeatherClient(), TomTomTrafficClient()
    rows = []
    with SessionLocal() as db:
        stations = db.scalars(select(Station).where(Station.active.is_(True))).all()
    weather_cache: dict[tuple[float, float], dict | None] = {}
    for st in stations:
        pol = openaq.nearest_latest(st.lat, st.lon) or waqi.at(st.lat, st.lon)
        if not pol:
            continue
        # Weather varies slowly in space; one call per ~10 km grid cell is enough.
        cell = (round(st.lat, 1), round(st.lon, 1))
        if cell not in weather_cache:
            weather_cache[cell] = owm.current(st.lat, st.lon)
        weather = weather_cache[cell] or {}
        row = {"station_id": st.id, "ts": now, **{p: pol.get(p) for p in POLLUTANTS}}
        for k in ("temp", "humidity", "wind_speed", "wind_dir"):
            row[k] = weather.get(k, pol.get(k))
        row["traffic"] = tomtom.congestion(st.lat, st.lon)
        rows.append(_with_aqi(row))
    written = store.write(rows)
    log.info("Live ingest wrote %s rows", written)
    return {"mode": "live", "written": written}


def summarize(rows: list[dict]) -> dict:
    vals = [r["aqi"] for r in rows if r.get("aqi") is not None]
    return {"n": len(rows), "mean_aqi": float(np.mean(vals)) if vals else None}
