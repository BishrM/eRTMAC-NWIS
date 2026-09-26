/**
 * Small typed API client for the eRTMAC-NWIS backend. All backend calls
 * go through here -- components never call fetch() directly, and never
 * recompute a similarity score, event classification, or evidence text
 * themselves; this layer only shapes/transports what the backend already
 * returns.
 */
import type {
  EventEvidenceResponse,
  HistoricalEventIntelligenceResponse,
  SimilarWellsResponse,
  Well,
  WellListResponse,
} from "./types";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Distinguishes a reachable backend that returned an error status (e.g.
 * 404/422/500) from a request that never reached the backend at all
 * (offline, CORS, DNS, connection refused) -- callers show a different
 * message for each, and neither ever falls back to fake data. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(API_BASE_URL + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  let response: Response;
  try {
    response = await fetch(url.toString());
  } catch {
    throw new ApiError("Could not reach the NWIS backend. Is it running?", null);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // response body wasn't JSON -- keep statusText
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

function encodeWellId(wellId: string): string {
  // SODIR/NPD well ids contain '/' (e.g. "15/9-F-4") -- must be
  // percent-encoded as a single path segment (matches the backend's
  // ":path" route converter, see backend/app/routes/wells.py).
  return encodeURIComponent(wellId);
}

export function listWells(params?: { limit?: number; offset?: number }): Promise<WellListResponse> {
  return request<WellListResponse>("/wells", params);
}

export function getWell(wellId: string): Promise<Well> {
  return request<Well>(`/wells/${encodeWellId(wellId)}`);
}

export function getSimilarWells(wellId: string, topK?: number): Promise<SimilarWellsResponse> {
  return request<SimilarWellsResponse>(`/wells/${encodeWellId(wellId)}/similar`, { top_k: topK });
}

export function getHistoricalEvents(
  wellId: string,
  params?: { top_k?: number; event_type?: string; min_similarity?: number },
): Promise<HistoricalEventIntelligenceResponse> {
  return request<HistoricalEventIntelligenceResponse>(`/wells/${encodeWellId(wellId)}/historical-events`, params);
}

export function getEventEvidence(sourceEventId: string): Promise<EventEvidenceResponse> {
  return request<EventEvidenceResponse>(`/historical-events/${encodeURIComponent(sourceEventId)}/evidence`);
}
