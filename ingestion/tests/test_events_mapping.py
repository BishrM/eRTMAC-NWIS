"""Pure parse/validate tests for ingestion/events.py — the structured
historical drilling-event ingestion contract (Milestone 5). No real
historical event data exists yet (Volve DDR/PDF ingestion is future
work) — every fixture here is synthetic test data, clearly labeled as
such in its own description text."""

from pathlib import Path

import pytest

from ingestion.events import SUPPORTED_EVENT_TYPES, parse_event_row, parse_events_csv

FIXTURE = Path(__file__).parent / "fixtures" / "events_sample.csv"

VALID_ROW = {
    "wellbore": "15/9-F-11 A",
    "event_type": "stuck_pipe",
    "depth_md_m": "3200",
    "depth_tvd_m": "3050",
    "occurred_at": "2013-05-20",
    "severity": "high",
    "description": "SYNTHETIC TEST DATA: pipe became stuck while tripping out of hole.",
    "source_document_id": "00000000-0000-0000-0000-000000000000",
    "source_location": "p.4 activity 2",
    "confidence": "0.9",
    "source": "demo",
    "source_event_id": "demo-evt-0001",
    "extra_metadata": '{"mud_weight_sg": 1.32}',
}


def _row(**overrides) -> dict:
    row = dict(VALID_ROW)
    row.update(overrides)
    return row


# --- valid rows ---------------------------------------------------------------


def test_parses_valid_row_into_normalized_event():
    result = parse_event_row(VALID_ROW, 0)
    assert result.ok
    event = result.event
    assert event.wellbore_identifier == "15/9-F-11 A"
    assert event.event_type == "stuck_pipe"
    assert event.depth_md_m == 3200
    assert event.depth_tvd_m == 3050
    assert event.occurred_at.isoformat() == "2013-05-20"
    assert event.severity == "high"
    assert event.confidence == 0.9
    assert event.source == "demo"
    assert event.source_event_id == "demo-evt-0001"
    assert event.extra_metadata == {"mud_weight_sg": 1.32}


def test_optional_fields_may_all_be_absent():
    row = _row(depth_md_m="", depth_tvd_m="", occurred_at="", severity="", confidence="", extra_metadata="")
    result = parse_event_row(row, 0)
    assert result.ok
    event = result.event
    assert event.depth_md_m is None
    assert event.depth_tvd_m is None
    assert event.occurred_at is None
    assert event.severity is None
    assert event.confidence is None
    assert event.extra_metadata is None


def test_parses_all_rows_from_csv_fixture():
    results = parse_events_csv(FIXTURE)
    assert len(results) == 2
    assert all(r.ok for r in results)


# --- event type: only the 4 supported this milestone --------------------------


def test_supported_event_types_are_exactly_the_four_listed():
    assert SUPPORTED_EVENT_TYPES == {"stuck_pipe", "lost_circulation", "kick_influx", "wellbore_instability"}


@pytest.mark.parametrize("event_type", ["bha_equipment_issue", "npt", "other", "made_up_type"])
def test_unsupported_event_type_is_rejected(event_type):
    # Real EventType enum values that exist in the DB model but aren't
    # extracted/validated yet, plus a nonsense value — all rejected the
    # same way (task rule: don't classify against an unvalidated category).
    result = parse_event_row(_row(event_type=event_type), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "event_type" for i in result.issues)


def test_missing_event_type_is_rejected():
    result = parse_event_row(_row(event_type=""), 0)
    assert not result.ok
    assert any(i.field == "event_type" for i in result.issues)


# --- depth values ---------------------------------------------------------------


def test_negative_depth_is_rejected():
    result = parse_event_row(_row(depth_md_m="-10"), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "depth_md_m" for i in result.issues)


def test_non_numeric_depth_is_rejected():
    result = parse_event_row(_row(depth_tvd_m="not-a-number"), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "depth_tvd_m" for i in result.issues)


def test_tvd_exceeding_md_is_a_warning_not_an_error():
    result = parse_event_row(_row(depth_md_m="1000", depth_tvd_m="1500"), 0)
    assert result.ok
    assert any(i.severity == "warning" and i.field == "depth_tvd_m" for i in result.issues)


# --- timestamps -----------------------------------------------------------------


def test_invalid_date_format_is_rejected():
    result = parse_event_row(_row(occurred_at="20/05/2013"), 0)  # DD/MM/YYYY, not our ISO contract
    assert not result.ok
    assert any(i.severity == "error" and i.field == "occurred_at" for i in result.issues)


# --- severity ---------------------------------------------------------------------


def test_invalid_severity_is_rejected():
    result = parse_event_row(_row(severity="catastrophic"), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "severity" for i in result.issues)


# --- confidence range -------------------------------------------------------------


@pytest.mark.parametrize("confidence", ["-0.1", "1.1", "2"])
def test_confidence_out_of_range_is_rejected(confidence):
    result = parse_event_row(_row(confidence=confidence), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "confidence" for i in result.issues)


# --- source references -------------------------------------------------------------


def test_missing_source_document_id_is_rejected():
    result = parse_event_row(_row(source_document_id=""), 0)
    assert not result.ok
    assert any(i.field == "source_document_id" for i in result.issues)


def test_missing_source_location_is_rejected():
    result = parse_event_row(_row(source_location=""), 0)
    assert not result.ok
    assert any(i.field == "source_location" for i in result.issues)


def test_missing_description_is_rejected():
    # Evidence text is not optional — an event with no description isn't evidence-backed.
    result = parse_event_row(_row(description=""), 0)
    assert not result.ok
    assert any(i.field == "description" for i in result.issues)


def test_missing_source_provenance_is_rejected():
    result = parse_event_row(_row(source=""), 0)
    assert not result.ok
    assert any(i.field == "source" for i in result.issues)


def test_missing_source_event_id_is_rejected():
    result = parse_event_row(_row(source_event_id=""), 0)
    assert not result.ok
    assert any(i.field == "source_event_id" for i in result.issues)


# --- extra_metadata: optional, free-form, but must be a JSON object -----------------


def test_invalid_json_extra_metadata_is_rejected():
    result = parse_event_row(_row(extra_metadata="{not valid json"), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "extra_metadata" for i in result.issues)


def test_non_object_json_extra_metadata_is_rejected():
    result = parse_event_row(_row(extra_metadata="[1, 2, 3]"), 0)
    assert not result.ok
    assert any(i.severity == "error" and i.field == "extra_metadata" for i in result.issues)


def test_csv_missing_required_column_raises(tmp_path):
    bad = tmp_path / "bad_events.csv"
    bad.write_text("wellbore,event_type\n15/9-F-11,stuck_pipe\n")
    with pytest.raises(ValueError, match="missing required columns"):
        parse_events_csv(bad)
