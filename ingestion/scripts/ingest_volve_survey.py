#!/usr/bin/env python3
"""Attach one Volve directional-survey CSV to its matching SODIR wellbore.

Usage (from repo root, backend/.venv activated):
    python -m ingestion.scripts.ingest_volve_survey data/volve/15_9_F_11_A_Survey_Data.csv

The target wellbore must already exist (run ingest_sodir_csv.py on its
SODIR metadata first) — matched by canonical wellbore key, not by
reconstructing the SODIR name from the filename. Safe to re-run.
"""

import sys

from ingestion import _backend_path  # noqa: F401
from ingestion.loaders import IngestionError, attach_volve_survey
from ingestion.volve import parse_volve_survey_csv

from app.db.session import SessionLocal


def main(csv_path: str) -> int:
    result = parse_volve_survey_csv(csv_path)

    for issue in result.issues:
        tag = "WARN" if issue.severity == "warning" else "ERROR"
        print(f"  [{tag}] {issue.field}: {issue.message}")

    print(f"source_identifier={result.source_identifier!r}  canonical_key={result.canonical_key!r}")
    print(f"stations parsed: {len(result.stations)}")

    if not result.ok:
        print("REJECTED (validation errors above)")
        return 1

    db = SessionLocal()
    try:
        wellbore = attach_volve_survey(db, result)
        db.commit()
        summary = (
            f"OK  wellbore={wellbore.name!r}  volve_source_id={wellbore.volve_source_id!r}  "
            f"md_top_m={wellbore.md_top_m}  md_bottom_m={wellbore.md_bottom_m}  "
            f"tvd_bottom_m={wellbore.tvd_bottom_m}"
        )
    except IngestionError as e:
        db.rollback()
        print(f"REJECTED ({e})")
        return 1
    finally:
        db.close()

    print(summary)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <volve_survey_csv_path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
