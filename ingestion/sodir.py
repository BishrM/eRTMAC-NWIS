"""Parse SODIR (Norwegian Offshore Directorate) wellbore export rows into
NormalizedWell / NormalizedWellbore pairs.

Source: the "Wellbore: Exploration/Development, all" CSV export from
https://factpages.sodir.no (field names verified against the Directorate's
own Wellbore Attributes documentation, 2026-09).

One SODIR row describes one wellbore, grouped under a parent well name
(wlbWell). Rows for the same well are simply repeated CSV rows sharing
that well name — the loader upserts the Well once per well_id.
"""

import csv
from pathlib import Path

from ingestion.schemas import IngestionIssue, NormalizedWell, NormalizedWellbore, SodirIngestionResult
from ingestion.validators import (
    check_ncs_plausibility,
    optional_date_ddmmyyyy,
    optional_float,
    optional_str,
    required_str,
)

SOURCE = "sodir"
COUNTRY = "Norway"
SUPPORTED_DATUM = "WGS84"

# Exact SODIR CSV column names this parser reads. Any other column in the
# source export is ignored.
REQUIRED_COLUMNS = {
    "wlbWell",
    "wlbWellboreName",
    "wlbNpdidWellbore",
}


def parse_sodir_row(row: dict[str, str], row_index: int) -> SodirIngestionResult:
    issues: list[IngestionIssue] = []

    well_id = required_str(row.get("wlbWell"), "wlbWell", issues)
    wellbore_name = required_str(row.get("wlbWellboreName"), "wlbWellboreName", issues)
    npdid_wellbore = required_str(row.get("wlbNpdidWellbore"), "wlbNpdidWellbore", issues)

    operator = optional_str(row.get("wlbDrillingOperator"))
    field_name = optional_str(row.get("wlbField"))
    formation = optional_str(row.get("wlbFormationAtTd"))

    water_depth_m = optional_float(row.get("wlbWaterDepth"), "wlbWaterDepth", issues, min_value=0)
    total_depth_md_m = optional_float(row.get("wlbTotalDepth"), "wlbTotalDepth", issues, min_value=0)
    total_depth_tvd_m = optional_float(
        row.get("wlbFinalVerticalDepth"), "wlbFinalVerticalDepth", issues, min_value=0
    )
    if (
        total_depth_md_m is not None
        and total_depth_tvd_m is not None
        and total_depth_tvd_m > total_depth_md_m
    ):
        issues.append(
            IngestionIssue(
                "wlbFinalVerticalDepth",
                f"TVD ({total_depth_tvd_m}) exceeds MD ({total_depth_md_m})",
                "warning",
            )
        )

    spud_date = optional_date_ddmmyyyy(row.get("wlbEntryDate"), "wlbEntryDate", issues)
    completion_date = optional_date_ddmmyyyy(row.get("wlbCompletionDate"), "wlbCompletionDate", issues)

    datum = optional_str(row.get("wlbGeodeticDatum"))
    latitude = optional_float(row.get("wlbNsDecDeg"), "wlbNsDecDeg", issues, min_value=-90, max_value=90)
    longitude = optional_float(row.get("wlbEwDecDeg"), "wlbEwDecDeg", issues, min_value=-180, max_value=180)

    if datum is None:
        if latitude is not None or longitude is not None:
            issues.append(
                IngestionIssue(
                    "wlbGeodeticDatum",
                    "no datum specified; assuming WGS84",
                    "warning",
                )
            )
    elif datum != SUPPORTED_DATUM:
        # ED50 (and any other non-WGS84 datum) needs a proper coordinate
        # transform we don't implement yet — skip ingesting the point
        # rather than silently storing a wrong position.
        issues.append(
            IngestionIssue(
                "wlbGeodeticDatum",
                f"datum '{datum}' is not supported yet (only WGS84) — coordinates dropped",
                "warning",
            )
        )
        latitude = longitude = None

    if latitude is not None and longitude is not None:
        check_ncs_plausibility(latitude, longitude, issues)

    has_errors = any(i.severity == "error" for i in issues)
    if has_errors:
        return SodirIngestionResult(row_index, well=None, wellbore=None, issues=issues)

    well = NormalizedWell(
        well_id=well_id,
        name=well_id,
        operator=operator,
        field=field_name,
        country=COUNTRY,
        longitude=longitude,
        latitude=latitude,
        water_depth_m=water_depth_m,
        total_depth_md_m=total_depth_md_m,
        total_depth_tvd_m=total_depth_tvd_m,
        formation=formation,
        spud_date=spud_date,
        completion_date=completion_date,
        source=SOURCE,
    )
    wellbore = NormalizedWellbore(
        well_id=well_id,
        name=wellbore_name,
        npdid_wellbore=npdid_wellbore,
        source=SOURCE,
    )
    return SodirIngestionResult(row_index, well=well, wellbore=wellbore, issues=issues)


def parse_sodir_csv(path: str | Path) -> list[SodirIngestionResult]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"SODIR CSV is missing required columns: {sorted(missing)}")
        return [parse_sodir_row(row, i) for i, row in enumerate(reader)]
