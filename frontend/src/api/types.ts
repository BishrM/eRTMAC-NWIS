/**
 * TypeScript types mirroring the backend's actual Pydantic response
 * schemas exactly (backend/app/schemas/*.py). No field here is invented:
 * every field maps 1:1 to a real API response field. The frontend
 * displays backend intelligence -- it never recomputes similarity,
 * event extraction, or evidence text itself.
 */

export interface Well {
  id: string;
  well_id: string;
  name: string;
  operator: string | null;
  field: string | null;
  country: string | null;
  longitude: number | null;
  latitude: number | null;
  water_depth_m: number | null;
  total_depth_md_m: number | null;
  total_depth_tvd_m: number | null;
  formation: string | null;
  spud_date: string | null;
  completion_date: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface WellListResponse {
  total: number;
  limit: number;
  offset: number;
  items: Well[];
}

export interface FactorScore {
  key: string;
  label: string;
  weight: number;
  score: number | null;
  available: boolean;
  detail: string;
}

export interface SimilarWellResult {
  well_id: string;
  name: string;
  field: string | null;
  distance_km: number;
  overall_score: number;
  factors: FactorScore[];
}

export interface SimilarWellsResponse {
  reference_well_id: string;
  top_k: number;
  weights: Record<string, number>;
  results: SimilarWellResult[];
  disclaimer: string;
}

export interface HistoricalEventResult {
  historical_well_id: string;
  historical_well_name: string;
  historical_wellbore_id: string | null;
  similarity_score: number;
  distance_km: number;
  event_type: string;
  severity: string | null;
  depth_md_m: number | null;
  depth_tvd_m: number | null;
  occurred_at: string | null;
  description: string | null;
  source_document_title: string | null;
  source_location: string | null;
  source: string;
  source_event_id: string | null;
  confidence: number | null;
}

export interface HistoricalEventFilters {
  event_type: string | null;
  min_similarity: number | null;
  depth_md_min: number | null;
  depth_md_max: number | null;
}

export interface HistoricalEventIntelligenceResponse {
  current_well_id: string;
  top_k: number;
  filters: HistoricalEventFilters;
  comparable_wells: SimilarWellResult[];
  historical_events: HistoricalEventResult[];
  disclaimer: string;
}

export interface EvidenceProvenance {
  original_corpus: string;
  derivative_dataset: string | null;
  derivative_is_original_source: boolean;
  source_document_id: string | null;
  source_document_title: string | null;
  source_document_uri: string | null;
}

export interface EventEvidenceResponse {
  source_event_id: string;
  event_type: string;
  well_id: string;
  wellbore_id: string | null;
  occurred_at: string | null;
  depth_md_m: number | null;
  depth_tvd_m: number | null;
  evidence_type: "verbatim_source_text" | "metadata_only";
  evidence_text: string | null;
  source_location: string | null;
  source: string;
  confidence: number | null;
  provenance: EvidenceProvenance;
  disclaimer: string;
}
