"""Tests for the Milestone 4 similarity engine.

Well/wellbore field values below are real numbers taken from the actual
ingested SODIR VOLVE-field export (data/sodir/wellbore_volve_field.csv)
and the real Volve F-11 A directional survey (already verified in
ingestion/tests/test_volve_mapping.py) — not invented — inserted through
the existing test-DB fixtures (backend/tests use an isolated
`nwis_test` database, so the real dev-DB rows aren't queried directly;
see backend/tests/conftest.py). Only the pure edge-case scenarios
(missing-data combinations, filter boundaries) use synthetic values,
per the task's "small synthetic fixtures only where necessary".
"""

import math

import pytest

from app.services import similarity_service
from app.services.similarity_service import SimilarityConfig, SimilarityWeights

# Real coordinates/depths, from data/sodir/wellbore_volve_field.csv.
F11_LONLAT = (1.8858360154953036, 58.44104459231898)
F11_MD, F11_TVD = 4770.0, 3258.0

F5_LONLAT = (1.8858690202634343, 58.440960589668826)  # ~10 m from F-11 (same platform)
F5_MD, F5_TVD = 3792.0, 3247.0

F7_LONLAT = (1.8858330165688761, 58.44101959136748)  # ~10 m from F-11 (same platform)
F7_MD, F7_TVD = 1085.0, 1077.0  # much shallower — real MD/TVD contrast

EXPLORATION_19_LONLAT = (1.9281094205165348, 58.43529191857428)  # ~2.55 km away, still VOLVE field
EXPLORATION_19_MD, EXPLORATION_19_TVD = 4644.0, 3132.0

BLANE_1_2_1_LONLAT = (2.4750712585486543, 56.88686341920516)  # ~177 km away, different field
BLANE_1_2_1_MD = 3574.0


def _offset_to_lonlat(wellhead_lon: float, wellhead_lat: float, ns_m: float, ew_m: float) -> tuple[float, float]:
    """Mirrors ingestion/loaders.py's local-tangent-plane offset (same
    formula, duplicated here so this test file has no import dependency
    on the ingestion package) — applied to the real F-11 A survey's
    first/last station NS/EW offsets (ingestion/tests/fixtures/15_9_F_11_A_Survey_Data.csv)."""
    earth_radius_m = 6_371_000.0
    lat = wellhead_lat + math.degrees(ns_m / earth_radius_m)
    lon = wellhead_lon + math.degrees(ew_m / (earth_radius_m * math.cos(math.radians(wellhead_lat))))
    return lon, lat


# Real F-11 A survey: first station md=145.9 ns=4.65 ew=-0.93, last station
# md=3762.0 tvd=3126.49 ns=706.05 ew=297.21.
F11_A_TRAJECTORY = [
    _offset_to_lonlat(*F11_LONLAT, ns_m=4.65, ew_m=-0.93),
    _offset_to_lonlat(*F11_LONLAT, ns_m=706.05, ew_m=297.21),
]
F11_A_MD_BOTTOM, F11_A_TVD_BOTTOM = 3762.0, 3126.49


# --- service-level tests -----------------------------------------------------


def test_excludes_reference_well_itself(db_session, make_well):
    ref = make_well(well_id="15/9-F-11", name="15/9-F-11")
    result = similarity_service.find_similar_wells(db_session, ref.well_id)
    assert all(r.well_id != ref.well_id for r in result.results)


def test_reference_well_not_found_returns_none(db_session):
    assert similarity_service.find_similar_wells(db_session, "does-not-exist") is None


def test_geographic_filter_excludes_distant_well_entirely(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )
    make_well(
        well_id="1/2-1", name="1/2-1", field="BLANE",
        location=from_shape(Point(*BLANE_1_2_1_LONLAT), srid=4326),
        total_depth_md_m=BLANE_1_2_1_MD, total_depth_tvd_m=None,
    )

    result = similarity_service.find_similar_wells(db_session, ref.well_id)

    ids = {r.well_id for r in result.results}
    assert "15/9-F-5" in ids  # ~10 m away — well within the default 50 km radius
    assert "1/2-1" not in ids  # ~177 km away — filtered out as a candidate entirely


def test_missing_tvd_is_dropped_not_fabricated(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_well(
        well_id="15/9-19", name="15/9-19", field="VOLVE",
        location=from_shape(Point(*EXPLORATION_19_LONLAT), srid=4326),
        total_depth_md_m=EXPLORATION_19_MD, total_depth_tvd_m=None,  # real gap: TVD genuinely missing
    )

    result = similarity_service.find_similar_wells(db_session, ref.well_id)
    candidate = next(r for r in result.results if r.well_id == "15/9-19")

    tvd_factor = next(f for f in candidate.factors if f.key == "tvd")
    assert tvd_factor.available is False
    assert tvd_factor.score is None

    # overall_score must be the weighted average over only the *available*
    # factors (geo + MD here), not tvd silently scored as 0.
    available = [f for f in candidate.factors if f.available]
    expected = sum(f.weight * f.score for f in available) / sum(f.weight for f in available)
    assert candidate.overall_score == pytest.approx(round(expected, 4))


def test_trajectory_factor_available_only_when_both_sides_have_one(db_session, make_well, make_wellbore):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_wellbore(
        ref, trajectory_points=F11_A_TRAJECTORY, name="15/9-F-11 A",
        md_top_m=145.9, md_bottom_m=F11_A_MD_BOTTOM, tvd_bottom_m=F11_A_TVD_BOTTOM,
        volve_source_id="15_9_F_11_A",
    )

    with_traj = make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )
    make_wellbore(
        with_traj, trajectory_points=F11_A_TRAJECTORY, name="15/9-F-5",  # reusing real geometry shape
        md_top_m=0, md_bottom_m=F11_A_MD_BOTTOM, tvd_bottom_m=F11_A_TVD_BOTTOM,
    )

    without_traj = make_well(
        well_id="15/9-F-7", name="15/9-F-7", field="VOLVE",
        location=from_shape(Point(*F7_LONLAT), srid=4326),
        total_depth_md_m=F7_MD, total_depth_tvd_m=F7_TVD,
    )
    # No wellbore/trajectory at all for this one.

    result = similarity_service.find_similar_wells(db_session, ref.well_id)

    traj_with = next(r for r in result.results if r.well_id == with_traj.well_id)
    traj_without = next(r for r in result.results if r.well_id == without_traj.well_id)

    f_with = next(f for f in traj_with.factors if f.key == "trajectory_deviation")
    f_without = next(f for f in traj_without.factors if f.key == "trajectory_deviation")

    assert f_with.available is True
    assert f_with.score == pytest.approx(1.0)  # identical trajectory shape reused -> zero deviation diff
    assert f_without.available is False
    assert f_without.score is None


def test_min_factors_excludes_geo_only_candidate(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    # Nearby, but no MD/TVD/trajectory at all — geographic proximity would
    # be the *only* computable factor, which must not be enough alone.
    make_well(
        well_id="15/9-bare", name="15/9-bare", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=None, total_depth_tvd_m=None,
    )

    result = similarity_service.find_similar_wells(db_session, ref.well_id)
    assert "15/9-bare" not in {r.well_id for r in result.results}


def test_top_k_limits_and_orders_results(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,  # close to ref's depth -> higher score
    )
    make_well(
        well_id="15/9-F-7", name="15/9-F-7", field="VOLVE",
        location=from_shape(Point(*F7_LONLAT), srid=4326),
        total_depth_md_m=F7_MD, total_depth_tvd_m=F7_TVD,  # much shallower -> lower score
    )

    result = similarity_service.find_similar_wells(db_session, ref.well_id, top_k=1)
    assert len(result.results) == 1
    assert result.results[0].well_id == "15/9-F-5"  # closer MD/TVD match ranks first
    assert result.results[0].overall_score >= 0
    for r in result.results:
        assert r.distance_km >= 0


def test_result_is_deterministic_across_repeated_calls(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )

    first = similarity_service.find_similar_wells(db_session, ref.well_id)
    second = similarity_service.find_similar_wells(db_session, ref.well_id)
    assert first.model_dump() == second.model_dump()


def test_weights_are_configurable_and_change_ranking(db_session, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    # Closer MD/TVD match, but ~2.55 km away (real exploration-well distance).
    close_depth = make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*EXPLORATION_19_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )
    # Very shallow (poor MD/TVD match) but placed exactly at the reference's
    # own coordinates (best possible geo score).
    close_geo = make_well(
        well_id="15/9-F-7", name="15/9-F-7", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F7_MD, total_depth_tvd_m=F7_TVD,
    )

    depth_heavy = SimilarityConfig(
        weights=SimilarityWeights(geographic_proximity=0.05, total_depth_md=0.7, tvd=0.2, trajectory_deviation=0.05)
    )
    geo_heavy = SimilarityConfig(
        weights=SimilarityWeights(geographic_proximity=0.97, total_depth_md=0.01, tvd=0.01, trajectory_deviation=0.01)
    )

    depth_ranked = similarity_service.find_similar_wells(db_session, ref.well_id, config=depth_heavy)
    geo_ranked = similarity_service.find_similar_wells(db_session, ref.well_id, config=geo_heavy)

    assert depth_ranked.results[0].well_id == close_depth.well_id
    assert geo_ranked.results[0].well_id == close_geo.well_id
    assert depth_ranked.weights["total_depth_md"] == pytest.approx(0.7)
    assert geo_ranked.weights["geographic_proximity"] == pytest.approx(0.97)


# --- HTTP endpoint tests -------------------------------------------------------


def test_similar_endpoint_returns_ranked_results(client, make_well):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )
    make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )

    resp = client.get("/wells/15%2F9-F-11/similar", params={"top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_well_id"] == "15/9-F-11"
    assert body["top_k"] == 5
    assert "disclaimer" in body and "not a validated" in body["disclaimer"].lower()
    assert body["results"][0]["well_id"] == "15/9-F-5"
    assert "factors" in body["results"][0]
    assert {f["key"] for f in body["results"][0]["factors"]} == {
        "geographic_proximity", "total_depth_md", "tvd", "trajectory_deviation",
    }


def test_similar_endpoint_404_for_unknown_well(client):
    resp = client.get("/wells/does-not-exist/similar")
    assert resp.status_code == 404


def test_plain_well_route_still_works_alongside_similar_route(client, make_well):
    # Regression guard: "/similar" is registered before "/{well_id:path}",
    # which uses a greedy path converter — make sure the plain well route
    # (no "/similar" suffix) still resolves to get_well, not 404/misroute.
    make_well(well_id="15/9-F-11", name="15/9-F-11")
    resp = client.get("/wells/15%2F9-F-11")
    assert resp.status_code == 200
    assert resp.json()["well_id"] == "15/9-F-11"
    assert "results" not in resp.json()
