"""Parse Volve directional-survey CSVs into SurveyStation lists.

Source: Volve's per-wellbore directional survey files, named
"<id>_Survey_Data.csv" where <id> has *every* separator ('/', '-', ' ')
replaced with '_' (e.g. "15_9_F_11_A_Survey_Data.csv" for wellbore
"15/9-F-11 A") — confirmed against a real file, see
ingestion/VOLVE_AUDIT.md. Columns: MD, Incl, Azi, TVD, NS, EW, VS, DLS,
Build, Turn (measured depth, inclination, azimuth, true vertical depth,
northing/easting offset from a tie-in point, all in metres/degrees).

Per the audit, Volve's files already supply computed TVD/NS/EW per
station — we use those directly (MD, TVD, NS, EW) and do not recompute
a trajectory from Incl/Azi ourselves. Incl/Azi/VS/DLS/Build/Turn are
read from the row but not used: DLS/Build/Turn in particular look like
a third party's own derived QC columns, not something to depend on
being present in every real file.

A Volve wellbore must already exist (created via SODIR ingestion) before
its survey can be attached — see loaders.attach_volve_survey, which
matches by canonical_wellbore_key (ingestion/identifiers.py), not by
reconstructing the SODIR name from the filename.
"""

import csv
from pathlib import Path

from ingestion.identifiers import WellboreIdentifier, volve_identifier_from_filename
from ingestion.schemas import IngestionIssue, SurveyStation, VolveSurveyIngestionResult
from ingestion.validators import required_float

REQUIRED_COLUMNS = {"MD", "TVD", "NS", "EW"}


def parse_volve_survey_row(
    row: dict[str, str], row_index: int, previous_md: float | None
) -> tuple[SurveyStation | None, list[IngestionIssue]]:
    issues: list[IngestionIssue] = []

    md = required_float(row.get("MD"), "MD", issues, min_value=0)
    tvd = required_float(row.get("TVD"), "TVD", issues, min_value=0)
    ns = required_float(row.get("NS"), "NS", issues)
    ew = required_float(row.get("EW"), "EW", issues)

    if md is not None and previous_md is not None and md < previous_md:
        issues.append(
            IngestionIssue(
                "MD", f"row {row_index}: MD {md} is less than previous station's {previous_md}", "warning"
            )
        )

    if any(i.severity == "error" for i in issues) or None in (md, tvd, ns, ew):
        return None, issues

    return SurveyStation(md_m=md, tvd_m=tvd, ns_m=ns, ew_m=ew), issues


def parse_volve_survey_csv(path: str | Path) -> VolveSurveyIngestionResult:
    path = Path(path)
    identifier: WellboreIdentifier = volve_identifier_from_filename(path.name)

    stations: list[SurveyStation] = []
    issues: list[IngestionIssue] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Volve survey CSV is missing required columns: {sorted(missing)}")

        previous_md: float | None = None
        for i, row in enumerate(reader):
            station, row_issues = parse_volve_survey_row(row, i, previous_md)
            issues.extend(row_issues)
            if station is not None:
                stations.append(station)
                previous_md = station.md_m

    # Defensive: build downstream (trajectory geometry) assumes MD order,
    # even though out-of-order input is only a warning above, not rejected.
    stations.sort(key=lambda s: s.md_m)

    return VolveSurveyIngestionResult(
        source_identifier=identifier.raw,
        canonical_key=identifier.canonical_key,
        stations=stations,
        issues=issues,
    )
