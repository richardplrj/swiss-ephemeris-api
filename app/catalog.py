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
# Zodiac signs (30° ecliptic sectors — how swe_split_deg presents longitude)   #
# --------------------------------------------------------------------------- #
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
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
