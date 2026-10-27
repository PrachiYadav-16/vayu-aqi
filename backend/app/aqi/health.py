"""Personal thresholds and advice for each health sensitivity group."""

from dataclasses import dataclass

from app.aqi.naqi import category_for

SENSITIVITY_GROUPS = {
    "asthma": ("Asthma", 100),
    "copd": ("COPD or other chronic lung disease", 100),
    "heart": ("Heart disease", 100),
    "pregnant": ("Pregnant", 150),
    "children": ("Children in the household", 150),
    "elderly": ("Aged 65 or above", 150),
    "outdoor_work": ("Works or exercises outdoors", 150),
}
DEFAULT_THRESHOLD = 200


def personal_threshold(sensitivity: list[str] | None, custom: int | None = None) -> int:
    if custom:
        return int(custom)
    limits = [SENSITIVITY_GROUPS[s][1] for s in (sensitivity or []) if s in SENSITIVITY_GROUPS]
    return min(limits) if limits else DEFAULT_THRESHOLD


@dataclass
class Advice:
    level: str  # ok | caution | avoid
    headline: str
    actions: list[str]


def advice_for(aqi: float | None, sensitivity: list[str] | None, custom: int | None = None) -> Advice:
    if aqi is None:
        return Advice("ok", "No reading for this place yet.", [])
    threshold = personal_threshold(sensitivity, custom)
    cat = category_for(aqi)
    sens = set(sensitivity or [])
    lung = bool(sens & {"asthma", "copd"})

    if aqi <= min(100, threshold * 0.6):
        return Advice("ok", f"{cat.label} air. Normal outdoor plans are fine.", [])

    if aqi < threshold:
        actions = ["Keep long outdoor workouts to the cleaner part of the day."]
        if lung:
            actions.append("Carry your reliever inhaler.")
        return Advice("caution", f"{cat.label} air, below your alert level of {threshold}.", actions)

    actions: list[str] = []
    if aqi > 300:
        actions.append("Stay indoors with windows closed if you can.")
        actions.append("Wear an N95 or FFP2 mask if you must go out.")
        actions.append("Run an air purifier in the room you spend most time in.")
    else:
        actions.append("Shorten time outdoors and skip strenuous activity.")
        actions.append("A well-fitted N95 mask helps on the road.")
    if lung:
        actions.append("Keep your reliever inhaler with you and follow your action plan.")
    if "heart" in sens:
        actions.append("Watch for chest pain, palpitations or unusual tiredness.")
    if "children" in sens:
        actions.append("Move children's outdoor play indoors.")
    return Advice("avoid", f"{cat.label} air, above your alert level of {threshold}.", actions)
