"""
Swiss Ephemeris Open API — FastAPI web layer.

One comprehensive endpoint, ``GET|POST /v1/chart``, returns everything Swiss
Ephemeris can compute for a moment in time (and, if a place is given, houses,
angles, rise/set and local eclipse visibility). No auth, no rate limiting.

The heavy iterative searches (eclipses, rise/set, fixed stars, nodes/apsides,
orbital elements) are opt-in via ``include=`` so the default response stays fast.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import __version__, catalog, engine, vedic, matching

# --------------------------------------------------------------------------- #
# App                                                                          #
# --------------------------------------------------------------------------- #
DESCRIPTION = """
A free, open, no-rate-limit API over the **Swiss Ephemeris** — the same
arc-second-precision engine professional astrology software uses.

`GET /v1/chart` returns **everything** for a moment (and place): tropical +
sidereal + equatorial positions of all bodies, all house cusps and chart angles,
the full ayanamsha table, and Vedic panchanga (nakshatra, tithi, yoga, karana,
navamsa, sunrise). Heavy searches (eclipses, rise/set, fixed stars, nodes,
orbital elements) are opt-in via `include=`.

Powered by [pyswisseph](https://pypi.org/project/pyswisseph/). Swiss Ephemeris
is © Astrodienst AG, used here under the **AGPL-3.0**. This service is
open-source; its full source is linked in every response (`meta.source`).
"""

app = FastAPI(
    title="Swiss Ephemeris Open API",
    description=DESCRIPTION,
    version=__version__,
    license_info={"name": "AGPL-3.0-or-later",
                  "url": "https://www.gnu.org/licenses/agpl-3.0.html"},
    contact={"name": "Source code", "url": engine.SOURCE_URL},
    docs_url="/docs",
    redoc_url="/redoc",
)

# Open API: allow any origin. No credentials (nothing is authenticated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.on_event("startup")
def _startup() -> None:
    engine.init()


# --------------------------------------------------------------------------- #
# Input parsing                                                                #
# --------------------------------------------------------------------------- #
def _resolve_tz(tz: str):
    """IANA name ('Asia/Kolkata') or fixed offset ('+05:30', '-0400', 'UTC')."""
    tz = tz.strip()
    if tz.upper() in ("UTC", "Z", "GMT"):
        return timezone.utc
    if tz and tz[0] in "+-":
        sign = 1 if tz[0] == "+" else -1
        body = tz[1:].replace(":", "")
        if not body.isdigit() or len(body) not in (2, 4):
            raise HTTPException(422, f"bad tz offset: {tz!r}")
        hours = int(body[:2])
        minutes = int(body[2:]) if len(body) == 4 else 0
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise HTTPException(422, f"unknown timezone: {tz!r}")


def _to_jd(dt_str: str | None, tz: str | None, jd_ut: float | None):
    """Return (jd_ut, jd_et, normalized_input_echo)."""
    if jd_ut is not None:
        # jd_et is derived from ΔT inside compute_chart when left None.
        return jd_ut, None, {"jd_ut": jd_ut}

    if not dt_str:
        raise HTTPException(422, "provide either `datetime` (ISO-8601) or `jd_ut`")

    s = dt_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"could not parse datetime: {dt_str!r} "
                                 "(use ISO-8601, e.g. 2026-07-06T14:30:00Z)")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_resolve_tz(tz) if tz else timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)

    jd_et, jd_ut = engine.julian_day_utc(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour, dt_utc.minute, dt_utc.second + dt_utc.microsecond / 1e6)
    echo = {
        "datetime": dt_str,
        "datetime_utc": dt_utc.isoformat().replace("+00:00", "Z"),
        "timezone": tz or "UTC",
    }
    return jd_ut, jd_et, echo


def _resolve_bodies(bodies: str | None):
    if not bodies or bodies.lower() == "default":
        return catalog.DEFAULT_BODIES
    if bodies.lower() == "all":
        return catalog.ALL_BODIES
    if bodies.lower() == "fictitious":
        return catalog.FICTITIOUS_BODIES
    wanted = [b.strip().lower() for b in bodies.split(",") if b.strip()]
    known = {key: (key, ipl, name, cat) for key, ipl, name, cat in catalog.ALL_BODIES}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise HTTPException(422, f"unknown bodies: {unknown}. "
                                 f"Valid: {sorted(known)} or 'all'/'default'/'fictitious'.")
    return [known[w] for w in wanted]


_VALID_FRAMES = set(engine._FRAME_FLAGS) | {"xyz"}


def _resolve_frames(frames: str | None):
    if not frames:
        return None
    if frames.lower() == "all":
        return list(_VALID_FRAMES)
    wanted = [f.strip().lower() for f in frames.split(",") if f.strip()]
    unknown = [f for f in wanted if f not in _VALID_FRAMES]
    if unknown:
        raise HTTPException(422, f"unknown frames: {unknown}. "
                                 f"Valid: {sorted(_VALID_FRAMES)} or 'all'.")
    return wanted


def _resolve_nodes(nodes: str | None):
    n = (nodes or "mean").strip().lower()
    if n not in ("mean", "osculating", "both"):
        raise HTTPException(422, "nodes must be mean, osculating, or both")
    return n


def _resolve_include(include: str | None):
    if not include:
        return set()
    if include.lower() == "all":
        return set(engine.HEAVY_SECTIONS)
    wanted = {s.strip().lower() for s in include.split(",") if s.strip()}
    unknown = wanted - set(engine.HEAVY_SECTIONS)
    if unknown:
        raise HTTPException(422, f"unknown include sections: {sorted(unknown)}. "
                                 f"Valid: {list(engine.HEAVY_SECTIONS)} or 'all'.")
    return wanted


def _run(*, datetime_str, jd_ut, tz, lat, lon, alt, ayanamsha, house_system,
         bodies, include, topocentric, atpress, attemp,
         frames=None, stars=None, nodes="mean",
         ayan_t0=0.0, ayan_value=0.0):
    jd_ut_val, jd_et, echo = _to_jd(datetime_str, tz, jd_ut)

    # Custom (user-defined) ayanamsha: ?ayanamsha=user with ayan_t0 + ayan_value.
    sid_t0, sid_ayan_t0 = 0.0, 0.0
    if str(ayanamsha).strip().lower() in ("user", "custom", "255"):
        ayan_id, ayan_name = 255, "User-defined"
        sid_t0, sid_ayan_t0 = ayan_t0 or 0.0, ayan_value or 0.0
    else:
        try:
            ayan_id, ayan_name = engine.resolve_ayanamsha(ayanamsha)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    hsys = (house_system or "P").strip()
    if len(hsys) != 1 or hsys not in catalog.HOUSE_SYSTEMS:
        raise HTTPException(422, f"unknown house_system: {house_system!r}. "
                                 f"Valid codes: {sorted(catalog.HOUSE_SYSTEMS)}")

    if lat is not None and not (-90 <= lat <= 90):
        raise HTTPException(422, "lat must be between -90 and 90")
    if lon is not None and not (-180 <= lon <= 180):
        raise HTTPException(422, "lon must be between -180 and 180")

    echo.update({
        "latitude": lat, "longitude": lon, "altitude": alt,
        "ayanamsha": ayan_name, "house_system": hsys,
        "topocentric": topocentric,
    })

    star_names = engine.resolve_star_names(stars) if stars else None

    try:
        result = engine.compute_chart(
            jd_ut=jd_ut_val, jd_et=jd_et, lat=lat, lon=lon, alt=alt or 0.0,
            ayanamsha_id=ayan_id, ayanamsha_name=ayan_name, hsys=hsys,
            body_defs=_resolve_bodies(bodies), include=_resolve_include(include),
            topocentric=topocentric, frames=_resolve_frames(frames),
            star_names=star_names, nodes_method=_resolve_nodes(nodes),
            sid_t0=sid_t0, sid_ayan_t0=sid_ayan_t0,
            atpress=atpress or 0.0, attemp=attemp or 0.0, input_echo=echo)
    except swe.Error as exc:
        # e.g. a date beyond the ~3000 BCE–3000 CE computable range
        raise HTTPException(422, f"cannot compute for these inputs: {exc}")
    return result


# Deterministic output → let clients/CDNs cache hard.
_CACHE = "public, max-age=31536000, immutable"


# --------------------------------------------------------------------------- #
# Routes                                                                       #
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"], summary="Liveness probe")
def health():
    test = engine.ephemeris_selftest()
    return {"status": "ok", "swe_version": engine.swe_version(),
            "service": "swiss-ephemeris-open-api", "version": __version__,
            "ephemeris": test["ephemeris"],
            "asteroids_ok": test["asteroids_ok"],
            "ephe_path": engine._EPHE_PATH,
            "ephe_file_present": engine._EPHE_OK,
            "selftest_detail": test["detail"]}


@app.get("/license", tags=["meta"], summary="License & attribution")
def license_info():
    return {
        "license": "AGPL-3.0-or-later",
        "license_url": "https://www.gnu.org/licenses/agpl-3.0.html",
        "source_code": engine.SOURCE_URL,
        "ephemeris": "Swiss Ephemeris © Astrodienst AG",
        "notice": ("This service is Free/Libre software under the GNU AGPL-3.0. "
                   "The complete corresponding source is available at the URL "
                   "above, satisfying the AGPL network-use clause."),
    }


@app.get("/v1/meta", tags=["meta"],
         summary="Supported ayanamshas, house systems, bodies & options")
def meta():
    return {
        "swe_version": engine.swe_version(),
        "ayanamshas": engine.available_ayanamshas(),
        "ayanamsha_aliases": catalog.AYANAMSHA_ALIASES,
        "house_systems": engine.valid_house_systems(),
        "bodies": {"default": [b[0] for b in catalog.DEFAULT_BODIES],
                   "all": [b[0] for b in catalog.ALL_BODIES],
                   "fictitious": [b[0] for b in catalog.FICTITIOUS_BODIES]},
        "include_sections": list(engine.HEAVY_SECTIONS),
        "coordinate_frames": sorted(_VALID_FRAMES),
        "node_methods": ["mean", "osculating", "both"],
        "fixed_star_count": len(engine.all_star_names()),
        "custom_ayanamsha": "ayanamsha=user with ayan_t0 (JD) + ayan_value (deg)",
        "notes": {
            "default_ayanamsha": "lahiri",
            "default_house_system": "P (Placidus)",
            "coordinates": "houses/angles/rise-set/local-eclipses require lat & lon",
            "time": "pass `datetime` (ISO-8601) with optional `tz`, or `jd_ut`",
        },
    }


class ChartRequest(BaseModel):
    datetime: str | None = Field(
        None, description="ISO-8601, e.g. 2026-07-06T14:30:00Z or 1990-08-15T05:45:00",
        examples=["2026-07-06T14:30:00Z"])
    jd_ut: float | None = Field(None, description="Julian Day (UT), alternative to datetime")
    tz: str | None = Field(None, description="IANA name or offset for a naive datetime",
                           examples=["Asia/Kolkata"])
    lat: float | None = Field(None, ge=-90, le=90, examples=[28.6139])
    lon: float | None = Field(None, ge=-180, le=180, examples=[77.2090])
    alt: float | None = Field(0.0, description="metres above sea level")
    ayanamsha: str = Field("lahiri", examples=["lahiri"])
    house_system: str = Field("P", description="single-char Swiss code", examples=["P"])
    bodies: str | None = Field(None, description="CSV of body keys, or 'all'/'default'/'fictitious'")
    include: str | None = Field(
        None, description="CSV of heavy sections, or 'all': "
        "eclipses,rise_transit,fixed_stars,nodes_apsides,orbital_elements,"
        "crossings,occultations,twilight,sky_position,all_house_systems,gauquelin,"
        "dasha,divisional_charts,ashtakavarga,aspects")
    topocentric: bool = False
    frames: str | None = Field(
        None, description="extra coordinate frames per body, CSV or 'all': "
        "heliocentric,barycentric,j2000,astrometric,true_geometric,xyz")
    stars: str | None = Field(None, description="fixed stars: CSV of names, or 'all' (~800)")
    nodes: str = Field("mean", description="node/apsis method: mean, osculating, or both")
    ayan_t0: float | None = Field(0.0, description="reference JD for a custom (user) ayanamsha")
    ayan_value: float | None = Field(0.0, description="ayanamsha degrees at ayan_t0 (with ayanamsha=user)")
    atpress: float | None = Field(0.0, description="atmospheric pressure (mbar) for rise/set")
    attemp: float | None = Field(0.0, description="atmospheric temperature (°C) for rise/set")


@app.post("/v1/chart", tags=["chart"], summary="Full chart (JSON body)")
def chart_post(req: ChartRequest, response: Response):
    result = _run(
        datetime_str=req.datetime, jd_ut=req.jd_ut, tz=req.tz,
        lat=req.lat, lon=req.lon, alt=req.alt, ayanamsha=req.ayanamsha,
        house_system=req.house_system, bodies=req.bodies, include=req.include,
        topocentric=req.topocentric, frames=req.frames, stars=req.stars,
        nodes=req.nodes, ayan_t0=req.ayan_t0, ayan_value=req.ayan_value,
        atpress=req.atpress, attemp=req.attemp)
    response.headers["Cache-Control"] = _CACHE
    return result


@app.get("/v1/chart", tags=["chart"], summary="Full chart (query params)")
def chart_get(
    response: Response,
    datetime: str | None = Query(None, examples=["2026-07-06T14:30:00Z"]),
    jd_ut: float | None = Query(None),
    tz: str | None = Query(None, examples=["Asia/Kolkata"]),
    lat: float | None = Query(None, ge=-90, le=90, examples=[28.6139]),
    lon: float | None = Query(None, ge=-180, le=180, examples=[77.2090]),
    alt: float | None = Query(0.0),
    ayanamsha: str = Query("lahiri"),
    house_system: str = Query("P"),
    bodies: str | None = Query(None),
    include: str | None = Query(None),
    topocentric: bool = Query(False),
    frames: str | None = Query(None),
    stars: str | None = Query(None),
    nodes: str = Query("mean"),
    ayan_t0: float | None = Query(0.0),
    ayan_value: float | None = Query(0.0),
    atpress: float | None = Query(0.0),
    attemp: float | None = Query(0.0),
):
    result = _run(
        datetime_str=datetime, jd_ut=jd_ut, tz=tz, lat=lat, lon=lon, alt=alt,
        ayanamsha=ayanamsha, house_system=house_system, bodies=bodies,
        include=include, topocentric=topocentric, frames=frames, stars=stars,
        nodes=nodes, ayan_t0=ayan_t0, ayan_value=ayan_value,
        atpress=atpress, attemp=attemp)
    response.headers["Cache-Control"] = _CACHE
    return result


# --------------------------------------------------------------------------- #
# Additional endpoints                                                         #
# --------------------------------------------------------------------------- #
@app.get("/v1/eclipses", tags=["events"],
         summary="All eclipses in a date range (calendar)")
def eclipses_range(
    response: Response,
    start: str | None = Query(None, description="ISO-8601 UTC start", examples=["2026-01-01T00:00:00Z"]),
    end: str | None = Query(None, description="ISO-8601 UTC end", examples=["2027-01-01T00:00:00Z"]),
    start_jd: float | None = Query(None),
    end_jd: float | None = Query(None),
    kind: str = Query("both", description="solar, lunar, or both"),
):
    s_jd, _e, _echo = _to_jd(start, None, start_jd)
    e_jd, _e2, _echo2 = _to_jd(end, None, end_jd)
    if kind not in ("solar", "lunar", "both"):
        raise HTTPException(422, "kind must be solar, lunar, or both")
    with engine._LOCK:
        if not engine._initialized:
            engine.init()
        try:
            data = engine.eclipse_range(s_jd, e_jd, kind)
        except swe.Error as exc:
            raise HTTPException(422, f"cannot compute: {exc}")
    response.headers["Cache-Control"] = _CACHE
    return {"start": engine.jd_to_time(s_jd), "end": engine.jd_to_time(e_jd),
            "kind": kind, **data}


class MatchRequest(BaseModel):
    boy_datetime: str = Field(..., examples=["1990-08-15T05:45:00"])
    boy_tz: str | None = Field("UTC", examples=["Asia/Kolkata"])
    girl_datetime: str = Field(..., examples=["1992-11-03T22:10:00"])
    girl_tz: str | None = Field("UTC", examples=["Asia/Kolkata"])
    ayanamsha: str = Field("lahiri")


def _moon_lon(dt_str, tz, ayan_id):
    jd_ut, _e, _echo = _to_jd(dt_str, tz, None)
    return engine.moon_sidereal_longitude(jd_ut, ayan_id)


@app.post("/v1/matching", tags=["events"],
          summary="Ashtakoot / Guna Milan (36-point marriage compatibility)")
def matching_post(req: MatchRequest, response: Response):
    try:
        ayan_id, _n = engine.resolve_ayanamsha(req.ayanamsha)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    try:
        boy = _moon_lon(req.boy_datetime, req.boy_tz, ayan_id)
        girl = _moon_lon(req.girl_datetime, req.girl_tz, ayan_id)
    except swe.Error as exc:
        raise HTTPException(422, f"cannot compute: {exc}")
    response.headers["Cache-Control"] = _CACHE
    return matching.ashtakoot(boy, girl)


@app.get("/v1/matching", tags=["events"], summary="Ashtakoot (query params)")
def matching_get(
    response: Response,
    boy_datetime: str = Query(..., examples=["1990-08-15T05:45:00"]),
    girl_datetime: str = Query(..., examples=["1992-11-03T22:10:00"]),
    boy_tz: str | None = Query("UTC"),
    girl_tz: str | None = Query("UTC"),
    ayanamsha: str = Query("lahiri"),
):
    try:
        ayan_id, _n = engine.resolve_ayanamsha(ayanamsha)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    try:
        boy = _moon_lon(boy_datetime, boy_tz, ayan_id)
        girl = _moon_lon(girl_datetime, girl_tz, ayan_id)
    except swe.Error as exc:
        raise HTTPException(422, f"cannot compute: {exc}")
    response.headers["Cache-Control"] = _CACHE
    return matching.ashtakoot(boy, girl)


@app.get("/v1/stars", tags=["chart"], summary="List all fixed-star names (~800)")
def stars_list():
    names = engine.all_star_names()
    return {"count": len(names), "stars": names}


@app.get("/v1/time", tags=["meta"], summary="Time conversions (JD, ΔT, sidereal time)")
def time_convert(
    datetime: str | None = Query(None, examples=["2026-07-06T14:30:00Z"]),
    tz: str | None = Query(None),
    jd_ut: float | None = Query(None),
    lon: float | None = Query(None, description="for local sidereal time"),
):
    jd_ut_val, jd_et, echo = _to_jd(datetime, tz, jd_ut)
    with engine._LOCK:
        if not engine._initialized:
            engine.init()
        gst = swe.sidtime(jd_ut_val)
        dt_days = swe.deltat(jd_ut_val)
        out = {
            "input": echo,
            "jd_ut": jd_ut_val,
            "jd_et": jd_et if jd_et is not None else jd_ut_val + dt_days,
            "delta_t_seconds": round(dt_days * 86400.0, 6),
            "greenwich_sidereal_time_hours": round(gst, 8),
            "weekday": vedic.weekday(jd_ut_val),
        }
        if lon is not None:
            out["local_sidereal_time_hours"] = round((gst + lon / 15.0) % 24, 8)
    return out
