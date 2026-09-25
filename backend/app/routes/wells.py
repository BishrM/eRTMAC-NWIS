from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.event import EventType
from app.schemas.historical_events import HistoricalEventIntelligenceResponse
from app.schemas.similarity import SimilarWellsResponse
from app.schemas.well import WellListResponse, WellRead
from app.services import historical_event_service, similarity_service, well_service
from app.services.historical_event_service import HistoricalEventQuery

router = APIRouter(prefix="/wells", tags=["wells"])


@router.get("", response_model=WellListResponse)
def list_wells(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> WellListResponse:
    return well_service.list_wells(db, limit=limit, offset=offset)


# Registered before the "/{well_id:path}" route below: that route's :path
# converter matches the rest of the URL (including further "/" segments),
# so it would otherwise swallow ".../similar" as part of well_id.
@router.get("/{well_id:path}/similar", response_model=SimilarWellsResponse)
def get_similar_wells(
    well_id: str,
    top_k: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SimilarWellsResponse:
    result = similarity_service.find_similar_wells(db, well_id, top_k=top_k)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found")
    return result


@router.get("/{well_id:path}/historical-events", response_model=HistoricalEventIntelligenceResponse)
def get_historical_events(
    well_id: str,
    top_k: int = Query(10, ge=1, le=100),
    event_type: EventType | None = Query(None),
    min_similarity: float | None = Query(None, ge=0.0, le=1.0),
    depth_md_min: float | None = Query(
        None, ge=0, description="Filters by each event's OWN recorded depth_md_m -- not a claim that this depth is equivalent to the current well's."
    ),
    depth_md_max: float | None = Query(None, ge=0),
    db: Session = Depends(get_db),
) -> HistoricalEventIntelligenceResponse:
    result = historical_event_service.get_historical_events_for_similar_wells(
        db,
        well_id,
        query=HistoricalEventQuery(
            top_k=top_k,
            event_type=event_type,
            min_similarity=min_similarity,
            depth_md_min=depth_md_min,
            depth_md_max=depth_md_max,
        ),
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found")
    return result


@router.get("/{well_id:path}", response_model=WellRead)
def get_well(well_id: str, db: Session = Depends(get_db)) -> WellRead:
    # SODIR/NPD well IDs contain '/' (e.g. "1/3-10"), so the default
    # single-segment path converter doesn't match them — use :path.
    well = well_service.get_well_by_well_id(db, well_id)
    if well is None:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found")
    return well
