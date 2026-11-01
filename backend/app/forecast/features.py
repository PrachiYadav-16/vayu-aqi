"""Feature engineering shared by training and serving.

Input: hourly readings for many stations (long DataFrame).
Output: a dense tensor (stations, hours, features) on a regular hourly grid.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 48      # hours of history the model sees
HORIZON = 24     # hours ahead it predicts
QUANTILES = (0.1, 0.5, 0.9)

FEATURES = [
    "aqi", "pm25", "pm10", "no2", "o3", "co",
    "temp", "humidity", "wind_speed", "wind_u", "wind_v", "traffic",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "doy_sin", "doy_cos",
    "city_aqi", "aqi_delta",
]

_LOG_COLS = ["aqi", "pm25", "pm10", "no2", "co", "city_aqi"]
AQI_SCALE = 100.0  # targets are AQI / 100
# Neutral values for weather/traffic when a station has none at all in the window.
_TYPICAL = {"temp": 26.0, "humidity": 60.0, "wind_speed": 2.0, "wind_dir": 180.0, "traffic": 0.4}


def to_grid(df: pd.DataFrame, station_city: dict[str, str], end: pd.Timestamp | None = None,
            hours: int | None = None) -> tuple[np.ndarray, list[str], pd.DatetimeIndex]:
    """Pivot readings onto a regular grid and build features.

    Returns (X, station_ids, times) with X shaped (S, T, F) and NaNs filled.
    """
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.floor("h")
    if end is None:
        end = df["ts"].max()
    # Normalise to plain UTC: Postgres may hand back Etc/UTC, which pandas treats as different.
    end = pd.Timestamp(end)
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    start = df["ts"].min() if hours is None else end - pd.Timedelta(hours=hours - 1)
    times = pd.date_range(start, end, freq="h", tz="UTC")
    stations = sorted(df["station_id"].unique())

    cols = ["aqi", "pm25", "pm10", "no2", "o3", "co", "temp", "humidity", "wind_speed", "wind_dir", "traffic"]
    cube = {}
    for c in cols:
        p = df.pivot_table(index="ts", columns="station_id", values=c, aggfunc="mean")
        p = p.reindex(index=times, columns=stations)
        # Short gaps: carry forward up to 6 h, then fall back to the station's own median.
        p = p.ffill(limit=6).bfill(limit=2)
        p = p.fillna(p.median())
        if c in _TYPICAL:  # a source that never reported this column (e.g. weather rate-limited)
            p = p.fillna(_TYPICAL[c])
        cube[c] = p.to_numpy(dtype=np.float32).T  # (S, T)

    # City-level context: mean AQI across the station's city at the same hour.
    city_of = np.array([station_city.get(s, "?") for s in stations])
    city_aqi = np.zeros_like(cube["aqi"])
    for city in np.unique(city_of):
        m = city_of == city
        city_aqi[m] = np.nanmean(cube["aqi"][m], axis=0, keepdims=True)

    local = times + pd.Timedelta(hours=5, minutes=30)
    hour = (local.hour + local.minute / 60).to_numpy()
    dow = local.dayofweek.to_numpy()
    doy = local.dayofyear.to_numpy()
    S, T = cube["aqi"].shape

    def row(v):
        return np.broadcast_to(v.astype(np.float32), (S, T))

    wd = np.deg2rad(np.nan_to_num(cube["wind_dir"]))
    ws = np.nan_to_num(cube["wind_speed"])
    aqi_delta = np.diff(cube["aqi"], axis=1, prepend=cube["aqi"][:, :1])

    feats = {
        "aqi": cube["aqi"], "pm25": cube["pm25"], "pm10": cube["pm10"], "no2": cube["no2"],
        "o3": cube["o3"], "co": cube["co"], "temp": cube["temp"], "humidity": cube["humidity"],
        "wind_speed": ws, "wind_u": ws * np.sin(wd), "wind_v": ws * np.cos(wd),
        "traffic": np.nan_to_num(cube["traffic"], nan=0.4),
        "hour_sin": row(np.sin(2 * np.pi * hour / 24)), "hour_cos": row(np.cos(2 * np.pi * hour / 24)),
        "dow_sin": row(np.sin(2 * np.pi * dow / 7)), "dow_cos": row(np.cos(2 * np.pi * dow / 7)),
        "doy_sin": row(np.sin(2 * np.pi * doy / 365.25)), "doy_cos": row(np.cos(2 * np.pi * doy / 365.25)),
        "city_aqi": city_aqi, "aqi_delta": aqi_delta,
    }
    for c in _LOG_COLS:
        feats[c] = np.log1p(np.clip(feats[c], 0, None))
    X = np.stack([feats[f] for f in FEATURES], axis=-1).astype(np.float32)
    X = np.nan_to_num(X)
    return X, stations, times


def fit_scaler(X: np.ndarray) -> dict:
    flat = X.reshape(-1, X.shape[-1])
    mean = flat.mean(axis=0)
    std = flat.std(axis=0) + 1e-6
    return {"mean": mean.tolist(), "std": std.tolist()}


def apply_scaler(X: np.ndarray, scaler: dict) -> np.ndarray:
    return ((X - np.asarray(scaler["mean"], dtype=np.float32)) / np.asarray(scaler["std"], dtype=np.float32)).astype(np.float32)

