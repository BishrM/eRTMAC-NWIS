"""Upsert normalized ingestion records into the backend's Well/Wellbore
tables. This is the only module in `ingestion/` that touches the
database.
"""

from ingestion import _backend_path  # noqa: F401  (wires sys.path before the app.* imports below)

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.well import Well
from app.models.wellbore import Wellbore

from ingestion.schemas import NormalizedWell, NormalizedWellbore, SodirIngestionResult, VolveSurveyIngestionResult


class IngestionError(Exception):
    """Raised when a record can't be loaded (missing prerequisite data,
    unresolved validation errors) — never to paper over bad data."""


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


def attach_volve_survey(db: Session, result: VolveSurveyIngestionResult) -> Wellbore:
    if not result.stations:
        raise IngestionError(f"no valid survey stations parsed for '{result.wellbore_name}'")

    wellbore = db.execute(
        select(Wellbore).where(Wellbore.name == result.wellbore_name)
    ).scalar_one_or_none()
    if wellbore is None:
        raise IngestionError(
            f"no existing wellbore named '{result.wellbore_name}' — ingest its SODIR "
            "metadata before attaching a Volve survey"
        )

    mds = [s.md_m for s in result.stations]
    wellbore.md_top_m = min(mds)
    wellbore.md_bottom_m = max(mds)
    # Full 3D trajectory (Wellbore.trajectory / tvd_bottom_m) needs a
    # minimum-curvature calculation from md/inc/azi — deferred, see volve.py.

    db.flush()
    return wellbore
