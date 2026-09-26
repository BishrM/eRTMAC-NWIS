import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HistoricalEventResult } from "../api/types";
import { HistoricalEventsPanel } from "./HistoricalEventsPanel";

const stuckPipeEvent: HistoricalEventResult = {
  historical_well_id: "15/9-F-1",
  historical_well_name: "15/9-F-1",
  historical_wellbore_id: "15/9-F-1",
  similarity_score: 0.873,
  distance_km: 7.2,
  event_type: "stuck_pipe",
  severity: null,
  depth_md_m: 2601,
  depth_tvd_m: null,
  occurred_at: "2013-08-22",
  description: 'Stuck with flex stab in 13 3/8" shoe.',
  source_document_title: "Volve DDR 15_9_F_1_2013_08_23",
  source_location: "15_9_F_1_2013_08_23 activity ...",
  source: "volve_ddr_hf_derivative",
  source_event_id: "volve_ddr:15_9_F_1_2013_08_23:act023",
  confidence: 1.0,
};

const lostCirculationEvent: HistoricalEventResult = {
  ...stuckPipeEvent,
  historical_well_id: "15/9-F-14",
  event_type: "lost_circulation",
  source_event_id: "volve_ddr:15_9_F_14_x:act001",
};

const noEvidenceEvent: HistoricalEventResult = {
  ...stuckPipeEvent,
  historical_well_id: "15/9-F-5",
  source_event_id: null,
};

describe("HistoricalEventsPanel", () => {
  it("shows an empty state instead of inventing events", () => {
    render(<HistoricalEventsPanel events={[]} selectedComparableWellId={null} selectedEventId={null} onSelectEvent={() => {}} />);
    expect(screen.getByText(/historical intelligence unavailable/i)).toBeInTheDocument();
  });

  it("labels documented history, never as a risk level", () => {
    render(
      <HistoricalEventsPanel
        events={[stuckPipeEvent, lostCirculationEvent]}
        selectedComparableWellId={null}
        selectedEventId={null}
        onSelectEvent={() => {}}
      />,
    );
    expect(screen.getByText("DOCUMENTED STUCK PIPE")).toBeInTheDocument();
    expect(screen.getByText("DOCUMENTED LOST CIRCULATION")).toBeInTheDocument();
    expect(screen.queryByText(/high risk/i)).not.toBeInTheDocument();
  });

  it("filters events down to the selected comparable well", () => {
    render(
      <HistoricalEventsPanel
        events={[stuckPipeEvent, lostCirculationEvent]}
        selectedComparableWellId="15/9-F-1"
        selectedEventId={null}
        onSelectEvent={() => {}}
      />,
    );
    expect(screen.getByText("DOCUMENTED STUCK PIPE")).toBeInTheDocument();
    expect(screen.queryByText("DOCUMENTED LOST CIRCULATION")).not.toBeInTheDocument();
  });

  it("calls onSelectEvent with the clicked event", () => {
    const onSelectEvent = vi.fn();
    render(
      <HistoricalEventsPanel
        events={[stuckPipeEvent]}
        selectedComparableWellId={null}
        selectedEventId={null}
        onSelectEvent={onSelectEvent}
      />,
    );
    fireEvent.click(screen.getByText("DOCUMENTED STUCK PIPE"));
    expect(onSelectEvent).toHaveBeenCalledWith(stuckPipeEvent);
  });

  it("disables selection for an event with no stable source_event_id, rather than fetching bad evidence", () => {
    render(
      <HistoricalEventsPanel
        events={[noEvidenceEvent]}
        selectedComparableWellId={null}
        selectedEventId={null}
        onSelectEvent={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /documented stuck pipe/i })).toBeDisabled();
    expect(screen.getByText(/evidence unavailable/i)).toBeInTheDocument();
  });
});
