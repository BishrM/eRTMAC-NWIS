"""Normalized, source-agnostic ingestion types.

Raw source rows (SODIR CSV, Volve survey CSV) are parsed and validated in
sodir.py / volve.py into these plain dataclasses. Nothing here touches the
database — that happens in loaders.py, which maps these onto the
SQLAlchemy models owned by backend/app/models.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Severity = Literal["error", "warning"]


@dataclass
class IngestionIssue:
    field: str
    message: str
    severity: Severity


@dataclass
class NormalizedWell:
    well_id: str
    name: str
    operator: str | None
    field: str | None
    country: str | None
    longitude: float | None
    latitude: float | None
    water_depth_m: float | None
    total_depth_md_m: float | None
    total_depth_tvd_m: float | None
    formation: str | None
    spud_date: date | None
    completion_date: date | None
    source: str


@dataclass
class NormalizedWellbore:
    well_id: str  # matches NormalizedWell.well_id (the parent well)
    name: str
    npdid_wellbore: str
    source: str


@dataclass
class SodirIngestionResult:
    row_index: int
    well: NormalizedWell | None
    wellbore: NormalizedWellbore | None
    issues: list[IngestionIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        has_errors = any(i.severity == "error" for i in self.issues)
        return self.well is not None and self.wellbore is not None and not has_errors


@dataclass
class SurveyStation:
    md_m: float
    tvd_m: float
    ns_m: float  # northing offset from the survey's tie-in point, metres
    ew_m: float  # easting offset from the survey's tie-in point, metres


@dataclass
class VolveSurveyIngestionResult:
    source_identifier: str  # raw, as found in the filename, e.g. "15_9_F_11_A"
    canonical_key: str  # canonical_wellbore_key(source_identifier), for matching
    stations: list[SurveyStation] = field(default_factory=list)
    issues: list[IngestionIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        has_errors = any(i.severity == "error" for i in self.issues)
        return len(self.stations) > 0 and not has_errors


@dataclass
class NormalizedEvent:
    """A structured historical drilling event, not yet loaded into the DB.

    `wellbore_identifier` is matched to an existing Wellbore by canonical
    key (ingestion/identifiers.py), the same pattern Volve survey
    attachment uses — never a raw FK, since the source format (eventually
    Volve DDR/XML) won't carry our internal UUIDs. `event_type` and
    `severity` are plain strings (the enum *values*), validated against
    the real app.models.event enums in ingestion/events.py — this module
    stays free of any app.* import, matching every other schema here.
    """

    wellbore_identifier: str
    event_type: str
    depth_md_m: float | None
    depth_tvd_m: float | None
    occurred_at: date | None
    severity: str | None
    description: str
    source_document_id: str  # UUID string of an existing SourceDocument
    source_location: str
    confidence: float | None
    source: str  # provenance tag, e.g. "volve_ddr", "demo"
    source_event_id: str  # stable external id — the upsert/dedup key
    extra_metadata: dict | None = None


@dataclass
class EventIngestionResult:
    row_index: int
    event: NormalizedEvent | None
    issues: list[IngestionIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        has_errors = any(i.severity == "error" for i in self.issues)
        return self.event is not None and not has_errors
