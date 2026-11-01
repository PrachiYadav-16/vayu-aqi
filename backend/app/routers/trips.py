from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Trip, User
from app.notify.engine import compact_assessment
from app.routing.advisor import assess
from app.routing.providers import MODES
from app.schemas import AssessIn, TripIn, TripOut
from app.security import current_user

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("/modes")
def modes():
    return [{"key": m.key, "label": m.label} for m in MODES.values()]


MAX_TRIP_KM = 150


def _check_trip_scope(body: AssessIn, for_forecast: bool) -> None:
    """Reject trips Vayu cannot judge honestly instead of returning made-up numbers."""
    from app.forecast.service import get_forecast_service
    from app.routing.providers import haversine_m

    o, d = (body.origin.lat, body.origin.lon), (body.destination.lat, body.destination.lon)
    if haversine_m(o, d) > MAX_TRIP_KM * 1000:
        raise HTTPException(422, f"Vayu plans trips within a city region (up to {MAX_TRIP_KM} km).")
    if haversine_m(o, d) < 100:
        raise HTTPException(422, "Start and destination are the same place.")
    pts = get_forecast_service().points_forecast([o[0], d[0]], [o[1], d[1]])
    if pts and all(p is not None and p["coverage"] == "outside" for p in pts):
        raise HTTPException(422, "This trip is outside the cities Vayu covers, so there is no reliable air data for it.")
    if for_forecast:
        ahead = body.depart_at - datetime.now(timezone.utc)
        if ahead > timedelta(hours=25):
            raise HTTPException(422, "Forecasts reach 24 hours ahead. Pick a time within the next day.")


@router.post("/assess")
def assess_trip(body: AssessIn, user: User = Depends(current_user)):
    _check_trip_scope(body, for_forecast=True)
    try:
        return assess((body.origin.lat, body.origin.lon), (body.destination.lat, body.destination.lon),
                      body.depart_at, body.mode, user.sensitivity, user.custom_threshold,
                      user.language or "en")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.get("", response_model=list[TripOut])
def list_trips(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.depart_at)).all()


@router.post("", response_model=TripOut, status_code=201)
def save_trip(body: TripIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check_trip_scope(body, for_forecast=False)
    now = datetime.now(timezone.utc)
    depart = body.depart_at if body.depart_at.tzinfo else body.depart_at.replace(tzinfo=timezone.utc)
    if not body.repeat_weekdays and depart < now - timedelta(minutes=10):
        raise HTTPException(422, "That time has already passed. Pick a future time or repeat days.")
    trip = Trip(user_id=user.id, label=body.label, origin_name=body.origin.name, origin_lat=body.origin.lat,
                origin_lon=body.origin.lon, dest_name=body.destination.name, dest_lat=body.destination.lat,
                dest_lon=body.destination.lon, depart_at=body.depart_at, mode=body.mode,
                repeat_weekdays=body.repeat_weekdays)
    # Keep the latest verdict with the trip so the list can show it right away.
    if depart - now <= timedelta(hours=24):
        try:
            trip.last_assessment = compact_assessment(assess(
                (trip.origin_lat, trip.origin_lon), (trip.dest_lat, trip.dest_lon), max(depart, now), trip.mode,
                user.sensitivity, user.custom_threshold, user.language or "en"))
        except Exception:
            pass  # saving must not fail because a routing service is slow
    db.add(trip)
    db.commit()
    return trip


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip or trip.user_id != user.id:
        raise HTTPException(404, "Trip not found")
    db.delete(trip)
    db.commit()
