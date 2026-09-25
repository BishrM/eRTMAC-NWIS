"""Historical drilling-event retrieval for a well's similarity neighborhood
(Milestone 8).

Deterministic structured retrieval only — no RAG, no embeddings, no LLM
reasoning. Connects two things that already exist and are NOT recomputed
here:

    app.services.similarity_service.find_similar_wells  (Milestone 4)
    app.models.event.Event                               (Milestones 5-7)

Workflow: current well -> existing similarity engine -> top-K comparable
wells -> real Event rows on those wells (via the actual Event.well_id /
Event.wellbore_id foreign keys — never by matching on a well/wellbore
*name* string, which could silently attach an event to the wrong well).

The similarity score returned alongside each event describes the
*well* the event happened on, relative to the current well — it is
never a claim about the event itself, and it is never invented: every
score comes straight from `find_similar_wells`'s own output.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.event import Event, EventType
from app.models.well import Well
from app.schemas.historical_events import (
    HistoricalEventFilters,
    HistoricalEventIntelligenceResponse,
    HistoricalEventResult,
)
from app.schemas.similarity import SimilarWellResult
from app.services.similarity_service import DEFAULT_CONFIG, SimilarityConfig, find_similar_wells


@dataclass(frozen=True)
class HistoricalEventQuery:
    """Every optional filter this milestone supports, in one place —
    see module docstring for why a depth filter is never a cross-well
    depth-equivalence claim."""

    top_k: int = 10
    event_type: EventType | None = None
    min_similarity: float | None = None
    depth_md_min: float | None = None
    depth_md_max: float | None = None


def get_historical_events_for_similar_wells(
    db: Session,
    well_id: str,
    query: HistoricalEventQuery = HistoricalEventQuery(),
    similarity_config: SimilarityConfig = DEFAULT_CONFIG,
) -> HistoricalEventIntelligenceResponse | None:
    """Returns None only if `well_id` itself doesn't exist (route maps
    that to 404) — same contract as find_similar_wells. Every other
    outcome (no comparable wells, comparable wells with no events, a
    filter that removes everything) is a normal response with an empty
    `historical_events` list — never a fabricated fallback."""
    similar = find_similar_wells(db, well_id, top_k=query.top_k, config=similarity_config)
    if similar is None:
        return None

    comparable_wells: list[SimilarWellResult] = similar.results
    if query.min_similarity is not None:
        comparable_wells = [r for r in comparable_wells if r.overall_score >= query.min_similarity]

    filters = HistoricalEventFilters(
        event_type=query.event_type.value if query.event_type else None,
        min_similarity=query.min_similarity,
        depth_md_min=query.depth_md_min,
        depth_md_max=query.depth_md_max,
    )

    if not comparable_wells:
        return HistoricalEventIntelligenceResponse(
            current_well_id=well_id,
            top_k=query.top_k,
            filters=filters,
            comparable_wells=[],
            historical_events=[],
        )

    # Map each comparable well's external well_id (the similarity
    # engine's identifier) to its internal UUID, so events are looked up
    # by the real Event.well_id foreign key -- never by name matching.
    wells_by_external_id = {
        w.well_id: w
        for w in db.execute(
            select(Well).where(Well.well_id.in_([r.well_id for r in comparable_wells]))
        ).scalars()
    }
    similarity_by_internal_id = {
        wells_by_external_id[r.well_id].id: r for r in comparable_wells if r.well_id in wells_by_external_id
    }

    if not similarity_by_internal_id:
        return HistoricalEventIntelligenceResponse(
            current_well_id=well_id,
            top_k=query.top_k,
            filters=filters,
            comparable_wells=comparable_wells,
            historical_events=[],
        )

    # Single bounded query (IN-clause over a top-K-sized set) with
    # eager-loaded wellbore/source_document -- avoids N+1 queries when
    # building each HistoricalEventResult below.
    stmt = (
        select(Event)
        .where(Event.well_id.in_(similarity_by_internal_id.keys()))
        .options(joinedload(Event.wellbore), joinedload(Event.source_document))
    )
    if query.event_type is not None:
        stmt = stmt.where(Event.event_type == query.event_type)
    if query.depth_md_min is not None:
        stmt = stmt.where(Event.depth_md_m >= query.depth_md_min)
    if query.depth_md_max is not None:
        stmt = stmt.where(Event.depth_md_m <= query.depth_md_max)

    events = db.execute(stmt).unique().scalars().all()

    results = [
        HistoricalEventResult(
            historical_well_id=similarity_by_internal_id[event.well_id].well_id,
            historical_well_name=similarity_by_internal_id[event.well_id].name,
            historical_wellbore_id=event.wellbore.name if event.wellbore is not None else None,
            similarity_score=similarity_by_internal_id[event.well_id].overall_score,
            distance_km=similarity_by_internal_id[event.well_id].distance_km,
            event_type=event.event_type.value,
            severity=event.severity.value if event.severity is not None else None,
            depth_md_m=event.depth_md_m,
            depth_tvd_m=event.depth_tvd_m,
            occurred_at=event.occurred_at,
            description=event.description,
            source_document_title=event.source_document.title if event.source_document is not None else None,
            source_location=event.source_location,
            source=event.source,
            source_event_id=event.source_event_id,
            confidence=event.confidence,
        )
        for event in events
    ]

    # Deterministic ordering (documented in the schema): similarity desc,
    # then this event's own depth_md_m asc (missing depth sorts last),
    # then source_event_id asc as a stable tie-breaker.
    results.sort(
        key=lambda r: (
            -r.similarity_score,
            r.depth_md_m is None,
            r.depth_md_m if r.depth_md_m is not None else 0.0,
            r.source_event_id or "",
        )
    )

    return HistoricalEventIntelligenceResponse(
        current_well_id=well_id,
        top_k=query.top_k,
        filters=filters,
        comparable_wells=comparable_wells,
        historical_events=results,
    )
