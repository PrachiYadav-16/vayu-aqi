"""Personal thresholds and advice for each health sensitivity group."""

from dataclasses import dataclass

from app.aqi.naqi import category_for
from app.i18n import cat_label, t

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


def advice_for(aqi: float | None, sensitivity: list[str] | None, custom: int | None = None,
               lang: str = "en") -> Advice:
    if aqi is None:
        return Advice("ok", t(lang, "adv.no_reading"), [])
    threshold = personal_threshold(sensitivity, custom)
    cat = cat_label(lang, category_for(aqi).key)
    sens = set(sensitivity or [])
    lung = bool(sens & {"asthma", "copd"})

    if aqi <= min(100, threshold * 0.6):
        return Advice("ok", t(lang, "adv.ok", cat=cat), [])

    if aqi < threshold:
        actions = [t(lang, "act.workout_clean")]
        if lung:
            actions.append(t(lang, "act.inhaler"))
        return Advice("caution", t(lang, "adv.below", cat=cat, t=threshold), actions)

    if aqi > 300:
        actions = [t(lang, "act.stay_indoors"), t(lang, "act.n95_must"), t(lang, "act.purifier_room")]
    else:
        actions = [t(lang, "act.shorten"), t(lang, "act.n95_road")]
    if lung:
        actions.append(t(lang, "act.inhaler_plan"))
    if "heart" in sens:
        actions.append(t(lang, "act.heart"))
    if "children" in sens:
        actions.append(t(lang, "act.children"))
    return Advice("avoid", t(lang, "adv.above", cat=cat, t=threshold), actions)
