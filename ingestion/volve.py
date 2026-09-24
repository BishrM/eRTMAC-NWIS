"""Parse Volve directional-survey CSVs into SurveyStation lists.

Source: Volve's raw per-wellbore deviation survey files, named
"<well>_Survey_Data.csv" with '/' replaced by '_' (e.g.
"15_9-F-11_Survey_Data.csv" for wellbore "15/9-F-11"), columns
"md,inc,azi" (measured depth in m, inclination in deg, azimuth in deg).

This module only maps and validates those raw stations — it does not
compute a 3D trajectory (that needs a minimum-curvature calculation from
md/inc/azi, which is a separate, later step). Only the MD range
(Wellbore.md_top_m / md_bottom_m) is derived here.

A Volve wellbore must already exist (created via SODIR ingestion) before
its survey can be attached — see loaders.attach_volve_survey.
"""

import csv
from pathlib import Path

from ingestion.schemas import IngestionIssue, SurveyStation, VolveSurveyIngestionResult
from ingestion.validators import required_float

REQUIRED_COLUMNS = {"md", "inc", "azi"}


def wellbore_name_from_filename(filename: str) -> str:
    """"15_9-F-11_Survey_Data.csv" -> "15/9-F-11".

    Volve encodes the wellbore's '/' as '_' in filenames. The NPD-style
    name is "<quad>/<block>-<suffix>", so the first underscore is the one
    to restore as a slash.
    """
    stem = Path(filename).stem
    stem = stem.removesuffix("_Survey_Data")
    quad, sep, rest = stem.partition("_")
    if not sep:
        raise ValueError(f"cannot derive wellbore name from filename '{filename}'")
    return f"{quad}/{rest}"


def parse_volve_survey_row(
    row: dict[str, str], row_index: int, previous_md: float | None
) -> tuple[SurveyStation | None, list[IngestionIssue]]:
    issues: list[IngestionIssue] = []

    md = required_float(row.get("md"), "md", issues, min_value=0)
    inclination = required_float(row.get("inc"), "inc", issues, min_value=0, max_value=180)
    azimuth = required_float(row.get("azi"), "azi", issues, min_value=0, max_value=360)

    if md is not None and previous_md is not None and md < previous_md:
        issues.append(
            IngestionIssue(
                "md", f"row {row_index}: md {md} is less than previous station's {previous_md}", "warning"
            )
        )

    if any(i.severity == "error" for i in issues) or md is None or inclination is None or azimuth is None:
        return None, issues

    return SurveyStation(md_m=md, inclination_deg=inclination, azimuth_deg=azimuth), issues


def parse_volve_survey_csv(path: str | Path) -> VolveSurveyIngestionResult:
    path = Path(path)
    wellbore_name = wellbore_name_from_filename(path.name)

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

    return VolveSurveyIngestionResult(wellbore_name=wellbore_name, stations=stations, issues=issues)
