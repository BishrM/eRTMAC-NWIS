import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  EventEvidenceResponse,
  HistoricalEventIntelligenceResponse,
  Well,
  WellListResponse,
} from "./api/types";

// Leaflet needs real DOM layout (ResizeObserver, getBoundingClientRect)
// that jsdom doesn't provide -- the map's own data wiring is exercised
// through this lightweight stand-in instead of real Leaflet internals.
vi.mock("./components/WellMap", () => ({
  WellMap: ({ currentWell, comparableWells }: { currentWell: Well; comparableWells: { well_id: string }[] }) => (
    <div data-testid="well-map">
      current:{currentWell.well_id} comparable:{comparableWells.map((w) => w.well_id).join(",")}
    </div>
  ),
}));

const { listWells, getWell, getHistoricalEvents, getEventEvidence } = vi.hoisted(() => ({
  listWells: vi.fn(),
  getWell: vi.fn(),
  getHistoricalEvents: vi.fn(),
  getEventEvidence: vi.fn(),
}));

vi.mock("./api/client", () => ({ listWells, getWell, getHistoricalEvents, getEventEvidence }));

import App from "./App";

// Deliberately NOT "15/9-F-4"/"15/9-F-1" -- proves the dashboard isn't
// secretly hard-coded around the known real demo scenario.
const CURRENT_WELL: Well = {
  id: "uuid-a",
  well_id: "TEST-WELL-A",
  name: "TEST-WELL-A",
  operator: "Demo Operator",
  field: "DEMO-FIELD",
  country: "Norway",
  longitude: 1.9,
  latitude: 58.5,
  water_depth_m: 90,
  total_depth_md_m: 4000,
  total_depth_tvd_m: 3500,
  formation: "Hugin",
  spud_date: null,
  completion_date: null,
  source: "demo",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const COMPARABLE_WELL: Well = { ...CURRENT_WELL, id: "uuid-b", well_id: "TEST-WELL-B", name: "TEST-WELL-B" };

const wellList: WellListResponse = { total: 2, limit: 500, offset: 0, items: [CURRENT_WELL, COMPARABLE_WELL] };

const historical: HistoricalEventIntelligenceResponse = {
  current_well_id: "TEST-WELL-A",
  top_k: 10,
  filters: { event_type: null, min_similarity: null, depth_md_min: null, depth_md_max: null },
  comparable_wells: [
    { well_id: "TEST-WELL-B", name: "TEST-WELL-B", field: "DEMO-FIELD", distance_km: 5.0, overall_score: 0.81, factors: [] },
  ],
  historical_events: [
    {
      historical_well_id: "TEST-WELL-B",
      historical_well_name: "TEST-WELL-B",
      historical_wellbore_id: "TEST-WELL-B",
      similarity_score: 0.81,
      distance_km: 5.0,
      event_type: "stuck_pipe",
      severity: null,
      depth_md_m: 1234,
      depth_tvd_m: null,
      occurred_at: "2010-05-01",
      description: "Demo documented event text.",
      source_document_title: "Demo source document",
      source_location: "demo-doc activity 1",
      source: "demo",
      source_event_id: "demo:test-well-b:act001",
      confidence: 1.0,
    },
  ],
  disclaimer: "test disclaimer",
};

const evidence: EventEvidenceResponse = {
  source_event_id: "demo:test-well-b:act001",
  event_type: "stuck_pipe",
  well_id: "TEST-WELL-B",
  wellbore_id: "TEST-WELL-B",
  occurred_at: "2010-05-01",
  depth_md_m: 1234,
  depth_tvd_m: null,
  evidence_type: "verbatim_source_text",
  evidence_text: "Exact demo verbatim source text.",
  source_location: "demo-doc activity 1",
  source: "demo",
  confidence: 1.0,
  provenance: {
    original_corpus: "Equinor Volve Daily Drilling Reports (original format: WITSML DrillReport)",
    derivative_dataset: null,
    derivative_is_original_source: false,
    source_document_id: "doc-b",
    source_document_title: "Demo source document",
    source_document_uri: "test://demo",
  },
  disclaimer: "test disclaimer",
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("App", () => {
  it("shows a backend-unavailable banner and never falls back to fake wells", async () => {
    listWells.mockRejectedValue(new Error("network down"));

    render(<App />);

    await waitFor(() => expect(screen.getByText(/nwis backend unavailable/i)).toBeInTheDocument());
    expect(screen.queryByText("TEST-WELL-A")).not.toBeInTheDocument();
  });

  it("runs the full demo flow end to end for a well that is not the known F-4/F-1 scenario", async () => {
    listWells.mockResolvedValue(wellList);
    getWell.mockResolvedValue(CURRENT_WELL);
    getHistoricalEvents.mockResolvedValue(historical);
    getEventEvidence.mockResolvedValue(evidence);

    render(<App />);

    // 1. well list loads
    await waitFor(() => expect(screen.getByText("TEST-WELL-A")).toBeInTheDocument());

    // 2. select the current well
    fireEvent.click(screen.getByText("TEST-WELL-A"));
    expect(getWell).toHaveBeenCalledWith("TEST-WELL-A");

    // 3. current well overview appears
    await waitFor(() => expect(screen.getByText("Demo Operator")).toBeInTheDocument());

    // 4. comparable wells + map appear, driven by the real backend response
    await waitFor(() => expect(screen.getByText("81.0%")).toBeInTheDocument());
    expect(screen.getByTestId("well-map")).toHaveTextContent("current:TEST-WELL-A comparable:TEST-WELL-B");

    // 5. historical event appears
    expect(screen.getByText("DOCUMENTED STUCK PIPE")).toBeInTheDocument();

    // 6. selecting the event fetches evidence on demand (not eagerly)
    expect(getEventEvidence).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("DOCUMENTED STUCK PIPE"));
    await waitFor(() => expect(getEventEvidence).toHaveBeenCalledWith("demo:test-well-b:act001"));

    // 7. the exact verbatim evidence text appears
    await waitFor(() => expect(screen.getByText('"Exact demo verbatim source text."')).toBeInTheDocument());
    expect(screen.getByText("Demo source document")).toBeInTheDocument();
  });

  it("shows a clean empty state when a well has no comparable wells or events", async () => {
    listWells.mockResolvedValue(wellList);
    getWell.mockResolvedValue(CURRENT_WELL);
    getHistoricalEvents.mockResolvedValue({ ...historical, comparable_wells: [], historical_events: [] });

    render(<App />);
    await waitFor(() => expect(screen.getByText("TEST-WELL-A")).toBeInTheDocument());
    fireEvent.click(screen.getByText("TEST-WELL-A"));

    await waitFor(() => expect(screen.getByText(/no historically comparable wells/i)).toBeInTheDocument());
    expect(screen.getByText(/historical intelligence unavailable/i)).toBeInTheDocument();
  });
});
