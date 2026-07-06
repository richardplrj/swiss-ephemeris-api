"""
Vedic (Jyotisha) derivations.

Everything here is DERIVED arithmetically from the sidereal Sun/Moon longitudes
that ``engine.py`` already computed via Swiss Ephemeris — the library itself has
no notion of tithi, yoga, karana, etc. Every field in the output is therefore
flagged ``"derived": true`` upstream so consumers never mistake it for a raw
ephemeris quantity.

Longitudes passed in are sidereal degrees (nirayana), which is what Jyotisha
uses. (Tithi/karana depend only on the Moon−Sun elongation, so the ayanamsha
cancels; yoga and nakshatra genuinely need the sidereal frame.)
"""

from __future__ import annotations

import swisseph as swe

from . import catalog

_NAK_SPAN = 360.0 / 27.0        # 13°20'
_YOGA_SPAN = 360.0 / 27.0       # 13°20'
_NAVAMSA_SPAN = 10.0 / 3.0      # 3°20'


def _norm360(x: float) -> float:
    return x % 360.0


def rasi(sidereal_longitude: float) -> dict:
    idx = int(_norm360(sidereal_longitude) // 30) % 12
    return {"index": idx, "number": idx + 1,
            "name": catalog.SIGNS[idx], "sanskrit": catalog.SIGNS_SANSKRIT[idx]}


def navamsa_sign(sidereal_longitude: float) -> dict:
    """D9 sign. The continuous 108-division formula reproduces the classical
    movable/fixed/dual starting-sign rule exactly."""
    idx = int(_norm360(sidereal_longitude) // _NAVAMSA_SPAN) % 12
    return {"index": idx, "number": idx + 1,
            "name": catalog.SIGNS[idx], "sanskrit": catalog.SIGNS_SANSKRIT[idx]}


def _phase_name(elongation: float) -> str:
    e = _norm360(elongation)
    if e < 45:
        return "New Moon (waxing crescent)"
    if e < 90:
        return "Waxing crescent"
    if e < 135:
        return "First quarter (waxing gibbous)"
    if e < 180:
        return "Waxing gibbous"
    if e < 225:
        return "Full Moon (waning gibbous)"
    if e < 270:
        return "Waning gibbous"
    if e < 315:
        return "Last quarter (waning crescent)"
    return "Waning crescent"


def tithi(sun_sid: float, moon_sid: float) -> dict:
    elong = _norm360(moon_sid - sun_sid)
    idx = int(elong // 12)                       # 0..29
    paksha = "Shukla" if idx < 15 else "Krishna"
    within = idx % 15                            # 0..14
    if within == 14:
        name = "Purnima" if paksha == "Shukla" else "Amavasya"
    else:
        name = catalog.TITHI_NAMES[within]
    frac = (elong % 12) / 12.0
    return {"index": idx, "number": idx + 1, "name": name, "paksha": paksha,
            "number_in_paksha": within + 1,
            "elongation": round(elong, 6),
            "completion_fraction": round(frac, 6)}


def yoga(sun_sid: float, moon_sid: float) -> dict:
    total = _norm360(sun_sid + moon_sid)
    idx = int(total // _YOGA_SPAN) % 27
    frac = (total % _YOGA_SPAN) / _YOGA_SPAN
    return {"index": idx, "number": idx + 1, "name": catalog.YOGAS[idx],
            "completion_fraction": round(frac, 6)}


def karana(sun_sid: float, moon_sid: float) -> dict:
    """60 half-tithis per lunar month → 11 karanas (7 movable + 4 fixed).

    Fixed placements: Kimstughna = 1st karana; Shakuni/Chatushpada/Naga = last
    three (58th/59th/60th); the 7 movable karanas fill 2nd..57th."""
    elong = _norm360(moon_sid - sun_sid)
    n = int(elong // 6)                          # 0..59
    if n == 0:
        name = "Kimstughna"
    elif 1 <= n <= 56:
        name = catalog.KARANA_MOVABLE[(n - 1) % 7]
    elif n == 57:
        name = "Shakuni"
    elif n == 58:
        name = "Chatushpada"
    else:                                        # n == 59
        name = "Naga"
    return {"index": n, "number": n + 1, "name": name}


def weekday(jd_ut: float) -> dict:
    idx = int((jd_ut + 1.5) % 7)                 # 0 = Sunday
    en, sanskrit, lord = catalog.WEEKDAYS[idx]
    return {"index": idx, "name": en, "sanskrit": sanskrit, "lord": lord}


# --------------------------------------------------------------------------- #
# Sunrise-anchored elements (need a location)                                 #
# --------------------------------------------------------------------------- #
def _next_event(jd_start, ipl, rsmi, geopos, atpress, attemp):
    try:
        res, tret = swe.rise_trans(jd_start, ipl, rsmi, geopos,
                                   atpress, attemp, swe.FLG_SWIEPH)
        if res == -2 or not tret[0]:
            return None
        return tret[0]
    except swe.Error:
        return None


def _most_recent(jd, ipl, rsmi, geopos, atpress, attemp):
    """Latest event at or before jd (events are ~1 day apart)."""
    e = _next_event(jd - 1.2, ipl, rsmi, geopos, atpress, attemp)
    if e is None:
        return None
    while True:
        nxt = _next_event(e + 0.01, ipl, rsmi, geopos, atpress, attemp)
        if nxt is not None and nxt <= jd:
            e = nxt
        else:
            return e


def sunrise_elements(jd_ut, geolat, geolon, alt, atpress, attemp, jd_to_time):
    """Sun/Moon rise & set around `jd`, day length, and sunrise-based Hindu vara.

    `jd_to_time` is engine.jd_to_time, injected to avoid an import cycle."""
    geopos = (geolon, geolat, alt or 0.0)
    hin_rise = swe.CALC_RISE | swe.BIT_HINDU_RISING
    hin_set = swe.CALC_SET | swe.BIT_HINDU_RISING

    prev_sunrise = _most_recent(jd_ut, swe.SUN, hin_rise, geopos, atpress, attemp)
    next_sunrise = _next_event(jd_ut, swe.SUN, hin_rise, geopos, atpress, attemp)
    next_sunset = _next_event(jd_ut, swe.SUN, hin_set, geopos, atpress, attemp)

    out = {
        "previous_sunrise": jd_to_time(prev_sunrise) if prev_sunrise else None,
        "next_sunrise": jd_to_time(next_sunrise) if next_sunrise else None,
        "next_sunset": jd_to_time(next_sunset) if next_sunset else None,
        "next_moonrise": None,
        "next_moonset": None,
        "day_length_hours": None,
        "hindu_vara": None,
    }

    mr = _next_event(jd_ut, swe.MOON, swe.CALC_RISE | swe.BIT_DISC_CENTER,
                     geopos, atpress, attemp)
    ms = _next_event(jd_ut, swe.MOON, swe.CALC_SET | swe.BIT_DISC_CENTER,
                     geopos, atpress, attemp)
    out["next_moonrise"] = jd_to_time(mr) if mr else None
    out["next_moonset"] = jd_to_time(ms) if ms else None

    # Day length = sunset following the most recent sunrise.
    if prev_sunrise is not None:
        sunset_after = _next_event(prev_sunrise, swe.SUN, hin_set,
                                   geopos, atpress, attemp)
        if sunset_after is not None:
            out["day_length_hours"] = round((sunset_after - prev_sunrise) * 24, 4)
        # Hindu day runs sunrise→sunrise, so the vara is that of prev_sunrise.
        wd = weekday(prev_sunrise)
        out["hindu_vara"] = wd
        # Muhurta windows for the current sunrise→sunrise day.
        if sunset_after is not None:
            night_end = _next_event(sunset_after + 0.01, swe.SUN, hin_rise,
                                    geopos, atpress, attemp)
            out["muhurta"] = muhurta(prev_sunrise, sunset_after, night_end,
                                     wd["index"], jd_to_time)

    return out


# --------------------------------------------------------------------------- #
# Muhurta / electional windows (derived from sunrise/sunset + weekday)        #
# --------------------------------------------------------------------------- #
def _segment(start, end, part_1based, n_parts, jd_to_time):
    seg = (end - start) / n_parts
    s = start + (part_1based - 1) * seg
    return {"start": jd_to_time(s), "end": jd_to_time(s + seg)}


def _choghadiya(start, end, weekday_idx, night, jd_to_time):
    seg = (end - start) / 8.0
    day_start = catalog.CHOGHADIYA_DAY_START[weekday_idx]
    first = (day_start + 5) % 7 if night else day_start
    out = []
    for i in range(8):
        name = catalog.CHOGHADIYA_ORDER[(first + i) % 7]
        quality, lord = catalog.CHOGHADIYA[name]
        s = start + i * seg
        out.append({"name": name, "quality": quality, "lord": lord,
                    "start": jd_to_time(s), "end": jd_to_time(s + seg)})
    return out


def _horas(day_sunrise, day_sunset, night_end, weekday_idx, jd_to_time):
    """24 planetary hours: 12 across the day, 12 across the night."""
    lord = catalog.WEEKDAY_LORD[weekday_idx]
    start_idx = catalog.HORA_ORDER.index(lord)
    day_seg = (day_sunset - day_sunrise) / 12.0
    night_seg = (night_end - day_sunset) / 12.0
    out = []
    for n in range(24):
        ruler = catalog.HORA_ORDER[(start_idx + n) % 7]
        if n < 12:
            s = day_sunrise + n * day_seg
            e = s + day_seg
        else:
            s = day_sunset + (n - 12) * night_seg
            e = s + night_seg
        out.append({"hora": n + 1, "lord": ruler, "period": "day" if n < 12 else "night",
                    "start": jd_to_time(s), "end": jd_to_time(e)})
    return out


def muhurta(day_sunrise, day_sunset, night_end, weekday_idx, jd_to_time):
    mu = 48.0 / 1440.0  # one muhurta = 48 minutes, in days
    out = {
        "rahu_kaal": _segment(day_sunrise, day_sunset,
                              catalog.RAHU_KAAL_PART[weekday_idx], 8, jd_to_time),
        "yamaganda": _segment(day_sunrise, day_sunset,
                             catalog.YAMAGANDA_PART[weekday_idx], 8, jd_to_time),
        "gulika_kaal": _segment(day_sunrise, day_sunset,
                              catalog.GULIKA_PART[weekday_idx], 8, jd_to_time),
        "abhijit_muhurta": _segment(day_sunrise, day_sunset, 8, 15, jd_to_time),
        "brahma_muhurta": {"start": jd_to_time(day_sunrise - 2 * mu),
                           "end": jd_to_time(day_sunrise - mu)},
        "choghadiya_day": _choghadiya(day_sunrise, day_sunset, weekday_idx, False, jd_to_time),
    }
    if night_end is not None:
        out["choghadiya_night"] = _choghadiya(day_sunset, night_end, weekday_idx, True, jd_to_time)
        out["hora"] = _horas(day_sunrise, day_sunset, night_end, weekday_idx, jd_to_time)
    return out


def compute(jd_ut, sun_sid, moon_sid, moon_illum=None,
            geolat=None, geolon=None, alt=None,
            atpress=0.0, attemp=0.0, jd_to_time=None):
    elong = _norm360(moon_sid - sun_sid)
    block = {
        "derived": True,
        "note": "Panchanga & varga computed from sidereal Sun/Moon; not raw ephemeris output.",
        "moon_rasi": rasi(moon_sid),
        "sun_rasi": rasi(sun_sid),
        "moon_navamsa": navamsa_sign(moon_sid),
        "sun_navamsa": navamsa_sign(sun_sid),
        "tithi": tithi(sun_sid, moon_sid),
        "yoga": yoga(sun_sid, moon_sid),
        "karana": karana(sun_sid, moon_sid),
        "vara": weekday(jd_ut),
        "moon_phase": {
            "elongation": round(elong, 6),
            "name": _phase_name(elong),
            "illuminated_fraction": round(moon_illum, 6) if moon_illum is not None else None,
            "paksha": "Shukla" if elong < 180 else "Krishna",
        },
    }
    if geolat is not None and geolon is not None and jd_to_time is not None:
        block["sunrise_sunset"] = sunrise_elements(
            jd_ut, geolat, geolon, alt, atpress, attemp, jd_to_time)
    return block
