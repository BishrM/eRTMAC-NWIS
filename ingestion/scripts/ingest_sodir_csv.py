#!/usr/bin/env python3
"""Ingest a SODIR wellbore CSV export into the dev database.

Usage (from repo root, backend/.venv activated):
    python -m ingestion.scripts.ingest_sodir_csv data/sodir/wellbore_exploration_sample.csv

Prints one line per row (ok / rejected, and any issues) plus a summary.
Safe to re-run: rows are upserted by well_id / npdid_wellbore.
"""

import sys
from pathlib import Path

from ingestion import _backend_path  # noqa: F401
from ingestion.loaders import IngestionError, ingest_sodir_result
from ingestion.sodir import parse_sodir_csv

from app.db.session import SessionLocal


def main(csv_path: str) -> int:
    results = parse_sodir_csv(csv_path)

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
                well, wellbore = ingest_sodir_result(db, result)
                db.commit()
                ok_count += 1
                print(
                    f"row {result.row_index}: OK  well_id={well.well_id!r}  "
                    f"wellbore={wellbore.name!r}  npdid={wellbore.npdid_wellbore}"
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
        print(f"usage: {sys.argv[0]} <sodir_csv_path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
