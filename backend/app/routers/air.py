import numpy as np
from fastapi import APIRouter, HTTPException, Query

from app.aqi.naqi import CATEGORIES, POLLUTANT_LABELS, category_for
from app.forecast.service import get_forecast_service
from app.forecast.spatial import SEARCH_RADIUS_KM, interpolate
from app.ingest.sources import any_pollutant_source
from app.notify.fcm import push_enabled
from app.routing import geocode

router = APIRouter(prefix="/api/air", tags=["air quality"])


def _need_data():
    sf = get_forecast_service().station_forecasts()
    if sf is None:
        raise HTTPException(503, "No readings ingested yet. Run `python -m scripts.seed` or wait for the first ingest.")
    return sf


@router.get("/meta")
def meta():
    svc = get_forecast_service()
    sf = svc.station_forecasts()
    return {
        "categories": [{"key": c.key, "label": c.label, "low": c.low, "high": c.high, "color": c.color,
                        "impact": c.impact} for c in CATEGORIES],
        "pollutants": POLLUTANT_LABELS,
        "data_mode": "live" if any_pollutant_source() else "simulated",
        "push_enabled": push_enabled(),
        "latest_reading": sf.issued_at.isoformat() if sf else None,
        "model": svc.model_info,
        "cities": sorted(set(sf.cities)) if sf else [],
    }


@router.get("/stations")
def stations(hour: int = Query(0, ge=0, le=24)):
    """All stations with current AQI, or the forecast `hour` hours ahead."""
    sf = _need_data()
    out = []
    for i, sid in enumerate(sf.station_ids):
        aqi = sf.current_aqi[i] if hour == 0 else sf.quantiles[i, hour - 1, 1]
        out.append({
            "id": sid, "name": sf.names[i], "city": sf.cities[i],
            "lat": float(sf.lat[i]), "lon": float(sf.lon[i]),
            "aqi": round(float(aqi)), "category": category_for(aqi).key,
            "next_24h": [round(float(v)) for v in sf.quantiles[i, :, 1]],
        })
    return {"issued_at": sf.issued_at.isoformat(), "hour": hour, "stations": out}


@router.get("/stations/{station_id}")
def station(station_id: str):
    sf = _need_data()
    if station_id not in sf.station_ids:
        raise HTTPException(404, "Station not found")
    i = sf.station_ids.index(station_id)
    pf = get_forecast_service().point_forecast(float(sf.lat[i]), float(sf.lon[i]))
    pf["station"] = {"id": station_id, "name": sf.names[i], "city": sf.cities[i]}
    return pf


@router.get("/point")
def point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    _need_data()
    return get_forecast_service().point_forecast(lat, lon)


@router.get("/grid")
def grid(south: float, west: float, north: float, east: float, hour: int = Query(0, ge=0, le=24),
         cells: int = Query(28, ge=6, le=48)):
    """Coarse interpolated AQI surface for the map overlay. Cells beyond the
    station search radius come back as null so the map does not invent data."""
    sf = _need_data()
    if north <= south or east <= west or (north - south) > 3 or (east - west) > 3:
        raise HTTPException(422, "Zoom in further to see the pollution surface")
    lats = np.linspace(south, north, cells)
    lons = np.linspace(west, east, cells)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    field = sf.current_aqi if hour == 0 else sf.quantiles[:, hour - 1, 1]
    est = interpolate(LA.ravel(), LO.ravel(), sf.lat, sf.lon, field, method="idw")  # IDW keeps local hotspots visible
    vals = np.where(est.nearest_km <= SEARCH_RADIUS_KM * 0.6, est.value, np.nan).reshape(cells, cells)
    return {
        "south": south, "west": west, "north": north, "east": east, "rows": cells, "cols": cells,
        "hour": hour,
        "values": [[None if np.isnan(v) else round(float(v)) for v in row] for row in vals],
    }


@router.get("/places")
def places(q: str = Query(..., min_length=2, max_length=120), lat: float | None = None, lon: float | None = None):
    near = (lat, lon) if lat is not None and lon is not None else None
    return geocode.search(q, near=near)
