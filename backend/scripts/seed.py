"""Prepare a local database: stations, 30 days of readings and a demo account.

    python -m scripts.seed            # stations + readings + demo user
    python -m scripts.seed --no-demo  # skip the demo user
"""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.forecast.service import get_forecast_service
from app.ingest.pipeline import backfill_simulated, ensure_stations, ingest_live
from app.ingest.sources import any_pollutant_source
from app.models import LocationPing, Trip, User
from app.security import hash_password

DEMO_EMAIL = "demo@vayu.local"
DEMO_PASSWORD = "vayu-demo-2026"


def seed_demo() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == DEMO_EMAIL)):
            print("demo user exists")
            return
        u = User(email=DEMO_EMAIL, name="Demo commuter", password_hash=hash_password(DEMO_PASSWORD),
                 sensitivity=["asthma"], location_consent=True, home_lat=12.9352, home_lon=77.6245)
        db.add(u)
        db.flush()
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        tomorrow_9 = (now + timedelta(days=1)).replace(hour=3, minute=30)  # 09:00 IST
        db.add(Trip(user_id=u.id, label="Office commute", origin_name="Koramangala, Bengaluru",
                    origin_lat=12.9352, origin_lon=77.6245, dest_name="Electronic City, Bengaluru",
                    dest_lat=12.8452, dest_lon=77.6602, depart_at=tomorrow_9, mode="two_wheeler",
                    repeat_weekdays=[0, 1, 2, 3, 4]))
        db.flush()

        # Two weeks of plausible location history: home at night, office by day.
        svc = get_forecast_service()
        sf = svc.station_forecasts()
        from app.store.timeseries import get_store
        from app.forecast.spatial import interpolate
        import numpy as np

        hist = get_store().history([s for s in sf.station_ids if s.startswith("blr")],
                                   since=now - timedelta(days=14))
        piv = hist.pivot_table(index="ts", columns="station_id", values="aqi")
        st_ids = list(piv.columns)
        lat = np.array([sf.lat[sf.station_ids.index(s)] for s in st_ids])
        lon = np.array([sf.lon[sf.station_ids.index(s)] for s in st_ids])
        for ts, row in piv.iterrows():
            local_h = (ts + timedelta(hours=5, minutes=30)).hour
            weekday = (ts + timedelta(hours=5, minutes=30)).weekday() < 5
            if weekday and 10 <= local_h < 18:
                p = (12.8452, 77.6602)
            elif weekday and local_h == 9:
                p = (12.89, 77.64)
            else:
                p = (12.9352, 77.6245)
            est = interpolate([p[0]], [p[1]], lat, lon, row.to_numpy())
            db.add(LocationPing(user_id=u.id, ts=ts.to_pydatetime(), lat=p[0], lon=p[1], aqi=round(float(est.value[0]))))
        db.commit()
        print(f"demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-demo", action="store_true")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    init_db()
    ensure_stations()
    if any_pollutant_source():
        print("live sources configured:", ingest_live())
    else:
        print("rows written:", backfill_simulated(days=args.days))
    get_forecast_service().station_forecasts(force=True)
    if not args.no_demo:
        seed_demo()


if __name__ == "__main__":
    main()
