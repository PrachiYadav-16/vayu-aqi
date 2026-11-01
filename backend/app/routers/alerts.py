from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, User
from app.notify.engine import check_daily_brief, check_location, check_trip, trip_is_due
from app.schemas import AlertOut
from app.security import current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(limit: int = Query(50, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).where(Alert.user_id == user.id)
                      .order_by(Alert.created_at.desc()).limit(limit)).all()
    unread = db.scalar(select(func.count()).select_from(Alert)
                       .where(Alert.user_id == user.id, Alert.read.is_(False)))
    return {"unread": unread, "alerts": [AlertOut.model_validate(r) for r in rows]}


@router.post("/read-all", status_code=204)
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Alert).where(Alert.user_id == user.id).values(read=True))
    db.commit()


@router.post("/{alert_id}/read", status_code=204)
def read_one(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Alert).where(Alert.user_id == user.id, Alert.id == alert_id).values(read=True))
    db.commit()


@router.post("/brief-now")
def brief_now(lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Send today's air brief immediately (preview of the morning notification).
    Uses the home location or recent shared location, else the position the app
    passes in for this one request (not stored)."""
    place = (lat, lon) if lat is not None and lon is not None else None
    a = check_daily_brief(db, user, datetime.now(timezone.utc), force=True, fallback_place=place)
    db.commit()
    reason = None if a else ("no_place" if place is None and user.home_lat is None else "outside")
    return {"created": [AlertOut.model_validate(a)] if a else [], "reason": reason}


@router.post("/check-now")
def check_now(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Run this user's alert rules immediately (used after saving a trip and in demos)."""
    now = datetime.now(timezone.utc)
    created = []
    a = check_location(db, user, now)
    if a:
        created.append(a)
    due = 0
    for trip in user.trips:
        if trip_is_due(trip, now):
            due += 1
        t = check_trip(db, user, trip, now)
        if t:
            created.append(t)
    db.commit()
    return {"created": [AlertOut.model_validate(a) for a in created], "trips": len(user.trips), "trips_due": due}
