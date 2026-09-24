from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.well import Well
from app.schemas.well import WellListResponse, WellRead
from app.services.geo import point_to_lonlat


def _to_read(well: Well) -> WellRead:
    lonlat = point_to_lonlat(well.location)
    longitude, latitude = lonlat if lonlat else (None, None)
    return WellRead(
        id=well.id,
        well_id=well.well_id,
        name=well.name,
        operator=well.operator,
        field=well.field,
        country=well.country,
        longitude=longitude,
        latitude=latitude,
        water_depth_m=well.water_depth_m,
        total_depth_md_m=well.total_depth_md_m,
        total_depth_tvd_m=well.total_depth_tvd_m,
        formation=well.formation,
        spud_date=well.spud_date,
        completion_date=well.completion_date,
        source=well.source,
        created_at=well.created_at,
        updated_at=well.updated_at,
    )


def list_wells(db: Session, limit: int = 50, offset: int = 0) -> WellListResponse:
    total = db.scalar(select(func.count()).select_from(Well)) or 0
    rows = (
        db.execute(select(Well).order_by(Well.well_id).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return WellListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_read(w) for w in rows],
    )


def get_well_by_well_id(db: Session, well_id: str) -> WellRead | None:
    well = db.execute(select(Well).where(Well.well_id == well_id)).scalar_one_or_none()
    return _to_read(well) if well else None
