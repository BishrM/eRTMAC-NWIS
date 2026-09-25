"""DB-level integration tests for the Milestone 7 Volve DDR event adapter
— wiring ingestion/volve_ddr.py's real-fixture output through the
*existing, unchanged* parse_event_row -> ingest_event_result pipeline,
plus the new find_or_create_source_document / find_wellbore_by_canonical_key
helpers.

Well/Wellbore rows below use real values from
data/sodir/wellbore_volve_field.csv (well 15/9-F-4, npdid 5693) —
constructed directly rather than re-run through parse_sodir_csv, since
only the loader/DDR-adapter wiring is under test here, not SODIR
parsing (already covered in test_sodir_mapping.py).
"""

import json
from pathlib import Path

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from ingestion.events import parse_event_row
from ingestion.identifiers import canonical_wellbore_key
from ingestion.loaders import (
    IngestionError,
    find_or_create_source_document,
    find_wellbore_by_canonical_key,
    ingest_event_result,
)
from ingestion.volve_ddr import HF_DATASET, SOURCE_TAG, extract_candidate_events
from app.models.document import DocumentType, SourceDocument
from app.models.event import Event, EventType
from app.models.well import Well
from app.models.wellbore import Wellbore

REAL_FIXTURE = Path(__file__).parent / "fixtures" / "volve_ddr_real_sample_15_9_F_4_2008_02_19.json"


def _make_real_f4(db_session) -> tuple[Well, Wellbore]:
    """Real SODIR values for well 15/9-F-4 (npdid 5693) — see
    data/sodir/wellbore_volve_field.csv."""
    well = Well(
        well_id="15/9-F-4",
        name="15/9-F-4",
        operator="StatoilHydro ASA",
        field="VOLVE",
        country="Norway",
        location=from_shape(Point(1.8858500189664156, 58.440977590048746), srid=4326),
        total_depth_md_m=3510.0,
        total_depth_tvd_m=3139.0,
        source="sodir",
    )
    db_session.add(well)
    db_session.flush()

    wellbore = Wellbore(well_id=well.id, name="15/9-F-4", npdid_wellbore="5693", source="sodir")
    db_session.add(wellbore)
    db_session.flush()
    return well, wellbore


def _ingest_candidate(db_session, candidate, wellbore):
    document = find_or_create_source_document(
        db_session,
        well_id=wellbore.well_id,
        title=f"Volve DDR {candidate.doc_name} (public derivative)",
        doc_type=DocumentType.DAILY_REPORT,
        uri=f"hf://{HF_DATASET}#docName={candidate.doc_name}",
        source=SOURCE_TAG,
    )
    row = {
        "wellbore": candidate.wellbore_identifier,
        "event_type": candidate.event_type,
        "depth_md_m": "" if candidate.depth_md_m is None else str(candidate.depth_md_m),
        "occurred_at": candidate.occurred_at or "",
        "description": candidate.description,
        "source_document_id": str(document.id),
        "source_location": candidate.source_location,
        "confidence": str(candidate.confidence),
        "source": candidate.source,
        "source_event_id": candidate.source_event_id,
        "extra_metadata": json.dumps(candidate.extra_metadata),
    }
    result = parse_event_row(row, 0)
    assert result.ok, result.issues
    return ingest_event_result(db_session, result)


def test_real_ddr_events_ingest_via_the_unchanged_event_pipeline(db_session):
    _, wellbore = _make_real_f4(db_session)
    real_row = json.loads(REAL_FIXTURE.read_text())
    candidates, rejections = extract_candidate_events(real_row)
    assert rejections == []
    assert len(candidates) == 3

    events = [_ingest_candidate(db_session, c, wellbore) for c in candidates]

    assert all(e.event_type == EventType.STUCK_PIPE for e in events)
    assert all(e.wellbore_id == wellbore.id for e in events)
    assert all(e.depth_md_m == 3245.0 for e in events)
    assert all(e.occurred_at.isoformat() == "2008-02-18" for e in events)
    assert all(e.source == SOURCE_TAG for e in events)
    assert all(e.confidence == 1.0 for e in events)
    assert len(set(e.source_event_id for e in events)) == 3  # distinct per activity


def test_source_document_is_created_once_and_reused_across_events(db_session):
    _, wellbore = _make_real_f4(db_session)
    real_row = json.loads(REAL_FIXTURE.read_text())
    candidates, _ = extract_candidate_events(real_row)

    events = [_ingest_candidate(db_session, c, wellbore) for c in candidates]

    doc_ids = {e.source_document_id for e in events}
    assert len(doc_ids) == 1  # all 3 activities are from the same DDR/document

    docs = db_session.query(SourceDocument).all()
    assert len(docs) == 1
    assert docs[0].source == SOURCE_TAG
    assert docs[0].doc_type == DocumentType.DAILY_REPORT
    assert "15_9_F_4_2008_02_19" in docs[0].uri
    assert HF_DATASET in docs[0].uri  # the derivative is named, never presented as the original WITSML


def test_provenance_never_claims_the_hf_derivative_is_the_original_source(db_session):
    _, wellbore = _make_real_f4(db_session)
    real_row = json.loads(REAL_FIXTURE.read_text())
    candidates, _ = extract_candidate_events(real_row)
    event = _ingest_candidate(db_session, candidates[0], wellbore)

    doc = db_session.get(SourceDocument, event.source_document_id)
    assert "derivative" in doc.title.lower()
    assert "original witsml" not in doc.title.lower() or "not the original" in doc.title.lower()


def test_reingesting_the_same_real_fixture_is_idempotent(db_session):
    _, wellbore = _make_real_f4(db_session)
    real_row = json.loads(REAL_FIXTURE.read_text())
    candidates, _ = extract_candidate_events(real_row)

    for c in candidates:
        _ingest_candidate(db_session, c, wellbore)
    for c in candidates:  # rerun, e.g. a second scheduled ingestion pass
        _ingest_candidate(db_session, c, wellbore)

    events = db_session.query(Event).filter_by(source=SOURCE_TAG).all()
    assert len(events) == 3  # no duplicates

    docs = db_session.query(SourceDocument).filter_by(source=SOURCE_TAG).all()
    assert len(docs) == 1  # no duplicate document either


def test_unmatched_wellbore_is_rejected_not_fabricated(db_session):
    # Real technical sidetrack identifiers observed in the audit
    # (VOLVE_DDR_AUDIT.md / Milestone 7 report) that have no matching
    # SODIR wellbore in our 27-row VOLVE-field list.
    for raw_name in ["NO 15/9-19 ST2", "NO 15/9-19 BT2", "NO 15/9-F-11 T2"]:
        with pytest.raises(IngestionError, match="no existing wellbore matches"):
            find_wellbore_by_canonical_key(db_session, canonical_wellbore_key(raw_name), raw_name)


def test_wellbore_association_reuses_existing_canonical_key_matcher(db_session):
    _, wellbore = _make_real_f4(db_session)
    matched = find_wellbore_by_canonical_key(db_session, canonical_wellbore_key("NO 15/9-F-4"), "NO 15/9-F-4")
    assert matched.id == wellbore.id
