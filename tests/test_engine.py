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
