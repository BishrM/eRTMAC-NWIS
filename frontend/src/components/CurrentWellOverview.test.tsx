import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Well } from "../api/types";
import { CurrentWellOverview } from "./CurrentWellOverview";

const well: Well = {
  id: "uuid-1",
  well_id: "15/9-F-4",
  name: "15/9-F-4",
  operator: "Equinor",
  field: "VOLVE",
  country: "Norway",
  longitude: 1.88,
  latitude: 58.44,
  water_depth_m: 80,
  total_depth_md_m: 3500,
  total_depth_tvd_m: 3000,
  formation: "Hugin",
  spud_date: null,
  completion_date: null,
  source: "sodir",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("CurrentWellOverview", () => {
  it("prompts for a well when idle", () => {
    render(<CurrentWellOverview wellState={{ status: "idle" }} />);
    expect(screen.getByText(/select a well/i)).toBeInTheDocument();
  });

  it("shows an error state, not fake data, when the request fails", () => {
    render(<CurrentWellOverview wellState={{ status: "error", message: "boom" }} />);
    expect(screen.getByText(/well details unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("15/9-F-4")).not.toBeInTheDocument();
  });

  it("renders whichever real well the backend returned -- not a hard-coded example", () => {
    render(<CurrentWellOverview wellState={{ status: "success", data: well }} />);
    expect(screen.getAllByText("15/9-F-4").length).toBeGreaterThan(0);
    expect(screen.getByText("VOLVE")).toBeInTheDocument();
    expect(screen.getByText("Equinor")).toBeInTheDocument();
    expect(screen.getByText("3,500 m / 3,000 m")).toBeInTheDocument();
  });

  it("reports missing fields as unavailable rather than inventing them", () => {
    render(<CurrentWellOverview wellState={{ status: "success", data: { ...well, operator: null, formation: null } }} />);
    expect(screen.getAllByText("unavailable").length).toBeGreaterThanOrEqual(2);
  });
});
