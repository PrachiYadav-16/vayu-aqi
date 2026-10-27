"""Route exposure: what you breathe along a route at a given departure time.

For each route we sample a point roughly every 200 m, estimate the 24-hour AQI
forecast at every sample once, and then evaluate any departure time by shifting
which forecast hour each sample falls in. That makes scanning many departure
times and alternatives cheap.

Dose is estimated as  sum(PM2.5 equivalent * breathing rate * infiltration * dt),
in micrograms. PM2.5 equivalent is the PM2.5 concentration that would produce
the forecast AQI; it is an approximation that keeps the number interpretable
and comparable across routes and modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from app.aqi.naqi import category_for, pm25_for_aqi
from app.forecast.service import get_forecast_service
from app.routing.providers import MODES, Route, haversine_m

SAMPLE_M = 200


@dataclass
class SampledRoute:
    route: Route
    lat: np.ndarray
    lon: np.ndarray
    offset_s: np.ndarray     # time from departure to reach each sample
    dt_s: np.ndarray         # time spent in each sample's segment
    hourly: np.ndarray       # (N, 24) forecast AQI at each sample
    current: np.ndarray      # (N,) current AQI
    issued_at: datetime
    coverage: str


def sample_route(route: Route) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pts = route.geometry
    seg = np.array([haversine_m(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1] if cum[-1] > 0 else 1.0
    n = max(2, int(total // SAMPLE_M) + 1)
    targets = np.linspace(0, total, n)
    lat = np.interp(targets, cum, [p[0] for p in pts])
    lon = np.interp(targets, cum, [p[1] for p in pts])
    frac = targets / total
    return lat, lon, frac


def prepare(route: Route) -> SampledRoute:
    lat, lon, frac = sample_route(route)
    offset = frac * route.duration_s
    dt = np.diff(offset, append=offset[-1])
    dt[-1] = dt[-2] if len(dt) > 1 else 0
    dt = dt * (route.duration_s / max(dt.sum(), 1))
    svc = get_forecast_service()
    pf = svc.points_forecast(lat.tolist(), lon.tolist())
    if not pf or pf[0] is None:
        raise RuntimeError("No air quality data available yet")
    hourly = np.array([[h["aqi"] for h in p["hours"]] for p in pf], dtype=float)
    current = np.array([p["current_aqi"] for p in pf], dtype=float)
    cov = [p["coverage"] for p in pf]
    coverage = "outside" if cov.count("outside") > len(cov) / 2 else ("good" if cov.count("good") > len(cov) / 2 else "fair")
    return SampledRoute(route, lat, lon, offset, dt, hourly, current,
                        datetime.fromisoformat(pf[0]["issued_at"]), coverage)


def aqi_at_times(sr: SampledRoute, depart: datetime) -> np.ndarray:
    times = [depart + timedelta(seconds=float(s)) for s in sr.offset_s]
    hours_ahead = np.array([(t - sr.issued_at).total_seconds() / 3600 for t in times])
    out = np.empty(len(times))
    for i, h in enumerate(hours_ahead):
        if h <= 0.5:
            out[i] = sr.current[i]
            continue
        # Linear interpolation between forecast hours; beyond 24 h hold the last value.
        x = min(h, 24.0) - 1
        lo = int(np.floor(x)) if x >= 0 else 0
        hi = min(lo + 1, 23)
        w = x - lo if x >= 0 else 0
        base = sr.current[i] if x < 0 else sr.hourly[i, lo]
        out[i] = (1 - w) * base + w * sr.hourly[i, hi]
    return out


def score(sr: SampledRoute, depart: datetime, mode_key: str, threshold: int) -> dict:
    mode = MODES.get(mode_key, MODES["driving"])
    aqi = aqi_at_times(sr, depart)
    dt_h = sr.dt_s / 3600
    pm = np.array([pm25_for_aqi(a) for a in aqi])
    dose = float((pm * mode.breathing_m3h * mode.infiltration * dt_h).sum())
    avg = float((aqi * sr.dt_s).sum() / max(sr.dt_s.sum(), 1))
    above = float(sr.dt_s[aqi > threshold].sum() / 60)
    return {"aqi": aqi, "dose_ug": dose, "avg_aqi": avg, "peak_aqi": float(aqi.max()),
            "minutes_above_threshold": above}


def strip(sr: SampledRoute, aqi: np.ndarray, depart: datetime, max_points: int = 60) -> list[dict]:
    """Downsample the per-sample AQI into a strip for the UI."""
    n = len(aqi)
    idx = np.linspace(0, n - 1, min(n, max_points)).round().astype(int)
    return [{
        "minute": round(float(sr.offset_s[i]) / 60, 1),
        "lat": round(float(sr.lat[i]), 5),
        "lon": round(float(sr.lon[i]), 5),
        "aqi": round(float(aqi[i])),
        "category": category_for(aqi[i]).key,
    } for i in idx]
