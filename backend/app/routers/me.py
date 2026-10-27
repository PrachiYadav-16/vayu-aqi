from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.aqi.health import SENSITIVITY_GROUPS, advice_for, personal_threshold
from app.db import get_db
from app.forecast.service import get_forecast_service
from app.models import DeviceToken, LocationPing, User
from app.schemas import DeviceIn, PingIn, ProfileIn, ProfileOut
from app.security import current_user

router = APIRouter(prefix="/api/me", tags=["me"])
IST = timezone(timedelta(hours=5, minutes=30))


def _profile(u: User) -> ProfileOut:
    return ProfileOut(
        id=u.id, email=u.email, name=u.name, sensitivity=u.sensitivity or [],
        custom_threshold=u.custom_threshold, threshold=personal_threshold(u.sensitivity, u.custom_threshold),
        home_lat=u.home_lat, home_lon=u.home_lon, location_consent=u.location_consent,
        notify_push=u.notify_push, notify_trip_advisories=u.notify_trip_advisories,
        quiet_start_hour=u.quiet_start_hour, quiet_end_hour=u.quiet_end_hour,
    )


@router.get("", response_model=ProfileOut)
def me(user: User = Depends(current_user)):
    return _profile(user)


@router.patch("", response_model=ProfileOut)
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if data.pop("clear_custom_threshold", False):
        user.custom_threshold = None
    for k, v in data.items():
        setattr(user, k, v)
    if body.location_consent is False:
        # Withdrawing consent deletes stored location history.
        db.execute(delete(LocationPing).where(LocationPing.user_id == user.id))
    db.commit()
    return _profile(user)


@router.get("/sensitivity-groups")
def groups():
    return [{"key": k, "label": v[0], "threshold": v[1]} for k, v in SENSITIVITY_GROUPS.items()]


@router.get("/here")
def here(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
         user: User = Depends(current_user)):
    """Point forecast plus advice for this user's health profile."""
    pf = get_forecast_service().point_forecast(lat, lon)
    if pf is None:
        return None
    threshold = personal_threshold(user.sensitivity, user.custom_threshold)
    now_adv = advice_for(pf["current_aqi"], user.sensitivity, user.custom_threshold)
    upcoming = [h for h in pf["hours"][:12] if h["aqi"] > threshold]
    cleanest = min(pf["hours"][:12], key=lambda h: h["aqi"])
    pf["advice"] = {"level": now_adv.level, "headline": now_adv.headline, "actions": now_adv.actions,
                    "threshold": threshold,
                    "next_breach": upcoming[0] if upcoming else None,
                    "cleanest_hour": cleanest}
    return pf


@router.post("/location", status_code=201)
def ping(body: PingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.location_consent:
        return {"stored": False, "reason": "Location sharing is off in your settings"}
    pf = get_forecast_service().point_forecast(body.lat, body.lon)
    aqi = pf["current_aqi"] if pf and pf["coverage"] != "outside" else None
    # Store at most one ping per 10 minutes to keep history light.
    last = db.scalars(select(LocationPing).where(LocationPing.user_id == user.id)
                      .order_by(LocationPing.ts.desc()).limit(1)).first()
    now = datetime.now(timezone.utc)
    last_ts = last.ts.replace(tzinfo=timezone.utc) if last and last.ts.tzinfo is None else (last.ts if last else None)
    if last_ts and now - last_ts < timedelta(minutes=10):
        last.lat, last.lon, last.aqi, last.accuracy_m, last.ts = body.lat, body.lon, aqi, body.accuracy_m, now
    else:
        db.add(LocationPing(user_id=user.id, lat=body.lat, lon=body.lon, accuracy_m=body.accuracy_m, aqi=aqi, ts=now))
    db.commit()
    return {"stored": True, "aqi": aqi}


@router.delete("/location", status_code=204)
def clear_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(LocationPing).where(LocationPing.user_id == user.id))
    db.commit()


@router.get("/exposure")
def exposure(days: int = Query(14, ge=1, le=30), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Daily exposure summary from location history: each ping counts for the time
    until the next ping (capped at 1 hour)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pings = db.scalars(select(LocationPing).where(LocationPing.user_id == user.id, LocationPing.ts >= since,
                                                  LocationPing.aqi.is_not(None))
                       .order_by(LocationPing.ts)).all()
    threshold = personal_threshold(user.sensitivity, user.custom_threshold)
    per_day: dict[str, dict] = defaultdict(lambda: {"weighted": 0.0, "minutes": 0.0, "above": 0.0, "peak": 0})
    for i, p in enumerate(pings):
        ts = p.ts if p.ts.tzinfo else p.ts.replace(tzinfo=timezone.utc)
        nxt = pings[i + 1].ts if i + 1 < len(pings) else ts + timedelta(minutes=30)
        nxt = nxt if nxt.tzinfo else nxt.replace(tzinfo=timezone.utc)
        mins = min((nxt - ts).total_seconds() / 60, 60)
        d = per_day[ts.astimezone(IST).date().isoformat()]
        d["weighted"] += p.aqi * mins
        d["minutes"] += mins
        d["peak"] = max(d["peak"], p.aqi)
        if p.aqi > threshold:
            d["above"] += mins
    out = []
    for day in sorted(per_day):
        d = per_day[day]
        out.append({"date": day, "avg_aqi": round(d["weighted"] / d["minutes"]) if d["minutes"] else None,
                    "peak_aqi": d["peak"], "tracked_minutes": round(d["minutes"]),
                    "minutes_above_threshold": round(d["above"])})
    return {"threshold": threshold, "days": out, "pings": len(pings)}


@router.post("/devices", status_code=201)
def register_device(body: DeviceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == body.token))
    if existing:
        existing.user_id = user.id
    else:
        db.add(DeviceToken(user_id=user.id, token=body.token, platform=body.platform))
    db.commit()
    return {"registered": True}


@router.delete("/devices/{token}", status_code=204)
def remove_device(token: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(DeviceToken).where(DeviceToken.user_id == user.id, DeviceToken.token == token))
    db.commit()
