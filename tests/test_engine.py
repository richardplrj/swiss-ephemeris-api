"""
Regression tests. Anchors are independently known values, so these guard the
wrapper logic (sign/nakshatra/panchanga math, timezone handling, house indexing)
rather than the Swiss Ephemeris library itself.

Run:  ./.venv/bin/python -m pytest tests/ -q
"""

import math

import swisseph as swe

from app import engine, vedic, catalog

engine.init()


def _jd(y, mo, d, h=0, mi=0, s=0):
    return engine.julian_day_utc(y, mo, d, h, mi, s)  # (jd_et, jd_ut)


# --------------------------------------------------------------------------- #
# Known ephemeris anchors                                                      #
# --------------------------------------------------------------------------- #
def test_sun_at_j2000_tropical():
    # 2000-01-01 12:00 UTC: Sun's apparent tropical longitude ≈ 280.37° (Cap 10°)
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, ayanamsha_id=1, ayanamsha_name="Lahiri")
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert abs(sun["tropical"]["longitude"] - 280.369) < 0.01
    assert sun["tropical"]["sign"]["name"] == "Capricorn"


def test_lahiri_ayanamsha_2000():
    # Lahiri ayanamsha on 2000-01-01 ≈ 23.85°
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, ayanamsha_id=1, ayanamsha_name="Lahiri")
    assert abs(res["ayanamsha"]["degrees"] - 23.853) < 0.01
    assert len(res["ayanamsha"]["all_modes"]) == 47


def test_next_solar_eclipse_feb_2000():
    _et, ut = _jd(2000, 1, 1)
    res = engine.compute_chart(jd_ut=ut, include={"eclipses"})
    ecl = res["eclipses"]["next_solar_global"]
    assert ecl["type"] == "partial"
    assert ecl["maximum"]["calendar"]["year"] == 2000
    assert ecl["maximum"]["calendar"]["month"] == 2


# --------------------------------------------------------------------------- #
# Sidereal / Vedic derivation math                                             #
# --------------------------------------------------------------------------- #
def test_nakshatra_boundaries():
    # Ashwini spans 0–13°20'; Revati is the last, ending at 360°.
    assert engine._nakshatra_block(0.0)["name"] == "Ashwini"
    assert engine._nakshatra_block(13.0)["name"] == "Ashwini"
    assert engine._nakshatra_block(13.34)["name"] == "Bharani"
    assert engine._nakshatra_block(359.9)["name"] == "Revati"
    # pada 1..4 inside a nakshatra
    assert engine._nakshatra_block(0.1)["pada"] == 1
    assert engine._nakshatra_block(13.0)["pada"] == 4


def test_navamsa_classical_rule():
    # Movable sign (Aries) navamsa starts at Aries; fixed (Taurus) at Capricorn;
    # dual (Gemini) at Libra.
    assert vedic.navamsa_sign(0.1)["name"] == "Aries"       # Aries → Aries
    assert vedic.navamsa_sign(30.1)["name"] == "Capricorn"  # Taurus → Capricorn
    assert vedic.navamsa_sign(60.1)["name"] == "Libra"      # Gemini → Libra


def test_tithi_new_and_full_moon():
    # elongation 0 → Shukla Pratipada; 180 → Purnima
    assert vedic.tithi(0.0, 0.0)["name"] == "Pratipada"
    assert vedic.tithi(0.0, 0.0)["paksha"] == "Shukla"
    full = vedic.tithi(0.0, 180.5)
    assert full["paksha"] == "Krishna"
    assert full["number"] == 16  # first tithi of Krishna paksha
    amav = vedic.tithi(0.0, 359.9)
    assert amav["name"] == "Amavasya"


def test_karana_fixed_and_movable_sequence():
    # n=0 Kimstughna; n=1 Bava; n=57 Shakuni; n=58 Chatushpada; n=59 Naga
    assert vedic.karana(0.0, 3.0)["name"] == "Kimstughna"    # elong 3 → n=0
    assert vedic.karana(0.0, 9.0)["name"] == "Bava"          # elong 9 → n=1
    assert vedic.karana(0.0, 57 * 6 + 3)["name"] == "Shakuni"
    assert vedic.karana(0.0, 58 * 6 + 3)["name"] == "Chatushpada"
    assert vedic.karana(0.0, 59 * 6 + 3)["name"] == "Naga"


def test_yoga_uses_sidereal_sum():
    y = vedic.yoga(0.0, 0.0)
    assert y["name"] == "Vishkambha" and y["number"] == 1


def test_weekday_saturday_at_j2000():
    _et, ut = _jd(2000, 1, 1, 12)   # 2000-01-01 was a Saturday
    assert vedic.weekday(ut)["name"] == "Saturday"


# --------------------------------------------------------------------------- #
# Structure / feature completeness                                             #
# --------------------------------------------------------------------------- #
def test_full_response_shape():
    _et, ut = _jd(1990, 8, 15, 0, 15)
    res = engine.compute_chart(
        jd_ut=ut, lat=28.6139, lon=77.2090, alt=216,
        ayanamsha_id=1, ayanamsha_name="Lahiri", hsys="P",
        body_defs=catalog.ALL_BODIES,
        include=set(engine.HEAVY_SECTIONS))
    for section in ("meta", "bodies", "angles", "houses", "ayanamsha", "vedic",
                    "eclipses", "rise_transit", "fixed_stars",
                    "nodes_apsides", "orbital_elements"):
        assert section in res, f"missing {section}"
    assert len(res["houses"]["tropical"]) == 12
    assert len(res["angles"]["tropical"]) == 8
    # Ketu present and opposite Rahu
    rahu = next(b for b in res["bodies"] if b["key"] == "true_node")
    ketu = next(b for b in res["bodies"] if b["key"] == "ketu")
    diff = abs((ketu["sidereal"]["longitude"] - rahu["sidereal"]["longitude"]) % 360)
    assert abs(diff - 180) < 1e-6


def test_moshier_fallback_below_bundled_range():
    # Year 1000 is before the earliest bundled file (1200 AD) but inside Moshier's
    # range → swisseph auto-falls-back to Moshier. We must report that honestly.
    _et, ut = _jd(1000, 6, 15)
    res = engine.compute_chart(jd_ut=ut)
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert sun["ephemeris"] == "moshier"
    assert sun["tropical"]["longitude"] is not None


def test_out_of_all_range_degrades_gracefully():
    # Year 5000 is beyond BOTH the bundled files and Moshier. Planet *positions*
    # need the ephemeris and fail; the purely-analytical quantities (obliquity,
    # houses/angles from time+location) still compute. Must never crash.
    _et, ut = _jd(5000, 1, 1)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2)
    assert "meta" in res and "bodies" in res
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert "error" in sun                              # position uncomputable
    assert res["meta"]["equation_of_time_minutes"] is None
    assert "houses" in res                             # analytical, still valid
    assert len(res["houses"]["tropical"]) == 12


# --------------------------------------------------------------------------- #
# Completeness layer (Swiss Ephemeris parity additions)                        #
# --------------------------------------------------------------------------- #
def test_fictitious_bodies_compute():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, body_defs=catalog.FICTITIOUS_BODIES)
    keys = {b["key"] for b in res["bodies"]}
    for k in ("cupido", "poseidon", "vulcan", "white_moon", "waldemath"):
        assert k in keys
        b = next(x for x in res["bodies"] if x["key"] == k)
        assert "error" not in b and b["tropical"]["longitude"] is not None


def test_coordinate_frames():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, frames=["heliocentric", "xyz", "j2000"])
    mars = next(b for b in res["bodies"] if b["key"] == "mars")
    assert set(mars["frames"]) == {"heliocentric", "xyz", "j2000"}
    assert "x" in mars["frames"]["xyz"]


def test_crossings_karka_sankranti_2026():
    # Sun enters sidereal Cancer (Karka Sankranti) mid-July.
    _et, ut = _jd(2026, 7, 1)
    res = engine.compute_chart(jd_ut=ut, include={"crossings"},
                               ayanamsha_id=1, ayanamsha_name="Lahiri")
    ing = res["crossings"]["sun"]["next_sidereal_ingress"]
    assert ing["to_sign"] == "Cancer"
    assert ing["time"]["calendar"]["month"] == 7
    assert 14 <= ing["time"]["calendar"]["day"] <= 18


def test_eclipse_range_2026():
    s = engine.julian_day_utc(2026, 1, 1, 0, 0, 0)[1]
    e = engine.julian_day_utc(2027, 1, 1, 0, 0, 0)[1]
    er = engine.eclipse_range(s, e, "both")
    assert len(er["solar"]) == 2 and len(er["lunar"]) == 2
    types = {ev["type"] for ev in er["solar"]}
    assert "annular" in types and "total" in types


def test_muhurta_rahu_kaal_and_hora():
    # 2026-07-07 is a Tuesday → first hora ruled by Mars, first choghadiya Rog.
    _et, ut = _jd(2026, 7, 7, 6, 30)
    res = engine.compute_chart(jd_ut=ut, lat=28.6139, lon=77.2090, alt=216)
    m = res["vedic"]["sunrise_sunset"]["muhurta"]
    assert m["hora"][0]["lord"] == "Mars"
    assert m["choghadiya_day"][0]["name"] == "Rog"
    # Rahu Kaal falls inside the daytime window
    assert m["rahu_kaal"]["start"]["jd_ut"] < m["rahu_kaal"]["end"]["jd_ut"]


def test_custom_ayanamsha():
    # Define 24.000° at J2000 → by 2026 it should have drifted ~+0.37°.
    _et, ut = _jd(2026, 1, 1)
    res = engine.compute_chart(jd_ut=ut, ayanamsha_id=255, ayanamsha_name="User",
                               sid_t0=2451545.0, sid_ayan_t0=24.0)
    assert 24.3 < res["ayanamsha"]["degrees"] < 24.45


def test_osculating_nodes_and_full_orbital():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, include={"nodes_apsides", "orbital_elements"},
                               nodes_method="both")
    assert set(res["nodes_apsides"]["mars"]) == {"mean", "osculating"}
    assert len(res["orbital_elements"]["mars"]) == 17


def test_full_star_catalog_and_all_house_systems():
    assert len(engine.all_star_names()) > 700
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2,
                               include={"all_house_systems", "sky_position"})
    assert len(res["all_house_systems"]["tropical"]) >= 20
    # Sun near local midnight/day — altitude bounded, azimuth is a compass bearing
    sun = res["sky_position"]["sun"]
    assert -90 <= sun["true_altitude"] <= 90 and 0 <= sun["azimuth"] < 360


# --------------------------------------------------------------------------- #
# Jyotisha interpretation layer                                                #
# --------------------------------------------------------------------------- #
from app import jyotisha


def test_ashtakavarga_checksum():
    pos = {"sun": {"lon": 10}, "moon": {"lon": 40}, "mars": {"lon": 70},
           "mercury": {"lon": 100}, "jupiter": {"lon": 130},
           "venus": {"lon": 160}, "saturn": {"lon": 190}}
    av = jyotisha.ashtakavarga(pos, asc_lon=220)
    for p, expected in jyotisha._BAV_TOTALS.items():
        assert av["bhinnashtakavarga"][p]["total"] == expected, p
    assert av["sarvashtakavarga"]["total"] == 337  # the invariant checksum


def test_dignity():
    assert jyotisha.dignity("sun", 10)["status"] == "exalted"        # Aries 10
    assert jyotisha.dignity("sun", 190)["status"] == "debilitated"   # Libra 10
    assert jyotisha.dignity("saturn", 200)["status"] == "exalted"    # Libra 20
    assert jyotisha.dignity("jupiter", 275)["status"] == "debilitated"
    assert jyotisha.dignity("sun", 125)["status"] == "moolatrikona"  # Leo 5


def test_combustion_retrograde_orbs():
    assert jyotisha.combustion("mercury", 100, 108, False)["combust"] is True   # 8°, orb 14
    assert jyotisha.combustion("mercury", 100, 113, True)["combust"] is False   # 13°, orb 12
    assert jyotisha.combustion("saturn", 100, 120, False)["combust"] is False   # 20°, orb 15


def test_divisional_d9_matches_navamsa():
    for lon in (15.0, 47.3, 123.4, 200.7, 358.9):
        d9 = jyotisha.SIGNS[jyotisha._varga_sign(lon, 9)]
        assert d9 == vedic.navamsa_sign(lon)["name"]
        assert jyotisha.SIGNS[jyotisha._varga_sign(lon, 1)] == \
            vedic.rasi(lon)["name"]


def test_vimshottari_balance():
    _et, ut = _jd(1990, 8, 15)
    # Moon at 0° = start of Ashwini (Ketu, 7 yrs); balance = 7.0
    d = jyotisha.vimshottari(ut, 0.0, engine.jd_to_time)
    assert d["starting_lord"] == "Ketu"
    assert abs(d["balance_at_birth_years"] - 7.0) < 1e-6
    assert [m["lord"] for m in d["maha_dashas"]][:3] == ["Ketu", "Venus", "Sun"]
    # mid-Ashwini → half balance
    d2 = jyotisha.vimshottari(ut, (360 / 27) / 2, engine.jd_to_time)
    assert abs(d2["balance_at_birth_years"] - 3.5) < 1e-6


def test_jyotisha_sections_in_chart():
    _et, ut = _jd(1990, 8, 15, 0, 15)
    res = engine.compute_chart(
        jd_ut=ut, lat=28.6139, lon=77.2090, alt=216,
        ayanamsha_id=1, ayanamsha_name="Lahiri",
        include={"dasha", "divisional_charts", "ashtakavarga", "aspects"})
    assert res["ashtakavarga"]["sarvashtakavarga"]["total"] == 337
    assert res["dasha"]["current"].get("maha")
    assert "D9" in res["divisional_charts"]["bodies"]["moon"]
    assert "graha_drishti" in res["aspects"]
    # dignity + combustion attached to the Sun/planets
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert "dignity" in sun["sidereal"]
    venus = next(b for b in res["bodies"] if b["key"] == "venus")
    assert "combustion" in venus["sidereal"]
