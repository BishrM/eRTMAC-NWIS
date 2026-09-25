"""Pure extraction-logic tests for ingestion/volve_ddr.py (Milestone 7).

Two fixture types, per the task's own instruction:
- SYNTHETIC rows below (`_synthetic_row`) — clearly labeled, used only to
  exercise edge cases (unsupported values, bad dates, missing text) that
  are awkward to find a real example of.
- One REAL row, `fixtures/volve_ddr_real_sample_15_9_F_4_2008_02_19.json`
  — an actual record from the public `bengsoon/volve_daily_drilling_report`
  Hugging Face dataset (CC-BY-4.0), docName "15_9_F_4_2008_02_19",
  fetched via its public datasets-server API during the Milestone 6/7
  audit. Real well 15/9-F-4, real depths, real timestamps, real
  narrative text — including a genuine case (activity #8) where the
  free-text comments mention "stuck" while `stateDetailActivity` is
  "success", proving in real data (not a contrived example) why this
  module never classifies on keywords.
"""

import json
from pathlib import Path

from ingestion.volve_ddr import (
    _MAX_PLAUSIBLE_DATE,
    _MIN_PLAUSIBLE_DATE,
    HF_DATASET,
    SOURCE_TAG,
    extract_candidate_events,
)

REAL_FIXTURE = Path(__file__).parent / "fixtures" / "volve_ddr_real_sample_15_9_F_4_2008_02_19.json"


def _synthetic_row(**overrides) -> dict:
    """SYNTHETIC TEST DATA — not a real DDR record. Base shape matches
    the real dataset's schema (docName/nameWell/nameWellbore/activity[])."""
    row = {
        "docName": "SYNTHETIC_TEST_15_9_F_99_2010_01_01",
        "nameWell": "NO 15/9-F-99",
        "nameWellbore": "NO 15/9-F-99",
        "activity": [
            {
                "comments": "SYNTHETIC: routine drilling, nothing notable.",
                "dTimStart": "2010-01-01T00:00:00+01:00",
                "dTimEnd": "2010-01-01T06:00:00+01:00",
                "md": "1000",
                "phase": "fixed",
                "proprietaryCode": "drilling -- rotary",
                "state": "ok",
                "stateDetailActivity": "success",
            }
        ],
    }
    row.update(overrides)
    return row


def _activity(**overrides) -> dict:
    base = {
        "comments": "SYNTHETIC: placeholder activity text.",
        "dTimStart": "2010-01-01T00:00:00+01:00",
        "dTimEnd": "2010-01-01T06:00:00+01:00",
        "md": "1000",
        "phase": "fixed",
        "proprietaryCode": "drilling -- rotary",
        "state": "ok",
        "stateDetailActivity": "success",
    }
    base.update(overrides)
    return base


# --- deterministic mappings (task B) -----------------------------------------


def test_circulation_loss_maps_to_lost_circulation():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="circulation loss")])
    events, rejections = extract_candidate_events(row)
    assert rejections == []
    assert len(events) == 1
    assert events[0].event_type == "lost_circulation"


def test_mud_loss_maps_to_lost_circulation():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="mud loss")])
    events, rejections = extract_candidate_events(row)
    assert len(events) == 1
    assert events[0].event_type == "lost_circulation"


def test_stuck_equipment_maps_to_stuck_pipe():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment")])
    events, rejections = extract_candidate_events(row)
    assert len(events) == 1
    assert events[0].event_type == "stuck_pipe"


def test_casing_and_whitespace_are_normalized():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="  Circulation Loss  ")])
    events, _ = extract_candidate_events(row)
    assert len(events) == 1
    assert events[0].event_type == "lost_circulation"


def test_unsupported_state_detail_values_produce_no_event_and_no_rejection():
    # "equipment failure"/"operation failed"/"injury"/"success" are real
    # values in the source (see VOLVE_DDR_AUDIT.md) but not mapped this
    # milestone — silently not-an-event, not logged as a data rejection.
    for value in ["equipment failure", "operation failed", "injury", "success", "", "something else entirely"]:
        row = _synthetic_row(activity=[_activity(stateDetailActivity=value)])
        events, rejections = extract_candidate_events(row)
        assert events == [], f"{value!r} unexpectedly produced an event"
        assert rejections == [], f"{value!r} unexpectedly produced a rejection"


def test_no_free_text_keyword_classification():
    # The word "stuck" appears in the free text, but stateDetailActivity
    # is "success" -- must NOT become a stuck_pipe event. This is the
    # exact real-data scenario found in the real fixture too (see below).
    row = _synthetic_row(
        activity=[
            _activity(
                stateDetailActivity="success",
                comments="SYNTHETIC: cable stuck momentarily but freed itself, no incident.",
            )
        ]
    )
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert rejections == []


# --- data-quality handling (task I) -------------------------------------------


def test_missing_comments_is_rejected_not_silently_dropped():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment", comments="")])
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert len(rejections) == 1
    assert "no comments text" in rejections[0]


def test_implausible_date_is_rejected_not_corrected():
    # The Milestone 6 date outlier (1979-12-31) is well before any real
    # Volve wellbore was even spudded (earliest real SODIR entry: 1992).
    row = _synthetic_row(
        activity=[_activity(stateDetailActivity="stuck equipment", dTimStart="1979-12-31T00:00:00+01:00")]
    )
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert len(rejections) == 1
    assert "outside the plausible" in rejections[0]
    assert "1979-12-31" not in [e.occurred_at for e in events]  # never silently kept/guessed


def test_unparseable_date_is_rejected():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="mud loss", dTimStart="not-a-timestamp")])
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert len(rejections) == 1


def test_date_bounds_are_grounded_not_arbitrary():
    # Documented reasoning lives in the module; just confirm the bounds
    # actually used match what the docstring/report claims.
    from datetime import date

    assert _MIN_PLAUSIBLE_DATE == date(1990, 1, 1)
    assert _MAX_PLAUSIBLE_DATE == date(2020, 1, 1)


def test_negative_depth_sentinel_becomes_none_not_a_fabricated_depth():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="circulation loss", md="-999.99")])
    events, rejections = extract_candidate_events(row)
    assert rejections == []
    assert len(events) == 1
    assert events[0].depth_md_m is None


def test_missing_depth_is_none_event_still_created():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment", md=None)])
    events, _ = extract_candidate_events(row)
    assert len(events) == 1
    assert events[0].depth_md_m is None


def test_real_depth_value_is_parsed_as_float():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment", md="3245")])
    events, _ = extract_candidate_events(row)
    assert events[0].depth_md_m == 3245.0


# --- provenance (task G) -------------------------------------------------------


def test_source_tag_identifies_the_derivative_not_the_original():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="mud loss")])
    events, _ = extract_candidate_events(row)
    assert events[0].source == SOURCE_TAG
    assert "hf" in SOURCE_TAG.lower() or "derivative" in SOURCE_TAG.lower()
    assert events[0].extra_metadata["hf_dataset"] == HF_DATASET


def test_source_location_is_real_not_invented():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="mud loss")])
    events, _ = extract_candidate_events(row)
    loc = events[0].source_location
    assert row["docName"] in loc
    assert "2010-01-01T00:00:00+01:00" in loc  # the real dTimStart, not a page number that doesn't exist


def test_confidence_is_extraction_confidence_not_source_certainty():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="mud loss")])
    events, _ = extract_candidate_events(row)
    assert events[0].confidence == 1.0


# --- source_event_id determinism (task H) -------------------------------------


def test_source_event_id_is_deterministic_across_repeated_calls():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment")])
    events1, _ = extract_candidate_events(row)
    events2, _ = extract_candidate_events(row)
    assert events1[0].source_event_id == events2[0].source_event_id
    assert events1[0].source_event_id == "volve_ddr:SYNTHETIC_TEST_15_9_F_99_2010_01_01:act000"


def test_source_event_id_is_not_a_random_uuid():
    row = _synthetic_row(activity=[_activity(stateDetailActivity="stuck equipment")])
    events, _ = extract_candidate_events(row)
    assert events[0].source_event_id.startswith("volve_ddr:")
    assert row["docName"] in events[0].source_event_id


def test_multiple_activities_get_distinct_ids_by_position():
    row = _synthetic_row(
        activity=[
            _activity(stateDetailActivity="success"),
            _activity(stateDetailActivity="mud loss"),
            _activity(stateDetailActivity="stuck equipment"),
        ]
    )
    events, _ = extract_candidate_events(row)
    assert len(events) == 2
    assert events[0].source_event_id.endswith("act001")
    assert events[1].source_event_id.endswith("act002")


# --- no event-count inflation (task 16) ---------------------------------------


def test_one_record_can_yield_zero_events():
    row = _synthetic_row()  # single "success" activity
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert rejections == []


def test_record_with_no_activities_yields_nothing():
    row = _synthetic_row(activity=[])
    events, rejections = extract_candidate_events(row)
    assert events == []
    assert rejections == []


# --- real audited data (task: at least one integration test on real data) ----


def test_real_fixture_only_extracts_the_three_genuine_stuck_equipment_activities():
    real_row = json.loads(REAL_FIXTURE.read_text())
    events, rejections = extract_candidate_events(real_row)

    assert rejections == []
    assert len(events) == 3  # confirmed by direct inspection of the real fixture
    assert all(e.event_type == "stuck_pipe" for e in events)
    assert all(e.wellbore_identifier == "NO 15/9-F-4" for e in events)
    assert all(e.depth_md_m == 3245.0 for e in events)  # real depth, consistent across all 3

    first = events[0]
    assert first.doc_name == "15_9_F_4_2008_02_19"
    assert first.occurred_at == "2008-02-18"
    assert "WL" in first.description  # real narrative text, not paraphrased
    assert first.source_event_id == "volve_ddr:15_9_F_4_2008_02_19:act010"


def test_real_fixture_activity_mentioning_stuck_in_free_text_is_not_an_event():
    # Activity #9 in the real fixture: comments literally say "found
    # string to be stuck" but stateDetailActivity is "success" — real
    # proof (not a synthetic contrivance) that keyword text is never
    # trusted, only the controlled-vocabulary field.
    real_row = json.loads(REAL_FIXTURE.read_text())
    activity_9 = real_row["activity"][9]
    assert "stuck" in activity_9["comments"].lower()
    assert activity_9["stateDetailActivity"] == "success"

    events, _ = extract_candidate_events(real_row)
    event_ids = {e.source_event_id for e in events}
    assert "volve_ddr:15_9_F_4_2008_02_19:act009" not in event_ids


def test_real_fixture_ignores_equipment_failure_activities():
    real_row = json.loads(REAL_FIXTURE.read_text())
    events, _ = extract_candidate_events(real_row)
    # 7 "equipment failure" activities in the real fixture, all real
    # WITSML-classified equipment issues -- none become an event this
    # milestone (bha_equipment_issue is out of scope per the task).
    assert all(e.event_type != "bha_equipment_issue" for e in events)
    assert len(events) == 3  # only the 3 stuck_equipment ones, not the 7 equipment-failure ones
