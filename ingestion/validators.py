"""Field-level parsing/validation helpers shared by all source parsers.

Every helper takes a raw string (as read from CSV) and returns a parsed
value plus zero or more IngestionIssue objects — it never raises, so a
parser can collect every problem in a row instead of stopping at the
first one.
"""

from datetime import date, datetime

from ingestion.schemas import IngestionIssue

# Norwegian Continental Shelf plausibility bounds (soft check only — a
# coordinate outside this box is a warning, not a hard error, since other
# sources may legitimately fall outside it).
NCS_LAT_RANGE = (56.0, 82.0)
NCS_LON_RANGE = (-5.0, 35.0)


def required_str(raw: str | None, field_name: str, issues: list[IngestionIssue]) -> str:
    value = (raw or "").strip()
    if not value:
        issues.append(IngestionIssue(field_name, "required field is missing", "error"))
    return value


def optional_str(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value or None


def optional_float(
    raw: str | None,
    field_name: str,
    issues: list[IngestionIssue],
    min_value: float | None = None,
    max_value: float | None = None,
) -> float | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        issues.append(IngestionIssue(field_name, f"'{value}' is not a valid number", "error"))
        return None
    if min_value is not None and parsed < min_value:
        issues.append(
            IngestionIssue(field_name, f"{parsed} is below minimum allowed {min_value}", "error")
        )
        return None
    if max_value is not None and parsed > max_value:
        issues.append(
            IngestionIssue(field_name, f"{parsed} is above maximum allowed {max_value}", "error")
        )
        return None
    return parsed


def required_float(
    raw: str | None,
    field_name: str,
    issues: list[IngestionIssue],
    min_value: float | None = None,
    max_value: float | None = None,
) -> float | None:
    if not (raw or "").strip():
        issues.append(IngestionIssue(field_name, "required field is missing", "error"))
        return None
    return optional_float(raw, field_name, issues, min_value, max_value)


def optional_date_ddmmyyyy(
    raw: str | None, field_name: str, issues: list[IngestionIssue]
) -> date | None:
    """SODIR CSV exports dates as DD.MM.YYYY."""
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        issues.append(
            IngestionIssue(field_name, f"'{value}' is not a valid DD.MM.YYYY date", "error")
        )
        return None


def check_ncs_plausibility(
    latitude: float, longitude: float, issues: list[IngestionIssue]
) -> None:
    lat_ok = NCS_LAT_RANGE[0] <= latitude <= NCS_LAT_RANGE[1]
    lon_ok = NCS_LON_RANGE[0] <= longitude <= NCS_LON_RANGE[1]
    if not (lat_ok and lon_ok):
        issues.append(
            IngestionIssue(
                "coordinates",
                f"({latitude}, {longitude}) is outside the expected NCS bounds "
                f"(lat {NCS_LAT_RANGE}, lon {NCS_LON_RANGE}) — check source data",
                "warning",
            )
        )
