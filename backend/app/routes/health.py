from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.health import HealthResponse
from app.services.qdrant_service import qdrant_is_healthy

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    qdrant_status = "ok" if qdrant_is_healthy() else "error"

    overall = "ok" if db_status == "ok" and qdrant_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, qdrant=qdrant_status)
