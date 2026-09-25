from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.evidence import EventEvidenceResponse
from app.services import evidence_service

router = APIRouter(prefix="/historical-events", tags=["historical-events"])


@router.get("/{source_event_id}/evidence", response_model=EventEvidenceResponse)
def get_event_evidence(source_event_id: str, db: Session = Depends(get_db)) -> EventEvidenceResponse:
    if not evidence_service.is_well_formed_source_event_id(source_event_id):
        raise HTTPException(status_code=422, detail=f"malformed source_event_id: '{source_event_id}'")

    result = evidence_service.get_evidence_for_event(db, source_event_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No event found with source_event_id '{source_event_id}'")
    return result
