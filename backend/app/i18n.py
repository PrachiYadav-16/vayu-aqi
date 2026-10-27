"""Server-side messages in English, Hindi and Kannada.

Everything the backend says to a person (advice, alerts, suggestions,
explanations, window advice) goes through `t(lang, key, **params)` so that
push notifications arrive in the language chosen in Settings.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

LANGUAGES = {"en": "English", "hi": "हिन्दी", "kn": "ಕನ್ನಡ"}
IST = timezone(timedelta(hours=5, minutes=30))

M: dict[str, dict[str, str]] = {
    # ---- CPCB categories
    "cat.good": {"en": "Good", "hi": "अच्छा", "kn": "ಉತ್ತಮ"},
    "cat.satisfactory": {"en": "Satisfactory", "hi": "संतोषजनक", "kn": "ತೃಪ್ತಿಕರ"},
    "cat.moderate": {"en": "Moderate", "hi": "मध्यम", "kn": "ಮಧ್ಯಮ"},
    "cat.poor": {"en": "Poor", "hi": "खराब", "kn": "ಕಳಪೆ"},
    "cat.very_poor": {"en": "Very poor", "hi": "बहुत खराब", "kn": "ತುಂಬಾ ಕಳಪೆ"},
    "cat.severe": {"en": "Severe", "hi": "गंभीर", "kn": "ಗಂಭೀರ"},

    # ---- advice headlines
    "adv.no_reading": {"en": "No reading for this place yet.",
                       "hi": "इस जगह की अभी कोई रीडिंग नहीं है।",
                       "kn": "ಈ ಸ್ಥಳಕ್ಕೆ ಇನ್ನೂ ಯಾವುದೇ ರೀಡಿಂಗ್ ಇಲ್ಲ."},
    "adv.ok": {"en": "{cat} air. Normal outdoor plans are fine.",
               "hi": "हवा {cat} है। बाहर के सामान्य काम कर सकते हैं।",
               "kn": "ಗಾಳಿ {cat} ಆಗಿದೆ. ಸಾಮಾನ್ಯ ಹೊರಾಂಗಣ ಯೋಜನೆಗಳು ಸರಿ."},
    "adv.below": {"en": "{cat} air, below your alert level of {t}.",
                  "hi": "हवा {cat} है, आपके अलर्ट स्तर {t} से नीचे।",
                  "kn": "ಗಾಳಿ {cat} ಆಗಿದೆ, ನಿಮ್ಮ ಎಚ್ಚರಿಕೆ ಮಟ್ಟ {t} ಕ್ಕಿಂತ ಕಡಿಮೆ."},
    "adv.above": {"en": "{cat} air, above your alert level of {t}.",
                  "hi": "हवा {cat} है, आपके अलर्ट स्तर {t} से ऊपर।",
                  "kn": "ಗಾಳಿ {cat} ಆಗಿದೆ, ನಿಮ್ಮ ಎಚ್ಚರಿಕೆ ಮಟ್ಟ {t} ಕ್ಕಿಂತ ಹೆಚ್ಚು."},

    # ---- actions
    "act.workout_clean": {"en": "Keep long outdoor workouts to the cleaner part of the day.",
                          "hi": "लंबी आउटडोर कसरत दिन के साफ़ हवा वाले समय में करें।",
                          "kn": "ದೀರ್ಘ ಹೊರಾಂಗಣ ವ್ಯಾಯಾಮವನ್ನು ದಿನದ ಸ್ವಚ್ಛ ಗಾಳಿಯ ಸಮಯದಲ್ಲಿ ಮಾಡಿ."},
    "act.inhaler": {"en": "Carry your reliever inhaler.",
                    "hi": "अपना रिलीवर इनहेलर साथ रखें।",
                    "kn": "ನಿಮ್ಮ ರಿಲೀವರ್ ಇನ್ಹೇಲರ್ ಜೊತೆಯಲ್ಲಿಡಿ."},
    "act.stay_indoors": {"en": "Stay indoors with windows closed if you can.",
                         "hi": "हो सके तो खिड़कियाँ बंद रखकर घर के अंदर रहें।",
                         "kn": "ಸಾಧ್ಯವಾದರೆ ಕಿಟಕಿ ಮುಚ್ಚಿ ಮನೆಯೊಳಗೆ ಇರಿ."},
    "act.n95_must": {"en": "Wear an N95 or FFP2 mask if you must go out.",
                     "hi": "बाहर जाना ज़रूरी हो तो N95 या FFP2 मास्क पहनें।",
                     "kn": "ಹೊರಗೆ ಹೋಗಲೇಬೇಕಾದರೆ N95 ಅಥವಾ FFP2 ಮಾಸ್ಕ್ ಧರಿಸಿ."},
    "act.purifier_room": {"en": "Run an air purifier in the room you spend most time in.",
                          "hi": "जिस कमरे में आप सबसे ज़्यादा रहते हैं, वहाँ एयर प्यूरीफ़ायर चलाएँ।",
                          "kn": "ನೀವು ಹೆಚ್ಚು ಸಮಯ ಇರುವ ಕೋಣೆಯಲ್ಲಿ ಏರ್ ಪ್ಯೂರಿಫೈಯರ್ ಚಾಲೂ ಮಾಡಿ."},
    "act.shorten": {"en": "Shorten time outdoors and skip strenuous activity.",
                    "hi": "बाहर कम समय बिताएँ और भारी कसरत न करें।",
                    "kn": "ಹೊರಗೆ ಕಡಿಮೆ ಸಮಯ ಕಳೆಯಿರಿ, ಶ್ರಮದ ಚಟುವಟಿಕೆ ಬೇಡ."},
    "act.n95_road": {"en": "A well-fitted N95 mask helps on the road.",
                     "hi": "सड़क पर अच्छी तरह फ़िट N95 मास्क मदद करता है।",
                     "kn": "ರಸ್ತೆಯಲ್ಲಿ ಸರಿಯಾಗಿ ಹೊಂದುವ N95 ಮಾಸ್ಕ್ ಸಹಾಯ ಮಾಡುತ್ತದೆ."},
    "act.inhaler_plan": {"en": "Keep your reliever inhaler with you and follow your action plan.",
                         "hi": "रिलीवर इनहेलर साथ रखें और डॉक्टर के बताए एक्शन प्लान का पालन करें।",
                         "kn": "ರಿಲೀವರ್ ಇನ್ಹೇಲರ್ ಜೊತೆಯಲ್ಲಿಡಿ ಮತ್ತು ವೈದ್ಯರು ಹೇಳಿದ ಕ್ರಿಯಾ ಯೋಜನೆ ಪಾಲಿಸಿ."},
    "act.heart": {"en": "Watch for chest pain, palpitations or unusual tiredness.",
                  "hi": "सीने में दर्द, तेज़ धड़कन या असामान्य थकान पर ध्यान दें।",
                  "kn": "ಎದೆನೋವು, ಹೃದಯ ಬಡಿತ ಹೆಚ್ಚಳ ಅಥವಾ ಅಸಾಮಾನ್ಯ ಆಯಾಸದ ಬಗ್ಗೆ ಗಮನವಿರಲಿ."},
    "act.children": {"en": "Move children's outdoor play indoors.",
                     "hi": "बच्चों का बाहर खेलना घर के अंदर करवाएँ।",
                     "kn": "ಮಕ್ಕಳ ಹೊರಾಂಗಣ ಆಟವನ್ನು ಮನೆಯೊಳಗೆ ಮಾಡಿಸಿ."},

    # ---- alerts
    "alert.loc_now_title": {"en": "AQI {aqi} where you are",
                            "hi": "आपकी जगह पर AQI {aqi}",
                            "kn": "ನೀವಿರುವ ಸ್ಥಳದಲ್ಲಿ AQI {aqi}"},
    "alert.loc_soon_title": {"en": "AQI expected to reach {aqi} by {time}",
                             "hi": "{time} तक AQI {aqi} होने की संभावना",
                             "kn": "{time} ರೊಳಗೆ AQI {aqi} ತಲುಪುವ ಸಾಧ್ಯತೆ"},
    "alert.loc_soon_body": {"en": "Your area is forecast to cross your alert level of {t}. Plan outdoor time before then.",
                            "hi": "आपके इलाके में AQI आपके अलर्ट स्तर {t} से ऊपर जाने का अनुमान है। बाहर के काम उससे पहले कर लें।",
                            "kn": "ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ AQI ನಿಮ್ಮ ಎಚ್ಚರಿಕೆ ಮಟ್ಟ {t} ದಾಟುವ ಮುನ್ಸೂಚನೆ ಇದೆ. ಹೊರಗಿನ ಕೆಲಸಗಳನ್ನು ಅದಕ್ಕೂ ಮೊದಲು ಮುಗಿಸಿ."},
    "alert.trip_title": {"en": "{name}, {time}: peak AQI {aqi}",
                         "hi": "{name}, {time}: अधिकतम AQI {aqi}",
                         "kn": "{name}, {time}: ಗರಿಷ್ಠ AQI {aqi}"},
    "trip.default_name": {"en": "{a} to {b}", "hi": "{a} से {b}", "kn": "{a} ನಿಂದ {b}"},
    "brief.title": {"en": "Today's air: AQI {lo} to {hi}",
                    "hi": "आज की हवा: AQI {lo} से {hi}",
                    "kn": "ಇಂದಿನ ಗಾಳಿ: AQI {lo} ರಿಂದ {hi}"},
    "brief.cigs": {"en": "A full day outdoors would equal about {cig} cigarettes.",
                   "hi": "पूरा दिन बाहर रहना लगभग {cig} सिगरेट पीने के बराबर होगा।",
                   "kn": "ಇಡೀ ದಿನ ಹೊರಗಿದ್ದರೆ ಸುಮಾರು {cig} ಸಿಗರೇಟ್‌ಗೆ ಸಮ."},

    # ---- trip suggestions
    "sug.route": {"en": "Take {route}: {pct}% less pollution inhaled",
                  "hi": "{route} से जाएँ: साँस में {pct}% कम प्रदूषण",
                  "kn": "{route} ಮೂಲಕ ಹೋಗಿ: ಉಸಿರಿನಲ್ಲಿ {pct}% ಕಡಿಮೆ ಮಾಲಿನ್ಯ"},
    "sug.route_extra": {"en": " for {m} extra minutes.", "hi": ", {m} मिनट ज़्यादा लगेंगे।",
                        "kn": ", {m} ನಿಮಿಷ ಹೆಚ್ಚು ಬೇಕು."},
    "sug.route_same": {"en": ", and it is no slower.", "hi": ", और समय भी उतना ही।",
                       "kn": ", ಸಮಯವೂ ಹೆಚ್ಚಾಗುವುದಿಲ್ಲ."},
    "sug.depart": {"en": "Leave {when}: {pct}% less pollution inhaled on the same route.",
                   "hi": "{when} निकलें: उसी रास्ते पर साँस में {pct}% कम प्रदूषण।",
                   "kn": "{when} ಹೊರಡಿ: ಅದೇ ಮಾರ್ಗದಲ್ಲಿ ಉಸಿರಿನಲ್ಲಿ {pct}% ಕಡಿಮೆ ಮಾಲಿನ್ಯ."},
    "sug.later": {"en": "{span} later", "hi": "{span} बाद", "kn": "{span} ನಂತರ"},
    "sug.earlier": {"en": "{span} earlier", "hi": "{span} पहले", "kn": "{span} ಮೊದಲು"},
    "unit.h": {"en": "h", "hi": "घंटा", "kn": "ಗಂಟೆ"},
    "unit.min": {"en": "min", "hi": "मिनट", "kn": "ನಿಮಿಷ"},
    "sug.mask": {"en": "Wear a well-fitted N95 mask; you are exposed to road air for the whole trip.",
                 "hi": "अच्छी तरह फ़िट N95 मास्क पहनें; पूरे सफ़र में आप सड़क की हवा में रहेंगे।",
                 "kn": "ಸರಿಯಾಗಿ ಹೊಂದುವ N95 ಮಾಸ್ಕ್ ಧರಿಸಿ; ಇಡೀ ಪ್ರಯಾಣದಲ್ಲಿ ನೀವು ರಸ್ತೆಯ ಗಾಳಿಯಲ್ಲಿರುತ್ತೀರಿ."},

    # ---- windows and purifier
    "win.open": {"en": "Open windows {from} to {to}. AQI will be around {aqi}, the cleanest stretch today.",
                 "hi": "{from} से {to} के बीच खिड़कियाँ खोलें। तब AQI लगभग {aqi} रहेगा, आज का सबसे साफ़ समय।",
                 "kn": "{from} ರಿಂದ {to} ರವರೆಗೆ ಕಿಟಕಿ ತೆರೆಯಿರಿ. ಆಗ AQI ಸುಮಾರು {aqi} ಇರುತ್ತದೆ, ಇಂದಿನ ಅತ್ಯಂತ ಸ್ವಚ್ಛ ಸಮಯ."},
    "win.short": {"en": "Air out briefly {from} to {to} (AQI about {aqi}), then close up.",
                  "hi": "{from} से {to} के बीच थोड़ी देर हवा आने दें (AQI लगभग {aqi}), फिर बंद कर दें।",
                  "kn": "{from} ರಿಂದ {to} ರವರೆಗೆ ಸ್ವಲ್ಪ ಹೊತ್ತು ಗಾಳಿ ಬರಲಿ (AQI ಸುಮಾರು {aqi}), ನಂತರ ಮುಚ್ಚಿ."},
    "win.closed": {"en": "Keep windows closed today. Even the cleanest stretch ({from} to {to}) stays around AQI {aqi}.",
                   "hi": "आज खिड़कियाँ बंद रखें। सबसे साफ़ समय ({from} से {to}) में भी AQI लगभग {aqi} रहेगा।",
                   "kn": "ಇಂದು ಕಿಟಕಿ ಮುಚ್ಚಿಡಿ. ಅತ್ಯಂತ ಸ್ವಚ್ಛ ಸಮಯದಲ್ಲೂ ({from} ರಿಂದ {to}) AQI ಸುಮಾರು {aqi} ಇರುತ್ತದೆ."},
    "pur.run": {"en": "Run the purifier {from} to {to}, when AQI peaks near {aqi}.",
                "hi": "{from} से {to} के बीच प्यूरीफ़ायर चलाएँ, तब AQI {aqi} के आसपास सबसे ज़्यादा होगा।",
                "kn": "{from} ರಿಂದ {to} ರವರೆಗೆ ಪ್ಯೂರಿಫೈಯರ್ ಚಾಲೂ ಮಾಡಿ, ಆಗ AQI ಸುಮಾರು {aqi} ಗರಿಷ್ಠ ಮಟ್ಟದಲ್ಲಿರುತ್ತದೆ."},
    "pur.optional": {"en": "A purifier is optional; the air stays below AQI {aqi}.",
                     "hi": "प्यूरीफ़ायर ज़रूरी नहीं; AQI {aqi} से नीचे रहेगा।",
                     "kn": "ಪ್ಯೂರಿಫೈಯರ್ ಅಗತ್ಯವಿಲ್ಲ; AQI {aqi} ಕ್ಕಿಂತ ಕಡಿಮೆ ಇರುತ್ತದೆ."},

    # ---- why the AQI is changing
    "exp.trend_up": {"en": "Likely to get worse over the next 6 hours.",
                     "hi": "अगले 6 घंटों में हवा और खराब होने की संभावना है।",
                     "kn": "ಮುಂದಿನ 6 ಗಂಟೆಗಳಲ್ಲಿ ಗಾಳಿ ಇನ್ನಷ್ಟು ಹದಗೆಡುವ ಸಾಧ್ಯತೆ ಇದೆ."},
    "exp.trend_down": {"en": "Likely to improve over the next 6 hours.",
                       "hi": "अगले 6 घंटों में हवा सुधरने की संभावना है।",
                       "kn": "ಮುಂದಿನ 6 ಗಂಟೆಗಳಲ್ಲಿ ಗಾಳಿ ಸುಧಾರಿಸುವ ಸಾಧ್ಯತೆ ಇದೆ."},
    "exp.trend_flat": {"en": "Likely to stay about the same over the next 6 hours.",
                       "hi": "अगले 6 घंटों में हवा लगभग ऐसी ही रहेगी।",
                       "kn": "ಮುಂದಿನ 6 ಗಂಟೆಗಳಲ್ಲಿ ಗಾಳಿ ಸುಮಾರು ಹೀಗೆಯೇ ಇರುತ್ತದೆ."},
    "exp.traffic.up": {"en": "Traffic nearby is adding to it", "hi": "आसपास का ट्रैफ़िक प्रदूषण बढ़ा रहा है",
                       "kn": "ಹತ್ತಿರದ ಸಂಚಾರ ಮಾಲಿನ್ಯ ಹೆಚ್ಚಿಸುತ್ತಿದೆ"},
    "exp.traffic.down": {"en": "Light traffic is helping", "hi": "कम ट्रैफ़िक से राहत है",
                         "kn": "ಕಡಿಮೆ ಸಂಚಾರದಿಂದ ನೆರವಾಗುತ್ತಿದೆ"},
    "exp.wind.up": {"en": "Calm wind is letting pollution build up", "hi": "हवा धीमी है, इसलिए प्रदूषण जमा हो रहा है",
                    "kn": "ಗಾಳಿ ನಿಧಾನವಾಗಿರುವುದರಿಂದ ಮಾಲಿನ್ಯ ಶೇಖರವಾಗುತ್ತಿದೆ"},
    "exp.wind.down": {"en": "Wind is carrying pollution away", "hi": "हवा प्रदूषण को दूर ले जा रही है",
                      "kn": "ಗಾಳಿ ಮಾಲಿನ್ಯವನ್ನು ದೂರ ಕೊಂಡೊಯ್ಯುತ್ತಿದೆ"},
    "exp.weather.up": {"en": "Cool, humid air is trapping particles", "hi": "ठंडी और नम हवा कणों को रोक रही है",
                       "kn": "ತಂಪಾದ, ತೇವಾಂಶದ ಗಾಳಿ ಕಣಗಳನ್ನು ಹಿಡಿದಿಡುತ್ತಿದೆ"},
    "exp.weather.down": {"en": "Warm, dry air is helping it spread out", "hi": "गर्म और सूखी हवा से प्रदूषण फैलकर कम हो रहा है",
                         "kn": "ಬೆಚ್ಚಗಿನ, ಒಣ ಗಾಳಿ ಮಾಲಿನ್ಯ ಹರಡಲು ಸಹಾಯ ಮಾಡುತ್ತಿದೆ"},
    "exp.time.up": {"en": "This time of day is usually worse", "hi": "दिन के इस समय हवा आमतौर पर खराब रहती है",
                    "kn": "ದಿನದ ಈ ಸಮಯದಲ್ಲಿ ಗಾಳಿ ಸಾಮಾನ್ಯವಾಗಿ ಕೆಟ್ಟದಾಗಿರುತ್ತದೆ"},
    "exp.time.down": {"en": "Air usually clears at this time of day", "hi": "दिन के इस समय हवा आमतौर पर साफ़ होती है",
                      "kn": "ದಿನದ ಈ ಸಮಯದಲ್ಲಿ ಗಾಳಿ ಸಾಮಾನ್ಯವಾಗಿ ಸ್ವಚ್ಛವಾಗುತ್ತದೆ"},
    "exp.season.up": {"en": "Seasonal build-up, winter months are worse",
                      "hi": "मौसम का असर, सर्दियों में हवा ज़्यादा खराब होती है",
                      "kn": "ಋತುವಿನ ಪ್ರಭಾವ, ಚಳಿಗಾಲದಲ್ಲಿ ಗಾಳಿ ಹೆಚ್ಚು ಕೆಟ್ಟದಾಗಿರುತ್ತದೆ"},
    "exp.season.down": {"en": "The season is in your favour", "hi": "मौसम साथ दे रहा है", "kn": "ಋತು ನಿಮ್ಮ ಪರವಾಗಿದೆ"},
    "exp.city.up": {"en": "Pollution is high across the city", "hi": "पूरे शहर में प्रदूषण ज़्यादा है",
                    "kn": "ನಗರದಾದ್ಯಂತ ಮಾಲಿನ್ಯ ಹೆಚ್ಚಾಗಿದೆ"},
    "exp.city.down": {"en": "The rest of the city is cleaner", "hi": "शहर के बाकी हिस्सों में हवा साफ़ है",
                      "kn": "ನಗರದ ಉಳಿದ ಭಾಗಗಳು ಸ್ವಚ್ಛವಾಗಿವೆ"},
    "exp.trend.up": {"en": "AQI has been climbing for the last few hours", "hi": "पिछले कुछ घंटों से AQI बढ़ रहा है",
                     "kn": "ಕಳೆದ ಕೆಲವು ಗಂಟೆಗಳಿಂದ AQI ಏರುತ್ತಿದೆ"},
    "exp.trend.down": {"en": "AQI has been falling for the last few hours", "hi": "पिछले कुछ घंटों से AQI घट रहा है",
                       "kn": "ಕಳೆದ ಕೆಲವು ಗಂಟೆಗಳಿಂದ AQI ಇಳಿಯುತ್ತಿದೆ"},
}


def norm_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else "en"


def t(lang: str | None, key: str, **params) -> str:
    entry = M.get(key)
    if entry is None:
        return key
    text = entry.get(norm_lang(lang)) or entry["en"]
    return text.format(**params) if params else text


def cat_label(lang: str | None, cat_key: str) -> str:
    return t(lang, f"cat.{cat_key}")


_PERIODS = {
    "hi": [(5, "सुबह"), (12, "दोपहर"), (16, "शाम"), (20, "रात")],
    "kn": [(5, "ಬೆಳಿಗ್ಗೆ"), (12, "ಮಧ್ಯಾಹ್ನ"), (16, "ಸಂಜೆ"), (20, "ರಾತ್ರಿ")],
}


def fmt_time(lang: str | None, dt: datetime, minutes: bool = False) -> str:
    """Clock time in IST, the way people say it in each language."""
    lang = norm_lang(lang)
    local = dt.astimezone(IST)
    h12 = local.hour % 12 or 12
    clock = f"{h12}:{local.minute:02d}" if minutes else f"{h12}"
    if lang == "en":
        return f"{clock} {'am' if local.hour < 12 else 'pm'}"
    period = _PERIODS[lang][-1][1]
    for start, name in _PERIODS[lang]:
        if local.hour >= start:
            period = name
    if local.hour < 5:
        period = _PERIODS[lang][-1][1]
    suffix = " बजे" if lang == "hi" else ""
    return f"{period} {clock}{suffix}"


def fmt_span(lang: str | None, minutes: int) -> str:
    h, m = divmod(abs(minutes), 60)
    parts = []
    if h:
        parts.append(f"{h} {t(lang, 'unit.h')}")
    if m:
        parts.append(f"{m} {t(lang, 'unit.min')}")
    return " ".join(parts)
