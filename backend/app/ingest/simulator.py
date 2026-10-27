"""Physically-shaped simulated feed for offline development and model bootstrap.

Real station data needs API keys and network access, which a fresh clone does
not have. The simulator reproduces the structure that makes AQI forecastable:

* a shared city-level pollution state (slow AR(1) on log scale) so stations in
  one city move together, plus a faster station-level component;
* diurnal cycles driven by traffic and boundary-layer depth (morning and late
  evening peaks, afternoon dilution);
* seasonality: winter build-up, monsoon washout, Delhi's Oct-Nov crop-burning
  episodes;
* weather coupling: stronger wind and rain lower particulates, sun and heat
  raise ozone.

Everything is deterministic for a given seed, so the history used to train the
model and the "live" readings served later are one continuous series.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from app.ingest.stations import CITY_PROFILE, SEED_STATIONS

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass
class SimFrame:
    times: list[datetime]
    station_ids: list[str]
    # arrays shaped (T, S)
    pm25: np.ndarray
    pm10: np.ndarray
    no2: np.ndarray
    o3: np.ndarray
    co: np.ndarray
    so2: np.ndarray
    temp: np.ndarray
    humidity: np.ndarray
    wind_speed: np.ndarray
    wind_dir: np.ndarray
    traffic: np.ndarray


def _season(month_frac: np.ndarray, winter: float, monsoon: float) -> np.ndarray:
    # month_frac in [0, 12): smooth curve peaking mid-Dec, trough in Jul-Aug.
    angle = 2 * np.pi * (month_frac - 11.5) / 12.0
    winter_part = (np.cos(angle) + 1) / 2  # 1 in Dec, 0 in Jun
    s = monsoon + (winter - monsoon) * winter_part
    # Monsoon dip is sharper than a cosine: extra washout Jun 15 - Sep 15.
    s = np.where((month_frac > 5.5) & (month_frac < 8.5), s * 0.85, s)
    return s


def _diurnal_traffic(hour: np.ndarray, weekday: np.ndarray) -> np.ndarray:
    morning = np.exp(-((hour - 9.0) ** 2) / (2 * 1.4**2))
    evening = np.exp(-((hour - 19.0) ** 2) / (2 * 1.8**2))
    base = 0.18 + 0.7 * morning + 0.8 * evening + 0.15 * ((hour > 10) & (hour < 18))
    weekend = np.isin(weekday, [5, 6])
    return np.clip(np.where(weekend, base * 0.65, base), 0, 1)


def _boundary_layer(hour: np.ndarray) -> np.ndarray:
    # >1 means stronger dilution. Deep mixing in the afternoon, inversion at night.
    return 0.85 + 0.45 * np.exp(-((hour - 14.5) ** 2) / (2 * 2.6**2))


def simulate(until: datetime, since: datetime | None = None, seed: int = 7) -> SimFrame:
    until = until.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    n_hours = int((until - EPOCH).total_seconds() // 3600) + 1
    times_all = [EPOCH + timedelta(hours=i) for i in range(n_hours)]

    rng = np.random.default_rng(seed)
    stations = SEED_STATIONS
    S = len(stations)
    cities = sorted(CITY_PROFILE)
    city_idx = np.array([cities.index(s[2]) for s in stations])
    bias = np.array([s[5] for s in stations])
    C = len(cities)

    # Pre-draw noise for the whole history so results do not depend on `since`.
    city_shock = rng.normal(0, 1, size=(n_hours, C))
    station_shock = rng.normal(0, 1, size=(n_hours, S))
    rain_draw = rng.random(size=(n_hours, C))
    wind_shock = rng.normal(0, 1, size=(n_hours, C))
    dir_shock = rng.normal(0, 1, size=(n_hours, C))
    meas_noise = rng.normal(0, 1, size=(n_hours, S, 6))

    city_state = np.zeros(C)
    station_state = np.zeros(S)
    wind_state = np.zeros(C)
    dir_state = rng.uniform(0, 360, size=C)
    rain_left = np.zeros(C)

    phi_city = np.exp(-1 / 40.0)  # ~40 h memory
    phi_station = np.exp(-1 / 6.0)
    phi_wind = np.exp(-1 / 10.0)

    out = {k: np.empty((n_hours, S)) for k in
           ("pm25", "pm10", "no2", "o3", "co", "so2", "temp", "humidity", "wind_speed", "wind_dir", "traffic")}

    for t, ts in enumerate(times_all):
        local = ts + timedelta(hours=5.5)
        hour = local.hour + local.minute / 60
        month_frac = (local.month - 1) + (local.day - 1) / 31.0
        weekday = local.weekday()

        city_state = phi_city * city_state + np.sqrt(1 - phi_city**2) * 0.32 * city_shock[t]
        station_state = phi_station * station_state + np.sqrt(1 - phi_station**2) * 0.12 * station_shock[t]
        wind_state = phi_wind * wind_state + np.sqrt(1 - phi_wind**2) * wind_shock[t]
        dir_state = (dir_state + 6 * dir_shock[t]) % 360

        monsoon = 5.5 < month_frac < 8.7
        rain_start = rain_draw[t] < (0.035 if monsoon else 0.004)
        rain_left = np.where(rain_start, rng.integers(2, 9, size=C), np.maximum(rain_left - 1, 0))
        raining = rain_left > 0

        hour_arr = np.full(S, hour)
        traffic = _diurnal_traffic(hour_arr, np.full(S, weekday)) * (0.85 + 0.3 * (bias - 0.85))
        traffic = np.clip(traffic + 0.05 * station_shock[t], 0, 1)

        wind = np.clip(2.2 + (1.4 if monsoon else 0) + 1.3 * np.sin((hour - 9) / 24 * 2 * np.pi)
                       + 0.9 * wind_state, 0.3, 9.0)
        wind_s = wind[city_idx]
        dilution = _boundary_layer(hour_arr) * (0.7 + 0.12 * wind_s)

        base = np.array([CITY_PROFILE[c]["pm25"] for c in cities])[city_idx]
        season = np.array([
            _season(np.array(month_frac), CITY_PROFILE[c]["winter"], CITY_PROFILE[c]["monsoon"])
            for c in cities
        ])[city_idx]

        episode = np.ones(S)
        if 9.4 < month_frac < 10.8:  # mid-Oct to late-Nov crop residue burning
            delhi = city_idx == cities.index("Delhi")
            episode[delhi] = 1.0 + 0.5 * np.exp(-((month_frac - 10.15) ** 2) / (2 * 0.25**2))

        pm25 = (base * bias * season * episode * (0.7 + 0.4 * traffic) / dilution
                * np.exp(city_state[city_idx] + station_state))
        pm25 = np.where(raining[city_idx], pm25 * 0.55, pm25)
        pm25 = np.clip(pm25 * (1 + 0.05 * meas_noise[t, :, 0]), 3, 900)

        dust = 18 + 25 * (1 - season / season.max()) * (~raining[city_idx])
        pm10 = np.clip(pm25 * (1.55 + 0.25 * np.sin(month_frac / 12 * 2 * np.pi)) + dust
                       + 4 * meas_noise[t, :, 1], 8, 1200)

        no2 = np.clip(12 + 48 * traffic * bias / dilution * np.exp(0.5 * station_state)
                      + 3 * meas_noise[t, :, 2], 2, 400)

        sun = max(0.0, np.sin((hour - 6) / 12 * np.pi))
        is_delhi = city_idx == cities.index("Delhi")
        seasonal_amp = np.where(is_delhi, 9.0, 3.0)  # Delhi swings far more across the year
        temp_c = (np.where(is_delhi, 25.0, 24.0)
                  + seasonal_amp * np.cos(2 * np.pi * (month_frac - 4.5) / 12)
                  + 5.5 * np.sin((hour - 9) / 24 * 2 * np.pi)
                  - 3.0 * raining[city_idx])
        o3 = np.clip(14 + 70 * sun * (temp_c / 30) * (0.9 if monsoon else 1.1) - 0.25 * no2
                     + 4 * meas_noise[t, :, 3], 2, 400)
        co = np.clip(0.35 + 1.4 * traffic * bias / dilution + 0.004 * pm25
                     + 0.05 * meas_noise[t, :, 4], 0.1, 20)
        so2 = np.clip(6 + 10 * bias * traffic + 1.5 * meas_noise[t, :, 5], 1, 120)
        humidity = np.clip(55 + (25 if monsoon else 0) - 18 * np.sin((hour - 9) / 24 * 2 * np.pi)
                           + 15 * raining[city_idx], 15, 100)

        out["pm25"][t] = pm25
        out["pm10"][t] = pm10
        out["no2"][t] = no2
        out["o3"][t] = o3
        out["co"][t] = co
        out["so2"][t] = so2
        out["temp"][t] = temp_c
        out["humidity"][t] = humidity
        out["wind_speed"][t] = wind_s
        out["wind_dir"][t] = dir_state[city_idx]
        out["traffic"][t] = traffic

    start = 0
    if since is not None:
        since = since.astimezone(timezone.utc)
        start = max(0, int((since - EPOCH).total_seconds() // 3600))
    sl = slice(start, n_hours)
    return SimFrame(
        times=times_all[sl],
        station_ids=[s[0] for s in stations],
        **{k: np.round(v[sl], 2) for k, v in out.items()},
    )
