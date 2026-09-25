"""Deterministic historical-drilling-event extraction from the audited
Volve DDR Hugging Face derivative (see `ingestion/VOLVE_DDR_AUDIT.md`).

This module does NOT classify free text. It maps exactly one real,
structured, controlled-vocabulary field — `activity[].stateDetailActivity`
— onto our four-type event vocabulary, per Milestone 6's finding that
naive keyword matching over the free-text `comments` field is unreliable
(562 loose keyword matches vs. 21 verified real incidents in the same
sample). Only the three deterministic mappings below are ever applied;
everything else (including `equipment failure`, `operation failed`,
`injury`, and plain `success`) is left alone — not an event, not an
error, just not something this milestone extracts.

Input shape: one raw DDR record, as returned by the public
`bengsoon/volve_daily_drilling_report` Hugging Face dataset (a
structure-preserving JSON conversion of the original WITSML
`DrillReport` — see the audit doc; this is a *derivative*, never
represented here as the original WITSML source itself). Fetching that
data is a separate concern (`ingestion/scripts/ingest_volve_ddr_events.py`)
— this module's `extract_candidate_events` is a pure function: no
network, no DB, fully unit-testable.

Output feeds the *existing*, unchanged event-ingestion contract
(`ingestion/events.py:parse_event_row` -> `NormalizedEvent` ->
`ingestion/loaders.py:ingest_event_result`) — this module produces
`DDRCandidateEvent` records, which the ingestion script turns into the
same plain string-keyed row dicts any other event source would, and
feeds through that pipeline unchanged. No second validation/loading path.
"""

from dataclasses import dataclass
from datetime import date

from ingestion import _backend_path  # noqa: F401  (wires sys.path before the app.* import below)

from app.models.event import EventType

# The dataset this module's `extract_candidate_events` consumes — a
# public, CC-BY-4.0 licensed, third-party structural conversion of the
# real Volve DDR corpus (see VOLVE_DDR_AUDIT.md), NOT Equinor's original
# WITSML files themselves. Recorded here once so every event/document
# this module produces cites it consistently.
HF_DATASET = "bengsoon/volve_daily_drilling_report"

# Provenance tag stored on both Event.source and SourceDocument.source —
# deliberately distinct from "volve" (the CSV/WITSML-trajectory tag) so
# it's never mistaken for the original disclosure itself.
SOURCE_TAG = "volve_ddr_hf_derivative"

# Deliberately exhaustive and exact — see module docstring. Casing/
# whitespace is normalized (the real corpus is consistently lowercase,
# verified against all 23,447 activities in the full corpus, but this
# guards the assumption rather than silently relying on it) — nothing
# else about the value is ever fuzzy-matched or guessed.
_STATE_DETAIL_TO_EVENT_TYPE: dict[str, str] = {
    "circulation loss": EventType.LOST_CIRCULATION.value,
    "mud loss": EventType.LOST_CIRCULATION.value,
    "stuck equipment": EventType.STUCK_PIPE.value,
}

# Real Volve field-life bounds, grounded in data already in this repo:
# the earliest real SODIR entry date across all 27 VOLVE-field wellbores
# is 1992 (15/9-19 S); Equinor's own dataset description states the
# field was produced 2008-2016; Milestone 6's audit separately observed
# real DDR dates up to 2018-01-24. 1990/2020 are round, conservative
# bounds well outside all of that — wide enough not to reject genuine
# late-campaign reporting, narrow enough to catch a clear artifact like
# the 1979-12-31 outlier Milestone 6 found (a placeholder, not a real
# report date — no real Volve wellbore was even spudded until 1992).
_MIN_PLAUSIBLE_DATE = date(1990, 1, 1)
_MAX_PLAUSIBLE_DATE = date(2020, 1, 1)


@dataclass(frozen=True)
class DDRCandidateEvent:
    """One deterministically-extracted event candidate, not yet matched
    to a Wellbore or loaded into the DB. `doc_name`/`well_name_for_doc`
    are carried alongside purely so the caller can resolve/create the
    associated SourceDocument before building the final ingestion row
    (source_document_id must be a real existing row's id — see
    ingestion/loaders.py:find_or_create_source_document)."""

    wellbore_identifier: str  # raw nameWellbore, e.g. "NO 15/9-F-4" — matched by canonical key, unchanged
    event_type: str
    depth_md_m: float | None
    occurred_at: str | None  # ISO YYYY-MM-DD, or None if genuinely not derivable
    description: str
    source_location: str
    confidence: float
    source: str
    source_event_id: str
    extra_metadata: dict
    doc_name: str
    well_name_for_doc: str


def _parse_activity_date(dtim_start: str) -> str | None:
    """"2008-02-18T10:15:00+01:00" -> "2008-02-18". Returns None (never a
    guess) if the value is empty or not a real calendar date."""
    if not dtim_start:
        return None
    date_str = dtim_start.split("T")[0]
    try:
        date.fromisoformat(date_str)
    except ValueError:
        return None
    return date_str


def _clean_depth(md_raw: object) -> float | None:
    """Real Volve DDR data uses -999.99 as a null sentinel in some
    report-level fields (confirmed in `statusInfo`/`fluid` during the
    Milestone 6/7 audit, though never observed in `activity.md` itself
    across the full 23,447-activity corpus) — treated as "not provided"
    rather than a real negative depth, since it never represents a real
    measurement in this source. A genuinely missing/blank value is also
    None. Never inferred/guessed otherwise."""
    if md_raw in (None, ""):
        return None
    try:
        value = float(md_raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def extract_candidate_events(raw_row: dict) -> tuple[list[DDRCandidateEvent], list[str]]:
    """One raw DDR record -> (candidate events, data-quality rejection
    reasons). Rejections here are *only* for activities that matched a
    supported `stateDetailActivity` but failed a genuine data-quality
    check (implausible date, no evidence text) — not for the vast
    majority of activities that simply aren't one of the three mapped
    values (those are silently not-events, not rejections; see module
    docstring)."""
    doc_name = raw_row.get("docName") or ""
    wellbore_identifier = raw_row.get("nameWellbore") or ""
    well_name_for_doc = raw_row.get("nameWell") or wellbore_identifier

    events: list[DDRCandidateEvent] = []
    rejections: list[str] = []

    for idx, activity in enumerate(raw_row.get("activity") or []):
        state_detail = (activity.get("stateDetailActivity") or "").strip().lower()
        event_type = _STATE_DETAIL_TO_EVENT_TYPE.get(state_detail)
        if event_type is None:
            continue  # not one of the 3 supported values -- not an event, not logged as a rejection

        dtim_start = activity.get("dTimStart") or ""
        occurred_at = _parse_activity_date(dtim_start)
        if dtim_start and occurred_at is None:
            rejections.append(f"{doc_name}#{idx}: dTimStart {dtim_start!r} is not a valid date")
            continue
        if occurred_at is not None:
            parsed = date.fromisoformat(occurred_at)
            if not (_MIN_PLAUSIBLE_DATE <= parsed <= _MAX_PLAUSIBLE_DATE):
                rejections.append(
                    f"{doc_name}#{idx}: date {occurred_at} is outside the plausible Volve field-life "
                    f"window ({_MIN_PLAUSIBLE_DATE}..{_MAX_PLAUSIBLE_DATE}) -- rejected, not guessed/corrected"
                )
                continue

        description = (activity.get("comments") or "").strip()
        if not description:
            rejections.append(f"{doc_name}#{idx}: no comments text -- no evidence to store, rejected")
            continue

        dtim_end = activity.get("dTimEnd") or ""
        events.append(
            DDRCandidateEvent(
                wellbore_identifier=wellbore_identifier,
                event_type=event_type,
                depth_md_m=_clean_depth(activity.get("md")),
                occurred_at=occurred_at,
                description=description,
                source_location=f"{doc_name} activity {dtim_start}..{dtim_end}",
                # 1.0 = the *mapping* stateDetailActivity -> event_type is an
                # exact controlled-vocabulary lookup (deterministic
                # extraction method), NOT a claim that the underlying
                # drilling incident itself is independently verified —
                # this is extraction-method confidence, not domain/source
                # certainty (task requirement: be explicit about this).
                confidence=1.0,
                source=SOURCE_TAG,
                # Deterministic, stable across reruns: real docName + the
                # activity's fixed position in that DDR's own activity
                # list (never a random UUID) — see loaders.py idempotency.
                source_event_id=f"volve_ddr:{doc_name}:act{idx:03d}",
                extra_metadata={
                    "state_detail_activity": state_detail,
                    "proprietary_code": activity.get("proprietaryCode"),
                    "phase": activity.get("phase"),
                    "hf_dataset": HF_DATASET,
                },
                doc_name=doc_name,
                well_name_for_doc=well_name_for_doc,
            )
        )

    return events, rejections
