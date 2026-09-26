import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getEventEvidence, getHistoricalEvents, getSimilarWells, getWell, listWells } from "./client";

function mockFetchOnce(status: number, body: unknown, ok = status >= 200 && status < 300) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      statusText: "status",
      json: async () => body,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client", () => {
  it("listWells requests /wells and returns the parsed body", async () => {
    mockFetchOnce(200, { total: 1, limit: 50, offset: 0, items: [{ well_id: "15/9-F-4" }] });
    const result = await listWells();
    expect(result.items[0].well_id).toBe("15/9-F-4");
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/wells");
  });

  it("getWell percent-encodes a well_id containing '/'", async () => {
    mockFetchOnce(200, { well_id: "15/9-F-4" });
    await getWell("15/9-F-4");
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/wells/15%2F9-F-4");
  });

  it("getSimilarWells passes top_k as a query param", async () => {
    mockFetchOnce(200, { reference_well_id: "15/9-F-4", top_k: 3, weights: {}, results: [], disclaimer: "" });
    await getSimilarWells("15/9-F-4", 3);
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("top_k=3");
  });

  it("getHistoricalEvents hits the historical-events route", async () => {
    mockFetchOnce(200, { current_well_id: "x", top_k: 10, filters: {}, comparable_wells: [], historical_events: [], disclaimer: "" });
    await getHistoricalEvents("15/9-F-4");
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/historical-events");
  });

  it("getEventEvidence hits the evidence route for the given source_event_id", async () => {
    mockFetchOnce(200, { source_event_id: "volve_ddr:x:act001" });
    await getEventEvidence("volve_ddr:x:act001");
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/evidence");
  });

  it("throws ApiError with the HTTP status on a non-2xx response", async () => {
    mockFetchOnce(404, { detail: "Well 'nope' not found" });
    await expect(getWell("nope")).rejects.toMatchObject({ status: 404, message: "Well 'nope' not found" });
  });

  it("throws an ApiError with a null status on a network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    const error = await listWells().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBeNull();
  });
});
