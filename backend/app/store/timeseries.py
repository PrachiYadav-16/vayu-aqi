"""Time-series storage for fused hourly readings.

Two interchangeable backends:

* SqlSeriesStore  - the `readings` table in the app database (SQLite/Postgres).
                    Zero setup, used in development and tests.
* InfluxSeriesStore - InfluxDB 2.x, enabled with VAYU_TIMESERIES_BACKEND=influx.
                    Better for long retention and high write rates.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Reading

FIELDS = ["pm25", "pm10", "no2", "o3", "co", "so2", "temp", "humidity",
          "wind_speed", "wind_dir", "traffic", "aqi"]


class SeriesStore(ABC):
    @abstractmethod
    def write(self, rows: Iterable[dict]) -> int: ...

    @abstractmethod
    def history(self, station_ids: list[str] | None, since: datetime,
                until: datetime | None = None) -> pd.DataFrame:
        """Return columns: station_id, ts, *FIELDS sorted by station, ts."""

    @abstractmethod
    def latest_ts(self) -> datetime | None: ...


class SqlSeriesStore(SeriesStore):
    def write(self, rows: Iterable[dict]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        with SessionLocal() as db:
            if engine.dialect.name == "sqlite":
                for i in range(0, len(rows), 2000):
                    chunk = rows[i:i + 2000]
                    stmt = sqlite_insert(Reading).values(chunk)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["station_id", "ts"],
                        set_={f: stmt.excluded[f] for f in FIELDS},
                    )
                    db.execute(stmt)
            else:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                for i in range(0, len(rows), 2000):
                    chunk = rows[i:i + 2000]
                    stmt = pg_insert(Reading).values(chunk)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_reading_station_ts",
                        set_={f: stmt.excluded[f] for f in FIELDS},
                    )
                    db.execute(stmt)
            db.commit()
        return len(rows)

    def history(self, station_ids, since, until=None) -> pd.DataFrame:
        q = select(Reading).where(Reading.ts >= since)
        if until is not None:
            q = q.where(Reading.ts <= until)
        if station_ids:
            q = q.where(Reading.station_id.in_(station_ids))
        q = q.order_by(Reading.station_id, Reading.ts)
        with engine.connect() as conn:
            df = pd.read_sql(q, conn)
        if df.empty:
            return pd.DataFrame(columns=["station_id", "ts", *FIELDS])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df[["station_id", "ts", *FIELDS]]

    def latest_ts(self) -> datetime | None:
        with SessionLocal() as db:
            ts = db.scalar(select(Reading.ts).order_by(Reading.ts.desc()).limit(1))
        if ts is not None and ts.tzinfo is None:
            ts = pd.Timestamp(ts, tz="UTC").to_pydatetime()
        return ts


class InfluxSeriesStore(SeriesStore):  # pragma: no cover - needs a running InfluxDB
    def __init__(self) -> None:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        s = get_settings()
        self.bucket, self.org = s.influx_bucket, s.influx_org
        self.client = InfluxDBClient(url=s.influx_url, token=s.influx_token, org=s.influx_org)
        self.writer = self.client.write_api(write_options=SYNCHRONOUS)
        self.query = self.client.query_api()

    def write(self, rows):
        from influxdb_client import Point

        points = []
        for r in rows:
            p = Point("reading").tag("station_id", r["station_id"]).time(r["ts"])
            for f in FIELDS:
                if r.get(f) is not None:
                    p = p.field(f, float(r[f]))
            points.append(p)
        self.writer.write(bucket=self.bucket, record=points)
        return len(points)

    def history(self, station_ids, since, until=None):
        stop = f", stop: {until.isoformat()}" if until else ""
        flt = ""
        if station_ids:
            ors = " or ".join(f'r.station_id == "{s}"' for s in station_ids)
            flt = f"|> filter(fn: (r) => {ors})"
        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {since.isoformat()}{stop})
          |> filter(fn: (r) => r._measurement == "reading")
          {flt}
          |> pivot(rowKey: ["_time", "station_id"], columnKey: ["_field"], valueColumn: "_value")
        '''
        df = self.query.query_data_frame(flux)
        if isinstance(df, list):
            df = pd.concat(df) if df else pd.DataFrame()
        if df.empty:
            return pd.DataFrame(columns=["station_id", "ts", *FIELDS])
        df = df.rename(columns={"_time": "ts"})
        for f in FIELDS:
            if f not in df:
                df[f] = None
        return df[["station_id", "ts", *FIELDS]].sort_values(["station_id", "ts"])

    def latest_ts(self):
        df = self.history(None, since=pd.Timestamp.utcnow() - pd.Timedelta(days=3))
        return None if df.empty else df["ts"].max().to_pydatetime()


_store: SeriesStore | None = None


def get_store() -> SeriesStore:
    global _store
    if _store is None:
        _store = InfluxSeriesStore() if get_settings().timeseries_backend == "influx" else SqlSeriesStore()
    return _store


def station_frame(db: Session):  # small helper used by several services
    from app.models import Station

    return db.scalars(select(Station).where(Station.active.is_(True))).all()
