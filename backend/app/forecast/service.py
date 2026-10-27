"""Serving layer: station forecasts, cached per hour, and point estimates."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.aqi.naqi import compute_aqi, category_for
from app.config import get_settings
from app.db import SessionLocal
from app.forecast.features import FEATURES, HORIZON, WINDOW, apply_scaler, to_grid
from app.forecast.gru_numpy import NumpyGRUForecaster
from app.forecast.spatial import SEARCH_RADIUS_KM, interpolate
from app.models import Station
from app.store.timeseries import get_store

log = logging.getLogger(__name__)
POLLUTANTS = ["pm25", "pm10", "no2", "o3", "co", "so2"]
EXPLAIN_GROUPS = [
    ("traffic", ["traffic"]),
    ("wind", ["wind_speed", "wind_u", "wind_v"]),
    ("weather", ["temp", "humidity"]),
    ("time", ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]),
    ("season", ["doy_sin", "doy_cos"]),
    ("city", ["city_aqi"]),
    ("trend", ["aqi_delta"]),
]


@dataclass
class StationForecast:
    issued_at: datetime                 # hour of the latest observation
    station_ids: list[str]
    lat: np.ndarray
    lon: np.ndarray
    names: list[str]
    cities: list[str]
    current_aqi: np.ndarray             # (S,)
    current_pollutants: np.ndarray      # (S, 6) concentrations
    quantiles: np.ndarray               # (S, H, 3) AQI
    model_version: str
    inputs: np.ndarray | None = None    # (S, WINDOW, F) scaled model inputs, kept for explanations


class ForecastService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: StationForecast | None = None
        self._model: NumpyGRUForecaster | None = None
        self._meta: dict | None = None
        self._explain_cache: dict = {}
        self.reload_model()

    # ------------------------------------------------------------ model

    def reload_model(self) -> None:
        d = Path(get_settings().model_dir)
        npz, meta = d / "forecaster.npz", d / "forecaster.json"
        if npz.exists() and meta.exists():
            self._model = NumpyGRUForecaster.load(str(npz))
            self._meta = json.loads(meta.read_text())
            log.info("Loaded forecaster %s", self._meta["version"])
        else:
            self._model, self._meta = None, None
            log.warning("No trained forecaster found in %s; using climatology fallback", d)
        self._cache = None

    @property
    def model_info(self) -> dict:
        if not self._meta:
            return {"version": "climatology-fallback", "metrics": {}}
        m = self._meta["metrics"]
        return {
            "version": self._meta["version"],
            "trained_at": self._meta["trained_at"],
            "source": self._meta["source"],
            "test_mae": m.get("gru_mae_all"),
            "persistence_mae": m.get("persistence_mae_all"),
            "interval_coverage": m.get("coverage_all"),
            "by_horizon": m.get("by_horizon"),
        }

    # ------------------------------------------------------------ stations

    def station_forecasts(self, force: bool = False) -> StationForecast | None:
        store = get_store()
        latest = store.latest_ts()
        if latest is None:
            return None
        with self._lock:
            if not force and self._cache and self._cache.issued_at == latest:
                return self._cache
            self._cache = self._compute(latest)
            return self._cache

    def _compute(self, latest: datetime) -> StationForecast:
        with SessionLocal() as db:
            stations = db.scalars(select(Station).where(Station.active.is_(True)).order_by(Station.id)).all()
        city_of = {s.id: s.city for s in stations}
        by_id = {s.id: s for s in stations}
        since = latest - timedelta(hours=WINDOW + 24)
        df = get_store().history(list(by_id), since=since, until=latest)
        X, sids, _ = to_grid(df, city_of, end=pd.Timestamp(latest), hours=WINDOW)
        aqi_now = np.expm1(X[:, -1, FEATURES.index("aqi")])

        last_rows = df.sort_values("ts").groupby("station_id").tail(1).set_index("station_id")
        pol = np.array([[float(last_rows.at[s, p]) if s in last_rows.index and pd.notna(last_rows.at[s, p]) else np.nan
                         for p in POLLUTANTS] for s in sids])

        Xs = None
        if self._model is not None:
            Xs = apply_scaler(X, self._meta["scaler"])
            q = self._model.predict(Xs, aqi_now)
            version = self._meta["version"]
        else:
            q = self._climatology(df, sids, latest, aqi_now)
            version = "climatology-fallback"

        return StationForecast(
            issued_at=latest,
            station_ids=sids,
            lat=np.array([by_id[s].lat for s in sids]),
            lon=np.array([by_id[s].lon for s in sids]),
            names=[by_id[s].name for s in sids],
            cities=[by_id[s].city for s in sids],
            current_aqi=aqi_now,
            current_pollutants=pol,
            quantiles=q,
            model_version=version,
            inputs=Xs,
        )

    @staticmethod
    def _climatology(df: pd.DataFrame, sids: list[str], latest: datetime, aqi_now: np.ndarray) -> np.ndarray:
        """Fallback: blend persistence into the station's hour-of-day profile."""
        df = df.copy()
        df["hour"] = pd.to_datetime(df["ts"]).dt.hour
        prof = df.groupby(["station_id", "hour"])["aqi"].mean()
        out = np.zeros((len(sids), HORIZON, 3))
        for i, s in enumerate(sids):
            for h in range(HORIZON):
                hour = (latest + timedelta(hours=h + 1)).hour
                clim = prof.get((s, hour), aqi_now[i])
                w = np.exp(-(h + 1) / 6)
                med = w * aqi_now[i] + (1 - w) * clim
                spread = 0.15 * med + 2 * h
                out[i, h] = [max(0, med - spread), med, med + spread]
        return out

    # ------------------------------------------------------------ explanations

    def explain_station(self, idx: int) -> list[dict] | None:
        """Occlusion attribution: replace one group of inputs with its training
        average (0 after scaling) and see how much the next-6-hour forecast moves.
        A positive effect means that factor is pushing AQI up compared with
        typical conditions."""
        sf = self.station_forecasts()
        if sf is None or sf.inputs is None or self._model is None:
            return None
        key = (sf.issued_at, idx)
        cached = self._explain_cache.get(key)
        if cached is not None:
            return cached
        base_x = sf.inputs[idx:idx + 1]
        variants = [base_x]
        for _, feats in EXPLAIN_GROUPS:
            x = base_x.copy()
            for f in feats:
                x[..., FEATURES.index(f)] = 0.0
            variants.append(x)
        batch = np.concatenate(variants)
        now = np.repeat(sf.current_aqi[idx:idx + 1], len(variants))
        pred = self._model.predict(batch, now)[:, :6, 1].mean(axis=1)
        out = [{"factor": name, "effect": round(float(pred[0] - pred[i + 1]), 1)}
               for i, (name, _) in enumerate(EXPLAIN_GROUPS)]
        out.sort(key=lambda d: abs(d["effect"]), reverse=True)
        if len(self._explain_cache) > 500:
            self._explain_cache.clear()
        self._explain_cache[key] = out
        return out

    def nearest_station(self, lat: float, lon: float) -> int | None:
        sf = self.station_forecasts()
        if sf is None:
            return None
        from app.forecast.spatial import haversine_matrix

        d = haversine_matrix([lat], [lon], sf.lat, sf.lon)[0]
        i = int(np.argmin(d))
        return i if d[i] <= SEARCH_RADIUS_KM else None

    # ------------------------------------------------------------ points

    def point_forecast(self, lat: float, lon: float) -> dict | None:
        return self.points_forecast([lat], [lon])[0]

    def points_forecast(self, lats: list[float], lons: list[float]) -> list[dict | None]:
        sf = self.station_forecasts()
        if sf is None:
            return [None] * len(lats)
        S = len(sf.station_ids)
        # Stack current AQI, pollutant concentrations and the forecast quantiles so one
        # interpolation call handles everything.
        field = np.concatenate([
            sf.current_aqi[:, None],
            np.nan_to_num(sf.current_pollutants, nan=np.nanmean(sf.current_pollutants)),
            sf.quantiles.reshape(S, -1),
        ], axis=1)
        est = interpolate(lats, lons, sf.lat, sf.lon, field)
        results: list[dict | None] = []
        for i in range(len(lats)):
            v = est.value[i]
            cur = float(v[0])
            pol = dict(zip(POLLUTANTS, (float(x) for x in v[1:1 + len(POLLUTANTS)])))
            q = v[1 + len(POLLUTANTS):].reshape(HORIZON, 3)
            spatial_sd = float(est.std[i]) if est.std is not None else 0.0
            _, dominant, subs = compute_aqi(pol)
            hours = []
            for h in range(HORIZON):
                lo, med, hi = q[h]
                widen = 1.28 * spatial_sd  # add interpolation uncertainty to the 80% band
                hours.append({
                    "ts": (sf.issued_at + timedelta(hours=h + 1)).isoformat(),
                    "aqi": round(float(med)),
                    "low": max(0, round(float(lo - widen))),
                    "high": min(500, round(float(hi + widen))),
                    "category": category_for(med).key,
                })
            nearest_km = float(est.nearest_km[i])
            results.append({
                "lat": lats[i],
                "lon": lons[i],
                "issued_at": sf.issued_at.isoformat(),
                "current_aqi": round(cur),
                "category": category_for(cur).key,
                "dominant_pollutant": dominant,
                "pollutants": {k: round(val, 2) for k, val in pol.items()},
                "sub_indices": subs,
                "hours": hours,
                "nearest_station_km": round(nearest_km, 2),
                "coverage": "good" if nearest_km <= 8 else "fair" if nearest_km <= SEARCH_RADIUS_KM else "outside",
                "method": est.method,
                "model_version": sf.model_version,
            })
        return results


_service: ForecastService | None = None


def get_forecast_service() -> ForecastService:
    global _service
    if _service is None:
        _service = ForecastService()
    return _service


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
