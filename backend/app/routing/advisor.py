"""Turn route exposure numbers into a recommendation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.aqi.health import advice_for, personal_threshold
from app.aqi.naqi import category_for
from app.routing.exposure import prepare, score, strip
from app.routing.providers import MODES, find_routes

SHIFT_STEP_MIN = 15
SHIFT_EARLIEST_MIN = -60
SHIFT_LATEST_MIN = 180
MEANINGFUL_GAIN = 0.12   # suggest an alternative only if it cuts dose by 12% or more


def _fmt_delta(minutes: int) -> str:
    if minutes == 0:
        return "now"
    h, m = divmod(abs(minutes), 60)
    span = (f"{h} h " if h else "") + (f"{m} min" if m else "").strip()
    return f"{span.strip()} {'later' if minutes > 0 else 'earlier'}"


def assess(origin: tuple[float, float], dest: tuple[float, float], depart: datetime, mode: str,
           sensitivity: list[str] | None = None, custom_threshold: int | None = None) -> dict:
    if depart.tzinfo is None:
        depart = depart.replace(tzinfo=timezone.utc)
    threshold = personal_threshold(sensitivity, custom_threshold)
    routes = find_routes(origin, dest, mode, int(depart.timestamp()))
    prepared = [prepare(r) for r in routes]

    scored = []
    for i, sr in enumerate(prepared):
        s = score(sr, depart, mode, threshold)
        scored.append((i, sr, s))
    fastest = min(scored, key=lambda x: x[1].route.duration_s)
    cleanest = min(scored, key=lambda x: x[2]["dose_ug"])

    route_out = []
    for i, sr, s in scored:
        route_out.append({
            "id": i,
            "summary": sr.route.summary,
            "provider": sr.route.provider,
            "distance_km": round(sr.route.distance_m / 1000, 1),
            "duration_min": round(sr.route.duration_s / 60),
            "avg_aqi": round(s["avg_aqi"]),
            "peak_aqi": round(s["peak_aqi"]),
            "category": category_for(s["avg_aqi"]).key,
            "dose_ug": round(s["dose_ug"], 1),
            "minutes_above_threshold": round(s["minutes_above_threshold"]),
            "is_fastest": i == fastest[0],
            "is_cleanest": i == cleanest[0],
            "geometry": [[round(a, 5), round(b, 5)] for a, b in sr.route.geometry[:: max(1, len(sr.route.geometry) // 400)]],
            "strip": strip(sr, s["aqi"], depart),
            "coverage": sr.coverage,
        })

    # Departure-time scan on the cleanest route.
    now = datetime.now(timezone.utc)
    _, best_sr, best_s = cleanest
    scan = []
    for delta in range(SHIFT_EARLIEST_MIN, SHIFT_LATEST_MIN + 1, SHIFT_STEP_MIN):
        t = depart + timedelta(minutes=delta)
        if t < now - timedelta(minutes=5):
            continue
        s = score(best_sr, t, mode, threshold)
        scan.append({"shift_min": delta, "depart_at": t.isoformat(), "dose_ug": round(s["dose_ug"], 1),
                     "avg_aqi": round(s["avg_aqi"]), "peak_aqi": round(s["peak_aqi"])})
    best_time = min(scan, key=lambda x: x["dose_ug"]) if scan else None

    suggestions = []
    base_dose = fastest[2]["dose_ug"]
    if cleanest[0] != fastest[0] and base_dose > 0:
        gain = 1 - cleanest[2]["dose_ug"] / base_dose
        extra = round((cleanest[1].route.duration_s - fastest[1].route.duration_s) / 60)
        if gain >= MEANINGFUL_GAIN:
            suggestions.append({
                "type": "route",
                "route_id": cleanest[0],
                "dose_reduction_pct": round(100 * gain),
                "extra_minutes": extra,
                "text": f"Take {cleanest[1].route.summary}: {round(100 * gain)}% less pollution inhaled"
                        + (f" for {extra} extra minutes." if extra > 0 else ", and it is no slower."),
            })
    if best_time and best_s["dose_ug"] > 0 and best_time["shift_min"] != 0:
        gain = 1 - best_time["dose_ug"] / best_s["dose_ug"]
        if gain >= MEANINGFUL_GAIN:
            suggestions.append({
                "type": "departure",
                "shift_min": best_time["shift_min"],
                "depart_at": best_time["depart_at"],
                "dose_reduction_pct": round(100 * gain),
                "text": f"Leave {_fmt_delta(best_time['shift_min'])}: {round(100 * gain)}% less pollution inhaled "
                        f"on the same route.",
            })
    m = MODES.get(mode, MODES["driving"])
    if m.key in ("two_wheeler", "cycling", "walking") and cleanest[2]["peak_aqi"] > threshold:
        suggestions.append({
            "type": "mask",
            "text": "Wear a well-fitted N95 mask; you are exposed to road air for the whole trip.",
        })

    adv = advice_for(cleanest[2]["peak_aqi"], sensitivity, custom_threshold)
    verdict = "go" if cleanest[2]["peak_aqi"] <= threshold else (
        "reconsider" if cleanest[2]["peak_aqi"] > max(threshold + 100, 300) else "caution")

    return {
        "depart_at": depart.isoformat(),
        "mode": mode,
        "mode_label": m.label,
        "threshold": threshold,
        "verdict": verdict,
        "headline": adv.headline,
        "actions": adv.actions,
        "routes": route_out,
        "recommended_route_id": cleanest[0],
        "departure_scan": scan,
        "suggestions": suggestions,
        "forecast_issued_at": prepared[0].issued_at.isoformat(),
        "approximate_geometry": all(sr.route.provider == "approximate" for sr in prepared),
    }
