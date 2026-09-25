#!/usr/bin/env python3
"""Attach one or more Volve WITSML directional-survey trajectory XML files
to their matching SODIR wellbores.

Usage (from repo root, backend/.venv activated):
    python -m ingestion.scripts.ingest_volve_trajectory_witsml data/volve/witsml/*.xml

Each file may contain more than one <trajectory> element (rare in
practice, but the WITSML schema allows it); each is matched and attached
independently. The target wellbore must already exist (run
ingest_sodir_csv.py on its SODIR metadata first) — matched by canonical
wellbore key, not by the filename. Safe to re-run.
"""

import sys

from ingestion import _backend_path  # noqa: F401
from ingestion.loaders import IngestionError, attach_volve_survey
from ingestion.witsml import parse_witsml_trajectory_xml

from app.db.session import SessionLocal


def main(paths: list[str]) -> int:
    files_found = len(paths)
    mapped = 0
    unmatched: list[str] = []
    total_stations = 0
    issue_count = 0

    db = SessionLocal()
    try:
        for path in paths:
            print(f"--- {path} ---")
            try:
                results = parse_witsml_trajectory_xml(path)
            except ValueError as e:
                print(f"  SKIPPED (not a usable trajectory file: {e})")
                continue

            for result in results:
                for issue in result.issues:
                    tag = "WARN" if issue.severity == "warning" else "ERROR"
                    print(f"  [{tag}] {issue.field}: {issue.message}")
                    issue_count += 1

                print(
                    f"  source_identifier={result.source_identifier!r}  "
                    f"canonical_key={result.canonical_key!r}  stations={len(result.stations)}"
                )

                if not result.ok:
                    print("  REJECTED (validation errors above)")
                    unmatched.append(result.source_identifier)
                    continue

                try:
                    wellbore = attach_volve_survey(db, result)
                    db.commit()
                    mapped += 1
                    total_stations += len(result.stations)
                    print(
                        f"  OK  wellbore={wellbore.name!r}  volve_source_id={wellbore.volve_source_id!r}  "
                        f"md_top_m={wellbore.md_top_m}  md_bottom_m={wellbore.md_bottom_m}  "
                        f"tvd_bottom_m={wellbore.tvd_bottom_m}"
                    )
                except IngestionError as e:
                    db.rollback()
                    print(f"  REJECTED ({e})")
                    unmatched.append(result.source_identifier)
    finally:
        db.close()

    print()
    print("Summary:")
    print(f"  trajectory files found: {files_found}")
    print(f"  successfully mapped: {mapped}")
    print(f"  wells without usable/matching survey data: {len(unmatched)}")
    for identifier in unmatched:
        print(f"    - {identifier}")
    print(f"  total stations ingested: {total_stations}")
    print(f"  issues logged: {issue_count}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <witsml_trajectory_xml_path>...", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
