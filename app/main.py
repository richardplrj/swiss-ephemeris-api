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

from . import __version__, catalog, engine

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
    wanted = [b.strip().lower() for b in bodies.split(",") if b.strip()]
    known = {key: (key, ipl, name, cat) for key, ipl, name, cat in catalog.ALL_BODIES}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise HTTPException(422, f"unknown bodies: {unknown}. "
                                 f"Valid: {sorted(known)} or 'all'/'default'.")
    return [known[w] for w in wanted]


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
         bodies, include, topocentric, atpress, attemp):
    jd_ut_val, jd_et, echo = _to_jd(datetime_str, tz, jd_ut)

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

    try:
        result = engine.compute_chart(
            jd_ut=jd_ut_val, jd_et=jd_et, lat=lat, lon=lon, alt=alt or 0.0,
            ayanamsha_id=ayan_id, ayanamsha_name=ayan_name, hsys=hsys,
            body_defs=_resolve_bodies(bodies), include=_resolve_include(include),
            topocentric=topocentric, atpress=atpress or 0.0, attemp=attemp or 0.0,
            input_echo=echo)
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
    return {"status": "ok", "swe_version": engine.swe_version(),
            "service": "swiss-ephemeris-open-api", "version": __version__}


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
                   "all": [b[0] for b in catalog.ALL_BODIES]},
        "include_sections": list(engine.HEAVY_SECTIONS),
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
    bodies: str | None = Field(None, description="CSV of body keys, or 'all'/'default'")
    include: str | None = Field(
        None, description="CSV of heavy sections, or 'all': "
        "eclipses,rise_transit,fixed_stars,nodes_apsides,orbital_elements")
    topocentric: bool = False
    atpress: float | None = Field(0.0, description="atmospheric pressure (mbar) for rise/set")
    attemp: float | None = Field(0.0, description="atmospheric temperature (°C) for rise/set")


@app.post("/v1/chart", tags=["chart"], summary="Full chart (JSON body)")
def chart_post(req: ChartRequest, response: Response):
    result = _run(
        datetime_str=req.datetime, jd_ut=req.jd_ut, tz=req.tz,
        lat=req.lat, lon=req.lon, alt=req.alt, ayanamsha=req.ayanamsha,
        house_system=req.house_system, bodies=req.bodies, include=req.include,
        topocentric=req.topocentric, atpress=req.atpress, attemp=req.attemp)
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
    atpress: float | None = Query(0.0),
    attemp: float | None = Query(0.0),
):
    result = _run(
        datetime_str=datetime, jd_ut=jd_ut, tz=tz, lat=lat, lon=lon, alt=alt,
        ayanamsha=ayanamsha, house_system=house_system, bodies=bodies,
        include=include, topocentric=topocentric, atpress=atpress, attemp=attemp)
    response.headers["Cache-Control"] = _CACHE
    return result
