"""
Jyotisha interpretation layer — pure arithmetic on the sidereal positions the
engine already computes (no swisseph calls, no data files).

Every convention that has competing traditions is stated explicitly in the
output and documented here, so nothing is silently "picked":

- Dignity / moolatrikona / natural friendships: classical Parashari tables.
- Combustion (astangata) orbs: Phaladeepika/BPHS, with retrograde variants for
  Mercury (14°→12°) and Venus (10°→8°).
- Vimshottari dasha: 120-year cycle, **365.25-day solar year**.
- Divisional charts (D2–D60): Brihat Parashara Hora Shastra rules.
- Ashtakavarga: Parashari benefic-place tables (row totals 48/49/39/54/56/52/39,
  sum 337 — a built-in checksum, asserted in the tests).

Sign indices are 0=Aries … 11=Pisces.
"""

from __future__ import annotations

from . import catalog

SIGNS = catalog.SIGNS
_SPAN = 360.0 / 27.0  # nakshatra width


def _norm360(x):
    return x % 360.0


def _sign_of(lon):
    return int(_norm360(lon) // 30)


# --------------------------------------------------------------------------- #
# Dignity                                                                      #
# --------------------------------------------------------------------------- #
# planet -> (exaltation sign index, exact degree). Debilitation = opposite.
_EXALT = {"sun": (0, 10), "moon": (1, 3), "mars": (9, 28), "mercury": (5, 15),
          "jupiter": (3, 5), "venus": (11, 27), "saturn": (6, 20)}
_OWN = {"sun": [4], "moon": [3], "mars": [0, 7], "mercury": [2, 5],
        "jupiter": [8, 11], "venus": [1, 6], "saturn": [9, 10]}
# planet -> (sign, start_deg, end_deg)
_MOOLATRIKONA = {"sun": (4, 0, 20), "moon": (1, 3, 30), "mars": (0, 0, 12),
                 "mercury": (5, 15, 20), "jupiter": (8, 0, 10),
                 "venus": (6, 0, 15), "saturn": (10, 0, 20)}
# Natural (naisargika) friendships.
_FRIENDSHIP = {
    "sun": {"friends": ["moon", "mars", "jupiter"], "enemies": ["venus", "saturn"], "neutral": ["mercury"]},
    "moon": {"friends": ["sun", "mercury"], "enemies": [], "neutral": ["mars", "jupiter", "venus", "saturn"]},
    "mars": {"friends": ["sun", "moon", "jupiter"], "enemies": ["mercury"], "neutral": ["venus", "saturn"]},
    "mercury": {"friends": ["sun", "venus"], "enemies": ["moon"], "neutral": ["mars", "jupiter", "saturn"]},
    "jupiter": {"friends": ["sun", "moon", "mars"], "enemies": ["mercury", "venus"], "neutral": ["saturn"]},
    "venus": {"friends": ["mercury", "saturn"], "enemies": ["sun", "moon"], "neutral": ["mars", "jupiter"]},
    "saturn": {"friends": ["mercury", "venus"], "enemies": ["sun", "moon", "mars"], "neutral": ["jupiter"]},
}
# Sign lords, for own-sign / dispositor logic.
_SIGN_LORD = ["mars", "venus", "mercury", "moon", "sun", "mercury",
              "venus", "mars", "jupiter", "saturn", "saturn", "jupiter"]


def dignity(planet, sid_lon):
    """Classical dignity of a graha at a sidereal longitude."""
    if planet not in _EXALT:
        return None
    sign = _sign_of(sid_lon)
    deg = _norm360(sid_lon) % 30
    ex_sign, ex_deg = _EXALT[planet]
    deb_sign = (ex_sign + 6) % 12
    status = "neutral"
    if sign == ex_sign:
        status = "exalted"
    elif sign == deb_sign:
        status = "debilitated"
    else:
        mt_sign, mt_lo, mt_hi = _MOOLATRIKONA[planet]
        if sign == mt_sign and mt_lo <= deg < mt_hi:
            status = "moolatrikona"
        elif sign in _OWN[planet]:
            status = "own_sign"
        else:
            lord = _SIGN_LORD[sign]
            if lord == planet:
                status = "own_sign"
            elif lord in _FRIENDSHIP[planet]["friends"]:
                status = "friendly_sign"
            elif lord in _FRIENDSHIP[planet]["enemies"]:
                status = "enemy_sign"
            else:
                status = "neutral_sign"
    return {"status": status, "sign": SIGNS[sign], "sign_lord": _SIGN_LORD[sign].capitalize(),
            "exaltation": f"{SIGNS[ex_sign]} {ex_deg}°",
            "debilitation": f"{SIGNS[deb_sign]} {ex_deg}°"}


# --------------------------------------------------------------------------- #
# Combustion (astangata)                                                       #
# --------------------------------------------------------------------------- #
_COMBUST_ORB = {"moon": (12.0, 12.0), "mars": (17.0, 17.0),
                "mercury": (14.0, 12.0), "jupiter": (11.0, 11.0),
                "venus": (10.0, 8.0), "saturn": (15.0, 15.0)}


def combustion(planet, sun_lon, planet_lon, retrograde):
    if planet not in _COMBUST_ORB:
        return None
    sep = abs(_norm360(planet_lon - sun_lon))
    if sep > 180:
        sep = 360 - sep
    orb = _COMBUST_ORB[planet][1 if retrograde else 0]
    return {"combust": sep <= orb, "separation": round(sep, 4), "orb": orb}


# --------------------------------------------------------------------------- #
# Graha Drishti (Vedic aspects) — whole-sign                                   #
# --------------------------------------------------------------------------- #
# Extra special aspects (besides the universal 7th), as house-distances.
_SPECIAL_ASPECTS = {"mars": [4, 8], "jupiter": [5, 9], "saturn": [3, 10]}
_DRISHTI_BODIES = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn"]


def graha_drishti(positions):
    """Which planets each graha aspects (whole-sign drishti)."""
    sign_of = {k: _sign_of(v["lon"]) for k, v in positions.items()
               if k in _DRISHTI_BODIES}
    out = {}
    for p, psign in sign_of.items():
        houses = [7] + _SPECIAL_ASPECTS.get(p, [])
        aspected_signs = sorted({(psign + h - 1) % 12 for h in houses})
        hits = [q for q, qsign in sign_of.items()
                if q != p and qsign in aspected_signs]
        out[p] = {"aspects_houses": sorted(houses),
                  "aspected_signs": [SIGNS[s] for s in aspected_signs],
                  "aspected_planets": hits}
    return out


def graha_yuddha(positions):
    """Planetary war: two star-planets within 1°. Winner = the more northern
    (higher ecliptic latitude), the common rule."""
    war_bodies = ["mars", "mercury", "jupiter", "venus", "saturn"]
    present = [b for b in war_bodies if b in positions]
    wars = []
    for i in range(len(present)):
        for j in range(i + 1, len(present)):
            a, b = present[i], present[j]
            sep = abs(_norm360(positions[a]["lon"] - positions[b]["lon"]))
            if sep > 180:
                sep = 360 - sep
            if sep <= 1.0:
                la = positions[a].get("lat", 0.0)
                lb = positions[b].get("lat", 0.0)
                winner = a if la >= lb else b
                wars.append({"planets": [a, b], "separation": round(sep, 4),
                             "winner": winner})
    return wars


# --------------------------------------------------------------------------- #
# Vimshottari Dasha                                                            #
# --------------------------------------------------------------------------- #
_DASHA_YEARS = {"ketu": 7, "venus": 20, "sun": 6, "moon": 10, "mars": 7,
                "rahu": 18, "jupiter": 16, "saturn": 19, "mercury": 17}
_DASHA_ORDER = ["ketu", "venus", "sun", "moon", "mars", "rahu",
                "jupiter", "saturn", "mercury"]
_YEAR_DAYS = 365.25


def vimshottari(jd_birth, moon_sid_lon, jd_to_time):
    nak = int(_norm360(moon_sid_lon) // _SPAN)
    lord = catalog.NAKSHATRA_LORDS[nak].lower()
    frac = (_norm360(moon_sid_lon) % _SPAN) / _SPAN
    elapsed_years = frac * _DASHA_YEARS[lord]
    start_i = _DASHA_ORDER.index(lord)

    cursor = jd_birth - elapsed_years * _YEAR_DAYS  # theoretical maha start
    out_mahas = []
    current = {}
    for k in range(9):
        L = _DASHA_ORDER[(start_i + k) % 9]
        yrs = _DASHA_YEARS[L]
        m_start, m_end = cursor, cursor + yrs * _YEAR_DAYS
        cursor = m_end
        ai = _DASHA_ORDER.index(L)
        antars, acur = [], m_start
        for j in range(9):
            AL = _DASHA_ORDER[(ai + j) % 9]
            a_end = acur + (yrs * _DASHA_YEARS[AL] / 120.0) * _YEAR_DAYS
            if a_end > jd_birth:
                antars.append({"lord": AL.capitalize(),
                               "start": jd_to_time(max(acur, jd_birth)),
                               "end": jd_to_time(a_end)})
                if acur <= jd_birth < a_end and m_start <= jd_birth < m_end:
                    current = {"maha": L.capitalize(), "antar": AL.capitalize()}
            acur = a_end
        out_mahas.append({
            "lord": L.capitalize(),
            "start": jd_to_time(max(m_start, jd_birth)),
            "end": jd_to_time(m_end),
            "years": round((m_end - max(m_start, jd_birth)) / _YEAR_DAYS, 4),
            "antardashas": antars,
        })
    return {"system": "Vimshottari", "year_length_days": _YEAR_DAYS,
            "moon_nakshatra": catalog.NAKSHATRAS[nak],
            "starting_lord": lord.capitalize(),
            "balance_at_birth_years": round(_DASHA_YEARS[lord] * (1 - frac), 4),
            "current": current, "maha_dashas": out_mahas}


# --------------------------------------------------------------------------- #
# Divisional charts (Shodasavarga, BPHS rules)                                 #
# --------------------------------------------------------------------------- #
def _varga_sign(lon, d):
    """Sign index (0-11) of a body in the D-`d` divisional chart."""
    lon = _norm360(lon)
    sign = int(lon // 30)
    deg = lon % 30
    odd = sign % 2 == 0            # Aries(0) is the 1st = odd sign
    movable = sign % 3 == 0
    fixed = sign % 3 == 1
    element = sign % 4            # 0 fire, 1 earth, 2 air, 3 water

    if d == 1:
        return sign
    if d == 2:  # Hora — odd: 0-15 Leo,15-30 Cancer; even reversed
        first, second = (4, 3) if odd else (3, 4)
        return first if deg < 15 else second
    if d == 3:  # Drekkana: 1st self, 2nd 5th, 3rd 9th
        return (sign + (int(deg // 10)) * 4) % 12
    if d == 4:  # Chaturthamsa: kendras
        return (sign + (int(deg // 7.5)) * 3) % 12
    if d == 7:  # Saptamsa: odd from self, even from 7th
        start = sign if odd else (sign + 6) % 12
        return (start + int(deg // (30 / 7))) % 12
    if d == 9:  # Navamsa (continuous 108-division)
        return int(lon // (10 / 3)) % 12
    if d == 10:  # Dasamsa: odd from self, even from 9th
        start = sign if odd else (sign + 8) % 12
        return (start + int(deg // 3)) % 12
    if d == 12:  # Dwadasamsa: from self
        return (sign + int(deg // 2.5)) % 12
    if d == 16:  # Shodasamsa: movable Aries, fixed Leo, dual Sag
        start = 0 if movable else (4 if fixed else 8)
        return (start + int(deg // (30 / 16))) % 12
    if d == 20:  # Vimsamsa: movable Aries, fixed Sag, dual Leo
        start = 0 if movable else (8 if fixed else 4)
        return (start + int(deg // 1.5)) % 12
    if d == 24:  # Chaturvimsamsa: odd Leo, even Cancer
        start = 4 if odd else 3
        return (start + int(deg // 1.25)) % 12
    if d == 27:  # Bhamsa: fire Aries, earth Cancer, air Libra, water Cap
        start = [0, 3, 6, 9][element]
        return (start + int(deg // (30 / 27))) % 12
    if d == 30:  # Trimsamsa (unequal, no even/odd sign-crossing)
        if odd:
            table = [(5, 0), (10, 10), (18, 8), (25, 2), (30, 6)]   # Mars,Sat,Jup,Merc,Ven
        else:
            table = [(5, 1), (12, 5), (20, 11), (25, 9), (30, 7)]   # Ven,Merc,Jup,Sat,Mars
        for upper, tsign in table:
            if deg < upper:
                return tsign
        return table[-1][1]
    if d == 40:  # Khavedamsa: odd Aries, even Libra
        start = 0 if odd else 6
        return (start + int(deg // 0.75)) % 12
    if d == 45:  # Akshavedamsa: movable Aries, fixed Leo, dual Sag
        start = 0 if movable else (4 if fixed else 8)
        return (start + int(deg // (30 / 45))) % 12
    if d == 60:  # Shashtiamsa: count from the sign itself
        return (sign + int(deg * 2)) % 12
    raise ValueError(f"unsupported varga D{d}")


_VARGAS = [
    (1, "Rasi"), (2, "Hora"), (3, "Drekkana"), (4, "Chaturthamsa"),
    (7, "Saptamsa"), (9, "Navamsa"), (10, "Dasamsa"), (12, "Dwadasamsa"),
    (16, "Shodasamsa"), (20, "Vimsamsa"), (24, "Chaturvimsamsa"),
    (27, "Bhamsa"), (30, "Trimsamsa"), (40, "Khavedamsa"),
    (45, "Akshavedamsa"), (60, "Shashtiamsa"),
]


def divisional_charts(positions, asc_lon=None):
    """For each body (and the Ascendant), its sign in every varga D1–D60."""
    result = {"convention": "Brihat Parashara Hora Shastra", "bodies": {}}
    items = dict(positions)
    if asc_lon is not None:
        items["ascendant"] = {"lon": asc_lon}
    for key, v in items.items():
        charts = {}
        for d, name in _VARGAS:
            s = _varga_sign(v["lon"], d)
            charts[f"D{d}"] = {"varga": name, "sign": SIGNS[s], "sign_index": s}
        result["bodies"][key] = charts
    return result


# --------------------------------------------------------------------------- #
# Ashtakavarga (Parashari benefic-place tables → 48/49/39/54/56/52/39 = 337)   #
# --------------------------------------------------------------------------- #
# For each planet, benefic house-positions counted from each reference point
# (order: sun, moon, mars, mercury, jupiter, venus, saturn, ascendant).
_AV_REFS = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "ascendant"]
_BAV = {
    "sun":     [[1, 2, 4, 7, 8, 9, 10, 11], [3, 6, 10, 11], [1, 2, 4, 7, 8, 9, 10, 11], [3, 5, 6, 9, 10, 11, 12], [5, 6, 9, 11], [6, 7, 12], [1, 2, 4, 7, 8, 9, 10, 11], [3, 4, 6, 10, 11, 12]],
    "moon":    [[3, 6, 7, 8, 10, 11], [1, 3, 6, 7, 10, 11], [2, 3, 5, 6, 9, 10, 11], [1, 3, 4, 5, 7, 8, 10, 11], [1, 4, 7, 8, 10, 11, 12], [3, 4, 5, 7, 9, 10, 11], [3, 5, 6, 11], [3, 6, 10, 11]],
    "mars":    [[3, 5, 6, 10, 11], [3, 6, 11], [1, 2, 4, 7, 8, 10, 11], [3, 5, 6, 11], [6, 10, 11, 12], [6, 8, 11, 12], [1, 4, 7, 8, 9, 10, 11], [1, 3, 6, 10, 11]],
    "mercury": [[5, 6, 9, 11, 12], [2, 4, 6, 8, 10, 11], [1, 2, 4, 7, 8, 9, 10, 11], [1, 3, 5, 6, 9, 10, 11, 12], [6, 8, 11, 12], [1, 2, 3, 4, 5, 8, 9, 11], [1, 2, 4, 7, 8, 9, 10, 11], [1, 2, 4, 6, 8, 10, 11]],
    "jupiter": [[1, 2, 3, 4, 7, 8, 9, 10, 11], [2, 5, 7, 9, 11], [1, 2, 4, 7, 8, 10, 11], [1, 2, 4, 5, 6, 9, 10, 11], [1, 2, 3, 4, 7, 8, 10, 11], [2, 5, 6, 9, 10, 11], [3, 5, 6, 12], [1, 2, 4, 5, 6, 7, 9, 10, 11]],
    "venus":   [[8, 11, 12], [1, 2, 3, 4, 5, 8, 9, 11, 12], [3, 5, 6, 9, 11, 12], [3, 5, 6, 9, 11], [5, 8, 9, 10, 11], [1, 2, 3, 4, 5, 8, 9, 10, 11], [3, 4, 5, 8, 9, 10, 11], [1, 2, 3, 4, 5, 8, 9, 11]],
    "saturn":  [[1, 2, 4, 7, 8, 10, 11], [3, 6, 11], [3, 5, 6, 10, 11, 12], [6, 8, 9, 10, 11, 12], [5, 6, 11, 12], [6, 11, 12], [3, 5, 6, 11], [1, 3, 4, 6, 10, 11]],
}
_BAV_TOTALS = {"sun": 48, "moon": 49, "mars": 39, "mercury": 54,
               "jupiter": 56, "venus": 52, "saturn": 39}


def ashtakavarga(positions, asc_lon):
    """Bhinnashtakavarga (per planet) + Sarvashtakavarga (combined) bindu tables.

    positions: {planet: {"lon": sidereal_lon}} for sun..saturn.
    """
    ref_sign = {}
    for r in _AV_REFS:
        if r == "ascendant":
            ref_sign[r] = _sign_of(asc_lon) if asc_lon is not None else None
        elif r in positions:
            ref_sign[r] = _sign_of(positions[r]["lon"])
    bhinna, sarva = {}, [0] * 12
    for planet, rows in _BAV.items():
        bav = [0] * 12
        for ref, houses in zip(_AV_REFS, rows):
            rs = ref_sign.get(ref)
            if rs is None:
                continue
            for h in houses:
                bav[(rs + h - 1) % 12] += 1
        # index bindu tables by sign name for clarity
        bhinna[planet] = {"by_sign": {SIGNS[i]: bav[i] for i in range(12)},
                          "total": sum(bav)}
        for i in range(12):
            sarva[i] += bav[i]
    return {
        "note": "Rahu/Ketu excluded (Parashari). Sarva total is always 337.",
        "bhinnashtakavarga": bhinna,
        "sarvashtakavarga": {"by_sign": {SIGNS[i]: sarva[i] for i in range(12)},
                             "total": sum(sarva)},
    }
