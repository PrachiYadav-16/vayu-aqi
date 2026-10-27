"""India National Air Quality Index (CPCB, 2014).

Sub-indices are computed by linear interpolation inside each breakpoint band.
The overall AQI is the maximum sub-index, reported only when at least one of
PM2.5 / PM10 is present (CPCB requires a particulate reading).
"""

from dataclasses import dataclass

# (concentration_low, concentration_high) for each AQI band:
# 0-50, 51-100, 101-200, 201-300, 301-400, 401-500
_AQI_BANDS = [(0, 50), (51, 100), (101, 200), (201, 300), (301, 400), (401, 500)]

BREAKPOINTS: dict[str, list[tuple[float, float]]] = {
    "pm25": [(0, 30), (31, 60), (61, 90), (91, 120), (121, 250), (251, 380)],
    "pm10": [(0, 50), (51, 100), (101, 250), (251, 350), (351, 430), (431, 600)],
    "no2": [(0, 40), (41, 80), (81, 180), (181, 280), (281, 400), (401, 600)],
    "o3": [(0, 50), (51, 100), (101, 168), (169, 208), (209, 748), (749, 1000)],
    "co": [(0, 1.0), (1.1, 2.0), (2.1, 10), (10.1, 17), (17.1, 34), (34.1, 50)],
    "so2": [(0, 40), (41, 80), (81, 380), (381, 800), (801, 1600), (1601, 2400)],
}

POLLUTANT_LABELS = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2",
    "o3": "O3",
    "co": "CO",
    "so2": "SO2",
}


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    low: int
    high: int
    color: str
    impact: str


CATEGORIES = [
    Category("good", "Good", 0, 50, "#2E9E4F", "Minimal impact."),
    Category("satisfactory", "Satisfactory", 51, 100, "#9ACD32",
             "Minor breathing discomfort for sensitive people."),
    Category("moderate", "Moderate", 101, 200, "#E8C21C",
             "Breathing discomfort for people with lung disease, asthma or heart disease, "
             "and for children and older adults."),
    Category("poor", "Poor", 201, 300, "#EE8B1E",
             "Breathing discomfort for most people on prolonged exposure."),
    Category("very_poor", "Very poor", 301, 400, "#D8342B",
             "Respiratory illness on prolonged exposure."),
    Category("severe", "Severe", 401, 500, "#7E1F23",
             "Affects healthy people and seriously affects those with existing disease."),
]


def sub_index(pollutant: str, conc: float | None) -> float | None:
    if conc is None or conc < 0:
        return None
    bands = BREAKPOINTS[pollutant]
    for (c_lo, c_hi), (i_lo, i_hi) in zip(bands, _AQI_BANDS):
        # Bands have small gaps (30 -> 31); treat a value inside the gap as belonging
        # to the upper band so the index stays continuous.
        if conc <= c_hi:
            c_lo_eff = min(c_lo, conc)
            if c_hi == c_lo_eff:
                return float(i_lo)
            return i_lo + (i_hi - i_lo) * (conc - c_lo_eff) / (c_hi - c_lo_eff)
    return 500.0


def compute_aqi(readings: dict[str, float | None]) -> tuple[int | None, str | None, dict[str, int]]:
    """Return (aqi, dominant pollutant, per-pollutant sub-indices)."""
    subs: dict[str, int] = {}
    for p in BREAKPOINTS:
        si = sub_index(p, readings.get(p))
        if si is not None:
            subs[p] = round(si)
    if not subs or not ({"pm25", "pm10"} & subs.keys()):
        return None, None, subs
    dominant = max(subs, key=subs.get)
    return subs[dominant], dominant, subs


def category_for(aqi: float | None) -> Category | None:
    if aqi is None:
        return None
    a = max(0, min(500, round(aqi)))
    for c in CATEGORIES:
        if a <= c.high:
            return c
    return CATEGORIES[-1]


def pm25_for_aqi(aqi: float) -> float:
    """Inverse of the PM2.5 sub-index, used to turn forecast AQI into an approximate dose."""
    a = max(0.0, min(500.0, aqi))
    for (c_lo, c_hi), (i_lo, i_hi) in zip(BREAKPOINTS["pm25"], _AQI_BANDS):
        if a <= i_hi:
            if i_hi == i_lo:
                return c_lo
            return c_lo + (c_hi - c_lo) * (a - i_lo) / (i_hi - i_lo)
    return BREAKPOINTS["pm25"][-1][1]
