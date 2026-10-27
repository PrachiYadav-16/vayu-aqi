from datetime import datetime, timedelta, timezone

from app import insights
from app.i18n import IST, M, fmt_time, t


def _hours(values, start=None):
    start = start or datetime(2026, 1, 10, 0, 30, tzinfo=timezone.utc)  # 6:00 IST
    return [{"ts": (start + timedelta(hours=i)).isoformat(), "aqi": v} for i, v in enumerate(values)]


def test_every_message_has_all_languages():
    for key, entry in M.items():
        assert {"en", "hi", "kn"} <= entry.keys(), key


def test_translation_and_fallback():
    assert t("hi", "cat.poor") == "खराब"
    assert t("kn", "cat.good") == "ಉತ್ತಮ"
    assert t("fr", "cat.good") == "Good"


def test_fmt_time_by_language():
    dt = datetime(2026, 1, 10, 8, 30, tzinfo=timezone.utc)  # 2:00 pm IST
    assert fmt_time("en", dt) == "2 pm"
    assert fmt_time("hi", dt) == "दोपहर 2 बजे"
    assert fmt_time("kn", dt).startswith("ಮಧ್ಯಾಹ್ನ")


def test_cigarette_constant():
    # One day at 22 ug/m3 is one cigarette.
    dose = 22 * insights.INHALED_M3_PER_DAY
    assert insights.cigarettes(dose) == 1.0


def test_window_advice_picks_cleanest_waking_block():
    vals = [180, 170, 160, 90, 60, 55, 70, 120, 200, 220, 230, 210] + [150] * 12
    adv = insights.window_advice(_hours(vals), "en")
    w = adv["windows"]
    assert w["action"] == "open" and w["aqi"] <= 60
    start_local = datetime.fromisoformat(w["from"]).astimezone(IST)
    assert 6 <= start_local.hour <= 22
    assert adv["purifier"]["action"] == "run" and adv["purifier"]["aqi"] >= 200


def test_window_advice_says_closed_on_bad_day():
    adv = insights.window_advice(_hours([320] * 24), "hi")
    assert adv["windows"]["action"] == "closed"
    assert "खिड़कियाँ बंद" in adv["windows"]["text"]


def test_budget_grows_with_forecast():
    now = datetime.now(timezone.utc)
    clean = insights.day_budget(now, [], 40, _hours([40] * 24, start=now))
    dirty = insights.day_budget(now, [], 300, _hours([300] * 24, start=now))
    assert dirty["projected_ug"] > clean["projected_ug"] * 4
    assert dirty["cigarettes_projected"] > 1


def test_explain_trend_and_factors():
    effects = [{"factor": "traffic", "effect": 20.0}, {"factor": "wind", "effect": -1.0}]
    out = insights.explain(effects, 100, _hours([130] * 6), "en")
    assert out["trend"] == "up"
    assert out["factors"] == [{"factor": "traffic", "direction": "up", "effect": 20,
                               "text": "Traffic nearby is adding to it"}]
