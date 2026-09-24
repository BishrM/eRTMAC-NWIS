from pathlib import Path

from ingestion.volve import parse_volve_survey_csv, wellbore_name_from_filename

FIXTURE = Path(__file__).parent / "fixtures" / "15_9-F-11_Survey_Data.csv"


def test_wellbore_name_from_filename():
    assert wellbore_name_from_filename("15_9-F-11_Survey_Data.csv") == "15/9-F-11"
    assert wellbore_name_from_filename("34_10-A-1_Survey_Data.csv") == "34/10-A-1"


def test_parses_all_stations_in_order():
    result = parse_volve_survey_csv(FIXTURE)
    assert result.ok
    assert result.wellbore_name == "15/9-F-11"
    assert len(result.stations) == 5
    assert [s.md_m for s in result.stations] == [0, 500, 1500, 2500, 3339]
    assert result.stations[-1].inclination_deg == 38.7
    assert result.stations[-1].azimuth_deg == 52.0
    assert result.issues == []


def test_non_monotonic_md_is_a_warning_not_a_rejection(tmp_path):
    bad_csv = tmp_path / "16_2-F-9_Survey_Data.csv"
    bad_csv.write_text("md,inc,azi\n0,0,0\n500,2.0,10.0\n300,3.0,11.0\n")

    result = parse_volve_survey_csv(bad_csv)
    assert result.ok  # still usable — the out-of-order station is kept
    assert len(result.stations) == 3
    assert any(i.severity == "warning" and i.field == "md" for i in result.issues)


def test_invalid_inclination_is_rejected(tmp_path):
    bad_csv = tmp_path / "16_2-F-9_Survey_Data.csv"
    bad_csv.write_text("md,inc,azi\n0,0,0\n500,999,10.0\n")

    result = parse_volve_survey_csv(bad_csv)
    assert len(result.stations) == 1  # only the valid row is kept
    assert any(i.severity == "error" and i.field == "inc" for i in result.issues)
