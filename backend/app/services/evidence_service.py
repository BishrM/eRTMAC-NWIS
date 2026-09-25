"""Deterministic source-evidence retrieval for a single historical event
(Milestone 9).

Connects, without recomputing or re-extracting anything:

    Event.source_event_id           (the stable, deterministic external id
                                      minted at ingestion time — see
                                      ingestion/volve_ddr.py)
      -> Event row (exact equality lookup on source_event_id -- never a
         string/keyword match against description)
      -> Event.source_document_id -> SourceDocument row (document identity)
      -> Event.description        -> the exact activity comments text
         already captured at ingestion time, if any

This module performs no network access, no filesystem access, and no new
text extraction. It exposes exactly what ingestion already wrote to the
row. If a record has no captured text (e.g. a future metadata-only
source), evidence_type is reported as "metadata_only" rather than
inventing text — see module docstring in ingestion/volve_ddr.py for why
free-text reconstruction is never attempted here either.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.event import Event
from app.schemas.evidence import EventEvidenceResponse, EvidenceProvenance

# Event.source_event_id is a String(128) column; anything longer or
# containing characters outside this set cannot be a real identifier
# minted by this project's own ingestion code (see ingestion/volve_ddr.py,
# ingestion/events.py) -- rejected before ever touching the DB. This is a
# format check only, not a security boundary: source_event_id is always
# used in a parameterized equality comparison, never interpolated into a
# query, file path, or URL.
_MAX_SOURCE_EVENT_ID_LEN = 128
_SOURCE_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:\-]+$")


def is_well_formed_source_event_id(source_event_id: str) -> bool:
    return (
        1 <= len(source_event_id) <= _MAX_SOURCE_EVENT_ID_LEN
        and _SOURCE_EVENT_ID_PATTERN.match(source_event_id) is not None
    )


def get_evidence_for_event(db: Session, source_event_id: str) -> EventEvidenceResponse | None:
    """Returns None if no Event has this exact source_event_id (route maps
    that to 404). `source_event_id` is unique at the DB level, so this can
    never resolve to more than one row -- no duplicate evidence is
    possible by construction."""
    event = (
        db.execute(
            select(Event)
            .where(Event.source_event_id == source_event_id)
            .options(joinedload(Event.well), joinedload(Event.wellbore), joinedload(Event.source_document))
        )
        .unique()
        .scalar_one_or_none()
    )
    if event is None:
        return None

    evidence_text = event.description
    evidence_type = "verbatim_source_text" if evidence_text else "metadata_only"

    extra_metadata = event.extra_metadata or {}
    source_document = event.source_document

    provenance = EvidenceProvenance(
        derivative_dataset=extra_metadata.get("hf_dataset"),
        source_document_id=str(source_document.id) if source_document is not None else None,
        source_document_title=source_document.title if source_document is not None else None,
        source_document_uri=source_document.uri if source_document is not None else None,
    )

    return EventEvidenceResponse(
        source_event_id=event.source_event_id,
        event_type=event.event_type.value,
        well_id=event.well.well_id,
        wellbore_id=event.wellbore.name if event.wellbore is not None else None,
        occurred_at=event.occurred_at,
        depth_md_m=event.depth_md_m,
        depth_tvd_m=event.depth_tvd_m,
        evidence_type=evidence_type,
        evidence_text=evidence_text,
        source_location=event.source_location,
        source=event.source,
        confidence=event.confidence,
        provenance=provenance,
    )
