from pathlib import Path

import pytest

from ingestion.loaders import IngestionError, attach_volve_survey, ingest_sodir_result
from ingestion.sodir import parse_sodir_csv
from ingestion.volve import parse_volve_survey_csv
from app.models.well import Well
from app.models.wellbore import Wellbore

SODIR_FIXTURE = Path(__file__).parent / "fixtures" / "sodir_wellbore_sample.csv"
VOLVE_FIXTURE = Path(__file__).parent / "fixtures" / "15_9-F-11_Survey_Data.csv"


def test_ingest_sodir_row_creates_well_and_wellbore(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[0]  # the clean 15/9-F-11 row
    well, wellbore = ingest_sodir_result(db_session, result)

    assert well.well_id == "15/9-F-11"
    assert well.source == "sodir"
    assert wellbore.name == "15/9-F-11"
    assert wellbore.npdid_wellbore == "5001"
    assert wellbore.well_id == well.id


def test_ingest_sodir_row_is_idempotent(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[0]
    ingest_sodir_result(db_session, result)
    ingest_sodir_result(db_session, result)  # re-run, e.g. next day's export

    wells = db_session.query(Well).filter_by(well_id="15/9-F-11").all()
    wellbores = db_session.query(Wellbore).filter_by(npdid_wellbore="5001").all()
    assert len(wells) == 1
    assert len(wellbores) == 1


def test_ingest_invalid_row_raises(db_session):
    result = parse_sodir_csv(SODIR_FIXTURE)[2]  # the row with hard errors
    with pytest.raises(IngestionError):
        ingest_sodir_result(db_session, result)


def test_attach_volve_survey_sets_md_range(db_session):
    sodir_result = parse_sodir_csv(SODIR_FIXTURE)[0]
    ingest_sodir_result(db_session, sodir_result)

    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    wellbore = attach_volve_survey(db_session, survey_result)

    assert wellbore.md_top_m == 0
    assert wellbore.md_bottom_m == 3339
    assert wellbore.trajectory is None  # not computed yet, by design


def test_attach_volve_survey_without_matching_wellbore_raises(db_session):
    survey_result = parse_volve_survey_csv(VOLVE_FIXTURE)
    with pytest.raises(IngestionError, match="no existing wellbore"):
        attach_volve_survey(db_session, survey_result)
