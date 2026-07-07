"""
Regression tests for the pure Swiss Ephemeris layer. Anchors are independently
known values, so these guard the wrapper logic (coordinate handling, sign split,
house indexing, timezone conversion) rather than the library itself.

Run:  ./.venv/bin/python -m pytest tests/ -q
"""

import swisseph as swe

from app import engine, catalog

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
    assert sun["ephemeris"] == "swiss"


def test_lahiri_ayanamsha_2000():
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


def test_eclipse_range_2026():
    s = engine.julian_day_utc(2026, 1, 1, 0, 0, 0)[1]
    e = engine.julian_day_utc(2027, 1, 1, 0, 0, 0)[1]
    er = engine.eclipse_range(s, e, "both")
    assert len(er["solar"]) == 2 and len(er["lunar"]) == 2
    assert {ev["type"] for ev in er["solar"]} == {"annular", "total"}


def test_crossings_karka_sankranti_2026():
    _et, ut = _jd(2026, 7, 1)
    res = engine.compute_chart(jd_ut=ut, include={"crossings"},
                               ayanamsha_id=1, ayanamsha_name="Lahiri")
    ing = res["crossings"]["sun"]["next_sidereal_ingress"]
    assert ing["to_sign"] == "Cancer"
    assert ing["time"]["calendar"]["month"] == 7
    assert 14 <= ing["time"]["calendar"]["day"] <= 18


# --------------------------------------------------------------------------- #
# Sign split (how swe presents ecliptic longitude)                             #
# --------------------------------------------------------------------------- #
def test_sign_split():
    assert engine._sign_block(0.0)["name"] == "Aries"
    assert engine._sign_block(35.0)["name"] == "Taurus"
    assert engine._sign_block(359.9)["name"] == "Pisces"
    assert abs(engine._sign_block(35.0)["degrees_in_sign"] - 5.0) < 1e-6
    assert "sanskrit" not in engine._sign_block(35.0)


# --------------------------------------------------------------------------- #
# Feature completeness (the whole Swiss Ephemeris surface)                     #
# --------------------------------------------------------------------------- #
def test_full_response_shape():
    _et, ut = _jd(1990, 8, 15, 0, 15)
    res = engine.compute_chart(
        jd_ut=ut, lat=28.6139, lon=77.2090, alt=216,
        ayanamsha_id=1, ayanamsha_name="Lahiri", hsys="P",
        body_defs=catalog.ALL_BODIES, frames=["heliocentric", "xyz"],
        include=set(engine.HEAVY_SECTIONS))
    for section in ("meta", "bodies", "angles", "houses", "ayanamsha",
                    "eclipses", "rise_transit", "fixed_stars", "nodes_apsides",
                    "orbital_elements", "crossings", "occultations", "twilight",
                    "sky_position", "all_house_systems", "gauquelin"):
        assert section in res, f"missing {section}"
    assert len(res["houses"]["tropical"]) == 12
    assert len(res["angles"]["tropical"]) == 8
    # Ketu present and opposite Rahu
    rahu = next(b for b in res["bodies"] if b["key"] == "true_node")
    ketu = next(b for b in res["bodies"] if b["key"] == "ketu")
    diff = abs((ketu["sidereal"]["longitude"] - rahu["sidereal"]["longitude"]) % 360)
    assert abs(diff - 180) < 1e-6


def test_pure_ephemeris_no_interpretation_fields():
    # The response must NOT carry any of the removed interpretation layer.
    _et, ut = _jd(1990, 8, 15, 0, 15)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2,
                               include=set(engine.HEAVY_SECTIONS))
    assert "vedic" not in res
    for banned in ("dasha", "ashtakavarga", "divisional_charts", "aspects",
                   "yogas", "yogini_dasha"):
        assert banned not in res
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    for banned in ("nakshatra", "navamsa", "dignity", "combustion",
                   "whole_sign_house"):
        assert banned not in sun.get("sidereal", {})


def test_fictitious_bodies_compute():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, body_defs=catalog.FICTITIOUS_BODIES)
    keys = {b["key"] for b in res["bodies"]}
    for k in ("cupido", "poseidon", "vulcan", "white_moon", "waldemath"):
        assert k in keys
        assert "error" not in next(b for b in res["bodies"] if b["key"] == k)


def test_coordinate_frames():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, frames=["heliocentric", "xyz", "j2000"])
    mars = next(b for b in res["bodies"] if b["key"] == "mars")
    assert set(mars["frames"]) == {"heliocentric", "xyz", "j2000"}


def test_full_star_catalog_and_all_house_systems():
    assert len(engine.all_star_names()) > 700
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2,
                               include={"all_house_systems", "sky_position"})
    assert len(res["all_house_systems"]["tropical"]) >= 20
    sun = res["sky_position"]["sun"]
    assert -90 <= sun["true_altitude"] <= 90 and 0 <= sun["azimuth"] < 360


def test_osculating_nodes_and_full_orbital():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, include={"nodes_apsides", "orbital_elements"},
                               nodes_method="both")
    assert set(res["nodes_apsides"]["mars"]) == {"mean", "osculating"}
    # 17 Kepler elements + max/min/true distance envelope
    assert len(res["orbital_elements"]["mars"]) == 20


# --------------------------------------------------------------------------- #
# Robustness / range                                                           #
# --------------------------------------------------------------------------- #
def test_moshier_fallback_below_bundled_range():
    _et, ut = _jd(1000, 6, 15)
    res = engine.compute_chart(jd_ut=ut)
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert sun["ephemeris"] == "moshier"
    assert sun["tropical"]["longitude"] is not None


def test_out_of_all_range_degrades_gracefully():
    _et, ut = _jd(5000, 1, 1)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2)
    sun = next(b for b in res["bodies"] if b["key"] == "sun")
    assert "error" in sun
    assert res["meta"]["equation_of_time_minutes"] is None
    assert "houses" in res  # analytical, still valid


# --------------------------------------------------------------------------- #
# 100% coverage: the 9 formerly-missing data functions                         #
# --------------------------------------------------------------------------- #
def test_eclipse_geographic_path():
    _et, ut = _jd(2026, 1, 1)
    res = engine.compute_chart(jd_ut=ut, include={"eclipses"})
    path = res["eclipses"]["next_solar_global"]["path"]
    assert -180 <= path["central_line"]["longitude"] <= 180
    assert -90 <= path["central_line"]["latitude"] <= 90


def test_orbit_max_min_distance():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, include={"orbital_elements"})
    mars = res["orbital_elements"]["mars"]
    assert mars["min_distance_au"] < mars["true_distance_au"] < mars["max_distance_au"]


def test_heliocentric_ingress():
    _et, ut = _jd(2026, 1, 1)
    res = engine.compute_chart(jd_ut=ut, include={"crossings"})
    assert "jupiter" in res["crossings"]["heliocentric_ingress"]


def test_house_cusp_speeds():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2)
    sp = res["houses"]["speeds"]["tropical"]
    assert len(sp["cusps"]) == 12 and "ascendant" in sp["angles"]


def test_planetocentric():
    _et, ut = _jd(2000, 1, 1, 12)
    res = engine.compute_chart(jd_ut=ut, center="mars")
    assert res["planetocentric"]["center"] == "mars"
    assert "moon" in res["planetocentric"]["bodies"]


def test_heliacal_section():
    _et, ut = _jd(2026, 7, 7)
    res = engine.compute_chart(jd_ut=ut, lat=28.6, lon=77.2, include={"heliacal"})
    v = res["heliacal"]["venus"]
    assert "heliacal_rising" in v and "limiting_magnitude" in v
    assert "observability" in v and len(v["observability"]["raw"]) == 50
