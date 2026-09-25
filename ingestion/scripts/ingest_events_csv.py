#!/usr/bin/env python3
"""Ingest a structured historical drilling-events CSV into the dev database.

Usage (from repo root, backend/.venv activated):
    python -m ingestion.scripts.ingest_events_csv path/to/events.csv

This is the loader half of the Milestone 5 event-ingestion contract
(ingestion/events.py) — it does NOT extract events from raw DDR/PDF text;
the input CSV must already be structured (see ingestion/events.py's
REQUIRED_COLUMNS/OPTIONAL_COLUMNS). Every row's wellbore and
source_document_id must already exist. Safe to re-run: rows are upserted
by source_event_id.
"""

import sys

from ingestion import _backend_path  # noqa: F401
from ingestion.events import parse_events_csv
from ingestion.loaders import IngestionError, ingest_event_result

from app.db.session import SessionLocal


def main(csv_path: str) -> int:
    results = parse_events_csv(csv_path)

    ok_count = 0
    rejected_count = 0
    warning_count = 0

    db = SessionLocal()
    try:
        for result in results:
            for issue in result.issues:
                tag = "WARN" if issue.severity == "warning" else "ERROR"
                print(f"  [{tag}] row {result.row_index} {issue.field}: {issue.message}")
                if issue.severity == "warning":
                    warning_count += 1

            if not result.ok:
                rejected_count += 1
                print(f"row {result.row_index}: REJECTED (validation errors above)")
                continue

            try:
                event = ingest_event_result(db, result)
                db.commit()
                ok_count += 1
                print(
                    f"row {result.row_index}: OK  event_type={event.event_type.value!r}  "
                    f"wellbore_id={event.wellbore_id}  source_event_id={event.source_event_id!r}"
                )
            except IngestionError as e:
                db.rollback()
                rejected_count += 1
                print(f"row {result.row_index}: REJECTED ({e})")
    finally:
        db.close()

    print()
    print(f"Summary: {ok_count} ingested, {rejected_count} rejected, {warning_count} warnings")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <events_csv_path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
