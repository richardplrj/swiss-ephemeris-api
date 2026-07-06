# Swiss Ephemeris Open API

A **free, open, no-rate-limit** HTTP API over the [Swiss Ephemeris](https://www.astro.com/swisseph/) — the same arc-second-precision astronomical engine used by professional astrology software. One endpoint returns **everything** the ephemeris can compute for a moment in time (and place) as a single JSON document.

- ⚡ **Fast** — a full chart in ~4 ms; *everything* (all bodies + eclipses + rise/set + fixed stars + orbital elements) in ~14 ms.
- 🎯 **Accurate** — bundled Swiss `.se1` data files give 0.001″ agreement with NASA JPL, for **1200 AD – 3000 AD**. Dates outside that fall back to the built-in Moshier model automatically (and the response says which was used).
- 🪐 **Complete** — tropical + sidereal + equatorial positions & speeds for all bodies, every house system, all 47 ayanamshas, chart angles, planetary phenomena, eclipses, risings/settings, fixed stars, planetary nodes & orbital elements.
- 🕉️ **Vedic-ready** — nakshatra + pada, rasi, navamsa, tithi, yoga, karana, vara, and sunrise-anchored Hindu day, all derived from sidereal longitudes.
- 🆓 **No API keys, no rate limits, CORS-open.**

> Powered by [`pyswisseph`](https://pypi.org/project/pyswisseph/). Swiss Ephemeris is © Astrodienst AG and used here under the **GNU AGPL-3.0**. This service is Free/Libre software; its complete source is linked in every response (`meta.source`). See [License](#license).

---

## Quick start

```bash
# 1. Install (Python 3.11 required — pyswisseph ships wheels up to cp311)
pip install -r requirements.txt

# 2. (data files are already committed; to refresh them: scripts/download_ephe.sh)

# 3. Run
uvicorn app.main:app --reload --port 8080

# 4. Open the interactive docs
open http://localhost:8080/docs
```

Or with Docker:

```bash
docker build -t swiss-ephemeris-api .
docker run -p 8080:8080 swiss-ephemeris-api
```

---

## The endpoint

### `GET /v1/chart` &nbsp;·&nbsp; `POST /v1/chart`

**Example — a birth chart in New Delhi (local time + IANA timezone):**

```bash
curl "http://localhost:8080/v1/chart?datetime=1990-08-15T05:45:00&tz=Asia/Kolkata&lat=28.6139&lon=77.2090"
```

**Example — everything, right now, in UTC:**

```bash
curl "http://localhost:8080/v1/chart?datetime=2026-07-06T12:00:00Z&lat=28.6&lon=77.2&bodies=all&include=all"
```

**POST with a JSON body** (identical parameters):

```bash
curl -X POST http://localhost:8080/v1/chart -H 'content-type: application/json' -d '{
  "datetime": "2026-07-06T14:30:00Z",
  "lat": 28.6139, "lon": 77.2090,
  "ayanamsha": "lahiri", "house_system": "P",
  "include": "eclipses,rise_transit"
}'
```

### Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `datetime` | — | ISO-8601 instant, e.g. `2026-07-06T14:30:00Z`. If it has no offset, it's read as UTC unless `tz` is given. |
| `jd_ut` | — | Alternative to `datetime`: a raw Julian Day (UT). |
| `tz` | `UTC` | IANA name (`Asia/Kolkata`) or offset (`+05:30`) applied to a naive `datetime`. |
| `lat`, `lon` | — | Decimal degrees. **Required for houses, angles, rise/set, and local eclipse visibility.** Omit for positions only. |
| `alt` | `0` | Metres above sea level (topocentric & rise/set). |
| `ayanamsha` | `lahiri` | Sidereal mode: a slug (`lahiri`, `kp`, `raman`, `fagan_bradley`, …), a `SIDM_*` name, or an integer id. See `/v1/meta`. |
| `house_system` | `P` | One-character Swiss code (`P` Placidus, `K` Koch, `W` Whole-sign, `B` Alcabitius, …). See `/v1/meta`. |
| `bodies` | default set | CSV of body keys, or `all` (43 incl. Uranian/fictitious), `default`, or `fictitious`. |
| `include` | *(none)* | CSV of heavy sections, or `all`: `eclipses,rise_transit,fixed_stars,nodes_apsides,orbital_elements,crossings,occultations,twilight,sky_position,all_house_systems,gauquelin`. |
| `frames` | *(none)* | Extra coordinate frames per body, CSV or `all`: `heliocentric,barycentric,j2000,astrometric,true_geometric,xyz`. |
| `stars` | curated 17 | Fixed stars: CSV of names, or `all` (~770). |
| `nodes` | `mean` | Node/apsis method: `mean`, `osculating`, or `both`. |
| `topocentric` | `false` | Add a topocentric position pass per body. |
| `ayanamsha=user` | — | With `ayan_t0` (JD) + `ayan_value` (deg): a fully custom ayanamsha. |
| `atpress`, `attemp` | `0` | Atmospheric pressure (mbar) / temperature (°C) for rise/set refraction. |

### More endpoints

- `GET /v1/eclipses?start=…&end=…&kind=solar|lunar|both` — every eclipse in a date range (a calendar).
- `GET /v1/stars` — the full ~770-name fixed-star catalog.
- `GET /v1/time?datetime=…&lon=…` — Julian day, ΔT, sidereal time, weekday.

### Jyotisha interpretation layer (v1.2)

- **Dignity + combustion** are attached to each classical planet's `sidereal` block automatically (exalted/debilitated/moolatrikona/own/friendly/enemy; combust with retrograde-aware orbs).
- Opt-in via `include=`:
  - `dasha` — **Vimshottari** Maha + Antar timeline (365.25-day year), with the running period.
  - `divisional_charts` — all **16 vargas** D1–D60 (BPHS conventions, each labeled) per body + Ascendant.
  - `ashtakavarga` — **Bhinna + Sarva** bindu tables (Sarva always totals 337 — a built-in checksum).
  - `aspects` — **Graha Drishti** (whole-sign, with Mars/Jupiter/Saturn special aspects) + Graha Yuddha.

Every convention with competing traditions is stated in the response and in `app/jyotisha.py`.

### Vedic muhurta (auto, when lat/lon given)

Every located chart's `vedic.sunrise_sunset.muhurta` block carries **Rahu Kaal, Yamaganda, Gulika, Abhijit, Brahma Muhurta**, the 8+8 **Choghadiya**, and the 24 planetary **Horas** — all anchored to the day's actual sunrise/sunset.

Everything is **deterministic**, so responses are sent with `Cache-Control: immutable` — safe to cache forever.

### What the response contains

| Section | Always? | Contents |
|---------|---------|----------|
| `meta` | ✅ | Julian days, ΔT, obliquity, nutation, sidereal time, equation of time, ephemeris used, `source`, `license`. |
| `bodies[]` | ✅ | Per body: **tropical**, **sidereal** (+ nakshatra + navamsa + whole-sign house), and **equatorial** coordinates with speeds & retrograde flag; house position; phenomena (phase, magnitude, diameter). Includes Ketu (derived). |
| `ayanamsha` | ✅ | The requested value **plus all 47 ayanamshas** tabulated for the instant. |
| `vedic` | ✅* | Nakshatra, rasi, navamsa, **tithi, yoga, karana, vara**, moon phase, and (with lat/lon) sunrise/sunset, day length, Hindu vara. |
| `angles` | 📍 | Ascendant, MC, ARMC, Vertex, Equatorial Ascendant, co-ascendants, polar ascendant — tropical & sidereal. |
| `houses` | 📍 | 12 cusps for the chosen system — tropical & sidereal. |
| `eclipses` | ⚙️ | Next/previous global solar & lunar eclipses; local visibility if lat/lon given. |
| `rise_transit` | ⚙️📍 | Rise, set, upper & lower transit for Sun–Pluto. |
| `fixed_stars` | ⚙️ | A curated bright/Vedic star set: position + magnitude. |
| `nodes_apsides` | ⚙️ | Ascending/descending node, perihelion, aphelion per planet. |
| `orbital_elements` | ⚙️ | Keplerian elements per planet. |

✅ always · 📍 needs `lat`+`lon` · ⚙️ opt-in via `include=` · * panchanga always; sunrise needs `lat`+`lon`

### Helper routes

- `GET /v1/meta` — every supported ayanamsha, house system, body key, and include-section.
- `GET /health` — liveness probe (used by keep-warm cron).
- `GET /license` — license & source-code link (AGPL network-use notice).
- `GET /docs` — interactive Swagger UI · `GET /redoc` — ReDoc · `GET /openapi.json` — spec.

---

## Accuracy & range

- **1200 AD – 3000 AD:** full Swiss precision (0.001″ vs JPL) for Sun–Pluto, Moon, the main asteroids (Ceres, Pallas, Juno, Vesta), Chiron/Pholus, and ~800 fixed stars.
- **Outside that (down to 3000 BCE / up to 3000 CE):** the built-in **Moshier** analytical model is used automatically (~1″, main planets only — no asteroids). Every body reports which model served it via `ephemeris: "swiss" | "moshier"`.
- **Beyond ±3000:** positions can't be computed and each body carries an `error`; purely-analytical outputs (obliquity, houses, angles) still return. Requests never 500.

To widen the Swiss-precision range, drop additional `sepl_*/semo_*/seas_*.se1` blocks into `ephe/` (each ~2 MB per 600-year span) — no code change needed.

## Development

```bash
python -m pytest tests/ -q      # regression suite (derivations + known anchors)
```

Project layout:

```
app/
  main.py      FastAPI routes, input parsing, validation
  engine.py    all swisseph calls (thread-locked), chart assembly
  vedic.py     panchanga & varga derivations
  catalog.py   static reference data (bodies, signs, nakshatras, ayanamsha names)
ephe/          bundled Swiss Ephemeris .se1 data files (~6 MB, committed)
tests/         pytest regression suite
scripts/       ephemeris downloader
Dockerfile     python:3.11-slim container
DEPLOY.md      free hosting guide (Cloud Run + alternatives)
```

**A note on concurrency:** Swiss Ephemeris keeps the ayanamsha/topocentre in C globals, so the engine serializes each computation behind a process lock — otherwise two concurrent requests with different ayanamshas would corrupt each other. Each request is only a few milliseconds, and the platform scales by adding instances.

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** ([`LICENSE`](./LICENSE)).

It bundles and links the **Swiss Ephemeris** (© Astrodienst AG, Zürich), which is dual-licensed; this project uses it under its **AGPL** option. That is the free path, and its one obligation — that the complete source of a network service be offered to its users — is met by publishing this repository and linking it from every API response (`meta.source`) and from `GET /license`.

If you fork this and run it publicly, keep it AGPL and keep the source link live. If you ever need to run it **closed-source**, you must instead purchase a [Swiss Ephemeris Professional License](https://www.astro.com/swisseph/) from Astrodienst.

**Not affiliated with or endorsed by Astrodienst AG.**
