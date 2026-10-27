"""Route providers.

Order of preference: Google Directions (if a key is set), then the public OSRM
servers run by FOSSGIS (routing.openstreetmap.de, separate car/bike/foot
profiles), then an offline approximation so the planner still works with no
network (clearly labelled `approximate` in the API and the UI).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class TravelMode:
    key: str
    label: str
    profile: str            # routing profile: car | bike | foot
    breathing_m3h: float    # typical inhalation rate while travelling
    infiltration: float     # in-vehicle / roadside PM2.5 ratio
    duration_factor: float  # adjustment on top of the car/bike/foot duration
    offline_kmh: float


MODES = {
    "walking": TravelMode("walking", "Walk", "foot", 1.4, 1.0, 1.0, 4.8),
    "cycling": TravelMode("cycling", "Cycle", "bike", 2.2, 1.0, 1.0, 13.0),
    "two_wheeler": TravelMode("two_wheeler", "Two-wheeler", "car", 0.9, 1.0, 0.85, 24.0),
    "auto": TravelMode("auto", "Auto rickshaw", "car", 0.7, 0.95, 1.05, 20.0),
    "bus": TravelMode("bus", "Bus", "car", 0.7, 0.85, 1.35, 15.0),
    "driving": TravelMode("driving", "Car", "car", 0.6, 0.5, 1.0, 22.0),
}


@dataclass
class Route:
    geometry: list[tuple[float, float]]  # (lat, lon)
    distance_m: float
    duration_s: float
    summary: str
    provider: str
    steps: list[dict] = field(default_factory=list)


def decode_polyline(s: str, precision: int = 5) -> list[tuple[float, float]]:
    coords, index, lat, lng = [], 0, 0, 0
    factor = 10**precision
    while index < len(s):
        for is_lng in (False, True):
            shift = result = 0
            while True:
                b = ord(s[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        coords.append((lat / factor, lng / factor))
    return coords


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


class GoogleDirections:
    url = "https://maps.googleapis.com/maps/api/directions/json"
    _mode = {"foot": "walking", "bike": "bicycling", "car": "driving"}

    def __init__(self) -> None:
        self.key = get_settings().google_maps_api_key

    def routes(self, o, d, mode: TravelMode, depart_epoch: int | None) -> list[Route] | None:
        if not self.key:
            return None
        params = {
            "origin": f"{o[0]},{o[1]}", "destination": f"{d[0]},{d[1]}",
            "mode": self._mode[mode.profile], "alternatives": "true", "key": self.key,
        }
        if mode.profile == "car" and depart_epoch:
            params["departure_time"] = depart_epoch
        try:
            data = httpx.get(self.url, params=params, timeout=12).json()
            if data.get("status") != "OK":
                log.warning("Google Directions status %s", data.get("status"))
                return None
            out = []
            for r in data["routes"]:
                leg = r["legs"][0]
                dur = leg.get("duration_in_traffic", leg["duration"])["value"]
                out.append(Route(decode_polyline(r["overview_polyline"]["points"]), leg["distance"]["value"],
                                 dur, r.get("summary") or "Route", "google"))
            return out
        except Exception as exc:
            log.warning("Google Directions failed: %s", exc)
            return None


class OSRM:
    _profile = {"car": "routed-car", "bike": "routed-bike", "foot": "routed-foot"}
    _osrm_profile = {"car": "driving", "bike": "bike", "foot": "foot"}

    def routes(self, o, d, mode: TravelMode, depart_epoch: int | None = None) -> list[Route] | None:
        base = get_settings().osrm_url.rstrip("/")
        if "openstreetmap.de" in base:
            url = f"{base}/{self._profile[mode.profile]}/route/v1/{self._osrm_profile[mode.profile]}"
        else:
            url = f"{base}/route/v1/{self._osrm_profile[mode.profile]}"
        url += f"/{o[1]},{o[0]};{d[1]},{d[0]}"
        try:
            data = httpx.get(url, params={"alternatives": 3, "overview": "full", "geometries": "polyline",
                                          "steps": "false"}, timeout=12,
                             headers={"User-Agent": "vayu-aqi/1.0"}).json()
            if data.get("code") != "Ok":
                return None
            out = []
            for r in data["routes"]:
                names = [leg.get("summary") for leg in r.get("legs", []) if leg.get("summary")]
                out.append(Route(decode_polyline(r["geometry"]), r["distance"], r["duration"],
                                 names[0] if names else "Route", "osrm"))
            return out
        except Exception as exc:
            log.info("OSRM unavailable: %s", exc)
            return None


class OfflineApprox:
    """Three plausible corridors: direct, bowed left, bowed right. Used only when
    no routing service is reachable."""

    def routes(self, o, d, mode: TravelMode, depart_epoch: int | None = None) -> list[Route]:
        straight = haversine_m(o, d)
        out = []
        for name, bow in (("Direct corridor", 0.0), ("Northern corridor", 0.18), ("Southern corridor", -0.18)):
            pts = []
            n = max(12, int(straight / 250))
            # Perpendicular offset for a quadratic Bezier control point.
            mid = ((o[0] + d[0]) / 2, (o[1] + d[1]) / 2)
            dx, dy = d[1] - o[1], d[0] - o[0]
            ctrl = (mid[0] + bow * dx, mid[1] - bow * dy)
            for i in range(n + 1):
                t = i / n
                lat = (1 - t) ** 2 * o[0] + 2 * (1 - t) * t * ctrl[0] + t**2 * d[0]
                lon = (1 - t) ** 2 * o[1] + 2 * (1 - t) * t * ctrl[1] + t**2 * d[1]
                pts.append((lat, lon))
            dist = sum(haversine_m(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) * 1.25
            out.append(Route(pts, dist, dist / 1000 / mode.offline_kmh * 3600, name, "approximate"))
        return out


def find_routes(origin, dest, mode_key: str, depart_epoch: int | None = None) -> list[Route]:
    mode = MODES.get(mode_key, MODES["driving"])
    for provider in (GoogleDirections(), OSRM()):
        routes = provider.routes(origin, dest, mode, depart_epoch)
        if routes:
            for r in routes:
                r.duration_s *= mode.duration_factor
            return routes[:3]
    return OfflineApprox().routes(origin, dest, mode)
