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
