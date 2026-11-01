"""Place search: Google Geocoding, Nominatim, then a small offline gazetteer."""

from __future__ import annotations

import logging
import threading
import time

import httpx

from app.config import get_settings
from app.ingest.stations import SEED_STATIONS

log = logging.getLogger(__name__)

_GAZETTEER = [
    ("Connaught Place, New Delhi", 28.6315, 77.2167),
    ("India Gate, New Delhi", 28.6129, 77.2295),
    ("Indira Gandhi International Airport, Delhi", 28.5562, 77.1000),
    ("Noida Sector 18", 28.5708, 77.3261),
    ("Gurugram Cyber City", 28.4950, 77.0890),
    ("MG Road, Bengaluru", 12.9756, 77.6050),
    ("Electronic City, Bengaluru", 12.8452, 77.6602),
    ("Koramangala, Bengaluru", 12.9352, 77.6245),
    ("Indiranagar, Bengaluru", 12.9784, 77.6408),
    ("Kempegowda International Airport, Bengaluru", 13.1986, 77.7066),
    ("Majestic, Bengaluru", 12.9767, 77.5713),
    ("Infosys Mysuru Campus", 12.3584, 76.5956),
    ("Mysuru Palace", 12.3052, 76.6552),
    ("Mysuru Junction railway station", 12.3165, 76.6456),
    ("Chamundi Hill, Mysuru", 12.2724, 76.6730),
    ("Chhatrapati Shivaji Maharaj Terminus, Mumbai", 18.9398, 72.8355),
    ("Bandra Kurla Complex, Mumbai", 19.0660, 72.8680),
    ("Powai, Mumbai", 19.1176, 72.9060),
    ("Mumbai Airport", 19.0896, 72.8656),
]


def _offline(q: str, limit: int) -> list[dict]:
    ql = q.lower().strip()
    places = list(_GAZETTEER) + [(f"{s[1]}, {s[2]}", s[3], s[4]) for s in SEED_STATIONS]
    hits = [p for p in places if all(tok in p[0].lower() for tok in ql.split())]
    return [{"name": n, "lat": la, "lon": lo, "source": "offline"} for n, la, lo in hits[:limit]]


_UA = {"User-Agent": "vayu-aqi/1.0 (+https://vayu-aqi.onrender.com)"}
_cache: dict[tuple, tuple[float, object]] = {}
_CACHE_TTL = 24 * 3600
_nominatim_lock = threading.Lock()
_nominatim_last = 0.0


def _cached(key: tuple, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    val = fn()
    if val:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[key] = (time.time(), val)
    return val


def _nominatim(path: str, params: dict) -> object:
    """Nominatim's usage policy allows at most one request per second."""
    global _nominatim_last
    with _nominatim_lock:
        wait = 1.0 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        _nominatim_last = time.monotonic()
    return httpx.get(f"{get_settings().nominatim_url}{path}", params=params, timeout=8, headers=_UA).json()


def reverse(lat: float, lon: float) -> str | None:
    """Short human name for a coordinate, e.g. "Koramangala, Bengaluru"."""
    def fetch():
        try:
            d = _nominatim("/reverse", {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16})
            a = d.get("address", {})
            local = a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("road")
            city = a.get("city") or a.get("town") or a.get("county") or a.get("state_district")
            name = ", ".join(x for x in (local, city) if x)
            return name or d.get("display_name")
        except Exception as exc:
            log.info("Reverse geocoding unavailable: %s", exc)
            return None
    return _cached(("rev", round(lat, 4), round(lon, 4)), fetch)


def search(q: str, limit: int = 6, near: tuple[float, float] | None = None) -> list[dict]:
    key = ("q", q.strip().lower(), limit, tuple(round(x, 1) for x in near) if near else None)
    return _cached(key, lambda: _search(q, limit, near)) or []


def _search(q: str, limit: int = 6, near: tuple[float, float] | None = None) -> list[dict]:
    s = get_settings()
    if s.google_maps_api_key:
        try:
            params = {"address": q, "key": s.google_maps_api_key, "components": "country:IN"}
            data = httpx.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=8).json()
            res = [{"name": r["formatted_address"], "lat": r["geometry"]["location"]["lat"],
                    "lon": r["geometry"]["location"]["lng"], "source": "google"} for r in data.get("results", [])]
            if res:
                return res[:limit]
        except Exception as exc:
            log.warning("Google geocoding failed: %s", exc)
    try:
        params = {"q": q, "format": "jsonv2", "countrycodes": "in", "limit": limit}
        if near:
            lat, lon = near
            params["viewbox"] = f"{lon - 0.6},{lat + 0.6},{lon + 0.6},{lat - 0.6}"
        res = [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"]), "source": "osm"}
               for x in _nominatim("/search", params)]
        if res:
            return res
    except Exception as exc:
        log.info("Nominatim unavailable: %s", exc)
    return _offline(q, limit)
