import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Well } from "../api/types";
import { WellSelector } from "./WellSelector";

const wells: Well[] = [
  { well_id: "15/9-F-4", name: "15/9-F-4", field: "VOLVE", source: "sodir" } as Well,
  { well_id: "15/9-F-1", name: "15/9-F-1", field: "VOLVE", source: "sodir" } as Well,
  { well_id: "1/2-1", name: "1/2-1", field: "BLANE", source: "sodir" } as Well,
];

describe("WellSelector", () => {
  it("shows a loading state", () => {
    render(<WellSelector wellsState={{ status: "loading" }} selectedWellId={null} onSelect={() => {}} />);
    expect(screen.getByText(/loading well list/i)).toBeInTheDocument();
  });

  it("shows an error state and never falls back to fake wells", () => {
    render(<WellSelector wellsState={{ status: "error", message: "network down" }} selectedWellId={null} onSelect={() => {}} />);
    expect(screen.getByText(/well list unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/network down/i)).toBeInTheDocument();
    expect(screen.queryByText("15/9-F-4")).not.toBeInTheDocument();
  });

  it("lists every real well from a successful response", () => {
    render(<WellSelector wellsState={{ status: "success", data: wells }} selectedWellId={null} onSelect={() => {}} />);
    expect(screen.getByText("15/9-F-4")).toBeInTheDocument();
    expect(screen.getByText("15/9-F-1")).toBeInTheDocument();
    expect(screen.getByText("1/2-1")).toBeInTheDocument();
  });

  it("filters the list by search text", () => {
    render(<WellSelector wellsState={{ status: "success", data: wells }} selectedWellId={null} onSelect={() => {}} />);
    fireEvent.change(screen.getByLabelText(/current well/i), { target: { value: "blane" } });
    expect(screen.getByText("1/2-1")).toBeInTheDocument();
    expect(screen.queryByText("15/9-F-4")).not.toBeInTheDocument();
  });

  it("shows an empty state when the search matches nothing", () => {
    render(<WellSelector wellsState={{ status: "success", data: wells }} selectedWellId={null} onSelect={() => {}} />);
    fireEvent.change(screen.getByLabelText(/current well/i), { target: { value: "zzz-no-match" } });
    expect(screen.getByText(/no wells match/i)).toBeInTheDocument();
  });

  it("calls onSelect with the clicked well's id", () => {
    const onSelect = vi.fn();
    render(<WellSelector wellsState={{ status: "success", data: wells }} selectedWellId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("15/9-F-1"));
    expect(onSelect).toHaveBeenCalledWith("15/9-F-1");
  });
});
