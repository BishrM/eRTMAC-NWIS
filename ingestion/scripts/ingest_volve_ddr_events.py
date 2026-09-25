#!/usr/bin/env python3
"""Deterministically extract and ingest real historical drilling events
from the audited Volve DDR Hugging Face derivative.

Fetches `bengsoon/volve_daily_drilling_report` via Hugging Face's public
`datasets-server` REST API (no auth, no bulk file download — paginated
row reads only; see ingestion/VOLVE_DDR_AUDIT.md for how this dataset
was found and audited). For each DDR record's activities, creates an
Event ONLY when that activity's `stateDetailActivity` is one of the
three controlled-vocabulary values mapped in `ingestion/volve_ddr.py` —
never from free text (see that module's docstring for why).

Reuses the existing event contract unchanged:
    ingestion.volve_ddr.extract_candidate_events (pure, this file's own logic)
    -> ingestion.events.parse_event_row            (existing, unchanged)
    -> ingestion.loaders.ingest_event_result        (existing, unchanged)

Usage (from repo root, backend/.venv activated):
    python -m ingestion.scripts.ingest_volve_ddr_events [--max-records N] [--dry-run]

Safe to re-run: events are upserted by a deterministic source_event_id
(ingestion/volve_ddr.py), source documents are found-or-created by uri
(ingestion/loaders.py:find_or_create_source_document).
"""

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request

import certifi

from ingestion import _backend_path  # noqa: F401
from ingestion.events import parse_event_row
from ingestion.identifiers import canonical_wellbore_key
from ingestion.loaders import (
    IngestionError,
    find_or_create_source_document,
    find_wellbore_by_canonical_key,
    ingest_event_result,
)
from ingestion.volve_ddr import HF_DATASET, SOURCE_TAG, extract_candidate_events

from app.db.session import SessionLocal
from app.models.document import DocumentType

API_BASE = "https://datasets-server.huggingface.co/rows"
PAGE_SIZE = 100

# This environment's stdlib SSL context doesn't resolve the system CA
# store for this host; certifi is already an installed (transitive)
# dependency, so reuse its bundle rather than add a new one.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def fetch_ddr_rows(max_records: int | None = None) -> list[dict]:
    """Paginated GET against the public datasets-server API — the same
    access route used for the Milestone 6 audit, not a new one."""
    rows: list[dict] = []
    offset = 0
    encoded_dataset = urllib.parse.quote(HF_DATASET, safe="")
    while True:
        remaining = PAGE_SIZE if max_records is None else min(PAGE_SIZE, max_records - len(rows))
        if remaining <= 0:
            break
        url = f"{API_BASE}?dataset={encoded_dataset}&config=default&split=all&offset={offset}&length={remaining}"
        with urllib.request.urlopen(url, timeout=30, context=_SSL_CONTEXT) as resp:
            data = json.load(resp)
        page_rows = [r["row"] for r in data.get("rows", [])]
        if not page_rows:
            break
        rows.extend(page_rows)
        offset += len(page_rows)
        if len(page_rows) < remaining:
            break  # last page
    return rows


def main(max_records: int | None, dry_run: bool) -> int:
    print(f"Fetching DDR records from {HF_DATASET!r} (Hugging Face public API)...")
    raw_rows = fetch_ddr_rows(max_records)
    print(f"Fetched {len(raw_rows)} DDR records.\n")

    n_activities = 0
    n_supported = 0
    n_rejected_data = 0
    n_rejected_wellbore = 0
    n_created = {"lost_circulation": 0, "stuck_pipe": 0}
    seen_docs: set[str] = set()
    wellbores_with_events: set[str] = set()

    db = SessionLocal()
    try:
        for raw_row in raw_rows:
            n_activities += len(raw_row.get("activity") or [])
            candidates, rejections = extract_candidate_events(raw_row)
            n_supported += len(candidates) + len(rejections)
            n_rejected_data += len(rejections)
            for reason in rejections:
                print(f"  [REJECTED-DATA] {reason}")

            for candidate in candidates:
                canonical_key = canonical_wellbore_key(candidate.wellbore_identifier)
                try:
                    wellbore = find_wellbore_by_canonical_key(db, canonical_key, candidate.wellbore_identifier)
                except IngestionError as e:
                    n_rejected_wellbore += 1
                    print(f"  [REJECTED-WELLBORE] {candidate.source_event_id}: {e}")
                    continue

                if dry_run:
                    n_created[candidate.event_type] += 1
                    wellbores_with_events.add(wellbore.name)
                    seen_docs.add(candidate.doc_name)
                    continue

                document = find_or_create_source_document(
                    db,
                    well_id=wellbore.well_id,
                    title=f"Volve DDR {candidate.doc_name} (public derivative, not the original WITSML file)",
                    doc_type=DocumentType.DAILY_REPORT,
                    uri=f"hf://{HF_DATASET}#docName={candidate.doc_name}",
                    source=SOURCE_TAG,
                )
                seen_docs.add(candidate.doc_name)

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
                if not result.ok:
                    n_rejected_data += 1
                    print(f"  [REJECTED-VALIDATION] {candidate.source_event_id}: {result.issues}")
                    continue

                try:
                    event = ingest_event_result(db, result)
                    db.commit()
                except IngestionError as e:
                    db.rollback()
                    n_rejected_wellbore += 1
                    print(f"  [REJECTED-WELLBORE] {candidate.source_event_id}: {e}")
                    continue

                n_created[candidate.event_type] += 1
                wellbores_with_events.add(wellbore.name)
                print(
                    f"  OK  {event.source_event_id}  {event.event_type.value}  "
                    f"wellbore={wellbore.name!r}  depth_md_m={event.depth_md_m}  occurred_at={event.occurred_at}"
                )
    finally:
        db.close()

    print()
    print("Summary:")
    print(f"  DDR records examined: {len(raw_rows)}")
    print(f"  total activities examined: {n_activities}")
    print(f"  activities with a supported stateDetailActivity: {n_supported}")
    print(f"  events created — lost_circulation: {n_created['lost_circulation']}")
    print(f"  events created — stuck_pipe: {n_created['stuck_pipe']}")
    print(f"  rejected (wellbore not found/ambiguous): {n_rejected_wellbore}")
    print(f"  rejected (data-quality/validation): {n_rejected_data}")
    print(f"  unique wellbores with >=1 event: {len(wellbores_with_events)}")
    print(f"  source documents created/found: {len(seen_docs)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-records", type=int, default=None, help="limit DDR records fetched (default: all 1,759)")
    parser.add_argument("--dry-run", action="store_true", help="extract and match but do not write to the DB")
    args = parser.parse_args()
    sys.exit(main(args.max_records, args.dry_run))
