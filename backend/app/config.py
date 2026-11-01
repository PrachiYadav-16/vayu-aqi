from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VAYU_", extra="ignore")

    env: str = "dev"
    database_url: str = f"sqlite:///{BASE_DIR / 'vayu.db'}"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"

    # Time-series backend: "sql" (default, uses database_url) or "influx"
    timeseries_backend: str = "sql"
    influx_url: str = "http://localhost:8086"
    influx_token: str = ""
    influx_org: str = "vayu"
    influx_bucket: str = "aqi"

    # External data sources. Any missing key disables that source.
    openaq_api_key: str = ""
    waqi_token: str = ""
    openweather_api_key: str = ""
    tomtom_api_key: str = ""
    # Open-Meteo serves Copernicus CAMS air quality and weather with no key or signup.
    open_meteo: bool = True
    google_maps_api_key: str = ""
    osrm_url: str = "https://routing.openstreetmap.de"
    nominatim_url: str = "https://nominatim.openstreetmap.org"

    # Push notifications
    firebase_credentials_file: str = ""

    model_dir: str = str(BASE_DIR / "artifacts")
    run_scheduler: bool = True
    ingest_interval_minutes: int = 30
    alert_interval_minutes: int = 15
    alert_cooldown_minutes: int = 180
    location_retention_days: int = 30

    # When no real source is configured, keep the demo alive with simulated readings.
    simulate_when_offline: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
