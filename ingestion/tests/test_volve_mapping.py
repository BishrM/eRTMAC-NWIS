from pathlib import Path

import pytest

from ingestion.identifiers import canonical_wellbore_key, volve_identifier_from_filename
from ingestion.volve import parse_volve_survey_csv

FIXTURE = Path(__file__).parent / "fixtures" / "15_9_F_11_A_Survey_Data.csv"


# --- identifier matching (task 1) ------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_raw",
    [
        ("15_9_F_11_A_Survey_Data.csv", "15_9_F_11_A"),
        ("15_9_F_11_Survey_Data.csv", "15_9_F_11"),  # no sidetrack suffix
        ("15_9_F_11_T2_Survey_Data.csv", "15_9_F_11_T2"),  # sidetrack leg notation
        ("16_2-F-9_Survey_Data.csv", "16_2-F-9"),  # a hyphenated variant — kept verbatim, not "fixed"
    ],
)
def test_volve_identifier_from_filename_preserves_raw_string(filename, expected_raw):
    identifier = volve_identifier_from_filename(filename)
    assert identifier.raw == expected_raw  # original source identifier preserved verbatim
    assert identifier.source == "volve"


@pytest.mark.parametrize(
    "a,b",
    [
        ("15/9-F-11 A", "15_9_F_11_A"),  # SODIR vs Volve filename
        ("15/9-F-11", "15_9_F_11"),  # no suffix, either side
        ("1/3-10 A", "1_3_10_A"),
    ],
)
def test_canonical_key_matches_across_separator_conventions(a, b):
    assert canonical_wellbore_key(a) == canonical_wellbore_key(b)


def test_canonical_key_does_not_strip_witsml_country_prefix():
    # WITSML headers use a "NO " (Norway) prefix (see VOLVE_AUDIT.md) —
    # we don't parse that source yet, so no normalization rule for it
    # exists; document the current (non-)behavior rather than assume it.
    assert canonical_wellbore_key("NO 15/9-F-11 A") != canonical_wellbore_key("15/9-F-11 A")


def test_canonical_key_does_not_collapse_different_wellbores():
    # "15/9-F-11" and "15/9-F-11 A" must NOT collide
    assert canonical_wellbore_key("15/9-F-11") != canonical_wellbore_key("15/9-F-11 A")


# --- survey parsing (task 3) -------------------------------------------------


def test_parses_all_stations_using_md_tvd_ns_ew():
    result = parse_volve_survey_csv(FIXTURE)
    assert result.ok
    assert result.source_identifier == "15_9_F_11_A"
    assert result.canonical_key == "159F11A"
    assert len(result.stations) == 5

    first, last = result.stations[0], result.stations[-1]
    assert first.md_m == 145.9
    assert first.tvd_m == 145.9
    assert first.ns_m == 4.65
    assert first.ew_m == -0.93
    assert last.md_m == 3762.0
    assert last.tvd_m == 3126.49
    assert last.ns_m == 706.05
    assert last.ew_m == 297.21
    assert result.issues == []


def test_inclination_and_azimuth_columns_are_ignored_not_required(tmp_path):
    # Real files have Incl/Azi columns, but we must not depend on them —
    # a file with only MD/TVD/NS/EW is still valid.
    minimal = tmp_path / "16_2_F_9_Survey_Data.csv"
    minimal.write_text("MD,TVD,NS,EW\n0,0,0,0\n500,498,10,-5\n")

    result = parse_volve_survey_csv(minimal)
    assert result.ok
    assert len(result.stations) == 2


def test_missing_required_column_raises(tmp_path):
    bad = tmp_path / "16_2_F_9_Survey_Data.csv"
    bad.write_text("MD,Incl,Azi\n0,0,0\n")  # no TVD/NS/EW

    with pytest.raises(ValueError, match="missing required columns"):
        parse_volve_survey_csv(bad)


def test_non_monotonic_md_is_a_warning_and_stations_are_sorted(tmp_path):
    bad = tmp_path / "16_2_F_9_Survey_Data.csv"
    bad.write_text("MD,TVD,NS,EW\n0,0,0,0\n500,498,10,-5\n300,299,6,-3\n")

    result = parse_volve_survey_csv(bad)
    assert result.ok
    assert len(result.stations) == 3
    # Task 4: "trajectory MD ordering is valid" — always sorted downstream,
    # regardless of what order the source file was in.
    assert [s.md_m for s in result.stations] == [0, 300, 500]
    assert any(i.severity == "warning" and i.field == "MD" for i in result.issues)


def test_invalid_required_numeric_field_is_rejected(tmp_path):
    bad = tmp_path / "16_2_F_9_Survey_Data.csv"
    bad.write_text("MD,TVD,NS,EW\n0,0,0,0\n500,not-a-number,10,-5\n")

    result = parse_volve_survey_csv(bad)
    assert len(result.stations) == 1  # only the valid row is kept
    assert any(i.severity == "error" and i.field == "TVD" for i in result.issues)
