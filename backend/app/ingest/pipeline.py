"""Ingestion: fetch, fuse and store one hourly reading per station."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import delete, select

from app.aqi.naqi import compute_aqi
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import simulator
from app.ingest.sources import (
    OpenAQClient,
    OpenMeteoClient,
    OpenWeatherClient,
    TomTomTrafficClient,
    WAQIClient,
    any_pollutant_source,
    data_source,
)
from app.ingest.stations import SEED_STATIONS
from app.models import Reading, Station
from app.store.timeseries import get_store

log = logging.getLogger(__name__)
POLLUTANTS = ("pm25", "pm10", "no2", "o3", "co", "so2")


def ensure_stations() -> None:
    # New stations start as "pending" when a live feed is on, so the first live
    # ingest backfills their history instead of mixing in simulated hours.
    source = "pending" if any_pollutant_source() else "simulated"
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

    if data_source() == "open-meteo":
        return ingest_open_meteo(now)

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


# CPCB averaging periods: particulates, NO2 and SO2 over 24 h; O3 and CO over 8 h.
_AVG_HOURS = {"pm25": 24, "pm10": 24, "no2": 24, "so2": 24, "o3": 8, "co": 8}
BACKFILL_DAYS = 31
_last_refill: datetime | None = None


def naqi_series(df: pd.DataFrame) -> pd.Series:
    """Indian AQI for every hour of an hourly concentration frame, using the CPCB
    averaging windows rather than single-hour values (which overstate ozone peaks)."""
    avg = {p: df[p].rolling(h, min_periods=max(1, int(h * 0.67))).mean() for p, h in _AVG_HOURS.items()}
    out = []
    for i in range(len(df)):
        vals = {p: (None if pd.isna(avg[p].iat[i]) else float(avg[p].iat[i])) for p in _AVG_HOURS}
        out.append(compute_aqi(vals)[0])
    return pd.Series(out, index=df.index, dtype="float")


def _traffic_index(ts: pd.DatetimeIndex, bias: float) -> np.ndarray:
    """No free traffic feed covers Indian cities, so use the typical weekday/weekend
    rush-hour curve scaled by how busy the station's surroundings are."""
    local = ts + pd.Timedelta(hours=5, minutes=30)
    hour = (local.hour + local.minute / 60).to_numpy(dtype=float)
    base = simulator._diurnal_traffic(hour, local.dayofweek.to_numpy())
    return np.clip(base * (0.85 + 0.3 * (bias - 0.85)), 0, 1)


def _weather_gaps(now: datetime) -> bool:
    if get_settings().timeseries_backend != "sql":
        return False
    since = now - timedelta(days=BACKFILL_DAYS - 1)
    with SessionLocal() as db:
        return db.scalar(select(Reading.id).where(Reading.ts >= since, Reading.temp.is_(None)).limit(1)) is not None


def ingest_open_meteo(now: datetime) -> dict:
    store = get_store()
    bias = {sid: b for sid, *_, b in SEED_STATIONS}
    with SessionLocal() as db:
        stations = db.scalars(select(Station).where(Station.active.is_(True))).all()
        stations = [(s.id, s.lat, s.lon, s.source) for s in stations]
    if not stations:
        return {"mode": "live", "source": "open-meteo", "written": 0}

    last = store.latest_ts()
    switching = any(src != "open-meteo" for *_, src in stations) or last is None
    # If an earlier run stored hours without weather (rate limit), refetch the whole
    # window so the gaps get filled once the weather API answers again.
    global _last_refill
    refill = (not switching and (_last_refill is None or now - _last_refill >= timedelta(hours=3))
              and _weather_gaps(now))
    if refill:
        _last_refill = now  # at most one full refetch every 3 h while gaps remain
    if switching or refill:
        past_days = BACKFILL_DAYS
    else:
        gap_days = max(0.0, (now - last).total_seconds() / 86400)
        past_days = int(min(BACKFILL_DAYS, gap_days + 2))

    frames = OpenMeteoClient().hourly([(lat, lon) for _, lat, lon, _ in stations], past_days)
    if frames is None or len(frames) != len(stations):
        if last is None and get_settings().simulate_when_offline:
            log.warning("Open-Meteo unreachable and no data stored; seeding simulated history")
            frame = simulator.simulate(until=now, since=now - timedelta(days=30))
            return {"mode": "simulated", "written": store.write(frame_to_rows(frame))}
        return {"mode": "live", "source": "open-meteo", "written": 0, "error": "fetch failed"}

    now_ts = pd.Timestamp(now)
    rows = []
    for (sid, *_), df in zip(stations, frames):
        df = df[df.index <= now_ts].copy()
        if df.empty:
            continue
        df["aqi"] = naqi_series(df)
        df["traffic"] = _traffic_index(df.index, bias.get(sid, 1.0))
        # The first day of a short fetch lacks a full 24 h window; those hours were
        # already stored with complete windows by an earlier run.
        if not (switching or refill):
            df = df[df.index >= df.index[0] + pd.Timedelta(hours=24)]
        for ts, r in df.iterrows():
            row = {"station_id": sid, "ts": ts.to_pydatetime()}
            for f in ("pm25", "pm10", "no2", "o3", "co", "so2", "temp", "humidity", "wind_speed",
                      "wind_dir", "traffic"):
                v = r.get(f)
                row[f] = None if v is None or pd.isna(v) else float(v)
            row["aqi"] = None if pd.isna(r["aqi"]) else int(round(r["aqi"]))
            rows.append(row)

    if switching and rows and get_settings().timeseries_backend == "sql":
        # Replace any simulated history so forecasts are built on real data only.
        with SessionLocal() as db:
            db.execute(delete(Reading))
            db.commit()
    written = store.write(rows)
    if switching and written:
        with SessionLocal() as db:
            for st in db.scalars(select(Station)).all():
                st.source = "open-meteo"
            db.commit()
    log.info("Open-Meteo ingest wrote %s rows (past_days=%s, refill=%s)", written, past_days, refill)
    return {"mode": "live", "source": "open-meteo", "written": written}


def summarize(rows: list[dict]) -> dict:
    vals = [r["aqi"] for r in rows if r.get("aqi") is not None]
    return {"n": len(rows), "mean_aqi": float(np.mean(vals)) if vals else None}
