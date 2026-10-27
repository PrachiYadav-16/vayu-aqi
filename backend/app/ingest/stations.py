"""Seed list of CPCB continuous monitoring stations (approximate coordinates).

Used to bootstrap the station table and the simulated feed. When OpenAQ / WAQI
keys are configured, live stations from those sources are merged in.
"""

# id, name, city, lat, lon, local pollution bias (1.0 = city average)
SEED_STATIONS = [
    # Delhi
    ("dl-anand-vihar", "Anand Vihar", "Delhi", 28.6469, 77.3159, 1.30),
    ("dl-ito", "ITO", "Delhi", 28.6286, 77.2410, 1.10),
    ("dl-punjabi-bagh", "Punjabi Bagh", "Delhi", 28.6740, 77.1310, 1.05),
    ("dl-rk-puram", "R K Puram", "Delhi", 28.5633, 77.1869, 0.95),
    ("dl-dwarka", "Dwarka Sector 8", "Delhi", 28.5710, 77.0719, 0.95),
    ("dl-lodhi-road", "Lodhi Road", "Delhi", 28.5918, 77.2273, 0.85),
    ("dl-rohini", "Rohini", "Delhi", 28.7325, 77.1199, 1.10),
    ("dl-okhla", "Okhla Phase 2", "Delhi", 28.5308, 77.2713, 1.15),
    ("dl-jahangirpuri", "Jahangirpuri", "Delhi", 28.7328, 77.1706, 1.25),
    ("dl-north-campus", "North Campus DU", "Delhi", 28.6573, 77.1585, 0.95),
    # Bengaluru
    ("blr-silk-board", "Silk Board", "Bengaluru", 12.9172, 77.6229, 1.35),
    ("blr-btm", "BTM Layout", "Bengaluru", 12.9135, 77.5950, 1.10),
    ("blr-hebbal", "Hebbal", "Bengaluru", 13.0294, 77.5859, 1.05),
    ("blr-peenya", "Peenya", "Bengaluru", 13.0270, 77.4940, 1.30),
    ("blr-jayanagar", "Jayanagar 5th Block", "Bengaluru", 12.9209, 77.5847, 0.90),
    ("blr-city-rly", "City Railway Station", "Bengaluru", 12.9776, 77.5713, 1.15),
    ("blr-bapuji-nagar", "Bapuji Nagar", "Bengaluru", 12.9510, 77.5400, 1.00),
    ("blr-hombegowda", "Hombegowda Nagar", "Bengaluru", 12.9380, 77.5900, 0.90),
    ("blr-whitefield", "Whitefield", "Bengaluru", 12.9698, 77.7500, 1.10),
    ("blr-kasturi-nagar", "Kasturi Nagar", "Bengaluru", 13.0035, 77.6600, 0.95),
    # Mumbai
    ("mum-bandra", "Bandra West", "Mumbai", 19.0596, 72.8295, 1.05),
    ("mum-colaba", "Colaba", "Mumbai", 18.9100, 72.8200, 0.85),
    ("mum-worli", "Worli", "Mumbai", 19.0000, 72.8150, 0.95),
    ("mum-andheri", "Andheri East", "Mumbai", 19.1197, 72.8697, 1.15),
    ("mum-chembur", "Chembur", "Mumbai", 19.0522, 72.9005, 1.20),
    ("mum-borivali", "Borivali East", "Mumbai", 19.2307, 72.8567, 0.95),
    ("mum-sion", "Sion", "Mumbai", 19.0400, 72.8620, 1.10),
    # Mysuru
    ("mys-hebbal-ia", "Hebbal Industrial Area", "Mysuru", 12.3530, 76.6100, 1.20),
    ("mys-kr-circle", "K R Circle", "Mysuru", 12.3080, 76.6520, 1.00),
    ("mys-vijayanagar", "Vijayanagar", "Mysuru", 12.3290, 76.6110, 0.85),
    ("mys-kuvempunagar", "Kuvempunagar", "Mysuru", 12.2860, 76.6250, 0.85),
]

# City-level climatology used by the simulator: base PM2.5 (ug/m3) and winter amplification.
CITY_PROFILE = {
    "Delhi": {"pm25": 62.0, "winter": 1.85, "monsoon": 0.45, "tz_offset": 5.5},
    "Bengaluru": {"pm25": 28.0, "winter": 1.2, "monsoon": 0.70, "tz_offset": 5.5},
    "Mumbai": {"pm25": 34.0, "winter": 1.55, "monsoon": 0.40, "tz_offset": 5.5},
    "Mysuru": {"pm25": 26.0, "winter": 1.2, "monsoon": 0.75, "tz_offset": 5.5},
}
