"""
Ashtakoot / Guna Milan — 36-point Vedic marriage compatibility from two Moons.

All lookup tables are the classical ones (yoni animals + the standard 14×14
yoni matrix, gana, nadi cross-checked across sources). The three genuinely
convention-variant kootas — Vashya, Gana matrix, Graha Maitri — use the widely
implemented (AstroSage-style) scoring and are labelled as such in the output,
so nothing is presented as the single "true" number.

Inputs are two Moon sidereal longitudes (→ nakshatra + rasi). Point weights:
Varna 1, Vashya 2, Tara 3, Yoni 4, Graha Maitri 5, Gana 6, Bhakoot 7, Nadi 8.
"""

from __future__ import annotations

from . import catalog, jyotisha

_SPAN = 360.0 / 27.0
SIGNS = catalog.SIGNS

_ANIMALS = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat",
            "Cow", "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion"]

# nakshatra index 0-26 -> animal index 0-13
_NAK_YONI = [0, 1, 2, 3, 3, 4, 5, 2, 5, 6, 6, 7, 8, 9, 8, 9, 10, 10, 4, 11,
             12, 11, 13, 0, 13, 7, 1]

# 14×14 symmetric yoni matrix (diagonal 4; the 7 sworn-enemy pairs = 0)
_YONI_MATRIX = [
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1],
    [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1],
    [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1],
    [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2],
    [1, 2, 3, 1, 2, 2, 2, 4, 3, 0, 3, 2, 2, 1],
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1],
    [1, 1, 1, 2, 1, 1, 2, 0, 1, 4, 1, 1, 2, 1],
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1],
    [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2],
    [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4],
]

# nakshatra 0-26 -> gana
_NAK_GANA = ["deva", "manushya", "rakshasa", "manushya", "deva", "manushya",
             "deva", "deva", "rakshasa", "rakshasa", "manushya", "manushya",
             "deva", "rakshasa", "deva", "rakshasa", "deva", "rakshasa",
             "rakshasa", "manushya", "manushya", "deva", "rakshasa", "rakshasa",
             "manushya", "manushya", "deva"]
# nakshatra 0-26 -> nadi
_NAK_NADI = ["aadi", "madhya", "antya", "antya", "madhya", "aadi", "aadi",
             "madhya", "antya", "antya", "madhya", "aadi", "aadi", "madhya",
             "antya", "antya", "madhya", "aadi", "aadi", "madhya", "antya",
             "antya", "madhya", "aadi", "aadi", "madhya", "antya"]

# sign 0-11 -> varna rank (Brahmin 4 > Kshatriya 3 > Vaishya 2 > Shudra 1)
_VARNA_RANK = {0: 3, 1: 2, 2: 1, 3: 4}  # by sign % 4 (fire/earth/air/water)
_VARNA_NAME = {4: "Brahmin", 3: "Kshatriya", 2: "Vaishya", 1: "Shudra"}
# sign -> vashya group
_VASHYA_GROUP = ["chatushpada", "chatushpada", "nara", "jalachara", "vanachara",
                 "nara", "nara", "keeta", "nara", "jalachara", "nara", "jalachara"]

_SIGN_LORD = jyotisha._SIGN_LORD
_FRIEND = jyotisha._FRIENDSHIP


def _nak(lon):
    return int((lon % 360.0) // _SPAN)


def _rel(a, b):
    if a == b:
        return "friend"
    if b in _FRIEND[a]["friends"]:
        return "friend"
    if b in _FRIEND[a]["enemies"]:
        return "enemy"
    return "neutral"


# --------------------------------------------------------------------------- #
# The eight kootas                                                             #
# --------------------------------------------------------------------------- #
def _varna(b_sign, g_sign):
    br = _VARNA_RANK[b_sign % 4]
    gr = _VARNA_RANK[g_sign % 4]
    pts = 1 if br >= gr else 0
    return {"points": pts, "max": 1,
            "boy": _VARNA_NAME[br], "girl": _VARNA_NAME[gr]}


def _vashya(b_sign, g_sign):
    bg, gg = _VASHYA_GROUP[b_sign], _VASHYA_GROUP[g_sign]
    if b_sign == g_sign or bg == gg:
        pts = 2.0
    elif "keeta" in (bg, gg) and "nara" in (bg, gg):
        pts = 0.0
    elif {bg, gg} == {"chatushpada", "jalachara"} or {bg, gg} == {"nara", "chatushpada"}:
        pts = 1.0
    else:
        pts = 0.5
    return {"points": pts, "max": 2, "boy_group": bg, "girl_group": gg,
            "convention": "group-based"}


def _tara(b_nak, g_nak):
    def half(fr, to):
        n = ((to - fr) % 27) + 1
        r = n % 9 or 9
        return 1.5 if r not in (3, 5, 7) else 0.0
    pts = half(b_nak, g_nak) + half(g_nak, b_nak)
    return {"points": pts, "max": 3}


def _yoni(b_nak, g_nak):
    ba, ga = _NAK_YONI[b_nak], _NAK_YONI[g_nak]
    return {"points": _YONI_MATRIX[ba][ga], "max": 4,
            "boy": _ANIMALS[ba], "girl": _ANIMALS[ga]}


def _graha_maitri(b_sign, g_sign):
    bl, gl = _SIGN_LORD[b_sign], _SIGN_LORD[g_sign]
    r1, r2 = _rel(bl, gl), _rel(gl, bl)
    s = {r1, r2}
    if bl == gl or s == {"friend"}:
        pts = 5.0
    elif s == {"friend", "neutral"}:
        pts = 4.0
    elif s == {"neutral"}:
        pts = 3.0
    elif s == {"friend", "enemy"}:
        pts = 1.0
    elif s == {"neutral", "enemy"}:
        pts = 0.5
    else:
        pts = 0.0
    return {"points": pts, "max": 5, "boy_lord": bl.capitalize(),
            "girl_lord": gl.capitalize(), "convention": "natural friendship"}


_GANA_MATRIX = {  # boy -> girl -> points
    "deva": {"deva": 6, "manushya": 6, "rakshasa": 1},
    "manushya": {"deva": 5, "manushya": 6, "rakshasa": 0},
    "rakshasa": {"deva": 1, "manushya": 0, "rakshasa": 6},
}


def _gana(b_nak, g_nak):
    bg, gg = _NAK_GANA[b_nak], _NAK_GANA[g_nak]
    return {"points": _GANA_MATRIX[bg][gg], "max": 6,
            "boy": bg.capitalize(), "girl": gg.capitalize(),
            "convention": "standard gana matrix"}


def _bhakoot(b_sign, g_sign):
    a = ((g_sign - b_sign) % 12) + 1
    b = ((b_sign - g_sign) % 12) + 1
    bad = {frozenset((6, 8)), frozenset((5, 9)), frozenset((2, 12))}
    pts = 0 if frozenset((a, b)) in bad else 7
    return {"points": pts, "max": 7, "distances": [a, b]}


def _nadi(b_nak, g_nak):
    bn, gn = _NAK_NADI[b_nak], _NAK_NADI[g_nak]
    # Same nadi = dosha (0). Exception: same nakshatra is not a dosha.
    dosha = (bn == gn) and (b_nak != g_nak)
    return {"points": 0 if dosha else 8, "max": 8,
            "boy": bn.capitalize(), "girl": gn.capitalize(),
            "nadi_dosha": dosha}


def ashtakoot(boy_moon_lon, girl_moon_lon):
    b_nak, g_nak = _nak(boy_moon_lon), _nak(girl_moon_lon)
    b_sign, g_sign = int(boy_moon_lon % 360 // 30), int(girl_moon_lon % 360 // 30)
    kootas = {
        "varna": _varna(b_sign, g_sign),
        "vashya": _vashya(b_sign, g_sign),
        "tara": _tara(b_nak, g_nak),
        "yoni": _yoni(b_nak, g_nak),
        "graha_maitri": _graha_maitri(b_sign, g_sign),
        "gana": _gana(b_nak, g_nak),
        "bhakoot": _bhakoot(b_sign, g_sign),
        "nadi": _nadi(b_nak, g_nak),
    }
    total = sum(k["points"] for k in kootas.values())
    return {
        "system": "Ashtakoot Guna Milan",
        "convention": "Classical tables; Vashya/Gana/Graha-Maitri use the "
                      "standard (AstroSage-style) scoring — see per-koota labels.",
        "boy": {"nakshatra": catalog.NAKSHATRAS[b_nak], "rasi": SIGNS[b_sign]},
        "girl": {"nakshatra": catalog.NAKSHATRAS[g_nak], "rasi": SIGNS[g_sign]},
        "kootas": kootas,
        "total_points": round(total, 1),
        "max_points": 36,
        "verdict": _verdict(total),
    }


def _verdict(total):
    if total >= 24:
        return "Very good match"
    if total >= 18:
        return "Acceptable match (classical minimum is 18)"
    return "Below the classical minimum of 18"
