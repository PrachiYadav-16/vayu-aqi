from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.aqi.health import SENSITIVITY_GROUPS
from app.routing.providers import MODES


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    sensitivity: list[str] = []

    @field_validator("sensitivity")
    @classmethod
    def _known(cls, v):
        bad = [s for s in v if s not in SENSITIVITY_GROUPS]
        if bad:
            raise ValueError(f"Unknown sensitivity group: {', '.join(bad)}")
        return v


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileOut(BaseModel):
    id: int
    email: str
    name: str
    sensitivity: list[str]
    custom_threshold: int | None
    threshold: int
    home_lat: float | None
    home_lon: float | None
    location_consent: bool
    notify_push: bool
    notify_trip_advisories: bool
    quiet_start_hour: int | None
    quiet_end_hour: int | None


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    sensitivity: list[str] | None = None
    custom_threshold: int | None = Field(default=None, ge=50, le=400)
    clear_custom_threshold: bool = False
    home_lat: float | None = Field(default=None, ge=-90, le=90)
    home_lon: float | None = Field(default=None, ge=-180, le=180)
    location_consent: bool | None = None
    notify_push: bool | None = None
    notify_trip_advisories: bool | None = None
    quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_end_hour: int | None = Field(default=None, ge=0, le=23)

    @field_validator("sensitivity")
    @classmethod
    def _known(cls, v):
        if v is None:
            return v
        bad = [s for s in v if s not in SENSITIVITY_GROUPS]
        if bad:
            raise ValueError(f"Unknown sensitivity group: {', '.join(bad)}")
        return v


class PingIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = None


class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class AssessIn(BaseModel):
    origin: PlaceIn
    destination: PlaceIn
    depart_at: datetime
    mode: str = "driving"

    @field_validator("mode")
    @classmethod
    def _mode(cls, v):
        if v not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        return v


class TripIn(AssessIn):
    label: str = Field(default="", max_length=120)
    repeat_weekdays: list[int] = []

    @field_validator("repeat_weekdays")
    @classmethod
    def _days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("weekdays are 0 (Mon) to 6 (Sun)")
        return sorted(set(v))


class TripOut(BaseModel):
    id: int
    label: str
    origin_name: str
    origin_lat: float
    origin_lon: float
    dest_name: str
    dest_lat: float
    dest_lon: float
    depart_at: datetime
    mode: str
    repeat_weekdays: list[int]
    last_assessment: dict | None

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    kind: str
    severity: str
    title: str
    body: str
    data: dict
    created_at: datetime
    read: bool

    model_config = {"from_attributes": True}


class DeviceIn(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    platform: str = "web"
