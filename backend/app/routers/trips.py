from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Trip, User
from app.routing.advisor import assess
from app.routing.providers import MODES
from app.schemas import AssessIn, TripIn, TripOut
from app.security import current_user

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("/modes")
def modes():
    return [{"key": m.key, "label": m.label} for m in MODES.values()]


@router.post("/assess")
def assess_trip(body: AssessIn, user: User = Depends(current_user)):
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
    trip = Trip(user_id=user.id, label=body.label, origin_name=body.origin.name, origin_lat=body.origin.lat,
                origin_lon=body.origin.lon, dest_name=body.destination.name, dest_lat=body.destination.lat,
                dest_lon=body.destination.lon, depart_at=body.depart_at, mode=body.mode,
                repeat_weekdays=body.repeat_weekdays)
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
