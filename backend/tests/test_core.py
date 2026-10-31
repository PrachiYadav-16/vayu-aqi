import numpy as np
import pytest

from app.aqi.health import advice_for, personal_threshold
from app.aqi.naqi import category_for, compute_aqi, pm25_for_aqi, sub_index
from app.forecast.spatial import idw, interpolate
from app.routing.providers import decode_polyline


@pytest.mark.parametrize("conc,expected", [(0, 0), (30, 50), (60, 100), (90, 200), (120, 300), (250, 400)])
def test_pm25_breakpoints(conc, expected):
    assert round(sub_index("pm25", conc)) == expected


def test_band_gap_is_continuous():
    # 30.5 sits in the CPCB gap between bands; it must land between 50 and 51.
    assert 50 <= sub_index("pm25", 30.5) <= 51


def test_aqi_needs_particulates():
    aqi, dom, subs = compute_aqi({"no2": 120})
    assert aqi is None and "no2" in subs


def test_dominant_pollutant():
    aqi, dom, _ = compute_aqi({"pm25": 95, "pm10": 120, "no2": 30})
    assert dom == "pm25" and aqi == round(sub_index("pm25", 95))


def test_pm25_inverse_roundtrip():
    for a in (20, 75, 150, 260, 350):
        assert abs(sub_index("pm25", pm25_for_aqi(a)) - a) < 1


def test_categories():
    assert category_for(42).key == "good"
    assert category_for(101).key == "moderate"
    assert category_for(450).key == "severe"


def test_thresholds():
    assert personal_threshold([]) == 200
    assert personal_threshold(["elderly", "asthma"]) == 100
    assert personal_threshold(["asthma"], custom=130) == 130


def test_advice_levels():
    assert advice_for(40, ["asthma"]).level == "ok"
    assert advice_for(90, ["asthma"]).level == "caution"
    adv = advice_for(320, ["asthma"])
    assert adv.level == "avoid" and any("inhaler" in a for a in adv.actions)


def test_idw_exact_at_station():
    d = np.array([[0.0, 10.0, 20.0]])
    v = idw(d, np.array([100.0, 50.0, 10.0]))
    assert v[0] == pytest.approx(100.0, abs=1)


def test_interpolation_stays_local():
    # Two clusters 1,700 km apart: a point in cluster A must ignore cluster B.
    lat = np.array([28.6, 28.62, 28.58, 12.9, 12.92, 12.88])
    lon = np.array([77.2, 77.22, 77.18, 77.6, 77.62, 77.58])
    vals = np.array([300.0, 310, 290, 50, 55, 45])
    est = interpolate([28.61], [77.21], lat, lon, vals)
    assert 285 <= est.value[0] <= 312


def test_polyline_decode():
    # Example from Google's polyline documentation.
    pts = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts[0] == pytest.approx((38.5, -120.2))
    assert pts[-1] == pytest.approx((43.252, -126.453))


def test_to_grid_accepts_etc_utc_end():
    # Neon/Postgres can return timestamps in Etc/UTC; pandas must not reject them.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import pandas as pd

    from app.forecast.features import to_grid

    ts = pd.date_range("2026-01-01", periods=60, freq="h", tz="UTC")
    df = pd.DataFrame({"station_id": "s1", "ts": ts, "aqi": 80.0, "pm25": 30.0, "pm10": 60.0, "no2": 20.0,
                       "o3": 10.0, "co": 0.5, "temp": 25.0, "humidity": 50.0, "wind_speed": 2.0,
                       "wind_dir": 90.0, "traffic": 0.4})
    end = datetime(2026, 1, 3, 11, tzinfo=ZoneInfo("Etc/UTC"))
    X, sids, times = to_grid(df, {"s1": "X"}, end=pd.Timestamp(end), hours=48)
    assert X.shape[:2] == (1, 48) and str(times.tz) == "UTC"


def test_congestion_factor_peaks_in_rush_hour():
    from datetime import datetime, timedelta, timezone

    from app.routing.providers import congestion_factor

    ist = timezone(timedelta(hours=5, minutes=30))
    night = congestion_factor(int(datetime(2026, 11, 2, 3, 0, tzinfo=ist).timestamp()))
    peak = congestion_factor(int(datetime(2026, 11, 2, 19, 0, tzinfo=ist).timestamp()))
    assert 1.3 < night < 1.6 and 2.0 < peak < 2.4
