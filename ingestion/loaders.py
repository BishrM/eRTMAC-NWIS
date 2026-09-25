"""Upsert normalized ingestion records into the backend's Well/Wellbore
tables. This is the only module in `ingestion/` that touches the
database.
"""

import math
import uuid

from ingestion import _backend_path  # noqa: F401  (wires sys.path before the app.* imports below)

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import SourceDocument
from app.models.event import Event, EventSeverity, EventType
from app.models.well import Well
from app.models.wellbore import Wellbore
from app.services.geo import point_to_lonlat

from ingestion.identifiers import canonical_wellbore_key
from ingestion.schemas import (
    EventIngestionResult,
    NormalizedWell,
    NormalizedWellbore,
    SodirIngestionResult,
    VolveSurveyIngestionResult,
)

# Mean Earth radius, for a local equirectangular NS/EW-offset -> lon/lat
# approximation. Not survey-grade, but consistent with the accuracy bar
# used elsewhere here (see ingestion/geodesy.py) — plenty for map-scale
# trajectory display.
_EARTH_RADIUS_M = 6_371_000.0


class IngestionError(Exception):
    """Raised when a record can't be loaded (missing prerequisite data,
    unresolved validation errors, an ambiguous match) — never to paper
    over bad data."""


def upsert_well(db: Session, normalized: NormalizedWell) -> Well:
    well = db.execute(select(Well).where(Well.well_id == normalized.well_id)).scalar_one_or_none()
    if well is None:
        well = Well(well_id=normalized.well_id, name=normalized.name, source=normalized.source)
        db.add(well)

    well.name = normalized.name
    well.operator = normalized.operator
    well.field = normalized.field
    well.country = normalized.country
    if normalized.longitude is not None and normalized.latitude is not None:
        well.location = from_shape(Point(normalized.longitude, normalized.latitude), srid=4326)
    well.water_depth_m = normalized.water_depth_m
    well.total_depth_md_m = normalized.total_depth_md_m
    well.total_depth_tvd_m = normalized.total_depth_tvd_m
    well.formation = normalized.formation
    well.spud_date = normalized.spud_date
    well.completion_date = normalized.completion_date

    db.flush()
    return well


def upsert_wellbore(db: Session, well: Well, normalized: NormalizedWellbore) -> Wellbore:
    wellbore = db.execute(
        select(Wellbore).where(Wellbore.npdid_wellbore == normalized.npdid_wellbore)
    ).scalar_one_or_none()
    if wellbore is None:
        wellbore = Wellbore(
            well_id=well.id,
            name=normalized.name,
            npdid_wellbore=normalized.npdid_wellbore,
            source=normalized.source,
        )
        db.add(wellbore)
    else:
        wellbore.well_id = well.id
        wellbore.name = normalized.name

    db.flush()
    return wellbore


def ingest_sodir_result(db: Session, result: SodirIngestionResult) -> tuple[Well, Wellbore]:
    if not result.ok:
        errors = [i for i in result.issues if i.severity == "error"]
        raise IngestionError(f"row {result.row_index}: unresolved validation errors: {errors}")

    well = upsert_well(db, result.well)
    wellbore = upsert_wellbore(db, well, result.wellbore)
    return well, wellbore


def _find_wellbore_by_canonical_key(db: Session, canonical_key: str, source_identifier: str) -> Wellbore:
    """Match a Volve source identifier to exactly one existing Wellbore,
    by canonical key (see ingestion/identifiers.py) — never by guessing
    separator positions in the filename. Raises if zero or more than one
    wellbore matches, rather than silently picking one."""
    all_wellbores = db.execute(select(Wellbore)).scalars().all()
    matches = [wb for wb in all_wellbores if canonical_wellbore_key(wb.name) == canonical_key]

    if not matches:
        raise IngestionError(
            f"no existing wellbore matches Volve identifier '{source_identifier}' "
            f"(canonical key '{canonical_key}') — ingest its SODIR metadata first"
        )
    if len(matches) > 1:
        names = sorted(wb.name for wb in matches)
        raise IngestionError(
            f"ambiguous match for Volve identifier '{source_identifier}': "
            f"{len(matches)} wellbores share canonical key '{canonical_key}': {names}"
        )
    return matches[0]


def _offset_to_lonlat(wellhead_lon: float, wellhead_lat: float, ns_m: float, ew_m: float) -> tuple[float, float]:
    """Local equirectangular approximation of a northing/easting offset
    (metres, relative to the wellhead) as an absolute WGS84 lon/lat."""
    lat = wellhead_lat + math.degrees(ns_m / _EARTH_RADIUS_M)
    lon = wellhead_lon + math.degrees(ew_m / (_EARTH_RADIUS_M * math.cos(math.radians(wellhead_lat))))
    return lon, lat


def attach_volve_survey(db: Session, result: VolveSurveyIngestionResult) -> Wellbore:
    if not result.stations:
        raise IngestionError(f"no valid survey stations parsed for '{result.source_identifier}'")

    wellbore = _find_wellbore_by_canonical_key(db, result.canonical_key, result.source_identifier)

    well = db.get(Well, wellbore.well_id)
    if well is None or well.location is None:
        raise IngestionError(
            f"wellbore '{wellbore.name}' has no parent well surface location — "
            "cannot place its trajectory without one"
        )
    wellhead_lon, wellhead_lat = point_to_lonlat(well.location)

    mds = [s.md_m for s in result.stations]
    wellbore.md_top_m = min(mds)
    wellbore.md_bottom_m = max(mds)
    wellbore.tvd_bottom_m = max(s.tvd_m for s in result.stations)
    wellbore.volve_source_id = result.source_identifier  # provenance: raw Volve identifier

    # result.stations is already MD-sorted (volve.py) — build the surface
    # trajectory from each station's NS/EW offset, as supplied by Volve
    # (not reconstructed from inclination/azimuth).
    line_points = [_offset_to_lonlat(wellhead_lon, wellhead_lat, s.ns_m, s.ew_m) for s in result.stations]
    wellbore.trajectory = from_shape(LineString(line_points), srid=4326)

    db.flush()
    return wellbore


def ingest_event_result(db: Session, result: EventIngestionResult) -> Event:
    """Upserts a structured historical drilling event (ingestion/events.py)
    by `source_event_id` — idempotent re-ingestion, same pattern as
    Wellbore.npdid_wellbore. Requires the referenced wellbore and source
    document to already exist; never creates either (out of scope here —
    see ingestion/events.py's module docstring)."""
    if not result.ok:
        errors = [i for i in result.issues if i.severity == "error"]
        raise IngestionError(f"row {result.row_index}: unresolved validation errors: {errors}")

    normalized = result.event
    wellbore = _find_wellbore_by_canonical_key(
        db, canonical_wellbore_key(normalized.wellbore_identifier), normalized.wellbore_identifier
    )

    try:
        source_document_uuid = uuid.UUID(normalized.source_document_id)
    except ValueError as e:
        raise IngestionError(f"'{normalized.source_document_id}' is not a valid source_document_id: {e}")

    source_document = db.get(SourceDocument, source_document_uuid)
    if source_document is None:
        raise IngestionError(
            f"no SourceDocument with id '{normalized.source_document_id}' — "
            "create/ingest the source document first"
        )

    event = db.execute(
        select(Event).where(Event.source_event_id == normalized.source_event_id)
    ).scalar_one_or_none()
    if event is None:
        event = Event(source_event_id=normalized.source_event_id)
        db.add(event)

    event.well_id = wellbore.well_id
    event.wellbore_id = wellbore.id
    event.source_document_id = source_document.id
    event.event_type = EventType(normalized.event_type)
    event.severity = EventSeverity(normalized.severity) if normalized.severity else None
    event.depth_md_m = normalized.depth_md_m
    event.depth_tvd_m = normalized.depth_tvd_m
    event.occurred_at = normalized.occurred_at
    event.description = normalized.description
    event.source_location = normalized.source_location
    event.confidence = normalized.confidence
    event.source = normalized.source
    event.extra_metadata = normalized.extra_metadata

    db.flush()
    return event
