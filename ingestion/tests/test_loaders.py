import math
from pathlib import Path

import pytest
from geoalchemy2.shape import to_shape

from ingestion.events import parse_event_row, parse_events_csv
from ingestion.loaders import IngestionError, attach_volve_survey, ingest_event_result, ingest_sodir_result
from ingestion.sodir import parse_sodir_csv
from ingestion.volve import parse_volve_survey_csv
from ingestion.witsml import parse_witsml_trajectory_xml
from app.models.document import DocumentType, SourceDocument
from app.models.event import Event, EventSeverity, EventType
from app.models.well import Well
from app.models.wellbore import Wellbore

SODIR_FIXTURE = Path(__file__).parent / "fixtures" / "sodir_wellbore_sample.csv"
VOLVE_FIXTURE = Path(__file__).parent / "fixtures" / "15_9_F_11_A_Survey_Data.csv"
WITSML_COUNTRY_PREFIX_FIXTURE = Path(__file__).parent / "fixtures" / "witsml_trajectory_country_prefix.xml"
WITSML_MAIN_WELLBORE_FIXTURE = Path(__file__).parent / "fixtures" / "witsml_trajectory_main_wellbore.xml"
WITSML_UNMATCHED_SIDETRACK_FIXTURE = (
    Path(__file__).parent / "fixtures" / "witsml_trajectory_unmatched_sidetrack.xml"
)
EVENTS_FIXTURE = Path(__file__).parent / "fixtures" / "events_sample.csv"


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


# --- WITSML trajectory attach (real second Volve survey format) -------------


def test_attach_witsml_survey_with_country_prefix_matches_base_wellbore(db_session):
    _, base_wellbore = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")  # sidetrack must stay untouched

    survey_result = parse_witsml_trajectory_xml(WITSML_COUNTRY_PREFIX_FIXTURE)[0]
    assert survey_result.canonical_key == "159F11"

    wellbore = attach_volve_survey(db_session, survey_result)

    assert wellbore.id == base_wellbore.id
    assert wellbore.name == "15/9-F-11"
    assert wellbore.md_top_m == 0
    assert wellbore.md_bottom_m == 500.0
    assert wellbore.tvd_bottom_m == 497.2
    assert wellbore.volve_source_id == "NO 15/9-F-11"  # raw WITSML name, prefix preserved
    assert wellbore.trajectory is not None

    sidetrack = db_session.query(Wellbore).filter_by(name="15/9-F-11 A").one()
    assert sidetrack.md_top_m is None


def test_attach_witsml_survey_strips_main_wellbore_suffix_before_matching(db_session):
    _, base_wellbore = _ingest_sodir_wellbore(db_session, "15/9-F-11")

    survey_result = parse_witsml_trajectory_xml(WITSML_MAIN_WELLBORE_FIXTURE)[0]
    wellbore = attach_volve_survey(db_session, survey_result)

    assert wellbore.id == base_wellbore.id
    assert wellbore.volve_source_id == "15/9-F-11"  # "- Main Wellbore" suffix stripped


def test_attach_witsml_survey_for_unmatched_sidetrack_raises(db_session):
    # Real WITSML data includes technical sidetracks (e.g. "T2") that are
    # not among SODIR's registered wellbores for this well — must be
    # rejected explicitly, never fabricated or force-matched.
    _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")

    survey_result = parse_witsml_trajectory_xml(WITSML_UNMATCHED_SIDETRACK_FIXTURE)[0]
    with pytest.raises(IngestionError, match="no existing wellbore matches"):
        attach_volve_survey(db_session, survey_result)


def test_attach_witsml_survey_is_idempotent(db_session):
    _ingest_sodir_wellbore(db_session, "15/9-F-11")
    survey_result = parse_witsml_trajectory_xml(WITSML_COUNTRY_PREFIX_FIXTURE)[0]
    attach_volve_survey(db_session, survey_result)
    attach_volve_survey(db_session, survey_result)  # re-run

    wellbores = db_session.query(Wellbore).filter_by(name="15/9-F-11").all()
    assert len(wellbores) == 1


# --- structured historical drilling-event ingestion (Milestone 5) -----------
#
# All description text below is prefixed "SYNTHETIC TEST DATA" — no real
# historical event data exists yet (Volve DDR/PDF ingestion is future work).


def _make_source_document(db_session, well) -> SourceDocument:
    doc = SourceDocument(
        well_id=well.id,
        title="SYNTHETIC TEST DATA: placeholder daily report",
        doc_type=DocumentType.DAILY_REPORT,
        uri="test://synthetic/placeholder.pdf",
        source="demo",
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _event_result_for(db_session, well, **row_overrides):
    """A real parsed EventIngestionResult from the fixture CSV, with
    source_document_id swapped for a real row created in this test's
    transaction (a static CSV fixture can't know that UUID ahead of time)."""
    doc = _make_source_document(db_session, well)
    row = dict(
        wellbore="15/9-F-11 A",
        event_type="stuck_pipe",
        depth_md_m="3200",
        depth_tvd_m="3050",
        occurred_at="2013-05-20",
        severity="high",
        description="SYNTHETIC TEST DATA: pipe became stuck while tripping out of hole.",
        source_document_id=str(doc.id),
        source_location="p.4 activity 2",
        confidence="0.9",
        source="demo",
        source_event_id="demo-evt-0001",
        extra_metadata='{"mud_weight_sg": 1.32}',
    )
    row.update(row_overrides)
    return parse_event_row(row, 0)


def test_ingest_event_attaches_to_correct_wellbore_and_document(db_session):
    well, _ = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _, wellbore_a = _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    result = _event_result_for(db_session, well)

    event = ingest_event_result(db_session, result)

    assert event.wellbore_id == wellbore_a.id
    assert event.well_id == well.id
    assert event.event_type == EventType.STUCK_PIPE
    assert event.severity == EventSeverity.HIGH
    assert event.depth_md_m == 3200
    assert event.depth_tvd_m == 3050
    assert event.occurred_at.isoformat() == "2013-05-20"
    assert event.confidence == 0.9
    assert event.source == "demo"
    assert event.source_event_id == "demo-evt-0001"
    assert event.extra_metadata == {"mud_weight_sg": 1.32}
    assert event.description.startswith("SYNTHETIC TEST DATA")


def test_ingest_event_without_matching_wellbore_raises(db_session):
    well, _ = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    doc = _make_source_document(db_session, well)
    result = parse_event_row(
        {
            "wellbore": "15/9-F-11 A",  # not ingested — doesn't exist yet
            "event_type": "stuck_pipe",
            "description": "SYNTHETIC TEST DATA: unmatched wellbore case.",
            "source_document_id": str(doc.id),
            "source_location": "p.1",
            "source": "demo",
            "source_event_id": "demo-evt-unmatched",
        },
        0,
    )
    with pytest.raises(IngestionError, match="no existing wellbore matches"):
        ingest_event_result(db_session, result)


def test_ingest_event_with_unknown_source_document_raises(db_session):
    well, _ = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    result = _event_result_for(db_session, well, source_document_id="00000000-0000-0000-0000-000000000000")

    with pytest.raises(IngestionError, match="no SourceDocument"):
        ingest_event_result(db_session, result)


def test_ingest_event_is_idempotent(db_session):
    well, _ = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    result = _event_result_for(db_session, well)

    ingest_event_result(db_session, result)
    ingest_event_result(db_session, result)  # re-run, same source_event_id

    events = db_session.query(Event).filter_by(source_event_id="demo-evt-0001").all()
    assert len(events) == 1


def test_ingest_event_rejects_unresolved_validation_errors(db_session):
    well, _ = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    result = _event_result_for(db_session, well, event_type="not_a_supported_type")

    assert not result.ok
    with pytest.raises(IngestionError, match="unresolved validation errors"):
        ingest_event_result(db_session, result)


def test_ingest_events_csv_fixture_end_to_end(db_session):
    # The fixture's two rows target "15/9-F-11 A" and "15/9-F-11" — both
    # must exist first, same prerequisite as Volve survey attachment.
    well, wellbore_a = _ingest_sodir_wellbore(db_session, "15/9-F-11 A")
    well_base, wellbore_base = _ingest_sodir_wellbore(db_session, "15/9-F-11")
    doc = _make_source_document(db_session, well)

    results = parse_events_csv(EVENTS_FIXTURE)
    assert all(r.ok for r in results)
    for r in results:
        r.event.source_document_id = str(doc.id)  # see _event_result_for's note above

    events = [ingest_event_result(db_session, r) for r in results]

    assert {e.wellbore_id for e in events} == {wellbore_a.id, wellbore_base.id}
    assert {e.event_type for e in events} == {EventType.STUCK_PIPE, EventType.LOST_CIRCULATION}
