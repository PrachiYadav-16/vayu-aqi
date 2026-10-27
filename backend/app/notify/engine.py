"""Alert rules.

1. Location breach: the user's latest known location (last 2 h) is above their
   personal threshold now, or will be within the next 3 hours.
2. Trip advisory: a saved trip departs in the next 3 hours (or repeats today)
   and its cleanest option still crosses the threshold, or a meaningfully
   better route / departure time exists.

Each (user, kind, subject) pair has a cooldown so people are not spammed, and
quiet hours suppress the push (the alert is still stored).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.aqi.health import advice_for, personal_threshold
from app import insights
from app.i18n import fmt_time, t
from app.config import get_settings
from app.db import SessionLocal
from app.forecast.service import get_forecast_service
from app.models import Alert, DeviceToken, LocationPing, Trip, User
from app.notify import fcm
from app.routing.advisor import assess

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def _recent_alert(db: Session, user_id: int, kind: str, subject: str, cooldown_min: int) -> bool:
    since = datetime.now(timezone.utc) - timedelta(minutes=cooldown_min)
    rows = db.scalars(select(Alert).where(Alert.user_id == user_id, Alert.kind == kind,
                                          Alert.created_at >= since)).all()
    return any(r.data.get("subject") == subject for r in rows)


def _in_quiet_hours(user: User, now: datetime) -> bool:
    if user.quiet_start_hour is None or user.quiet_end_hour is None:
        return False
    h = now.astimezone(IST).hour
    s, e = user.quiet_start_hour, user.quiet_end_hour
    return (s <= h < e) if s < e else (h >= s or h < e)


def create_alert(db: Session, user: User, kind: str, severity: str, title: str, body: str, data: dict) -> Alert:
    alert = Alert(user_id=user.id, kind=kind, severity=severity, title=title, body=body, data=data)
    db.add(alert)
    db.flush()
    now = datetime.now(timezone.utc)
    if user.notify_push and not _in_quiet_hours(user, now):
        tokens = [t.token for t in db.scalars(select(DeviceToken).where(DeviceToken.user_id == user.id)).all()]
        bad = fcm.send(tokens, title, body, {"alert_id": alert.id, "kind": kind, "link": "/alerts"})
        alert.delivered_push = bool(tokens) and fcm.push_enabled()
        if bad:
            db.execute(delete(DeviceToken).where(DeviceToken.token.in_(bad)))
    return alert


def check_location(db: Session, user: User, now: datetime) -> Alert | None:
    if not user.location_consent:
        return None
    ping = db.scalars(select(LocationPing).where(LocationPing.user_id == user.id,
                                                 LocationPing.ts >= now - timedelta(hours=2))
                      .order_by(LocationPing.ts.desc()).limit(1)).first()
    if ping is None:
        return None
    pf = get_forecast_service().point_forecast(ping.lat, ping.lon)
    if pf is None or pf["coverage"] == "outside":
        return None
    threshold = personal_threshold(user.sensitivity, user.custom_threshold)
    next3 = pf["hours"][:3]
    peak = max([pf["current_aqi"]] + [h["aqi"] for h in next3])
    if peak <= threshold:
        return None
    subject = f"loc:{round(ping.lat, 2)},{round(ping.lon, 2)}"
    if _recent_alert(db, user.id, "location_breach", subject, get_settings().alert_cooldown_minutes):
        return None
    now_over = pf["current_aqi"] > threshold
    lang = user.language or "en"
    adv = advice_for(peak, user.sensitivity, user.custom_threshold, lang)
    if now_over:
        title = t(lang, "alert.loc_now_title", aqi=pf["current_aqi"])
        body = f"{adv.headline} {adv.actions[0] if adv.actions else ''}"
    else:
        first = next(h for h in next3 if h["aqi"] > threshold)
        title = t(lang, "alert.loc_soon_title", aqi=first["aqi"], time=fmt_time(lang, datetime.fromisoformat(first["ts"])))
        body = t(lang, "alert.loc_soon_body", t=threshold)
    severity = "critical" if peak > 300 else "warning"
    return create_alert(db, user, "location_breach", severity, title, body.strip(),
                        {"subject": subject, "lat": ping.lat, "lon": ping.lon, "peak_aqi": peak})


def _utc(ts: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything is stored in UTC.
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _next_departure(trip: Trip, now: datetime) -> datetime | None:
    depart = _utc(trip.depart_at)
    if not trip.repeat_weekdays:
        return depart if depart >= now - timedelta(minutes=10) else None
    local_now = now.astimezone(IST)
    dep_local = depart.astimezone(IST)
    for add in range(0, 8):
        day = local_now.date() + timedelta(days=add)
        if day.weekday() in trip.repeat_weekdays:
            cand = datetime.combine(day, dep_local.timetz()).astimezone(timezone.utc)
            if cand >= now - timedelta(minutes=10):
                return cand
    return None


def check_trip(db: Session, user: User, trip: Trip, now: datetime) -> Alert | None:
    if not user.notify_trip_advisories:
        return None
    dep = _next_departure(trip, now)
    if dep is None or dep - now > timedelta(hours=3):
        return None
    lang = user.language or "en"
    result = assess((trip.origin_lat, trip.origin_lon), (trip.dest_lat, trip.dest_lon), dep, trip.mode,
                    user.sensitivity, user.custom_threshold, lang)
    trip.last_assessment = {k: v for k, v in result.items() if k != "routes"} | {
        "routes": [{k: v for k, v in r.items() if k not in ("geometry", "strip")} for r in result["routes"]]
    }
    subject = f"trip:{trip.id}:{dep.date().isoformat()}"
    if _recent_alert(db, user.id, "trip_advisory", subject, 24 * 60):
        return None
    if result["verdict"] == "go" and not result["suggestions"]:
        return None
    best = next(r for r in result["routes"] if r["id"] == result["recommended_route_id"])
    when = fmt_time(lang, dep, minutes=True)
    name = trip.label or t(lang, "trip.default_name", a=trip.origin_name.split(",")[0], b=trip.dest_name.split(",")[0])
    title = t(lang, "alert.trip_title", name=name, time=when, aqi=best["peak_aqi"])
    body = result["suggestions"][0]["text"] if result["suggestions"] else result["headline"]
    severity = "critical" if result["verdict"] == "reconsider" else "warning" if result["verdict"] == "caution" else "info"
    return create_alert(db, user, "trip_advisory", severity, title, body,
                        {"subject": subject, "trip_id": trip.id, "depart_at": dep.isoformat()})


def _brief_place(db: Session, user: User, now: datetime) -> tuple[float, float] | None:
    if user.location_consent:
        ping = db.scalars(select(LocationPing).where(LocationPing.user_id == user.id,
                                                     LocationPing.ts >= now - timedelta(hours=18))
                          .order_by(LocationPing.ts.desc()).limit(1)).first()
        if ping:
            return ping.lat, ping.lon
    if user.home_lat is not None and user.home_lon is not None:
        return user.home_lat, user.home_lon
    return None


def check_daily_brief(db: Session, user: User, now: datetime, force: bool = False) -> Alert | None:
    """Morning summary: today's AQI range, when to open windows, when to run the
    purifier, and the day's cigarette equivalent. Sent once per day at brief_hour."""
    if not user.notify_daily_brief and not force:
        return None
    local = now.astimezone(IST)
    if not force and local.hour != (user.brief_hour or 7):
        return None
    subject = f"brief:{local.date().isoformat()}"
    if not force and _recent_alert(db, user.id, "daily_brief", subject, 20 * 60):
        return None
    place = _brief_place(db, user, now)
    if place is None:
        return None
    pf = get_forecast_service().point_forecast(*place)
    if pf is None or pf["coverage"] == "outside":
        return None
    lang = user.language or "en"
    day = pf["hours"][:16]
    lo, hi = min(h["aqi"] for h in day), max(h["aqi"] for h in day)
    home = insights.window_advice(pf["hours"], lang)
    budget = insights.day_budget(now, [], pf["current_aqi"], pf["hours"])
    body = " ".join(filter(None, [home["windows"]["text"] if home else "",
                                  home["purifier"]["text"] if home and home["purifier"]["action"] == "run" else "",
                                  t(lang, "brief.cigs", cig=round(budget["cigarettes_projected"], 1))]))
    threshold = personal_threshold(user.sensitivity, user.custom_threshold)
    severity = "warning" if hi > threshold else "info"
    return create_alert(db, user, "daily_brief", severity, t(lang, "brief.title", lo=lo, hi=hi), body,
                        {"subject": subject, "home": home, "cigarettes": budget["cigarettes_projected"]})


def run_checks(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    created = 0
    with SessionLocal() as db:
        users = db.scalars(select(User)).all()
        for u in users:
            try:
                if check_location(db, u, now):
                    created += 1
                if check_daily_brief(db, u, now):
                    created += 1
                for trip in u.trips:
                    if check_trip(db, u, trip, now):
                        created += 1
            except Exception as exc:
                log.exception("Alert check failed for user %s: %s", u.id, exc)
        # Retention: drop old location history.
        cutoff = now - timedelta(days=get_settings().location_retention_days)
        db.execute(delete(LocationPing).where(LocationPing.ts < cutoff))
        db.commit()
    return {"alerts_created": created, "users_checked": len(users)}
