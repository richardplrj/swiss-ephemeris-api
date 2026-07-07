<!--
YOU ARE AN ASSISTANT WITH ACCESS TO AN ASTRONOMY API.
This single document is the complete, self-contained reference for the Swiss
Ephemeris Open API. After reading it you can call the API (base URL below) to
get any astronomical position or event for any date/time/place, and interpret
every field it returns. You need no other file or spec. When a user asks about
planetary positions, houses, ayanamshas, eclipses, risings/settings, fixed
stars, nodes, or similar, build the appropriate GET/POST request as documented
here and use the response. The API is astronomy only — it returns no horoscope
text, predictions, or interpretation.
-->

# Swiss Ephemeris Open API — Complete Reference (for AI / LLM use)

This document fully describes the **Swiss Ephemeris Open API**. It is written so
an AI can read it once and then correctly (a) build any request and (b) interpret
every field in the response. It is exhaustive and self-contained — **it is the
only file you need; give this whole document to your AI.**

- **Base URL:** `https://swiss-ephemeris-api-2m5g.onrender.com`
- **Auth:** none. **Rate limit:** none. **CORS:** open (any origin).
- **What it is:** a pure-astronomy API over the Swiss Ephemeris. It returns
  *positions and events* (the "where/when" of the sky). It contains **no
  astrological interpretation** (no predictions, dashas, or compatibility).
- **Precision:** arc-second (0.001″ vs NASA JPL) for **1200 AD – 3000 AD** via
  bundled data files; automatically falls back to the ~1″ Moshier model outside
  that range, and each body reports which was used (`"ephemeris": "swiss" | "moshier"`).
- **Determinism:** identical input → identical output; responses are cacheable.

---

## 1. Quick usage

The main endpoint is **`GET /v1/chart`** (a `POST /v1/chart` with a JSON body of
the same fields also exists). Provide a **time** and (optionally) a **place**:

```
GET /v1/chart?datetime=1990-08-15T05:45:00&tz=Asia/Kolkata&lat=28.6139&lon=77.2090
```

**Important:** a plain request returns only the CORE sections (`meta`, `input`,
`time`, `bodies`, `angles`, `houses`, `ayanamsha`). All the heavier data
(eclipses, rise/set, fixed stars, etc.) is **opt-in** — request it with
`include=`. To get **everything** in one call:

```
GET /v1/chart?datetime=1990-08-15T05:45:00&tz=Asia/Kolkata&lat=28.6139&lon=77.2090&bodies=all&frames=all&stars=all&nodes=both&include=all
```

`angles`, `houses`, and location-dependent sections require `lat` **and** `lon`.

---

## 2. Endpoints

| Method · Path | Purpose |
|---|---|
| `GET`/`POST` `/v1/chart` | The full chart: positions, houses, angles, ayanamsha + opt-in sections. |
| `GET` `/v1/eclipses` | List every eclipse in a date range (a calendar). |
| `GET` `/v1/stars` | The full list of ~770 fixed-star names. |
| `GET` `/v1/time` | Time conversions: Julian Day, ΔT, sidereal time. |
| `GET` `/v1/meta` | Machine-readable lists of all valid bodies, ayanamshas, house systems, includes, frames. |
| `GET` `/health` | Liveness + which ephemeris is active. |
| `GET` `/license` | License + source link. |
| `GET` `/docs` | Interactive Swagger UI (for humans). |

---

## 3. `/v1/chart` — request parameters

All are query params on GET, or JSON body fields on POST. All are optional except
that you must supply **either `datetime` or `jd_ut`**.

| Param | Type | Default | Meaning |
|---|---|---|---|
| `datetime` | string | — | ISO-8601 instant, e.g. `2026-07-06T14:30:00Z`. If it has no timezone offset it is read as UTC, unless `tz` is given. |
| `jd_ut` | float | — | Julian Day (UT) directly, as an alternative to `datetime`. |
| `tz` | string | `UTC` | Timezone applied to a *naive* `datetime`: an IANA name (`Asia/Kolkata`) or a fixed offset (`+05:30`, `-0400`). Ignored if `datetime` already has an offset. |
| `lat` | float | — | Geographic latitude, decimal degrees, −90..90 (north positive). Required for houses/angles/rise-set/local-eclipses/sky-position/heliacal/gauquelin. |
| `lon` | float | — | Geographic longitude, decimal degrees, −180..180 (**east positive**). |
| `alt` | float | `0` | Altitude above sea level, metres. |
| `ayanamsha` | string | `lahiri` | Sidereal zero-point. A slug (`lahiri`, `kp`, `raman`, `fagan_bradley`, …), a `SIDM_*` name, an integer id (0–46), or `user` (see custom ayanamsha below). Full list at `/v1/meta`. |
| `house_system` | string | `P` | One-character Swiss house-system code (e.g. `P`=Placidus, `K`=Koch, `W`=Whole-sign, `B`=Alcabitius). Full map at `/v1/meta`. |
| `bodies` | string | *default set* | Which bodies to compute. CSV of body keys, or `default` (19), `all` (43, incl. Uranian/fictitious), or `fictitious` (the 19 Uranian/hypothetical). |
| `include` | string | *(none)* | CSV of opt-in sections to add, or `all`. Valid: `eclipses,rise_transit,fixed_stars,nodes_apsides,orbital_elements,crossings,occultations,twilight,sky_position,all_house_systems,gauquelin,heliacal`. |
| `frames` | string | *(none)* | Extra coordinate frames to add to each body. CSV or `all`. Valid: `heliocentric,barycentric,j2000,astrometric,true_geometric,xyz`. |
| `stars` | string | *curated 17* | Which fixed stars for the `fixed_stars` section: CSV of names, or `all` (~770). Only used if `include` contains `fixed_stars`. |
| `nodes` | string | `mean` | Node/apsis method for `nodes_apsides`: `mean`, `osculating`, or `both`. |
| `center` | string | *(none)* | If set to a body key (e.g. `mars`), adds a `planetocentric` section = each body as seen from that center body. |
| `topocentric` | bool | `false` | If true (and lat/lon given), adds a `topocentric` block to each body (position as seen from the observer's exact location rather than Earth's center). |
| `ayan_t0` | float | `0` | With `ayanamsha=user`: reference Julian Day for a custom ayanamsha. |
| `ayan_value` | float | `0` | With `ayanamsha=user`: the ayanamsha value (degrees) at `ayan_t0`. |
| `atpress` | float | `0` | Atmospheric pressure (mbar) for rise/set/twilight refraction (0 = library default). |
| `attemp` | float | `0` | Atmospheric temperature (°C) for rise/set/twilight refraction. |

**Errors:** invalid parameters return HTTP **422** with body `{"detail": "..."}`.
A date outside the computable range (~3000 BC – 3000 AD) also returns 422, or
degrades gracefully (bodies get an `"error"` field; analytical sections still
compute). It never returns 500 for bad input.

---

## 4. `/v1/chart` — response structure

Top-level keys always present: `meta`, `input`, `time`, `bodies`, `ayanamsha`.
Present when `lat`+`lon` given: `angles`, `houses`. Present when requested via
`include=`/`center=`: the opt-in sections below.

### 4.1 Units & conventions (apply everywhere)
- **Angles/longitudes/latitudes:** degrees. Ecliptic longitude is 0–360.
- **Distances:** astronomical units (AU). The Moon too.
- **Speeds:** per day (`*_speed` = degrees/day; distance speed = AU/day).
- **`retrograde`:** boolean, true when `longitude_speed < 0`.
- **Timestamps** (any date/time value) are an object:
  `{"jd_ut": float, "iso": "YYYY-MM-DDTHH:MM:SS.ffffffZ" | null, "calendar": {"year","month","day","hour","minute","second"}}`.
  `iso` is `null` for years outside 1–9999 (Julian Day + calendar still given).
- **`sign` block:** `{"index": 0–11, "name": "Aries".."Pisces", "degrees_in_sign": 0–30, "dms": "DD°MM'SS.s\""}`.
- Sign index → name: 0 Aries, 1 Taurus, 2 Gemini, 3 Cancer, 4 Leo, 5 Virgo,
  6 Libra, 7 Scorpio, 8 Sagittarius, 9 Capricorn, 10 Aquarius, 11 Pisces.

### 4.2 `meta`
```
jd_ut, jd_et                      float  Julian Day in Universal Time / Ephemeris Time (TT)
delta_t_seconds                   float  ΔT = TT − UT, seconds
obliquity: {true, mean}           deg    obliquity of the ecliptic
nutation: {longitude, obliquity}  deg
greenwich_sidereal_time_hours     0–24   apparent GST
local_sidereal_time_hours         0–24   (only if lon given)
equation_of_time_minutes          float  apparent minus mean solar time
ephemeris_default                 "swiss"
ayanamsha: {id, name}             the sidereal mode used
house_system: {code, name}
swe_version, source, license, attribution   strings
```

### 4.3 `input`
Echo of the normalized request: `datetime`, `datetime_utc`, `timezone`,
`latitude`, `longitude`, `altitude`, `ayanamsha`, `house_system`, `topocentric`.

### 4.4 `time`
A timestamp object (see 4.1) for the requested instant.

### 4.5 `bodies` — array, one object per body
```
key            string   machine key, e.g. "sun", "true_node", "ketu"
id             int      Swiss Ephemeris body number (Ketu = -1, derived)
name           string   display name
category       string   "luminary" | "planet" | "point" | "asteroid" | "uranian" | "fictitious"
ephemeris      string   "swiss" | "moshier" (which model served this body)
tropical:      {longitude, latitude, distance_au, longitude_speed, latitude_speed,
                distance_speed, retrograde, sign}
sidereal:      same shape as tropical, longitudes shifted by the ayanamsha
equatorial:    {right_ascension, declination, distance_au, ra_speed, dec_speed}
house          float 1.0–13.0   fractional house position (only if lat/lon given)
phenomena:     {phase_angle, phase_illuminated_fraction (0–1), elongation,
                apparent_diameter_arcsec, apparent_magnitude, horizontal_parallax}
                (only for physical bodies)
frames:        (only if frames= requested) e.g.
               heliocentric/barycentric/j2000/astrometric/true_geometric:
                 {longitude, latitude, distance_au, longitude_speed}
               xyz: {x, y, z, dx, dy, dz}   rectangular AU + AU/day
topocentric:   (only if topocentric=true) {longitude, latitude, distance_au, ..., sign}
```
Ketu (`key:"ketu"`) is the descending lunar node = true node + 180°; it has
tropical/sidereal ecliptic blocks + house, but no equatorial/phenomena.
Bodies out of range carry `{"key","id","name","category","error": "..."}`.

### 4.6 `angles` (needs lat+lon)
`{tropical: {...}, sidereal: {...}}` where each has:
`ascendant, mc, armc, vertex, equatorial_ascendant, coascendant_koch,
coascendant_munkasey, polar_ascendant` — all degrees.

### 4.7 `houses` (needs lat+lon)
```
system, system_name
tropical: [ {house 1–12, longitude, sign} × 12 ]     cusp longitudes
sidereal: [ ... × 12 ]
speeds: { tropical: {cusps: [12 floats deg/day], angles: {ascendant, mc, ...}},
          sidereal: {...} }
```

### 4.8 `ayanamsha`
```
id, name, degrees                 the requested mode's value (degrees)
true_and_mean: {with_nutation, mean_without_nutation}
all_modes: [ {id, name, degrees} × 47 ]   value of every ayanamsha at this instant
```

### 4.9 Opt-in sections (via `include=`)

**`eclipses`**
```
next_solar_global / previous_solar_global:
  {type: "total"|"annular"|"hybrid"|"partial", central: bool,
   maximum, begin, end (timestamps),
   path: {central_line: {longitude, latitude}, eclipse_magnitude, obscuration}}
next_lunar_global / previous_lunar_global:
  {type: "total"|"partial"|"penumbral", maximum,
   partial_begin/end, total_begin/end, penumbral_begin/end (timestamps or null)}
next_solar_local (needs lat/lon):
  {type, visible: bool, maximum, magnitude, obscuration, sun_altitude,
   saros_series, saros_member}
next_lunar_local (needs lat/lon):
  {type, visible, maximum, umbral_magnitude, penumbral_magnitude}
```

**`rise_transit`** (needs lat+lon) — per body key (sun..pluto):
`{rise, set, upper_transit, lower_transit}` each a timestamp, or
`{"circumpolar": true}`, or `null`.

**`twilight`** (needs lat+lon):
`{civil: {dawn, dusk}, nautical: {dawn, dusk}, astronomical: {dawn, dusk}}` (timestamps).

**`sky_position`** (needs lat+lon) — per body:
`{azimuth (deg from due North, clockwise), compass ("N".."NNW"), true_altitude,
apparent_altitude, above_horizon: bool}`.

**`fixed_stars`** — array (controlled by `stars=`):
`{requested, name (resolved), magnitude, tropical:{lon,lat,sign},
sidereal:{lon,lat,sign}, equatorial:{right_ascension, declination}}`.

**`nodes_apsides`** — per body (sun..pluto), keyed by method (`mean`/`osculating`, or both):
`{ascending_node:{longitude,latitude}, descending_node:{...},
perihelion:{longitude,distance_au}, aphelion:{longitude,distance_au}}`.

**`orbital_elements`** — per body: Keplerian elements +
`semimajor_axis_au, eccentricity, inclination, ascending_node_longitude,
argument_of_periapsis, longitude_of_periapsis, mean_anomaly, true_anomaly,
eccentric_anomaly, mean_longitude, sidereal_period_years, mean_daily_motion,
tropical_period_years, synodic_period_days, perihelion_passage_jd,
perihelion_distance_au, aphelion_distance_au, max_distance_au, min_distance_au,
true_distance_au`.

**`crossings`** — exact sign-change / node-crossing times:
```
sun / moon: {next_tropical_ingress: {from_sign, to_sign, time},
             next_sidereal_ingress: {from_sign, to_sign, time}}
moon_node_crossing: {time, longitude}
heliocentric_ingress: per planet (mercury..pluto) {to_sign, time}
```

**`occultations`** — Moon occulting planets/stars; per target:
`{next_global (timestamp), path: {longitude, latitude},
next_local (timestamp, needs lat/lon), visible: bool}`.

**`all_house_systems`** (needs lat+lon):
`{tropical: [ {code, name, cusps:[12], ascendant, mc} × ~25 ], sidereal: [...]}`.

**`gauquelin`** (needs lat+lon) — per body: a float sector value 1.0–36.99.

**`heliacal`** (needs lat+lon) — per body (venus, mercury, mars, jupiter, saturn,
sirius, canopus):
```
heliacal_rising / heliacal_setting: {visibility_start, optimum, visibility_end}
                                     (timestamps), or null
limiting_magnitude: float   dark-sky limiting visual magnitude
observability: {object_altitude, sun_altitude, arcus_visionis,
                min_visible_magnitude, raw: [50 floats]}
```

### 4.10 `planetocentric` (via `center=<body>`)
`{center: "<body key>", bodies: {<key>: {longitude, latitude, distance_au,
longitude_speed}}}` — each body as seen from the center body.

---

## 5. Other endpoints

### `GET /v1/eclipses`
Params: `start`+`end` (ISO-8601 UTC) **or** `start_jd`+`end_jd` (Julian Day);
`kind` = `solar` | `lunar` | `both` (default `both`).
Response: `{start, end (timestamps), kind, solar: [ {type, central, maximum} ],
lunar: [ {type, maximum} ]}`.

### `GET /v1/stars`
Response: `{count: int, stars: [names...]}` — the ~770 usable fixed-star names.

### `GET /v1/time`
Params: `datetime`(+`tz`) or `jd_ut`; optional `lon` (for local sidereal time).
Response: `{input, jd_ut, jd_et, delta_t_seconds, greenwich_sidereal_time_hours,
local_sidereal_time_hours?}`.

### `GET /v1/meta`
Machine-readable reference for building requests:
`{swe_version, ayanamshas:[{id,const,name}], ayanamsha_aliases:{slug:id},
house_systems:{code:name}, bodies:{default:[],all:[],fictitious:[]},
include_sections:[], coordinate_frames:[], node_methods:[], fixed_star_count}`.

### `GET /health`
`{status:"ok", swe_version, version, ephemeris:"swiss"|"moshier-fallback",
asteroids_ok: bool, ephe_path, ephe_file_present}`.

---

## 6. Reference lists (enumerations)

### Bodies — `default` (19)
`sun, moon, mercury, venus, mars, jupiter, saturn, uranus, neptune, pluto,
mean_node, true_node, mean_lilith, true_lilith, chiron, ceres, pallas, juno, vesta`
(plus `ketu`, the derived descending node, always appended).

### Bodies — extra in `all` (24 more)
`earth, pholus, interpolated_apogee, interpolated_perigee` and the fictitious/Uranian:
`cupido, hades, zeus, kronos, apollon, admetos, vulkanus, poseidon, isis_transpluto,
nibiru, harrington, neptune_leverrier, neptune_adams, pluto_lowell, pluto_pickering,
vulcan, white_moon, proserpina, waldemath`.

### Ayanamshas (id → name); use the id, name, or an alias slug
0 Fagan/Bradley · 1 Lahiri · 2 De Luce · 3 Raman · 4 Usha/Shashi ·
5 Krishnamurti (KP) · 6 Djwhal Khul · 7 Yukteshwar · 8 J.N. Bhasin ·
9–14 Babylonian variants · 15 Hipparchos · 16 Sassanian · 17 Galactic Center=0 Sag ·
18 J2000 · 19 J1900 · 20 B1950 · 21 Suryasiddhanta · 22 Suryasiddhanta (mean Sun) ·
23 Aryabhata · 24 Aryabhata (mean Sun) · 25 SS Revati · 26 SS Citra ·
27 True Chitrapaksha · 28 True Revati · 29 True Pushya · 30 Galactic Center (Gil Brand) ·
31–34 Galactic-equator variants · 35 True Mula · 36 Dhruva/Gal.Center/Mula ·
37 Aryabhata 522 · 38 Babylonian/Britton · 39 Vedic/Sheoran · 40 Cochrane ·
41 Galactic Equator (Fiorenza) · 42 Vettius Valens · 43 Lahiri 1940 ·
44 Lahiri VP285 · 45 Krishnamurti-Senthilathiban · 46 Lahiri ICRC.
Common aliases: `lahiri`, `kp`/`krishnamurti`, `raman`, `fagan_bradley`,
`true_chitra`, `galactic_center`, `j2000`, `b1950`, `yukteshwar`.

### House systems (code → name)
P Placidus · K Koch · O Porphyry · R Regiomontanus · C Campanus · A/E Equal ·
D Equal (from MC) · V Vehlow Equal · W Whole-sign · N Whole-sign (Aries=1st) ·
B Alcabitius · M Morinus · U Krusinski-Pisa-Goelzer · X Meridian/axial ·
H Horizon/azimuthal · T Polich-Page · G Gauquelin sectors · F Carter poli-equ. ·
L Pullen SD · Q Pullen SR · S Sripati · I Sunshine · i Sunshine (alt) · Y APC.

### `include` sections
`eclipses, rise_transit, fixed_stars, nodes_apsides, orbital_elements, crossings,
occultations, twilight, sky_position, all_house_systems, gauquelin, heliacal`
(or `include=all`).

### Coordinate `frames`
`heliocentric, barycentric, j2000, astrometric, true_geometric, xyz` (or `frames=all`).

---

## 7. Worked examples

**A birth-style chart (local time + timezone), core data only:**
`GET /v1/chart?datetime=1990-08-15T05:45:00&tz=Asia/Kolkata&lat=28.6139&lon=77.2090`
→ `meta`, `time`, 20 `bodies` (with tropical/sidereal/equatorial + house),
`angles`, `houses`, `ayanamsha`. Sun sidereal ≈ Cancer 28° (Lahiri).

**Everything for a moment + place:**
`GET /v1/chart?datetime=2026-07-06T12:00:00Z&lat=28.6&lon=77.2&bodies=all&frames=all&stars=all&nodes=both&include=all`
→ all core sections + all 12 opt-in sections + 43 bodies.

**Just the Sun & Moon, sidereal, KP ayanamsha, Whole-sign houses:**
`GET /v1/chart?datetime=2026-07-06T12:00:00Z&lat=28.6&lon=77.2&bodies=sun,moon&ayanamsha=kp&house_system=W`

**Eclipse calendar for a year:**
`GET /v1/eclipses?start=2026-01-01T00:00:00Z&end=2027-01-01T00:00:00Z&kind=both`

**Positions as seen from Mars:**
`GET /v1/chart?datetime=2026-07-06T12:00:00Z&center=mars`

---

## 8. Notes for correct use

- Longitude is **east-positive** (so New Delhi is `lon=77.209`, not −77.209).
- To convert a body's ecliptic longitude to a zodiac position: `sign_index =
  floor(longitude / 30)`, `degrees_in_sign = longitude mod 30` (the API already
  provides the `sign` block).
- `tropical` vs `sidereal`: tropical is measured from the moving vernal equinox
  (Western astrology / astronomy); sidereal subtracts the ayanamsha (Vedic). The
  `equatorial` block is RA/Dec.
- If you only need positions, omit `lat`/`lon` (houses/angles will be absent).
- The API is astronomy only. It will never return horoscope text, predictions,
  dashas, nakshatras, or compatibility — compute those yourself from the returned
  positions if needed.
- Attribution: Swiss Ephemeris © Astrodienst AG, used under AGPL-3.0. Source:
  https://github.com/richardplrj/swiss-ephemeris-api
