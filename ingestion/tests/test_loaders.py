import math
from pathlib import Path

import pytest
from geoalchemy2.shape import to_shape

from ingestion.loaders import IngestionError, attach_volve_survey, ingest_sodir_result
from ingestion.sodir import parse_sodir_csv
from ingestion.volve import parse_volve_survey_csv
from app.models.well import Well
from app.models.wellbore import Wellbore

SODIR_FIXTURE = Path(__file__).parent / "fixtures" / "sodir_wellbore_sample.csv"
VOLVE_FIXTURE = Path(__file__).parent / "fixtures" / "15_9_F_11_A_Survey_Data.csv"


def _ingest_sodir_wellbore(db_session, wellbore_name: str):
    """Helper: ingest the fixture row for a given wlbWellboreName."""
    results = parse_sodir_csv(SODIR_FIXTURE)
    result = next(r for r in results if r.wellbore and r.wellbore.name == wellbore_name)
    return ingest_sodir_result(db_session, result)


def test_ingest_sodir_row_creates_well_and_wellbore(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[0]  # the clean 15/9-F-11 row
    well, wellbore = ingest_sodir_result(db_session, result)

    assert well.well_id == "15/9-F-11"
    assert well.source == "sodir"
    assert wellbore.name == "15/9-F-11"
    assert wellbore.npdid_wellbore == "7078"
    assert wellbore.well_id == well.id


def test_ingest_sodir_row_is_idempotent(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[0]
    ingest_sodir_result(db_session, result)
    ingest_sodir_result(db_session, result)  # re-run, e.g. next day's export

    wells = db_session.query(Well).filter_by(well_id="15/9-F-11").all()
    wellbores = db_session.query(Wellbore).filter_by(npdid_wellbore="7078").all()
    assert len(wells) == 1
    assert len(wellbores) == 1


def test_ingest_invalid_row_raises(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[2]  # the row with hard errors
    with pytest.raises(IngestionError):
        ingest_sodir_result(db_session, result)


# --- Volve survey attach (tasks 3 & 4) --------------------------------------


def test_attach_volve_survey_to_correct_wellbore(db_session):
    # Two wellbores share the well "15/9-F-11": "15/9-F-11" (base) and
    # "15/9-F-11 A" (sidetrack). The survey must attach to the "A" one,
    # not the base wellbore, even though both exist in the DB.
    _, base_wellbore = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")

    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    assert survey_result.canonical_key == "159F11A"

    wellbore = attach_volve_survey(db_session, survey_result)

    assert wellbore.name == "15/9-F-11 A"
    assert wellbore.id != base_wellbore.id
    assert base_wellbore.md_top_m is None  # the base wellbore is untouched


def test_attach_volve_survey_uses_source_md_tvd_ns_ew(db_session):
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    wellbore = attach_volve_survey(db_session, survey_result)

    assert wellbore.md_top_m == 145.9
    assert wellbore.md_bottom_m == 3762.0
    assert wellbore.tvd_bottom_m == 3126.49  # max TVD, straight from the source column
    assert wellbore.trajectory is not None

    line = to_shape(wellbore.trajectory)
    assert len(line.coords) == 5  # one point per station

    # First station has NS=4.65, EW=-0.93 (near-zero offset) — its point
    # should sit very close to the wellhead itself.
    well = db_session.get(Well, wellbore.well_id)
    wellhead = to_shape(well.location)
    first_point = line.coords[0]
    assert math.dist(first_point, (wellhead.x, wellhead.y)) < 0.01  # well under a degree


def test_attach_volve_survey_preserves_source_provenance(db_session):
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    wellbore = attach_volve_survey(db_session, survey_result)

    # Raw Volve identifier preserved verbatim (not a reconstructed guess),
    # and the wellbore's SODIR provenance (source, npdid) is untouched.
    assert wellbore.volve_source_id == "15_9_F_11_A"
    assert wellbore.source == "sodir"
    assert wellbore.npdid_wellbore == "7079"


def test_attach_volve_survey_without_matching_wellbore_raises(db_session):
    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    with pytest.raises(IngestionError, match="no existing wellbore matches"):
        attach_volve_survey(db_session, survey_result)


def test_attach_volve_survey_ambiguous_match_raises(db_session):
    # Two distinct wellbores that canonicalize to the same key must not
    # be silently disambiguated by picking one.
    _, wb1 = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    wb1.name = "15/9-F-11 A"  # force a collision with the real "15/9-F-11 A" row
    db_session.flush()
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")

    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    with pytest.raises(IngestionError, match="ambiguous match"):
        attach_volve_survey(db_session, survey_result)


def test_attach_volve_survey_without_wellhead_location_raises(db_session):
    _, wellbore_a = _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    well = db_session.get(Well, wellbore_a.well_id)
    well.location = None
    db_session.flush()

    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    with pytest.raises(IngestionError, match="no parent well surface location"):
        attach_volve_survey(db_session, survey_result)


def test_attach_volve_survey_is_idempotent(db_session):
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    attach_volve_survey(db_session, survey_result)
    attach_volve_survey(db_session, survey_result)  # re-run

    wellbores = db_session.query(Wellbore).filter_by(name="15/9-F-11 A").all()
    assert len(wellbores) == 1  # no duplicate wellbore association created
