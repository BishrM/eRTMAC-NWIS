from datetime import date

from pydantic import BaseModel

from app.schemas.similarity import SIMILARITY_DISCLAIMER, SimilarWellResult

HISTORICAL_EVENTS_DISCLAIMER = (
    SIMILARITY_DISCLAIMER
    + " Historical events themselves are real extracted records (see each"
    " event's source/source_event_id) — the well-similarity score is a"
    " prototype ranking of the *well*, never a claim about the event."
)


class HistoricalEventResult(BaseModel):
    """One real Event row, alongside the well-similarity context that
    surfaced it. `similarity_score`/`distance_km` describe how similar
    the *well* this event occurred on is to the current well — never a
    claim about the event itself (see module disclaimer). Full
    factor-level detail for that well lives once in `comparable_wells`,
    not repeated per event — cross-reference by `historical_well_id`.
    """

    historical_well_id: str
    historical_well_name: str
    historical_wellbore_id: str | None  # Wellbore.name, if the event is tied to a specific wellbore

    similarity_score: float
    distance_km: float

    event_type: str
    severity: str | None
    depth_md_m: float | None
    depth_tvd_m: float | None
    occurred_at: date | None
    description: str | None

    source_document_title: str | None
    source_location: str | None
    source: str
    source_event_id: str | None
    confidence: float | None


class HistoricalEventFilters(BaseModel):
    """Echoes exactly which filters were applied, so a caller (or a
    future RAG layer) never has to guess why a given event is absent."""

    event_type: str | None
    min_similarity: float | None
    depth_md_min: float | None
    depth_md_max: float | None


class HistoricalEventIntelligenceResponse(BaseModel):
    current_well_id: str
    top_k: int
    filters: HistoricalEventFilters

    # The exact wells the historical_events below were drawn from — same
    # SimilarWellResult shape as GET /wells/{id}/similar, already filtered
    # by min_similarity (a well that didn't pass the threshold appears in
    # neither list). Reused verbatim, not recomputed.
    comparable_wells: list[SimilarWellResult]

    # Ordering: historical well similarity score descending, then this
    # event's own recorded depth_md_m ascending (events with no recorded
    # depth sort last), then source_event_id ascending as a stable
    # tie-breaker. See backend/app/services/historical_event_service.py.
    historical_events: list[HistoricalEventResult]

    disclaimer: str = HISTORICAL_EVENTS_DISCLAIMER
