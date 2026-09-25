"""Tests for the Milestone 9 source-evidence retrieval layer.

Event/document rows here are demo/synthetic (labeled `source="demo"` or
the real `"volve_ddr_hf_derivative"` tag where the test is specifically
about provenance labeling), since this suite runs against the isolated
`nwis_test` database. The real 204-event dev DB is verified separately,
directly, per the task (see the Milestone 9 report for the real
`volve_ddr:15_9_F_1_2013_08_23:act023` evidence-chain check).
"""

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models.document import DocumentType, SourceDocument
from app.services import evidence_service


def _make_doc(db_session, well, **overrides):
    defaults = dict(
        well_id=well.id,
        title="Demo test document",
        doc_type=DocumentType.DAILY_REPORT,
        uri="test://demo/placeholder.json",
        source="demo",
    )
    defaults.update(overrides)
    doc = SourceDocument(**defaults)
    db_session.add(doc)
    db_session.flush()
    return doc


def _make_well(make_well, **overrides):
    defaults = dict(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(1.8858690202634343, 58.440960589668826), srid=4326),
    )
    defaults.update(overrides)
    return make_well(**defaults)


# --- core lookup: real Event -> correct evidence -----------------------------


def test_real_event_resolves_to_correct_evidence(db_session, make_well, make_wellbore, make_event):
    well = _make_well(make_well)
    bore = make_wellbore(well, name="15/9-F-5 A")
    doc = _make_doc(
        db_session, well,
        title="Volve DDR 15_9_F_5_2013_08_23 (public derivative, not the original WITSML file)",
        uri="hf://bengsoon/volve_daily_drilling_report#docName=15_9_F_5_2013_08_23",
        source="volve_ddr_hf_derivative",
    )
    event = make_event(
        well, wellbore=bore,
        event_type="stuck_pipe",
        depth_md_m=2601.0,
        occurred_at="2013-08-22",
        description='Stuck with flex stab in 13 3/8" shoe, stab 5 m behind bit. Attempted to free string.',
        source_document_id=doc.id,
        source_location="15_9_F_5_2013_08_23 activity 2013-08-22T22:30:00+02:00..2013-08-22T23:00:00+02:00",
        source="volve_ddr_hf_derivative",
        source_event_id="volve_ddr:15_9_F_5_2013_08_23:act023",
        confidence=1.0,
        extra_metadata={"state_detail_activity": "stuck equipment", "hf_dataset": "bengsoon/volve_daily_drilling_report"},
    )

    result = evidence_service.get_evidence_for_event(db_session, "volve_ddr:15_9_F_5_2013_08_23:act023")

    assert result is not None
    assert result.source_event_id == event.source_event_id
    assert result.event_type == "stuck_pipe"
    assert result.well_id == "15/9-F-5"
    assert result.wellbore_id == "15/9-F-5 A"
    assert result.depth_md_m == 2601.0
    assert result.occurred_at.isoformat() == "2013-08-22"
    assert result.evidence_type == "verbatim_source_text"
    assert result.evidence_text.startswith('Stuck with flex stab in 13 3/8" shoe')
    assert result.source_location.startswith("15_9_F_5_2013_08_23 activity")
    assert result.confidence == 1.0


def test_source_document_association_preserved(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well, title="Volve DDR 15_9_F_5_2013_08_23 (public derivative, not the original WITSML file)")
    make_event(well, source_document_id=doc.id, source_event_id="evt-1")

    result = evidence_service.get_evidence_for_event(db_session, "evt-1")

    assert result.provenance.source_document_id == str(doc.id)
    assert result.provenance.source_document_title == doc.title
    assert result.provenance.source_document_uri == doc.uri


def test_lookup_is_by_exact_source_event_id_not_description_text(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(
        well, source_document_id=doc.id, source_event_id="evt-real",
        description="stuck pipe stuck pipe stuck pipe",  # deliberately matches naive keyword search
    )
    make_event(well, source_document_id=doc.id, source_event_id="evt-other", description="unrelated text")

    result = evidence_service.get_evidence_for_event(db_session, "evt-other")
    assert result.evidence_text == "unrelated text"  # never resolved by matching "stuck pipe" text


# --- evidence_type: verbatim text vs. metadata-only, never fabricated -------


def test_metadata_only_when_no_description_text(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-no-text", description=None)

    result = evidence_service.get_evidence_for_event(db_session, "evt-no-text")

    assert result.evidence_type == "metadata_only"
    assert result.evidence_text is None  # never invented to fill the gap


# --- provenance: derivative vs. original, never conflated -------------------


def test_provenance_never_claims_derivative_is_the_original(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-prov")

    result = evidence_service.get_evidence_for_event(db_session, "evt-prov")

    assert result.provenance.derivative_is_original_source is False
    assert "Equinor" in result.provenance.original_corpus
    assert "not the original" in result.disclaimer or "original" in result.disclaimer


def test_derivative_dataset_recorded_from_extra_metadata(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(
        well, source_document_id=doc.id, source_event_id="evt-hf",
        extra_metadata={"hf_dataset": "bengsoon/volve_daily_drilling_report"},
    )

    result = evidence_service.get_evidence_for_event(db_session, "evt-hf")
    assert result.provenance.derivative_dataset == "bengsoon/volve_daily_drilling_report"


def test_derivative_dataset_none_when_not_recorded(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-no-meta", extra_metadata=None)

    result = evidence_service.get_evidence_for_event(db_session, "evt-no-meta")
    assert result.provenance.derivative_dataset is None


# --- not found / malformed ----------------------------------------------------


def test_nonexistent_source_event_id_returns_none(db_session):
    assert evidence_service.get_evidence_for_event(db_session, "does-not-exist") is None


def test_malformed_identifier_rejected_empty():
    assert evidence_service.is_well_formed_source_event_id("") is False


def test_malformed_identifier_rejected_too_long():
    assert evidence_service.is_well_formed_source_event_id("a" * 200) is False


def test_malformed_identifier_rejected_bad_characters():
    assert evidence_service.is_well_formed_source_event_id("../../etc/passwd") is False
    assert evidence_service.is_well_formed_source_event_id("evt with spaces") is False
    assert evidence_service.is_well_formed_source_event_id("evt<script>") is False


def test_well_formed_identifier_accepted():
    assert evidence_service.is_well_formed_source_event_id("volve_ddr:15_9_F_1_2013_08_23:act023") is True
    assert evidence_service.is_well_formed_source_event_id("demo-evt-12345678") is True


# --- deterministic repeated retrieval / no duplicates ------------------------


def test_repeated_retrieval_is_deterministic(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-repeat")

    first = evidence_service.get_evidence_for_event(db_session, "evt-repeat")
    second = evidence_service.get_evidence_for_event(db_session, "evt-repeat")
    assert first.model_dump() == second.model_dump()


def test_source_event_id_unique_so_no_duplicate_evidence(db_session, make_well, make_event):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-unique")

    result = evidence_service.get_evidence_for_event(db_session, "evt-unique")
    assert result is not None  # a single, unambiguous row -- unique constraint guarantees no duplicate


# --- HTTP endpoint -------------------------------------------------------------


def test_evidence_endpoint_returns_expected_shape(client, make_well, make_event, db_session):
    well = _make_well(make_well)
    doc = _make_doc(db_session, well, title="Volve DDR 15_9_F_5_2013_08_23 (public derivative, not the original WITSML file)")
    make_event(
        well, source_document_id=doc.id, source_event_id="volve_ddr:15_9_F_5_2013_08_23:act023",
        event_type="stuck_pipe", depth_md_m=2601.0, occurred_at="2013-08-22",
        description="Stuck with flex stab in 13 3/8 shoe.",
    )

    resp = client.get("/historical-events/volve_ddr:15_9_F_5_2013_08_23:act023/evidence")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_event_id"] == "volve_ddr:15_9_F_5_2013_08_23:act023"
    assert body["event_type"] == "stuck_pipe"
    assert body["evidence_type"] == "verbatim_source_text"
    assert body["evidence_text"] == "Stuck with flex stab in 13 3/8 shoe."
    assert body["provenance"]["source_document_title"].startswith("Volve DDR")
    assert "disclaimer" in body


def test_evidence_endpoint_404_for_unknown_event(client):
    resp = client.get("/historical-events/does-not-exist/evidence")
    assert resp.status_code == 404


def test_evidence_endpoint_422_for_malformed_identifier(client):
    resp = client.get("/historical-events/evt with spaces/evidence")
    assert resp.status_code == 422


def test_historical_events_endpoint_remains_compatible(client, make_well, make_event, db_session):
    from geoalchemy2.shape import from_shape as _from_shape
    from shapely.geometry import Point as _Point

    ref = make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=_from_shape(_Point(1.8858360154953036, 58.44104459231898), srid=4326),
        total_depth_md_m=4770.0, total_depth_tvd_m=3258.0,
    )
    well = _make_well(
        make_well, total_depth_md_m=3792.0, total_depth_tvd_m=3247.0,
        location=_from_shape(_Point(1.8858690202634343, 58.440960589668826), srid=4326),
    )
    doc = _make_doc(db_session, well)
    make_event(well, source_document_id=doc.id, source_event_id="evt-compat")

    resp = client.get("/wells/15%2F9-F-11/historical-events")
    assert resp.status_code == 200
    body = resp.json()
    assert any(e["source_event_id"] == "evt-compat" for e in body["historical_events"])
