"""Human-scale numbers on top of the forecast.

Cigarette equivalent
    Berkeley Earth's rule of thumb: breathing air with 22 ug/m3 of PM2.5 for a
    day is roughly as harmful as smoking one cigarette. With an adult inhaling
    about 18 m3 of air a day, that is 22 * 18 = 396 ug of PM2.5 per cigarette.

Daily budget
    The WHO 2021 guideline for 24-hour PM2.5 is 15 ug/m3, i.e. 15 * 18 = 270 ug
    inhaled per day. Everything is reported against that.

Both are approximations meant for comparison and motivation, not diagnosis.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.aqi.naqi import pm25_for_aqi
from app.i18n import IST, fmt_time, t

INHALED_M3_PER_DAY = 18.0
BREATHING_M3_PER_H = INHALED_M3_PER_DAY / 24
UG_PER_CIGARETTE = 22.0 * INHALED_M3_PER_DAY        # 396 ug
WHO_DAILY_BUDGET_UG = 15.0 * INHALED_M3_PER_DAY     # 270 ug
WINDOW_OK_AQI = 100
WINDOW_SHORT_AQI = 150
PURIFIER_AQI = 150


def cigarettes(dose_ug: float) -> float:
    return round(dose_ug / UG_PER_CIGARETTE, 2)


def dose_for(aqi: float, hours: float, breathing: float = BREATHING_M3_PER_H, infiltration: float = 1.0) -> float:
    return pm25_for_aqi(aqi) * breathing * infiltration * hours


def day_budget(now: datetime, pings: list[tuple[datetime, int]], current_aqi: float,
               hours: list[dict]) -> dict:
    """Today's (IST) outdoor-air dose: tracked pings for the past, the current
    estimate for untracked past hours, and the forecast for the rest of the day."""
    local_now = now.astimezone(IST)
    midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    end = midnight + timedelta(days=1)

    tracked_ug, tracked_h = 0.0, 0.0
    for i, (ts, aqi) in enumerate(pings):
        nxt = pings[i + 1][0] if i + 1 < len(pings) else min(now, ts + timedelta(minutes=30))
        h = min(max((nxt - ts).total_seconds() / 3600, 0), 1.0)
        tracked_ug += dose_for(aqi, h)
        tracked_h += h
    past_h = max((now - midnight).total_seconds() / 3600, 0)
    untracked_ug = dose_for(current_aqi, max(past_h - tracked_h, 0))
    used = tracked_ug + untracked_ug

    rest = 0.0
    for hdict in hours:
        ts = datetime.fromisoformat(hdict["ts"])
        if now < ts <= end:
            rest += dose_for(hdict["aqi"], 1.0)
    projected = used + rest
    return {
        "budget_ug": WHO_DAILY_BUDGET_UG,
        "used_ug": round(used, 1),
        "projected_ug": round(projected, 1),
        "used_pct": round(100 * used / WHO_DAILY_BUDGET_UG),
        "projected_pct": round(100 * projected / WHO_DAILY_BUDGET_UG),
        "cigarettes_used": cigarettes(used),
        "cigarettes_projected": cigarettes(projected),
        "tracked_hours": round(tracked_h, 1),
        "estimated": tracked_h < past_h * 0.5,
    }


def _best_window(hours: list[dict], width: int, pick_min: bool, waking_only: bool) -> tuple[int, float] | None:
    """Start index and mean AQI of the cleanest (or dirtiest) run of `width` hours."""
    best = None
    for i in range(0, len(hours) - width + 1):
        block = hours[i:i + width]
        if waking_only:
            local_hours = [datetime.fromisoformat(h["ts"]).astimezone(IST).hour for h in block]
            if any(h < 6 or h > 22 for h in local_hours):
                continue
        mean = sum(h["aqi"] for h in block) / width
        if best is None or (mean < best[1] if pick_min else mean > best[1]):
            best = (i, mean)
    return best


def window_advice(hours: list[dict], lang: str = "en") -> dict | None:
    """When to air out the home and when to run a purifier, over the next 24 hours."""
    if len(hours) < 4:
        return None
    clean = _best_window(hours, 2, pick_min=True, waking_only=True) or _best_window(hours, 2, True, False)
    dirty = _best_window(hours, 3, pick_min=False, waking_only=False)
    i, aqi = clean
    start = datetime.fromisoformat(hours[i]["ts"])
    stop = start + timedelta(hours=2)
    params = {"from": fmt_time(lang, start), "to": fmt_time(lang, stop), "aqi": round(aqi)}
    if aqi <= WINDOW_OK_AQI:
        windows = {"action": "open", "text": t(lang, "win.open", **params)}
    elif aqi <= WINDOW_SHORT_AQI:
        windows = {"action": "brief", "text": t(lang, "win.short", **params)}
    else:
        windows = {"action": "closed", "text": t(lang, "win.closed", **params)}
    windows.update({"from": start.isoformat(), "to": stop.isoformat(), "aqi": round(aqi)})

    j, peak = dirty
    p_start = datetime.fromisoformat(hours[j]["ts"])
    p_stop = p_start + timedelta(hours=3)
    if peak > PURIFIER_AQI:
        purifier = {"action": "run", "from": p_start.isoformat(), "to": p_stop.isoformat(), "aqi": round(peak),
                    "text": t(lang, "pur.run", **{"from": fmt_time(lang, p_start), "to": fmt_time(lang, p_stop),
                                                  "aqi": round(peak)})}
    else:
        purifier = {"action": "optional", "aqi": PURIFIER_AQI,
                    "text": t(lang, "pur.optional", aqi=PURIFIER_AQI)}
    return {"windows": windows, "purifier": purifier}


def explain(effects: list[dict] | None, current: float, hours: list[dict], lang: str = "en") -> dict | None:
    if not hours:
        return None
    nxt = sum(h["aqi"] for h in hours[:6]) / min(6, len(hours))
    change = nxt - current
    trend = "up" if change > max(5, 0.06 * current) else "down" if change < -max(5, 0.06 * current) else "flat"
    out = {"trend": trend, "change": round(change), "summary": t(lang, f"exp.trend_{trend}"), "factors": []}
    if not effects:
        return out
    scale = max(5.0, 0.04 * max(current, 50))
    for e in effects:
        if abs(e["effect"]) < scale:
            continue
        direction = "up" if e["effect"] > 0 else "down"
        out["factors"].append({"factor": e["factor"], "direction": direction, "effect": round(e["effect"]),
                               "text": t(lang, f"exp.{e['factor']}.{direction}")})
        if len(out["factors"]) == 3:
            break
    return out
