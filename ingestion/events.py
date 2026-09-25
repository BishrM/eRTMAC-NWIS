"""Parse and validate structured historical drilling-event rows into
NormalizedEvent records — the event-ingestion contract for Milestone 5.

This module does NOT extract events from raw text/PDF/DDR-XML — that
extraction step (Volve DDR/report parsing) is future work, out of scope
per CLAUDE.md ("Do not build features outside the current milestone").
What this module defines is the *contract* a future extractor must
produce: a plain dict per event (see REQUIRED_COLUMNS/OPTIONAL_COLUMNS
below), validated and normalized the same way regardless of where it
came from. `parse_events_csv` is one convenience reader for that dict
shape (useful for tests and any manually-curated real event data); a
future DDR-XML parser would produce the same dict shape per extracted
event and call `parse_event_row` unchanged.

Only four event types are accepted this milestone (see
SUPPORTED_EVENT_TYPES) — the app.models.event.EventType enum has more
(bha_equipment_issue, npt, other) reserved for later, but nothing
extracts those yet, so ingestion rejects them rather than silently
accepting an unvalidated category.
"""

import csv
import json
from pathlib import Path

from ingestion import _backend_path  # noqa: F401  (wires sys.path before the app.* import below)

from app.models.event import EventSeverity, EventType

from ingestion.schemas import EventIngestionResult, IngestionIssue, NormalizedEvent
from ingestion.validators import optional_date_iso, optional_float, optional_str, required_str

# Deliberately a subset of EventType — see module docstring.
SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.STUCK_PIPE.value,
        EventType.LOST_CIRCULATION.value,
        EventType.KICK_INFLUX.value,
        EventType.WELLBORE_INSTABILITY.value,
    }
)

_SEVERITY_VALUES: frozenset[str] = frozenset(e.value for e in EventSeverity)

# The intermediate structured-event contract (see module docstring).
REQUIRED_COLUMNS = {
    "wellbore",
    "event_type",
    "description",
    "source_document_id",
    "source_location",
    "source",
    "source_event_id",
}
OPTIONAL_COLUMNS = {"depth_md_m", "depth_tvd_m", "occurred_at", "severity", "confidence", "extra_metadata"}


def parse_event_row(row: dict[str, str], row_index: int) -> EventIngestionResult:
    issues: list[IngestionIssue] = []

    wellbore_identifier = required_str(row.get("wellbore"), "wellbore", issues)

    event_type = required_str(row.get("event_type"), "event_type", issues)
    if event_type and event_type not in SUPPORTED_EVENT_TYPES:
        issues.append(
            IngestionIssue(
                "event_type",
                f"'{event_type}' is not a currently supported event type "
                f"(supported this milestone: {sorted(SUPPORTED_EVENT_TYPES)})",
                "error",
            )
        )

    depth_md_m = optional_float(row.get("depth_md_m"), "depth_md_m", issues, min_value=0)
    depth_tvd_m = optional_float(row.get("depth_tvd_m"), "depth_tvd_m", issues, min_value=0)
    if (
        depth_md_m is not None
        and depth_tvd_m is not None
        and depth_tvd_m > depth_md_m
    ):
        issues.append(IngestionIssue("depth_tvd_m", f"TVD ({depth_tvd_m}) exceeds MD ({depth_md_m})", "warning"))

    occurred_at = optional_date_iso(row.get("occurred_at"), "occurred_at", issues)

    severity = optional_str(row.get("severity"))
    if severity and severity not in _SEVERITY_VALUES:
        issues.append(
            IngestionIssue("severity", f"'{severity}' is not a valid severity (expected one of {sorted(_SEVERITY_VALUES)})", "error")
        )

    description = required_str(row.get("description"), "description", issues)
    source_document_id = required_str(row.get("source_document_id"), "source_document_id", issues)
    source_location = required_str(row.get("source_location"), "source_location", issues)
    confidence = optional_float(row.get("confidence"), "confidence", issues, min_value=0, max_value=1)
    source = required_str(row.get("source"), "source", issues)
    source_event_id = required_str(row.get("source_event_id"), "source_event_id", issues)

    extra_metadata: dict | None = None
    raw_metadata = optional_str(row.get("extra_metadata"))
    if raw_metadata:
        try:
            parsed = json.loads(raw_metadata)
        except json.JSONDecodeError as e:
            issues.append(IngestionIssue("extra_metadata", f"invalid JSON: {e}", "error"))
        else:
            if isinstance(parsed, dict):
                extra_metadata = parsed
            else:
                issues.append(IngestionIssue("extra_metadata", "must be a JSON object, not a list/scalar", "error"))

    if any(i.severity == "error" for i in issues):
        return EventIngestionResult(row_index, event=None, issues=issues)

    event = NormalizedEvent(
        wellbore_identifier=wellbore_identifier,
        event_type=event_type,
        depth_md_m=depth_md_m,
        depth_tvd_m=depth_tvd_m,
        occurred_at=occurred_at,
        severity=severity or None,
        description=description,
        source_document_id=source_document_id,
        source_location=source_location,
        confidence=confidence,
        source=source,
        source_event_id=source_event_id,
        extra_metadata=extra_metadata,
    )
    return EventIngestionResult(row_index, event=event, issues=issues)


def parse_events_csv(path: str | Path) -> list[EventIngestionResult]:
    path = Path(path)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"events CSV is missing required columns: {sorted(missing)}")
        return [parse_event_row(row, i) for i, row in enumerate(reader)]
