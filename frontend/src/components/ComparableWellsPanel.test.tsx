import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HistoricalEventResult, SimilarWellResult } from "../api/types";
import { ComparableWellsPanel } from "./ComparableWellsPanel";

const comparableWells: SimilarWellResult[] = [
  {
    well_id: "15/9-F-1",
    name: "15/9-F-1",
    field: "VOLVE",
    distance_km: 7.2,
    overall_score: 0.873,
    factors: [
      { key: "geographic_proximity", label: "Geographic proximity", weight: 0.25, score: 0.96, available: true, detail: "7.20 km apart" },
      { key: "total_depth_md", label: "Total depth (MD)", weight: 0.35, score: 0.91, available: true, detail: "MD difference 300 m" },
      { key: "tvd", label: "True vertical depth", weight: 0.25, score: 0.97, available: true, detail: "TVD difference 90 m" },
      { key: "trajectory_deviation", label: "Trajectory deviation", weight: 0.15, score: null, available: false, detail: "insufficient real trajectory data for one or both wells" },
    ],
  },
  { well_id: "15/9-F-14", name: "15/9-F-14", field: "VOLVE", distance_km: 0.5, overall_score: 0.9463, factors: [] },
];

const events: HistoricalEventResult[] = [
  {
    historical_well_id: "15/9-F-1",
    historical_well_name: "15/9-F-1",
    historical_wellbore_id: null,
    similarity_score: 0.873,
    distance_km: 7.2,
    event_type: "stuck_pipe",
    severity: null,
    depth_md_m: 2601,
    depth_tvd_m: null,
    occurred_at: "2013-08-22",
    description: null,
    source_document_title: null,
    source_location: null,
    source: "volve_ddr_hf_derivative",
    source_event_id: "volve_ddr:15_9_F_1_2013_08_23:act023",
    confidence: 1.0,
  },
];

describe("ComparableWellsPanel", () => {
  it("shows an empty state instead of inventing comparable wells", () => {
    render(
      <ComparableWellsPanel comparableWells={[]} historicalEvents={[]} selectedComparableWellId={null} onSelectComparableWell={() => {}} />,
    );
    expect(screen.getByText(/no historically comparable wells/i)).toBeInTheDocument();
  });

  it("renders the backend's own ranking and score, unmodified", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    expect(screen.getByText("87.3%")).toBeInTheDocument();
    expect(screen.getByText("94.6%")).toBeInTheDocument();
  });

  it("derives the event count from the historical events already returned, not a separate invented field", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    expect(screen.getByText("1 documented event")).toBeInTheDocument();
    expect(screen.getByText("0 documented events")).toBeInTheDocument();
  });

  it("toggles the selected comparable well on click", () => {
    const onSelect = vi.fn();
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("15/9-F-1"));
    expect(onSelect).toHaveBeenCalledWith("15/9-F-1");
  });

  it("never labels the score as a risk or failure probability", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    expect(screen.queryByText(/risk probability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/failure probability/i)).not.toBeInTheDocument();
  });

  // --- Milestone 11: "Why similar?" breakdown -------------------------------

  it("shows a 'Why similar?' control for each comparable well, collapsed by default", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    const controls = screen.getAllByRole("button", { name: /why similar\?/i });
    expect(controls).toHaveLength(2);
    expect(screen.queryByText("Similarity breakdown")).not.toBeInTheDocument();
  });

  it("reveals the factor breakdown from the backend's own data on click, without altering the ranking", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );

    const toggle = screen.getAllByRole("button", { name: /why similar\?/i })[0];
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    expect(screen.getByText("Similarity breakdown")).toBeInTheDocument();
    expect(screen.getByText("Geographic proximity")).toBeInTheDocument();
    expect(screen.getByText("96%")).toBeInTheDocument();
    expect(screen.getByText("Total depth (MD)")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByText("True vertical depth")).toBeInTheDocument();
    expect(screen.getByText("97%")).toBeInTheDocument();
    // The row's overall score (87.3%) is unaffected by expanding the breakdown.
    expect(screen.getAllByText("87.3%").length).toBeGreaterThanOrEqual(1);
  });

  it("shows an unavailable factor as 'Not available', never as 0%", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /why similar\?/i })[0]);

    expect(screen.getByText("Trajectory deviation")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getByText("insufficient real trajectory data for one or both wells")).toBeInTheDocument();
  });

  it("lets each comparable well's breakdown expand independently", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /why similar\?/i })[0]);

    expect(screen.getByText("Geographic proximity")).toBeInTheDocument(); // F-1's breakdown open
    expect(screen.getAllByText("Similarity breakdown")).toHaveLength(1); // F-14's is still collapsed

    // Only F-14's toggle still reads "Why similar?" -- F-1's now reads "Hide...".
    fireEvent.click(screen.getAllByRole("button", { name: /why similar\?/i })[0]);
    expect(screen.getAllByText("Similarity breakdown")).toHaveLength(2);
  });

  it("collapses the breakdown again when toggled a second time", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    const toggle = screen.getAllByRole("button", { name: /why similar\?/i })[0];
    fireEvent.click(toggle);
    expect(screen.getByText("Similarity breakdown")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /hide similarity breakdown/i }));
    expect(screen.queryByText("Similarity breakdown")).not.toBeInTheDocument();
  });

  it("never labels a similarity factor as risk, failure, or likelihood", () => {
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={() => {}}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /why similar\?/i })[0]);
    // The panel's own disclaimer deliberately *disclaims* risk/failure framing
    // ("not a risk or failure probability") -- check for the mislabeling
    // itself, not that reassurance text.
    expect(screen.queryByText(/predicted failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/likelihood of failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hazard probability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/safety score/i)).not.toBeInTheDocument();
  });

  it("does not break the existing comparable-well selection click when the breakdown is expanded", () => {
    const onSelect = vi.fn();
    render(
      <ComparableWellsPanel
        comparableWells={comparableWells}
        historicalEvents={events}
        selectedComparableWellId={null}
        onSelectComparableWell={onSelect}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /why similar\?/i })[0]);
    fireEvent.click(screen.getByText("15/9-F-1"));
    expect(onSelect).toHaveBeenCalledWith("15/9-F-1");
  });
});
