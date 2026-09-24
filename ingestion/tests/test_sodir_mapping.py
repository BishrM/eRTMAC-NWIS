import csv
import tempfile
from pathlib import Path

import pytest

from ingestion.geodesy import ed50_to_wgs84
from ingestion.sodir import parse_sodir_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sodir_wellbore_sample.csv"


def test_clean_ed50_row_is_transformed_to_wgs84():
    """SODIR's real, near-universal case: ED50 datum, transformed on ingest."""
    results = parse_sodir_csv(FIXTURE)
    row = results[0]
    assert row.ok
    assert row.well.well_id == "15/9-F-11"
    assert row.well.operator == "Statoil Petroleum AS"
    assert row.well.field == "VOLVE"
    assert row.well.country == "Norway"
    assert row.well.source == "sodir"

    expected_lat, expected_lon = ed50_to_wgs84(58.441656, 1.887464)
    assert row.well.latitude == pytest.approx(expected_lat)
    assert row.well.longitude == pytest.approx(expected_lon)
    # sanity: the transform actually moved the point, it didn't pass through
    assert row.well.latitude != 58.441656

    assert row.well.water_depth_m == 91.0
    assert row.well.total_depth_md_m == 4562.0
    assert row.well.total_depth_tvd_m == 3400.0
    assert row.well.spud_date.isoformat() == "2013-03-07"
    assert row.well.completion_date.isoformat() == "2013-05-12"
    assert row.wellbore.name == "15/9-F-11"
    assert row.wellbore.npdid_wellbore == "7078"

    warning_fields = {i.field for i in row.issues}
    assert "wlbGeodeticDatum" in warning_fields  # "transformed from ED50" note


def test_wgs84_row_with_missing_optional_fields_is_still_valid():
    results = parse_sodir_csv(FIXTURE)
    row = results[1]
    assert row.ok
    assert row.well.latitude == 58.10
    assert row.well.longitude == 2.05
    assert row.well.field is None
    assert row.well.total_depth_tvd_m is None
    assert row.well.formation is None
    assert row.well.completion_date is None
    assert row.issues == []  # no warnings for a clean WGS84 row


def test_row_with_hard_errors_is_rejected():
    results = parse_sodir_csv(FIXTURE)
    row = results[2]
    assert not row.ok
    assert row.well is None
    assert row.wellbore is None
    error_fields = {i.field for i in row.issues if i.severity == "error"}
    assert "wlbWellboreName" in error_fields  # missing wellbore name
    assert "wlbWaterDepth" in error_fields  # negative depth
    assert "wlbEntryDate" in error_fields  # invalid date


def test_second_ed50_row_is_also_transformed():
    results = parse_sodir_csv(FIXTURE)
    row = results[3]
    assert row.ok
    assert row.well.latitude is not None
    assert row.well.longitude is not None
    assert row.well.latitude != 58.5  # transformed, not passed through


def test_unrecognized_datum_drops_coordinates_but_keeps_row_valid():
    results = parse_sodir_csv(FIXTURE)
    row = results[4]
    assert row.ok  # still ingestable — just without a position
    assert row.well.latitude is None
    assert row.well.longitude is None
    warning_fields = {i.field for i in row.issues if i.severity == "warning"}
    assert "wlbGeodeticDatum" in warning_fields


def test_missing_required_column_raises():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["wlbWell"])  # missing wlbWellboreName, wlbNpdidWellbore
        writer.writerow(["15/9-F-11"])
        path = f.name

    try:
        with pytest.raises(ValueError, match="missing required columns"):
            parse_sodir_csv(path)
    finally:
        Path(path).unlink()
