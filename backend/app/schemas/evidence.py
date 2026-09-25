from datetime import date

from pydantic import BaseModel

EVIDENCE_DISCLAIMER = (
    "Evidence text is copied verbatim from the audited public derivative described in "
    "ingestion/VOLVE_DDR_AUDIT.md at ingestion time — it is not the original Equinor "
    "WITSML file itself, and this layer never summarizes, paraphrases, or reconstructs "
    "missing source text. A future AI layer may summarize this evidence; this layer "
    "only ever returns exactly what was recorded."
)


class EvidenceProvenance(BaseModel):
    """The full disclosure chain for one piece of evidence, kept explicit
    so a caller never mistakes the accessible derivative for Equinor's
    original WITSML disclosure (see CLAUDE.md's provenance rule)."""

    original_corpus: str = "Equinor Volve Daily Drilling Reports (original format: WITSML DrillReport)"
    derivative_dataset: str | None  # e.g. "bengsoon/volve_daily_drilling_report" (HF dataset id), if recorded
    derivative_is_original_source: bool = False
    source_document_id: str | None
    source_document_title: str | None
    source_document_uri: str | None  # an identifier (e.g. "hf://...#docName=..."), never a fetchable/filesystem path


class EventEvidenceResponse(BaseModel):
    """Source evidence for exactly one historical Event, located by its
    stable `source_event_id` (never by matching description text) — see
    backend/app/services/evidence_service.py."""

    source_event_id: str
    event_type: str
    well_id: str
    wellbore_id: str | None  # Wellbore.name, if the event is tied to a specific wellbore
    occurred_at: date | None
    depth_md_m: float | None
    depth_tvd_m: float | None

    # "verbatim_source_text" when the source derivative's own activity
    # comments were captured at ingestion time (evidence_text is
    # populated with exactly that text); "metadata_only" when no such
    # text exists for this event — never fabricated to fill the gap.
    evidence_type: str
    evidence_text: str | None
    source_location: str | None

    source: str
    confidence: float | None
    provenance: EvidenceProvenance

    disclaimer: str = EVIDENCE_DISCLAIMER
