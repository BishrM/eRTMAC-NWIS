"""Tests for the Milestone 8 historical-event retrieval layer.

Reuses the exact real coordinates/depths from test_similarity.py (SODIR
VOLVE-field export values) so well-similarity behavior here is grounded
in the same real data already verified there — this milestone must not
duplicate or alter the similarity algorithm, only consume its output.
Event/document rows are demo/synthetic (labeled `source="demo"`), since
this suite runs against the isolated `nwis_test` database, not the real
204-event dev DB (that's verified separately, directly, per the task).
"""

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models.document import DocumentType, SourceDocument
from app.services import historical_event_service
from app.services.historical_event_service import HistoricalEventQuery

# Real coordinates/depths, from data/sodir/wellbore_volve_field.csv
# (identical to test_similarity.py's constants).
F11_LONLAT = (1.8858360154953036, 58.44104459231898)
F11_MD, F11_TVD = 4770.0, 3258.0

F5_LONLAT = (1.8858690202634343, 58.440960589668826)  # ~10 m from F-11 (same platform)
F5_MD, F5_TVD = 3792.0, 3247.0

F7_LONLAT = (1.8858330165688761, 58.44101959136748)  # ~10 m from F-11 (same platform)
F7_MD, F7_TVD = 1085.0, 1077.0

BLANE_1_2_1_LONLAT = (2.4750712585486543, 56.88686341920516)  # ~177 km away, different field
BLANE_1_2_1_MD = 3574.0


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


def _make_f11(make_well):
    return make_well(
        well_id="15/9-F-11", name="15/9-F-11", field="VOLVE",
        location=from_shape(Point(*F11_LONLAT), srid=4326),
        total_depth_md_m=F11_MD, total_depth_tvd_m=F11_TVD,
    )


def _make_f5(make_well):
    return make_well(
        well_id="15/9-F-5", name="15/9-F-5", field="VOLVE",
        location=from_shape(Point(*F5_LONLAT), srid=4326),
        total_depth_md_m=F5_MD, total_depth_tvd_m=F5_TVD,
    )


def _make_f7(make_well):
    return make_well(
        well_id="15/9-F-7", name="15/9-F-7", field="VOLVE",
        location=from_shape(Point(*F7_LONLAT), srid=4326),
        total_depth_md_m=F7_MD, total_depth_tvd_m=F7_TVD,
    )


# --- core workflow: current well -> comparable wells -> events --------------


def test_current_well_to_comparable_wells_to_events(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(
        f5, event_type="lost_circulation", depth_md_m=2200.0, description="Real-shaped demo event on F-5.",
        source_document_id=doc.id, source="demo",
    )

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)

    assert result is not None
    assert any(w.well_id == "15/9-F-5" for w in result.comparable_wells)
    assert len(result.historical_events) == 1
    event = result.historical_events[0]
    assert event.historical_well_id == "15/9-F-5"
    assert event.event_type == "lost_circulation"
    assert event.depth_md_m == 2200.0


def test_reference_well_not_found_returns_none(db_session):
    assert historical_event_service.get_historical_events_for_similar_wells(db_session, "does-not-exist") is None


# --- well -> wellbore -> event association -----------------------------------


def test_correct_wellbore_to_well_association(db_session, make_well, make_wellbore, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    bore = make_wellbore(f5, name="15/9-F-5 A")
    doc = _make_doc(db_session, f5)
    make_event(f5, wellbore=bore, source_document_id=doc.id)

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)

    event = result.historical_events[0]
    assert event.historical_well_id == "15/9-F-5"
    assert event.historical_wellbore_id == "15/9-F-5 A"


def test_event_with_no_wellbore_reports_none_not_fabricated(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, wellbore=None, source_document_id=doc.id)

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    assert result.historical_events[0].historical_wellbore_id is None


def test_multiple_wellbores_on_one_well_each_report_their_own_bore(db_session, make_well, make_wellbore, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    bore_a = make_wellbore(f5, name="15/9-F-5 A")
    bore_b = make_wellbore(f5, name="15/9-F-5 B")
    doc = _make_doc(db_session, f5)
    make_event(f5, wellbore=bore_a, source_document_id=doc.id, source_event_id="evt-a", depth_md_m=1000.0)
    make_event(f5, wellbore=bore_b, source_document_id=doc.id, source_event_id="evt-b", depth_md_m=2000.0)

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)

    bores_seen = {e.historical_wellbore_id for e in result.historical_events}
    assert bores_seen == {"15/9-F-5 A", "15/9-F-5 B"}


# --- similarity context: present, correct, never invented for the event -----


def test_similarity_score_matches_the_similar_endpoint_exactly(db_session, make_well, make_event):
    from app.services import similarity_service

    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, source_document_id=doc.id)

    similar = similarity_service.find_similar_wells(db_session, ref.well_id)
    expected_score = next(r.overall_score for r in similar.results if r.well_id == "15/9-F-5")

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    event = result.historical_events[0]

    assert event.similarity_score == expected_score
    # Full per-factor breakdown lives once in comparable_wells, not per event.
    comparable = next(w for w in result.comparable_wells if w.well_id == "15/9-F-5")
    assert comparable.factors  # the detail is there, just not duplicated onto the event


def test_event_metadata_is_fully_populated(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5, title="Volve DDR 15_9_F_5_1997_01_01")
    make_event(
        f5,
        event_type="stuck_pipe",
        severity="high",
        depth_md_m=3245.0,
        depth_tvd_m=3100.0,
        occurred_at="2008-02-18",
        description="Real-shaped demo description text.",
        source_document_id=doc.id,
        source_location="15_9_F_5_1997_01_01 activity 2008-02-18T10:15:00..2008-02-18T12:00:00",
        source="demo",
        source_event_id="demo-evt-full",
        confidence=1.0,
    )

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    event = result.historical_events[0]

    assert event.event_type == "stuck_pipe"
    assert event.severity == "high"
    assert event.depth_md_m == 3245.0
    assert event.depth_tvd_m == 3100.0
    assert event.occurred_at.isoformat() == "2008-02-18"
    assert event.description == "Real-shaped demo description text."
    assert event.source_document_title == "Volve DDR 15_9_F_5_1997_01_01"
    assert "activity" in event.source_location
    assert event.source == "demo"
    assert event.source_event_id == "demo-evt-full"
    assert event.confidence == 1.0


def test_severity_is_none_when_not_present_not_guessed(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, severity=None, source_document_id=doc.id)

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    assert result.historical_events[0].severity is None


# --- filters --------------------------------------------------------------------


def test_event_type_filter(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, event_type="stuck_pipe", source_document_id=doc.id, source_event_id="evt-stuck")
    make_event(f5, event_type="lost_circulation", source_document_id=doc.id, source_event_id="evt-loss")

    from app.models.event import EventType

    result = historical_event_service.get_historical_events_for_similar_wells(
        db_session, ref.well_id, query=HistoricalEventQuery(event_type=EventType.LOST_CIRCULATION)
    )
    assert len(result.historical_events) == 1
    assert result.historical_events[0].event_type == "lost_circulation"
    assert result.filters.event_type == "lost_circulation"


def test_event_type_filter_returning_nothing_is_not_an_error(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, event_type="stuck_pipe", source_document_id=doc.id)

    from app.models.event import EventType

    result = historical_event_service.get_historical_events_for_similar_wells(
        db_session, ref.well_id, query=HistoricalEventQuery(event_type=EventType.KICK_INFLUX)
    )
    assert result.historical_events == []
    assert result.comparable_wells  # the well is still a valid comparable well, just has no matching events


def test_min_similarity_filter_removes_low_scoring_candidates(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)  # close MD/TVD match -> high score
    f7 = _make_f7(make_well)  # far MD/TVD (1085 vs 4770) -> much lower score
    doc5 = _make_doc(db_session, f5)
    doc7 = _make_doc(db_session, f7)
    make_event(f5, source_document_id=doc5.id, source_event_id="evt-f5")
    make_event(f7, source_document_id=doc7.id, source_event_id="evt-f7")

    from app.services import similarity_service

    similar = similarity_service.find_similar_wells(db_session, ref.well_id)
    f5_score = next(r.overall_score for r in similar.results if r.well_id == "15/9-F-5")
    f7_score = next(r.overall_score for r in similar.results if r.well_id == "15/9-F-7")
    assert f5_score > f7_score  # sanity: confirms the threshold below is meaningful

    threshold = (f5_score + f7_score) / 2
    result = historical_event_service.get_historical_events_for_similar_wells(
        db_session, ref.well_id, query=HistoricalEventQuery(min_similarity=threshold)
    )

    well_ids = {w.well_id for w in result.comparable_wells}
    assert "15/9-F-5" in well_ids
    assert "15/9-F-7" not in well_ids
    assert all(e.historical_well_id != "15/9-F-7" for e in result.historical_events)


def test_min_similarity_removing_all_candidates_yields_empty_not_fabricated(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, source_document_id=doc.id)

    result = historical_event_service.get_historical_events_for_similar_wells(
        db_session, ref.well_id, query=HistoricalEventQuery(min_similarity=1.01)
    )
    assert result.comparable_wells == []
    assert result.historical_events == []


def test_depth_filters_apply_to_the_events_own_recorded_depth(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, depth_md_m=1000.0, source_document_id=doc.id, source_event_id="evt-shallow")
    make_event(f5, depth_md_m=3000.0, source_document_id=doc.id, source_event_id="evt-deep")

    result = historical_event_service.get_historical_events_for_similar_wells(
        db_session, ref.well_id, query=HistoricalEventQuery(depth_md_min=2000.0)
    )
    assert [e.source_event_id for e in result.historical_events] == ["evt-deep"]
    assert result.filters.depth_md_min == 2000.0


# --- edge cases -------------------------------------------------------------------


def test_no_comparable_wells_yields_empty_response(db_session, make_well):
    # Only a well far outside the default 50 km candidate radius exists.
    ref = _make_f11(make_well)
    make_well(
        well_id="1/2-1", name="1/2-1", field="BLANE",
        location=from_shape(Point(*BLANE_1_2_1_LONLAT), srid=4326),
        total_depth_md_m=BLANE_1_2_1_MD,
    )

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    assert result.comparable_wells == []
    assert result.historical_events == []


def test_comparable_wells_with_no_events_yields_empty_events_list(db_session, make_well):
    ref = _make_f11(make_well)
    _make_f5(make_well)  # a valid comparable well, but no Event rows at all

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    assert result.comparable_wells  # it IS comparable
    assert result.historical_events == []  # just has nothing to show


def test_current_well_own_events_are_excluded(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    ref_doc = _make_doc(db_session, ref)
    f5_doc = _make_doc(db_session, f5)
    make_event(ref, source_document_id=ref_doc.id, source_event_id="evt-on-reference-itself")
    make_event(f5, source_document_id=f5_doc.id, source_event_id="evt-on-f5")

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)

    ids = {e.source_event_id for e in result.historical_events}
    assert "evt-on-reference-itself" not in ids
    assert "evt-on-f5" in ids
    assert all(e.historical_well_id != ref.well_id for e in result.historical_events)


# --- ordering ----------------------------------------------------------------------


def test_deterministic_ordering_similarity_then_depth_then_source_event_id(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)  # higher similarity to ref
    f7 = _make_f7(make_well)  # lower similarity to ref
    doc5 = _make_doc(db_session, f5)
    doc7 = _make_doc(db_session, f7)

    # Two events on the higher-similarity well, out of depth order, plus
    # a tie at the same depth to exercise the source_event_id tie-break.
    make_event(f5, depth_md_m=3000.0, source_document_id=doc5.id, source_event_id="f5-c")
    make_event(f5, depth_md_m=1000.0, source_document_id=doc5.id, source_event_id="f5-a")
    make_event(f5, depth_md_m=1000.0, source_document_id=doc5.id, source_event_id="f5-b")
    make_event(f5, depth_md_m=None, source_document_id=doc5.id, source_event_id="f5-nodepth")
    make_event(f7, depth_md_m=500.0, source_document_id=doc7.id, source_event_id="f7-a")

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)

    ordered_ids = [e.source_event_id for e in result.historical_events]
    assert ordered_ids == ["f5-a", "f5-b", "f5-c", "f5-nodepth", "f7-a"]


def test_ordering_is_stable_across_repeated_calls(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, depth_md_m=1000.0, source_document_id=doc.id, source_event_id="a")
    make_event(f5, depth_md_m=2000.0, source_document_id=doc.id, source_event_id="b")

    first = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    second = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    assert first.model_dump() == second.model_dump()


# --- provenance ----------------------------------------------------------------------


def test_source_provenance_is_preserved_exactly(db_session, make_well, make_event):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5, title="Volve DDR 15_9_F_5_2008_01_01 (public derivative)", source="volve_ddr_hf_derivative")
    make_event(
        f5,
        source="volve_ddr_hf_derivative",
        source_event_id="volve_ddr:15_9_F_5_2008_01_01:act001",
        source_document_id=doc.id,
    )

    result = historical_event_service.get_historical_events_for_similar_wells(db_session, ref.well_id)
    event = result.historical_events[0]

    assert event.source == "volve_ddr_hf_derivative"
    assert event.source_event_id == "volve_ddr:15_9_F_5_2008_01_01:act001"
    assert event.source_document_title == "Volve DDR 15_9_F_5_2008_01_01 (public derivative)"


# --- HTTP endpoint -----------------------------------------------------------------


def test_historical_events_endpoint_returns_expected_shape(client, make_well, make_event, db_session):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, event_type="lost_circulation", depth_md_m=2200.0, source_document_id=doc.id)

    resp = client.get("/wells/15%2F9-F-11/historical-events", params={"top_k": 5})
    assert resp.status_code == 200
    body = resp.json()

    assert body["current_well_id"] == "15/9-F-11"
    assert body["top_k"] == 5
    assert len(body["comparable_wells"]) >= 1
    assert len(body["historical_events"]) == 1
    event = body["historical_events"][0]
    assert event["historical_well_id"] == "15/9-F-5"
    assert event["event_type"] == "lost_circulation"
    assert event["depth_md_m"] == 2200.0
    assert "disclaimer" in body


def test_historical_events_endpoint_404_for_unknown_well(client):
    resp = client.get("/wells/does-not-exist/historical-events")
    assert resp.status_code == 404


def test_historical_events_endpoint_event_type_query_param(client, make_well, make_event, db_session):
    ref = _make_f11(make_well)
    f5 = _make_f5(make_well)
    doc = _make_doc(db_session, f5)
    make_event(f5, event_type="stuck_pipe", source_document_id=doc.id, source_event_id="a")
    make_event(f5, event_type="kick_influx", source_document_id=doc.id, source_event_id="b")

    resp = client.get("/wells/15%2F9-F-11/historical-events", params={"event_type": "kick_influx"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["historical_events"]) == 1
    assert body["historical_events"][0]["event_type"] == "kick_influx"


def test_plain_similar_and_well_routes_still_work_alongside_new_route(client, make_well):
    make_well(well_id="15/9-F-11", name="15/9-F-11")
    assert client.get("/wells/15%2F9-F-11").status_code == 200
    assert client.get("/wells/15%2F9-F-11/similar").status_code == 200
    assert client.get("/wells/15%2F9-F-11/historical-events").status_code == 200
