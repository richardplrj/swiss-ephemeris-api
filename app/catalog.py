"""
Static reference catalog for the Swiss Ephemeris API.

Pure data + naming tables — no `swisseph` import here, so this module is safe to
import anywhere and cheap to test. Anything that depends on the live `swisseph`
build (ayanamsha enum, available house systems) is resolved dynamically in
``engine.py`` instead, so this file never drifts against the compiled library.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Bodies (planets, points, asteroids)                                         #
# --------------------------------------------------------------------------- #
# swisseph planet constants are stable across versions (0..21), so they are
# safe to hard-code. `key` is the stable machine name used in the JSON output.
#
# tuple = (key, swe_const, display_name, category)
#   category: "luminary" | "planet" | "point" | "asteroid"

# swisseph integer constants (mirrored so catalog.py needs no swisseph import)
_SUN, _MOON, _MERCURY, _VENUS, _MARS = 0, 1, 2, 3, 4
_JUPITER, _SATURN, _URANUS, _NEPTUNE, _PLUTO = 5, 6, 7, 8, 9
_MEAN_NODE, _TRUE_NODE, _MEAN_APOG, _OSCU_APOG = 10, 11, 12, 13
_EARTH = 14
_CHIRON, _PHOLUS, _CERES, _PALLAS, _JUNO, _VESTA = 15, 16, 17, 18, 19, 20
_INTP_APOG, _INTP_PERG = 21, 22

# Default body set returned on every request.
# Ketu (South Node) is derived as Rahu + 180 in the engine, not a swe constant.
DEFAULT_BODIES: list[tuple[str, int, str, str]] = [
    ("sun", _SUN, "Sun", "luminary"),
    ("moon", _MOON, "Moon", "luminary"),
    ("mercury", _MERCURY, "Mercury", "planet"),
    ("venus", _VENUS, "Venus", "planet"),
    ("mars", _MARS, "Mars", "planet"),
    ("jupiter", _JUPITER, "Jupiter", "planet"),
    ("saturn", _SATURN, "Saturn", "planet"),
    ("uranus", _URANUS, "Uranus", "planet"),
    ("neptune", _NEPTUNE, "Neptune", "planet"),
    ("pluto", _PLUTO, "Pluto", "planet"),
    ("mean_node", _MEAN_NODE, "Mean Node (Rahu)", "point"),
    ("true_node", _TRUE_NODE, "True Node (Rahu)", "point"),
    ("mean_lilith", _MEAN_APOG, "Mean Lilith (Mean Apogee)", "point"),
    ("true_lilith", _OSCU_APOG, "True Lilith (Osculating Apogee)", "point"),
    ("chiron", _CHIRON, "Chiron", "asteroid"),
    ("ceres", _CERES, "Ceres", "asteroid"),
    ("pallas", _PALLAS, "Pallas", "asteroid"),
    ("juno", _JUNO, "Juno", "asteroid"),
    ("vesta", _VESTA, "Vesta", "asteroid"),
]

# Extra bodies exposed only when the caller asks for bodies=all.
EXTRA_BODIES: list[tuple[str, int, str, str]] = [
    ("earth", _EARTH, "Earth (heliocentric only)", "point"),
    ("pholus", _PHOLUS, "Pholus", "asteroid"),
    ("interpolated_apogee", _INTP_APOG, "Interpolated Apogee", "point"),
    ("interpolated_perigee", _INTP_PERG, "Interpolated Perigee", "point"),
]

# Uranian (Hamburg school) + fictitious/hypothetical bodies. All computed from
# built-in orbital elements (40-54) or seorbel.txt (55-58) — NO .se1 data files.
# Included only when the caller asks for bodies=all or bodies=fictitious.
FICTITIOUS_BODIES: list[tuple[str, int, str, str]] = [
    ("cupido", 40, "Cupido", "uranian"),
    ("hades", 41, "Hades", "uranian"),
    ("zeus", 42, "Zeus", "uranian"),
    ("kronos", 43, "Kronos", "uranian"),
    ("apollon", 44, "Apollon", "uranian"),
    ("admetos", 45, "Admetos", "uranian"),
    ("vulkanus", 46, "Vulkanus", "uranian"),
    ("poseidon", 47, "Poseidon", "uranian"),
    ("isis_transpluto", 48, "Isis-Transpluto", "fictitious"),
    ("nibiru", 49, "Nibiru", "fictitious"),
    ("harrington", 50, "Harrington", "fictitious"),
    ("neptune_leverrier", 51, "Neptune (Leverrier)", "fictitious"),
    ("neptune_adams", 52, "Neptune (Adams)", "fictitious"),
    ("pluto_lowell", 53, "Pluto (Lowell)", "fictitious"),
    ("pluto_pickering", 54, "Pluto (Pickering)", "fictitious"),
    ("vulcan", 55, "Vulcan", "fictitious"),
    ("white_moon", 56, "White Moon (Selena)", "fictitious"),
    ("proserpina", 57, "Proserpina", "fictitious"),
    ("waldemath", 58, "Waldemath (Dark Moon)", "fictitious"),
]

ALL_BODIES = DEFAULT_BODIES + EXTRA_BODIES + FICTITIOUS_BODIES
BODY_KEY_TO_CONST = {key: const for key, const, _n, _c in ALL_BODIES}

# --------------------------------------------------------------------------- #
# Muhurta / Kaala tables (derived; used by vedic.py)                          #
# --------------------------------------------------------------------------- #
# Which of the 8 equal day-parts (1..8, sunrise→sunset) each falls in,
# indexed by weekday 0=Sunday .. 6=Saturday.
RAHU_KAAL_PART = [8, 2, 7, 5, 6, 4, 3]
YAMAGANDA_PART = [5, 4, 3, 2, 1, 7, 6]
GULIKA_PART = [7, 6, 5, 4, 3, 2, 1]

# Choghadiya: 7 types with fixed quality. Day sequence starts at a weekday-set
# offset and cycles in this fixed order; night sequence uses a +offset.
CHOGHADIYA = {
    "Udveg": ("bad", "Sun"), "Chal": ("neutral", "Venus"),
    "Labh": ("good", "Mercury"), "Amrit": ("good", "Moon"),
    "Kaal": ("bad", "Saturn"), "Shubh": ("good", "Jupiter"),
    "Rog": ("bad", "Mars"),
}
# Fixed cyclic order of choghadiyas.
CHOGHADIYA_ORDER = ["Udveg", "Chal", "Labh", "Amrit", "Kaal", "Shubh", "Rog"]
# Index into CHOGHADIYA_ORDER of the FIRST day-choghadiya, by weekday 0=Sun..6=Sat.
CHOGHADIYA_DAY_START = {0: 0, 1: 3, 2: 6, 3: 2, 4: 5, 5: 1, 6: 4}

# Planetary-hours (Hora) ruler cycle (Chaldean order) and the day-lord that
# rules the first hora after sunrise, by weekday 0=Sun..6=Sat.
HORA_ORDER = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
WEEKDAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# --------------------------------------------------------------------------- #
# House systems (single-char swisseph codes)                                  #
# --------------------------------------------------------------------------- #
# The engine validates each code against the live build via swe.house_name();
# this table is for documentation / the /v1/meta listing.
HOUSE_SYSTEMS: dict[str, str] = {
    "P": "Placidus",
    "K": "Koch",
    "O": "Porphyry",
    "R": "Regiomontanus",
    "C": "Campanus",
    "A": "Equal (cusp 1 = Ascendant)",
    "E": "Equal (cusp 1 = Ascendant)",
    "D": "Equal (cusp 10 = MC)",
    "V": "Vehlow equal",
    "W": "Whole sign",
    "N": "Whole sign (Aries = 1st house)",
    "B": "Alcabitius",
    "M": "Morinus",
    "U": "Krusinski-Pisa-Goelzer",
    "X": "Axial rotation / Meridian",
    "H": "Horizontal / Azimuthal",
    "T": "Polich-Page (topocentric)",
    "G": "Gauquelin sectors",
    "F": "Carter poli-equatorial",
    "L": "Pullen SD (sinusoidal delta)",
    "Q": "Pullen SR (sinusoidal ratio)",
    "S": "Sripati",
    "I": "Sunshine (Makransky)",
    "i": "Sunshine (alternative)",
    "Y": "APC houses",
}

# The 8 meaningful slots of the swisseph ascmc[] array.
ASCMC_NAMES = [
    "ascendant",
    "mc",
    "armc",
    "vertex",
    "equatorial_ascendant",
    "coascendant_koch",
    "coascendant_munkasey",
    "polar_ascendant",
]

# --------------------------------------------------------------------------- #
# Ayanamsha display names (keyed by swisseph SIDM_* integer value)            #
# --------------------------------------------------------------------------- #
# The engine builds the *authoritative* list from the live build's SIDM_*
# attributes; this table just supplies friendly names + a canonical slug.
AYANAMSHA_NAMES: dict[int, str] = {
    0: "Fagan/Bradley",
    1: "Lahiri",
    2: "De Luce",
    3: "Raman",
    4: "Usha/Shashi",
    5: "Krishnamurti (KP)",
    6: "Djwhal Khul",
    7: "Yukteshwar",
    8: "J.N. Bhasin",
    9: "Babylonian/Kugler 1",
    10: "Babylonian/Kugler 2",
    11: "Babylonian/Kugler 3",
    12: "Babylonian/Huber",
    13: "Babylonian/Eta Piscium",
    14: "Babylonian/Aldebaran = 15 Tau",
    15: "Hipparchos",
    16: "Sassanian",
    17: "Galactic Center = 0 Sag",
    18: "J2000",
    19: "J1900",
    20: "B1950",
    21: "Suryasiddhanta",
    22: "Suryasiddhanta (mean Sun)",
    23: "Aryabhata",
    24: "Aryabhata (mean Sun)",
    25: "SS Revati",
    26: "SS Citra",
    27: "True Chitrapaksha (Spica 180)",
    28: "True Revati",
    29: "True Pushya (PVRN Rao)",
    30: "Galactic Center (Gil Brand)",
    31: "Galactic Equator (IAU 1958)",
    32: "Galactic Equator",
    33: "Galactic Equator (mid-Mula)",
    34: "Skydram/Mardyks",
    35: "True Mula (Chandra Hari)",
    36: "Dhruva/Galactic Center/Mula (Wilhelm)",
    37: "Aryabhata 522",
    38: "Babylonian/Britton",
    39: "Vedic/Sheoran",
    40: "Cochrane (Galactic Center = 0 Cap)",
    41: "Galactic Equator (Fiorenza)",
    42: "Vettius Valens",
    43: "Lahiri 1940",
    44: "Lahiri VP285",
    45: "Krishnamurti-Senthilathiban",
    46: "Lahiri ICRC",
}

# Friendly slug -> SIDM value, for the ?ayanamsha= query param.
AYANAMSHA_ALIASES: dict[str, int] = {
    "fagan_bradley": 0, "fagan/bradley": 0, "fagan": 0,
    "lahiri": 1, "chitrapaksha": 1,
    "deluce": 2, "de_luce": 2,
    "raman": 3,
    "usha_shashi": 4,
    "krishnamurti": 5, "kp": 5,
    "djwhal_khul": 6,
    "yukteshwar": 7,
    "jn_bhasin": 8, "bhasin": 8,
    "hipparchos": 15,
    "sassanian": 16,
    "galactic_center": 17, "galcent": 17,
    "j2000": 18, "j1900": 19, "b1950": 20,
    "suryasiddhanta": 21,
    "aryabhata": 23,
    "ss_revati": 25, "ss_citra": 26,
    "true_chitra": 27, "true_chitrapaksha": 27,
    "true_revati": 28, "true_pushya": 29,
    "galactic_center_gilbrand": 30,
    "true_mula": 35,
    "lahiri_1940": 43, "lahiri_icrc": 46,
    "krishnamurti_senthilathiban": 45,
}

# --------------------------------------------------------------------------- #
# Vedic naming tables                                                         #
# --------------------------------------------------------------------------- #
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGNS_SANSKRIT = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]
# Vimshottari dasha lord of each nakshatra (repeats every 9).
_NAKSHATRA_LORD_CYCLE = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]
NAKSHATRA_LORDS = [_NAKSHATRA_LORD_CYCLE[i % 9] for i in range(27)]

# Tithi names within a paksha (1..15). Index 14 differs by paksha
# (Purnima for Shukla, Amavasya for Krishna) — handled in vedic.py.
TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Purnima/Amavasya",
]

YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha",
    "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra",
    "Vaidhriti",
]

# The 7 repeating (movable) karanas + 4 fixed karanas. Mapping of the 60
# half-tithis of a lunar month to names is done in vedic.py.
KARANA_MOVABLE = [
    "Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti",
]
KARANA_FIXED = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"]

# Weekday (vara). Index 0 = Sunday, matching (floor(jd_ut + 1.5) % 7).
WEEKDAYS = [
    ("Sunday", "Ravivara", "Sun"),
    ("Monday", "Somavara", "Moon"),
    ("Tuesday", "Mangalavara", "Mars"),
    ("Wednesday", "Budhavara", "Mercury"),
    ("Thursday", "Guruvara", "Jupiter"),
    ("Friday", "Shukravara", "Venus"),
    ("Saturday", "Shanivara", "Saturn"),
]

# --------------------------------------------------------------------------- #
# Curated fixed-star set returned by include=fixed_stars (default subset)     #
# --------------------------------------------------------------------------- #
# Names are passed to swe.fixstar2_ut(); unresolved names are skipped safely.
DEFAULT_FIXED_STARS = [
    "Spica", "Regulus", "Aldebaran", "Antares", "Sirius", "Canopus",
    "Arcturus", "Vega", "Betelgeuse", "Rigel", "Pollux", "Fomalhaut",
    "Altair", "Deneb", "Polaris", "Castor", "Alcyone",
]
