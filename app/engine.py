"""
Swiss Ephemeris compute engine.

Every ``swisseph`` call in the whole service goes through this module. It wraps
the C library's global-state functions (``set_sid_mode``, ``set_topo``) behind a
single process-wide lock, because pyswisseph keeps ayanamsha / topocentre in
C globals and FastAPI runs sync endpoints in a threadpool — without the lock,
two concurrent requests with different ayanamshas would corrupt each other.

All angular outputs are in degrees. Distances are in AU (the Moon too).
Speeds are per day. Times are Julian Day (UT) plus an ISO-8601 UTC rendering.
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache

import swisseph as swe

from . import catalog
from . import vedic

# --------------------------------------------------------------------------- #
# Module state                                                                #
# --------------------------------------------------------------------------- #
_LOCK = threading.RLock()
_EPHE_PATH = os.environ.get(
    "SWISSAPI_EPHE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ephe"),
)
SOURCE_URL = os.environ.get(
    "SWISSAPI_SOURCE_URL", "https://github.com/richardplrj/swiss-ephemeris-api"
)
LICENSE = "AGPL-3.0-or-later"

_BASE = swe.FLG_SWIEPH | swe.FLG_SPEED

# Which bodies physically support phase / magnitude / rise-set.
_PHYSICAL = {"sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
             "uranus", "neptune", "pluto", "chiron", "ceres", "pallas",
             "juno", "vesta", "pholus"}
_RISE_BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
                "saturn", "uranus", "neptune", "pluto"]

_initialized = False


def init() -> None:
    """Point swisseph at the bundled .se1 files. Idempotent, called at startup."""
    global _initialized
    with _LOCK:
        swe.set_ephe_path(_EPHE_PATH)
        _initialized = True


def swe_version() -> str:
    return swe.version


# --------------------------------------------------------------------------- #
# Small formatting helpers                                                    #
# --------------------------------------------------------------------------- #
def _norm360(x: float) -> float:
    return x % 360.0


def _r8(x):
    """round-8 that tolerates None (for out-of-range degraded fields)."""
    return None if x is None else round(x, 8)


def _sign_block(longitude: float, sidereal: bool = False) -> dict:
    """Sign placement of an ecliptic longitude (0..360)."""
    lon = _norm360(longitude)
    idx = int(lon // 30) % 12
    deg_in_sign = lon - idx * 30
    d = int(deg_in_sign)
    m_full = (deg_in_sign - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    return {
        "index": idx,
        "name": catalog.SIGNS[idx],
        "sanskrit": catalog.SIGNS_SANSKRIT[idx],
        "degrees_in_sign": round(deg_in_sign, 6),
        "dms": f"{d:02d}°{m:02d}'{s:04.1f}\"",
    }


def _nakshatra_block(sidereal_longitude: float) -> dict:
    """27-nakshatra placement of a *sidereal* longitude."""
    lon = _norm360(sidereal_longitude)
    span = 360.0 / 27.0                      # 13°20'
    idx = int(lon // span) % 27
    pos_in_nak = lon - idx * span
    pada = int(pos_in_nak // (span / 4.0)) + 1
    return {
        "index": idx,
        "number": idx + 1,
        "name": catalog.NAKSHATRAS[idx],
        "pada": pada,
        "lord": catalog.NAKSHATRA_LORDS[idx],
        "degrees_in_nakshatra": round(pos_in_nak, 6),
    }


def jd_to_time(jd_ut: float) -> dict:
    """Julian Day (UT) -> {jd_ut, iso, calendar} with a BCE-safe fallback."""
    y, mo, d, hour = swe.revjul(jd_ut, swe.GREG_CAL)
    hh = int(hour)
    mm = int((hour - hh) * 60)
    ss = (hour - hh) * 3600 - mm * 60
    cal = {"year": y, "month": mo, "day": d, "hour": hh, "minute": mm,
           "second": round(ss, 3)}
    iso = None
    if 1 <= y <= 9999:
        iso = (f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:"
               f"{int(ss):02d}.{int((ss % 1) * 1e6):06d}Z")
    return {"jd_ut": jd_ut, "iso": iso, "calendar": cal}


def _ephe_label(retflag: int) -> str:
    if retflag < 0:
        return "error"
    if retflag & swe.FLG_MOSEPH:
        return "moshier"
    if retflag & swe.FLG_JPLEPH:
        return "jpl"
    return "swiss"


# --------------------------------------------------------------------------- #
# Per-body positions                                                          #
# --------------------------------------------------------------------------- #
def _calc(jd_ut: float, ipl: int, flags: int):
    """swe.calc_ut wrapper -> (xx6, retflag) or (None, err) on swe.Error."""
    try:
        xx, retflag = swe.calc_ut(jd_ut, ipl, flags)
        return xx, retflag
    except swe.Error as exc:  # out-of-range date, missing body, etc.
        return None, str(exc)


def _ecliptic(xx) -> dict:
    return {
        "longitude": round(_norm360(xx[0]), 8),
        "latitude": round(xx[1], 8),
        "distance_au": round(xx[2], 10),
        "longitude_speed": round(xx[3], 8),
        "latitude_speed": round(xx[4], 8),
        "distance_speed": round(xx[5], 10),
        "retrograde": xx[3] < 0,
    }


def _equatorial(xx) -> dict:
    return {
        "right_ascension": round(_norm360(xx[0]), 8),
        "declination": round(xx[1], 8),
        "distance_au": round(xx[2], 10),
        "ra_speed": round(xx[3], 8),
        "dec_speed": round(xx[4], 8),
    }


def _body_object(jd_ut, key, ipl, name, category, want_pheno, want_topo,
                 armc, geolat, eps):
    trop_xx, trop_ret = _calc(jd_ut, ipl, _BASE)
    if trop_xx is None:
        return {"key": key, "id": ipl, "name": name, "category": category,
                "error": trop_ret}

    sid_xx, _ = _calc(jd_ut, ipl, _BASE | swe.FLG_SIDEREAL)
    equ_xx, _ = _calc(jd_ut, ipl, _BASE | swe.FLG_EQUATORIAL)

    obj = {
        "key": key,
        "id": ipl,
        "name": name,
        "category": category,
        "ephemeris": _ephe_label(trop_ret),
    }
    trop = _ecliptic(trop_xx)
    trop["sign"] = _sign_block(trop_xx[0])
    obj["tropical"] = trop

    if sid_xx is not None:
        sid = _ecliptic(sid_xx)
        sid["sign"] = _sign_block(sid_xx[0], sidereal=True)
        sid["nakshatra"] = _nakshatra_block(sid_xx[0])
        sid["navamsa"] = vedic.navamsa_sign(sid_xx[0])
        obj["sidereal"] = sid

    if equ_xx is not None:
        obj["equatorial"] = _equatorial(equ_xx)

    # House position (tropical frame, selected system).
    if armc is not None and eps is not None:
        try:
            hpos = swe.house_pos(armc, geolat, eps,
                                 (trop_xx[0], trop_xx[1]), _HSYS_BYTE.value)
            obj["house"] = round(hpos, 6)
        except swe.Error:
            obj["house"] = None

    # Topocentric pass.
    if want_topo:
        topo_xx, _ = _calc(jd_ut, ipl, _BASE | swe.FLG_TOPOCTR)
        if topo_xx is not None:
            t = _ecliptic(topo_xx)
            t["sign"] = _sign_block(topo_xx[0])
            obj["topocentric"] = t

    # Phenomena (phase / magnitude / diameter) for physical bodies.
    if want_pheno and key in _PHYSICAL:
        try:
            attr = swe.pheno_ut(jd_ut, ipl, swe.FLG_SWIEPH)
            obj["phenomena"] = {
                "phase_angle": round(attr[0], 6),
                "phase_illuminated_fraction": round(attr[1], 8),
                "elongation": round(attr[2], 6),
                "apparent_diameter_arcsec": round(attr[3], 6),
                "apparent_magnitude": round(attr[4], 4),
            }
        except swe.Error:
            pass

    return obj


# Thread-local-ish holder so _body_object can see the selected house system
# byte without threading it through every call. Guarded by _LOCK.
class _Holder:
    value = b"P"


_HSYS_BYTE = _Holder()


def _ketu_object(rahu_obj: dict, armc, geolat, eps) -> dict:
    """South Node (Ketu) = Rahu + 180°, latitude negated. Ecliptic only."""
    ket = {"key": "ketu", "id": -1, "name": "Ketu (South Node)",
           "category": "point", "ephemeris": rahu_obj.get("ephemeris"),
           "note": "derived: true node + 180°"}
    for zodiac in ("tropical", "sidereal"):
        src = rahu_obj.get(zodiac)
        if not src:
            continue
        lon = _norm360(src["longitude"] + 180.0)
        blk = {
            "longitude": round(lon, 8),
            "latitude": round(-src["latitude"], 8),
            "distance_au": src["distance_au"],
            "longitude_speed": src["longitude_speed"],
            "latitude_speed": round(-src["latitude_speed"], 8),
            "distance_speed": src["distance_speed"],
            "retrograde": src["retrograde"],
            "sign": _sign_block(lon),
        }
        if zodiac == "sidereal":
            blk["nakshatra"] = _nakshatra_block(lon)
            blk["navamsa"] = vedic.navamsa_sign(lon)
        ket[zodiac] = blk
    if armc is not None and ket.get("tropical"):
        try:
            ket["house"] = round(
                swe.house_pos(armc, geolat, eps,
                              (ket["tropical"]["longitude"],
                               ket["tropical"]["latitude"]), _HSYS_BYTE.value), 6)
        except swe.Error:
            ket["house"] = None
    return ket


# --------------------------------------------------------------------------- #
# Ayanamsha                                                                    #
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def available_ayanamshas() -> list[dict]:
    """All SIDM_* modes compiled into this build (id, const, name)."""
    out = []
    for attr in dir(swe):
        if attr.startswith("SIDM_") and attr != "SIDM_USER":
            val = getattr(swe, attr)
            out.append({"id": val, "const": attr,
                        "name": catalog.AYANAMSHA_NAMES.get(val, attr)})
    out.sort(key=lambda x: x["id"])
    return out


def _ayanamsha_table(jd_ut: float) -> list[dict]:
    """Value of every ayanamsha at this instant. Mutates global sid mode, so
    the caller must reset the requested mode afterwards (done in compute_chart).
    """
    table = []
    for a in available_ayanamshas():
        swe.set_sid_mode(a["id"], 0, 0)
        try:
            _ret, value = swe.get_ayanamsa_ex_ut(jd_ut, swe.FLG_SWIEPH)
            table.append({"id": a["id"], "name": a["name"],
                          "degrees": round(value, 8)})
        except swe.Error:
            table.append({"id": a["id"], "name": a["name"], "degrees": None})
    return table


def resolve_ayanamsha(name_or_id) -> tuple[int, str]:
    """Accept a slug ('lahiri'), a SIDM_ constant name, or an int id."""
    if isinstance(name_or_id, int):
        sid = name_or_id
    else:
        key = str(name_or_id).strip().lower()
        if key in catalog.AYANAMSHA_ALIASES:
            sid = catalog.AYANAMSHA_ALIASES[key]
        elif key.startswith("sidm_") and hasattr(swe, key.upper()):
            sid = getattr(swe, key.upper())
        elif key.isdigit():
            sid = int(key)
        else:
            raise ValueError(f"unknown ayanamsha: {name_or_id!r}")
    return sid, catalog.AYANAMSHA_NAMES.get(sid, str(sid))


# --------------------------------------------------------------------------- #
# Houses & angles                                                             #
# --------------------------------------------------------------------------- #
def _angles_from_ascmc(ascmc) -> dict:
    return {catalog.ASCMC_NAMES[i]: round(_norm360(ascmc[i]), 8)
            for i in range(min(len(ascmc), len(catalog.ASCMC_NAMES)))}


def _houses(jd_ut, geolat, geolon, hsys_byte, sidereal: bool):
    flags = swe.FLG_SIDEREAL if sidereal else 0
    cusps, ascmc = swe.houses_ex(jd_ut, geolat, geolon, hsys_byte, flags)
    cusp_list = [{"house": i + 1, "longitude": round(_norm360(c), 8),
                  "sign": _sign_block(c, sidereal)}
                 for i, c in enumerate(cusps)]
    return cusp_list, _angles_from_ascmc(ascmc), ascmc


# --------------------------------------------------------------------------- #
# Heavy / opt-in sections                                                     #
# --------------------------------------------------------------------------- #
def _solar_eclipse_type(retflag: int) -> str:
    if retflag & swe.ECL_TOTAL:
        return "total"
    if retflag & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if retflag & swe.ECL_ANNULAR:
        return "annular"
    if retflag & swe.ECL_PARTIAL:
        return "partial"
    return "unknown"


def _lunar_eclipse_type(retflag: int) -> str:
    if retflag & swe.ECL_TOTAL:
        return "total"
    if retflag & swe.ECL_PARTIAL:
        return "partial"
    if retflag & swe.ECL_PENUMBRAL:
        return "penumbral"
    return "unknown"


def eclipses(jd_ut, geolat, geolon, alt) -> dict:
    out = {}
    # Solar — next & previous, globally.
    try:
        ret, tret = swe.sol_eclipse_when_glob(jd_ut, swe.FLG_SWIEPH, 0, False)
        out["next_solar_global"] = {
            "type": _solar_eclipse_type(ret),
            "central": bool(ret & swe.ECL_CENTRAL),
            "maximum": jd_to_time(tret[0]),
            "begin": jd_to_time(tret[2]),
            "end": jd_to_time(tret[3]),
        }
        ret, tret = swe.sol_eclipse_when_glob(jd_ut, swe.FLG_SWIEPH, 0, True)
        out["previous_solar_global"] = {
            "type": _solar_eclipse_type(ret), "maximum": jd_to_time(tret[0])}
    except swe.Error as exc:
        out["solar_error"] = str(exc)

    # Lunar — next & previous, globally.
    try:
        ret, tret = swe.lun_eclipse_when(jd_ut, swe.FLG_SWIEPH, 0, False)
        out["next_lunar_global"] = {
            "type": _lunar_eclipse_type(ret),
            "maximum": jd_to_time(tret[0]),
            "partial_begin": jd_to_time(tret[2]) if tret[2] else None,
            "partial_end": jd_to_time(tret[3]) if tret[3] else None,
            "total_begin": jd_to_time(tret[4]) if tret[4] else None,
            "total_end": jd_to_time(tret[5]) if tret[5] else None,
            "penumbral_begin": jd_to_time(tret[6]) if tret[6] else None,
            "penumbral_end": jd_to_time(tret[7]) if tret[7] else None,
        }
        ret, tret = swe.lun_eclipse_when(jd_ut, swe.FLG_SWIEPH, 0, True)
        out["previous_lunar_global"] = {
            "type": _lunar_eclipse_type(ret), "maximum": jd_to_time(tret[0])}
    except swe.Error as exc:
        out["lunar_error"] = str(exc)

    # Local visibility, if a place is given.
    if geolat is not None and geolon is not None:
        geopos = (geolon, geolat, alt or 0.0)
        try:
            ret, tret, attr = swe.sol_eclipse_when_loc(
                jd_ut, geopos, swe.FLG_SWIEPH, False)
            out["next_solar_local"] = {
                "type": _solar_eclipse_type(ret),
                "visible": bool(ret & swe.ECL_VISIBLE),
                "maximum": jd_to_time(tret[0]),
                "magnitude": round(attr[0], 6),
                "obscuration": round(attr[2], 6),
                "sun_altitude": round(attr[6], 4),
                "saros_series": int(attr[9]),
                "saros_member": int(attr[10]),
            }
        except swe.Error as exc:
            out["next_solar_local_error"] = str(exc)
        try:
            ret, tret, attr = swe.lun_eclipse_when_loc(
                jd_ut, geopos, swe.FLG_SWIEPH, False)
            out["next_lunar_local"] = {
                "type": _lunar_eclipse_type(ret),
                "visible": bool(ret & swe.ECL_VISIBLE),
                "maximum": jd_to_time(tret[0]),
                "umbral_magnitude": round(attr[0], 6),
                "penumbral_magnitude": round(attr[1], 6),
            }
        except swe.Error as exc:
            out["next_lunar_local_error"] = str(exc)
    return out


def rise_transit(jd_ut, geolat, geolon, alt, atpress, attemp) -> dict:
    geopos = (geolon, geolat, alt or 0.0)
    events = {
        "rise": swe.CALC_RISE | swe.BIT_DISC_CENTER,
        "set": swe.CALC_SET | swe.BIT_DISC_CENTER,
        "upper_transit": swe.CALC_MTRANSIT,
        "lower_transit": swe.CALC_ITRANSIT,
    }
    out = {}
    for key in _RISE_BODIES:
        ipl = catalog.BODY_KEY_TO_CONST[key]
        body_out = {}
        for label, rsmi in events.items():
            try:
                res, tret = swe.rise_trans(
                    jd_ut, ipl, rsmi, geopos, atpress, attemp, swe.FLG_SWIEPH)
                if res == -2:
                    body_out[label] = {"circumpolar": True}
                elif tret[0]:
                    body_out[label] = jd_to_time(tret[0])
                else:
                    body_out[label] = None
            except swe.Error as exc:
                body_out[label] = {"error": str(exc)}
        out[key] = body_out
    return out


def fixed_stars(jd_ut, armc, geolat, eps, names=None) -> list[dict]:
    names = names or catalog.DEFAULT_FIXED_STARS
    out = []
    for name in names:
        try:
            trop, stnam, _ret = swe.fixstar2_ut(name, jd_ut, _BASE)
            sid, _s2, _r2 = swe.fixstar2_ut(name, jd_ut, _BASE | swe.FLG_SIDEREAL)
            equ, _s3, _r3 = swe.fixstar2_ut(name, jd_ut, _BASE | swe.FLG_EQUATORIAL)
            mag, _s4 = swe.fixstar2_mag(name)
            entry = {
                "requested": name,
                "name": stnam,
                "magnitude": round(mag, 4),
                "tropical": {"longitude": round(_norm360(trop[0]), 8),
                             "latitude": round(trop[1], 8),
                             "sign": _sign_block(trop[0])},
                "sidereal": {"longitude": round(_norm360(sid[0]), 8),
                             "latitude": round(sid[1], 8),
                             "sign": _sign_block(sid[0], True),
                             "nakshatra": _nakshatra_block(sid[0])},
                "equatorial": {"right_ascension": round(_norm360(equ[0]), 8),
                               "declination": round(equ[1], 8)},
            }
            out.append(entry)
        except swe.Error:
            continue  # unresolved star name — skip quietly
    return out


def nodes_apsides(jd_ut) -> dict:
    out = {}
    for key in _RISE_BODIES:
        ipl = catalog.BODY_KEY_TO_CONST[key]
        try:
            asc, dsc, peri, aphe = swe.nod_aps_ut(
                jd_ut, ipl, swe.NODBIT_MEAN, _BASE)
            out[key] = {
                "ascending_node": {"longitude": round(_norm360(asc[0]), 8),
                                   "latitude": round(asc[1], 8)},
                "descending_node": {"longitude": round(_norm360(dsc[0]), 8),
                                    "latitude": round(dsc[1], 8)},
                "perihelion": {"longitude": round(_norm360(peri[0]), 8),
                               "distance_au": round(peri[2], 8)},
                "aphelion": {"longitude": round(_norm360(aphe[0]), 8),
                             "distance_au": round(aphe[2], 8)},
            }
        except swe.Error as exc:
            out[key] = {"error": str(exc)}
    return out


def orbital_elements(jd_et) -> dict:
    out = {}
    for key in _RISE_BODIES:
        ipl = catalog.BODY_KEY_TO_CONST[key]
        try:
            e = swe.get_orbital_elements(jd_et, ipl, swe.FLG_SWIEPH)
            out[key] = {
                "semimajor_axis_au": round(e[0], 8),
                "eccentricity": round(e[1], 8),
                "inclination": round(e[2], 8),
                "ascending_node_longitude": round(e[3], 8),
                "argument_of_periapsis": round(e[4], 8),
                "longitude_of_periapsis": round(e[5], 8),
                "mean_anomaly": round(e[6], 8),
                "true_anomaly": round(e[7], 8),
                "sidereal_period_years": round(e[10], 8),
                "mean_daily_motion": round(e[11], 8),
                "perihelion_distance_au": round(e[15], 8),
                "aphelion_distance_au": round(e[16], 8),
            }
        except swe.Error as exc:
            out[key] = {"error": str(exc)}
    return out


# --------------------------------------------------------------------------- #
# Top-level orchestrator                                                       #
# --------------------------------------------------------------------------- #
HEAVY_SECTIONS = ("eclipses", "rise_transit", "fixed_stars",
                  "nodes_apsides", "orbital_elements")


def compute_chart(*, jd_ut, jd_et=None, lat=None, lon=None, alt=0.0,
                  ayanamsha_id=1, ayanamsha_name="Lahiri",
                  hsys="P", body_defs=None, include=None,
                  topocentric=False, want_phenomena=True,
                  atpress=0.0, attemp=0.0, input_echo=None):
    """Assemble the full 'everything' chart. Serialized by _LOCK because every
    swisseph global (sid mode, topocentre, ephe path) is process-global."""
    include = set(include or [])
    body_defs = body_defs or catalog.DEFAULT_BODIES
    has_place = lat is not None and lon is not None
    hsys_byte = hsys.encode() if isinstance(hsys, str) else hsys

    with _LOCK:
        if not _initialized:
            init()
        _HSYS_BYTE.value = hsys_byte

        if jd_et is None:
            jd_et = jd_ut + swe.deltat(jd_ut)

        # Topocentre must be set before any FLG_TOPOCTR pass.
        if topocentric and has_place:
            swe.set_topo(lon, lat, alt or 0.0)

        # Requested sidereal mode drives every sidereal calc below.
        swe.set_sid_mode(ayanamsha_id, 0, 0)

        # ---- meta: obliquity, nutation, dt, sidereal time, eq. of time ---- #
        # Each guarded: a date beyond the ephemeris range must degrade to null,
        # never 500 the request.
        try:
            ecl = swe.calc_ut(jd_ut, swe.ECL_NUT, swe.FLG_SWIEPH)[0]
            eps_true, eps_mean = ecl[0], ecl[1]
            nut_long, nut_obl = ecl[2], ecl[3]
        except swe.Error:
            eps_true = eps_mean = nut_long = nut_obl = None
        delta_t = swe.deltat(jd_ut)                  # pure polynomial, safe
        try:
            gst = swe.sidtime(jd_ut)                 # apparent GST, hours
        except swe.Error:
            gst = 0.0
        try:
            eqt_min = round(swe.time_equ(jd_ut) * 24 * 60, 6)
        except swe.Error:
            eqt_min = None

        meta = {
            "jd_ut": jd_ut,
            "jd_et": jd_et,
            "delta_t_seconds": round(delta_t * 86400.0, 6),
            "obliquity": {"true": _r8(eps_true), "mean": _r8(eps_mean)},
            "nutation": {"longitude": _r8(nut_long), "obliquity": _r8(nut_obl)},
            "greenwich_sidereal_time_hours": round(gst, 8),
            "equation_of_time_minutes": eqt_min,
            "ephemeris_default": "swiss",
            "ayanamsha": {"id": ayanamsha_id, "name": ayanamsha_name},
            "house_system": {"code": hsys,
                             "name": catalog.HOUSE_SYSTEMS.get(hsys, hsys)},
            "swe_version": swe.version,
            "source": SOURCE_URL,
            "license": LICENSE,
            "attribution": "Swiss Ephemeris © Astrodienst AG (AGPL-3.0)",
        }
        if has_place:
            meta["local_sidereal_time_hours"] = round((gst + lon / 15.0) % 24, 8)

        # ---- houses & angles (tropical + sidereal) ------------------------ #
        armc = None
        asc_sid_sign = None
        houses_block = None
        angles_block = None
        if has_place:
            try:
                trop_cusps, trop_angles, trop_ascmc = _houses(
                    jd_ut, lat, lon, hsys_byte, sidereal=False)
                sid_cusps, sid_angles, sid_ascmc = _houses(
                    jd_ut, lat, lon, hsys_byte, sidereal=True)
                armc = trop_ascmc[2]
                asc_sid_sign = int(_norm360(sid_ascmc[0]) // 30)
                houses_block = {
                    "system": hsys,
                    "system_name": catalog.HOUSE_SYSTEMS.get(hsys, hsys),
                    "tropical": trop_cusps,
                    "sidereal": sid_cusps,
                }
                angles_block = {"tropical": trop_angles, "sidereal": sid_angles}
            except swe.Error:
                # date beyond house-computable range → skip houses/angles
                armc = asc_sid_sign = houses_block = angles_block = None

        # ---- bodies ------------------------------------------------------- #
        bodies = []
        by_key = {}
        for key, ipl, name, category in body_defs:
            obj = _body_object(jd_ut, key, ipl, name, category,
                               want_phenomena, topocentric and has_place,
                               armc, lat, eps_true)
            # whole-sign house relative to the sidereal ascendant
            if asc_sid_sign is not None and obj.get("sidereal"):
                bsign = obj["sidereal"]["sign"]["index"]
                obj["sidereal"]["whole_sign_house"] = ((bsign - asc_sid_sign) % 12) + 1
            bodies.append(obj)
            by_key[key] = obj

        # Ketu (South Node), derived from the true node if present.
        rahu = by_key.get("true_node") or by_key.get("mean_node")
        if rahu and "error" not in rahu:
            ketu = _ketu_object(rahu, armc, lat, eps_true)
            if asc_sid_sign is not None and ketu.get("sidereal"):
                bsign = ketu["sidereal"]["sign"]["index"]
                ketu["sidereal"]["whole_sign_house"] = ((bsign - asc_sid_sign) % 12) + 1
            bodies.append(ketu)
            by_key["ketu"] = ketu

        # ---- Vedic panchanga / varga ------------------------------------- #
        vedic_block = None
        sun_o, moon_o = by_key.get("sun"), by_key.get("moon")
        if sun_o and moon_o and sun_o.get("sidereal") and moon_o.get("sidereal"):
            moon_illum = None
            if moon_o.get("phenomena"):
                moon_illum = moon_o["phenomena"]["phase_illuminated_fraction"]
            vedic_block = vedic.compute(
                jd_ut,
                sun_o["sidereal"]["longitude"],
                moon_o["sidereal"]["longitude"],
                moon_illum=moon_illum,
                geolat=lat, geolon=lon, alt=alt,
                atpress=atpress, attemp=attemp,
                jd_to_time=jd_to_time)

        # ---- ayanamsha value + full table (table mutates sid mode) -------- #
        _ret, ayan_val = swe.get_ayanamsa_ex_ut(jd_ut, swe.FLG_SWIEPH)
        ayan_block = {
            "id": ayanamsha_id,
            "name": ayanamsha_name,
            "degrees": round(ayan_val, 8),
            "all_modes": _ayanamsha_table(jd_ut),
        }
        # _ayanamsha_table() mutated the global sid mode; restore the request's.
        swe.set_sid_mode(ayanamsha_id, 0, 0)

        # ---- assemble ----------------------------------------------------- #
        result = {
            "meta": meta,
            "input": input_echo or {},
            "time": jd_to_time(jd_ut),
            "bodies": bodies,
        }
        if angles_block:
            result["angles"] = angles_block
        if houses_block:
            result["houses"] = houses_block
        result["ayanamsha"] = ayan_block
        if vedic_block:
            result["vedic"] = vedic_block

        # ---- heavy / opt-in ---------------------------------------------- #
        if "eclipses" in include:
            result["eclipses"] = eclipses(jd_ut, lat, lon, alt)
        if "rise_transit" in include and has_place:
            result["rise_transit"] = rise_transit(
                jd_ut, lat, lon, alt, atpress, attemp)
        elif "rise_transit" in include:
            result["rise_transit"] = {"error": "lat/lon required"}
        if "fixed_stars" in include:
            result["fixed_stars"] = fixed_stars(jd_ut, armc, lat, eps_true)
        if "nodes_apsides" in include:
            result["nodes_apsides"] = nodes_apsides(jd_ut)
        if "orbital_elements" in include:
            result["orbital_elements"] = orbital_elements(jd_et)

        return result


# --------------------------------------------------------------------------- #
# Time & validation helpers (used by the web layer)                            #
# --------------------------------------------------------------------------- #
def julian_day_utc(year, month, day, hour, minute, second):
    """UTC calendar -> (jd_et, jd_ut) using swisseph's leap-second-aware call."""
    with _LOCK:
        if not _initialized:
            init()
        return swe.utc_to_jd(year, month, day, hour, minute, second, swe.GREG_CAL)


def valid_house_systems() -> dict:
    """House-system codes actually supported by this build -> label."""
    out = {}
    with _LOCK:
        for code in catalog.HOUSE_SYSTEMS:
            try:
                out[code] = swe.house_name(code.encode())
            except swe.Error:
                continue
    return out
