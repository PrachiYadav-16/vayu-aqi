"""Clients for live data sources. Each returns None when it has no key or fails,
so the pipeline can degrade gracefully instead of crashing a whole ingest run."""

from __future__ import annotations

import logging
import math

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(10.0)

# OpenAQ reports parameters by name; units are ug/m3 except CO which we convert to mg/m3.
_OPENAQ_PARAMS = {"pm25": "pm25", "pm10": "pm10", "no2": "no2", "o3": "o3", "co": "co", "so2": "so2"}


def _haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class OpenAQClient:
    """OpenAQ v3. Finds the nearest location within 3 km and reads its latest values."""

    base = "https://api.openaq.org/v3"

    def __init__(self) -> None:
        self.key = get_settings().openaq_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def nearest_latest(self, lat: float, lon: float) -> dict | None:
        if not self.enabled:
            return None
        headers = {"X-API-Key": self.key}
        try:
            with httpx.Client(timeout=TIMEOUT, headers=headers) as c:
                locs = c.get(f"{self.base}/locations",
                             params={"coordinates": f"{lat},{lon}", "radius": 3000, "limit": 5}).json()
                results = locs.get("results") or []
                if not results:
                    return None
                loc = results[0]
                sensors = {s["id"]: s["parameter"]["name"] for s in loc.get("sensors", [])}
                latest = c.get(f"{self.base}/locations/{loc['id']}/latest").json().get("results", [])
            out: dict[str, float] = {}
            for item in latest:
                name = sensors.get(item.get("sensorsId"))
                if name in _OPENAQ_PARAMS and item.get("value") is not None:
                    v = float(item["value"])
                    if name == "co" and v > 50:  # ug/m3 -> mg/m3
                        v /= 1000
                    out[_OPENAQ_PARAMS[name]] = v
            return out or None
        except Exception as exc:  # network, schema change, rate limit
            log.warning("OpenAQ fetch failed at %s,%s: %s", lat, lon, exc)
            return None


class WAQIClient:
    """World Air Quality Index project. Returns US-EPA style sub-indices, so we
    convert PM sub-indices back to concentrations before recomputing the Indian AQI."""

    base = "https://api.waqi.info"

    def __init__(self) -> None:
        self.token = get_settings().waqi_token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    @staticmethod
    def _us_pm25_conc(i: float) -> float:
        bands = [(0, 50, 0, 12), (51, 100, 12.1, 35.4), (101, 150, 35.5, 55.4),
                 (151, 200, 55.5, 150.4), (201, 300, 150.5, 250.4), (301, 500, 250.5, 500.4)]
        for i_lo, i_hi, c_lo, c_hi in bands:
            if i <= i_hi:
                return c_lo + (c_hi - c_lo) * (i - i_lo) / (i_hi - i_lo)
        return 500.0

    @staticmethod
    def _us_pm10_conc(i: float) -> float:
        bands = [(0, 50, 0, 54), (51, 100, 55, 154), (101, 150, 155, 254),
                 (151, 200, 255, 354), (201, 300, 355, 424), (301, 500, 425, 604)]
        for i_lo, i_hi, c_lo, c_hi in bands:
            if i <= i_hi:
                return c_lo + (c_hi - c_lo) * (i - i_lo) / (i_hi - i_lo)
        return 604.0

    def at(self, lat: float, lon: float) -> dict | None:
        if not self.enabled:
            return None
        try:
            r = httpx.get(f"{self.base}/feed/geo:{lat};{lon}/", params={"token": self.token}, timeout=TIMEOUT)
            data = r.json()
            if data.get("status") != "ok":
                return None
            iaqi = data["data"].get("iaqi", {})
            out: dict[str, float] = {}
            if "pm25" in iaqi:
                out["pm25"] = self._us_pm25_conc(iaqi["pm25"]["v"])
            if "pm10" in iaqi:
                out["pm10"] = self._us_pm10_conc(iaqi["pm10"]["v"])
            for k in ("t", "h", "w"):
                if k in iaqi:
                    out[{"t": "temp", "h": "humidity", "w": "wind_speed"}[k]] = float(iaqi[k]["v"])
            return out or None
        except Exception as exc:
            log.warning("WAQI fetch failed: %s", exc)
            return None


class OpenWeatherClient:
    base = "https://api.openweathermap.org/data/2.5"

    def __init__(self) -> None:
        self.key = get_settings().openweather_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def current(self, lat: float, lon: float) -> dict | None:
        if not self.enabled:
            return None
        try:
            d = httpx.get(f"{self.base}/weather",
                          params={"lat": lat, "lon": lon, "appid": self.key, "units": "metric"},
                          timeout=TIMEOUT).json()
            return {
                "temp": d["main"]["temp"],
                "humidity": d["main"]["humidity"],
                "wind_speed": d["wind"]["speed"],
                "wind_dir": d["wind"].get("deg", 0.0),
            }
        except Exception as exc:
            log.warning("OpenWeather fetch failed: %s", exc)
            return None


class TomTomTrafficClient:
    """Congestion index = 1 - current speed / free-flow speed on the nearest road segment."""

    base = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

    def __init__(self) -> None:
        self.key = get_settings().tomtom_api_key

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def congestion(self, lat: float, lon: float) -> float | None:
        if not self.enabled:
            return None
        try:
            d = httpx.get(self.base, params={"point": f"{lat},{lon}", "key": self.key}, timeout=TIMEOUT).json()
            f = d["flowSegmentData"]
            free = max(float(f["freeFlowSpeed"]), 1.0)
            return max(0.0, min(1.0, 1 - float(f["currentSpeed"]) / free))
        except Exception as exc:
            log.warning("TomTom fetch failed: %s", exc)
            return None


class OpenMeteoClient:
    """Copernicus CAMS air quality plus weather from Open-Meteo (free, no key, CC BY 4.0).

    One request covers every station: coordinates are passed as comma-separated lists.
    Values are hourly model analyses on a ~10 km grid, not single-sensor readings."""

    aq_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    wx_url = "https://api.open-meteo.com/v1/forecast"
    # Same data on a separate host; used when the main one rate-limits a shared cloud IP.
    wx_url_alt = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    _aq = {"pm2_5": "pm25", "pm10": "pm10", "nitrogen_dioxide": "no2", "ozone": "o3",
           "carbon_monoxide": "co", "sulphur_dioxide": "so2"}
    _wx = {"temperature_2m": "temp", "relative_humidity_2m": "humidity",
           "wind_speed_10m": "wind_speed", "wind_direction_10m": "wind_dir"}

    @property
    def enabled(self) -> bool:
        return get_settings().open_meteo

    def _get(self, url: str, coords, past_days: int, fields, extra=None) -> list[dict] | None:
        params = {"latitude": ",".join(f"{c[0]:.4f}" for c in coords),
                  "longitude": ",".join(f"{c[1]:.4f}" for c in coords),
                  "hourly": ",".join(fields), "timezone": "GMT", **(extra or {})}
        if url == self.wx_url_alt:  # this host takes a date range instead of past_days
            from datetime import date, timedelta

            params["start_date"] = (date.today() - timedelta(days=past_days)).isoformat()
            params["end_date"] = (date.today() + timedelta(days=1)).isoformat()
        else:
            params.update(past_days=past_days, forecast_days=1)
        r = httpx.get(url, params=params, timeout=httpx.Timeout(40.0),
                      headers={"User-Agent": "vayu-aqi/1.0"})
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]

    def _get_retry(self, *args, **kw) -> list[dict]:
        import time

        for attempt in range(3):
            try:
                return self._get(*args, **kw)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt == 2:
                    raise
                time.sleep(4 * (attempt + 1))  # free tier: back off and try again
        raise RuntimeError("unreachable")

    def hourly(self, coords: list[tuple[float, float]], past_days: int):
        """Return one DataFrame per coordinate (UTC hourly index), or None on failure."""
        import pandas as pd

        if not self.enabled or not coords:
            return None
        try:
            aq = self._get_retry(self.aq_url, coords, past_days, self._aq)
        except Exception as exc:
            log.warning("Open-Meteo air quality fetch failed: %s", exc)
            return None

        # Weather changes slowly in space: fetch it once per ~25 km cell, not per station.
        cells = sorted({(round(c[0] * 4) / 4, round(c[1] * 4) / 4) for c in coords})
        weather: dict[tuple[float, float], pd.DataFrame] = {}
        for url in (self.wx_url, self.wx_url_alt):
            try:
                wx = self._get_retry(url, cells, past_days, self._wx, {"wind_speed_unit": "ms"})
                for cell, w in zip(cells, wx):
                    h = w["hourly"]
                    weather[cell] = pd.DataFrame({ours: h.get(theirs) for theirs, ours in self._wx.items()},
                                                 index=pd.to_datetime(h["time"], utc=True))
                break
            except Exception as exc:  # weather is optional; the model fills gaps
                log.warning("Open-Meteo weather fetch failed (%s): %s", url, exc)

        frames = []
        for c, loc in zip(coords, aq):
            h = loc["hourly"]
            idx = pd.to_datetime(h["time"], utc=True)
            df = pd.DataFrame({ours: h.get(theirs) for theirs, ours in self._aq.items()}, index=idx)
            df["co"] = df["co"] / 1000.0  # ug/m3 -> mg/m3, the unit CPCB breakpoints use
            wdf = weather.get((round(c[0] * 4) / 4, round(c[1] * 4) / 4))
            if wdf is not None:
                df = df.join(wdf, how="left")
            else:
                for col in self._wx.values():
                    df[col] = float("nan")
            frames.append(df.astype(float))
        return frames


def data_source() -> str:
    if OpenAQClient().enabled:
        return "openaq"
    if WAQIClient().enabled:
        return "waqi"
    if OpenMeteoClient().enabled:
        return "open-meteo"
    return "simulated"


def any_pollutant_source() -> bool:
    return data_source() != "simulated"
