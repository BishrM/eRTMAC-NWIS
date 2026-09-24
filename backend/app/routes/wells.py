from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.well import WellListResponse, WellRead
from app.services import well_service

router = APIRouter(prefix="/wells", tags=["wells"])


@router.get("", response_model=WellListResponse)
def list_wells(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> WellListResponse:
    return well_service.list_wells(db, limit=limit, offset=offset)


@router.get("/{well_id}", response_model=WellRead)
def get_well(well_id: str, db: Session = Depends(get_db)) -> WellRead:
    well = well_service.get_well_by_well_id(db, well_id)
    if well is None:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found")
    return well
