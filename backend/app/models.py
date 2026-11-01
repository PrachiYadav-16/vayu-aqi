from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC and always hands back timezone-aware datetimes.

    SQLite drops the offset, which would make the API return naive timestamps
    that browsers then read as local time."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        # Postgres returns the session time zone (e.g. Etc/UTC on Neon); normalise it.
        return value.astimezone(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    # Health profile. Sensitivity groups drive personal alert thresholds.
    sensitivity: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["asthma", "elderly"]
    custom_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Consent + preferences
    location_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_trip_advisories: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_start_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)  # local hour
    quiet_end_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    notify_daily_brief: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    brief_hour: Mapped[int] = mapped_column(Integer, default=7, server_default="7")  # local hour, IST

    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(80), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))  # openaq | waqi | cpcb | simulated
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reading(Base):
    """Hourly fused observation per station (pollutants + weather + traffic)."""

    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("station_id", "ts", name="uq_reading_station_ts"),
        Index("ix_reading_station_ts", "station_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    no2: Mapped[float | None] = mapped_column(Float, nullable=True)
    o3: Mapped[float | None] = mapped_column(Float, nullable=True)
    co: Mapped[float | None] = mapped_column(Float, nullable=True)  # mg/m3
    so2: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_dir: Mapped[float | None] = mapped_column(Float, nullable=True)
    traffic: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 congestion index
    aqi: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LocationPing(Base):
    __tablename__ = "location_pings"
    __table_args__ = (Index("ix_ping_user_ts", "user_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi: Mapped[int | None] = mapped_column(Integer, nullable=True)  # estimated AQI at ping time
    pm25: Mapped[float | None] = mapped_column(Float, nullable=True)  # estimated PM2.5 (ug/m3) at ping time


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    origin_name: Mapped[str] = mapped_column(String(255))
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lon: Mapped[float] = mapped_column(Float)
    dest_name: Mapped[str] = mapped_column(String(255))
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lon: Mapped[float] = mapped_column(Float)
    depart_at: Mapped[datetime] = mapped_column(UTCDateTime())
    mode: Mapped[str] = mapped_column(String(16), default="driving")
    repeat_weekdays: Mapped[list] = mapped_column(JSON, default=list)  # 0=Mon .. 6=Sun
    last_assessment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="trips")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))  # location_breach | trip_advisory | forecast_spike
    severity: Mapped[str] = mapped_column(String(16))  # info | warning | critical
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(1000))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_push: Mapped[bool] = mapped_column(Boolean, default=False)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(32), default="web")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    version: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    promoted: Mapped[bool] = mapped_column(Boolean, default=False)
