import { useMemo, useState } from "react";
import { getEventEvidence, getHistoricalEvents, getWell, listWells } from "./api/client";
import type { HistoricalEventResult, Well } from "./api/types";
import { ComparableWellsPanel } from "./components/ComparableWellsPanel";
import { CurrentWellOverview } from "./components/CurrentWellOverview";
import { EvidencePanel } from "./components/EvidencePanel";
import { HistoricalEventsPanel } from "./components/HistoricalEventsPanel";
import { StatusMessage } from "./components/StatusMessage";
import { WellMap } from "./components/WellMap";
import { WellSelector } from "./components/WellSelector";
import { useAsync } from "./hooks/useAsync";

export default function App() {
  const [selectedWellId, setSelectedWellId] = useState<string | null>(null);
  const [selectedComparableWellId, setSelectedComparableWellId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<HistoricalEventResult | null>(null);

  // Fetched once; also doubles as the coordinate lookup for the map, so
  // comparable wells never need their own extra API round-trip.
  const wellListState = useAsync(() => listWells({ limit: 500 }).then((r) => r.items), []);
  const wellsById = useMemo(() => {
    const map = new Map<string, Well>();
    if (wellListState.status === "success") {
      for (const w of wellListState.data) map.set(w.well_id, w);
    }
    return map;
  }, [wellListState]);

  const currentWellState = useAsync(selectedWellId ? () => getWell(selectedWellId) : null, [selectedWellId]);

  // One call returns both the comparable-wells ranking and the
  // historical events on them -- the frontend never calls /similar
  // separately, avoiding a redundant second request for the same ranking.
  const historicalState = useAsync(
    selectedWellId ? () => getHistoricalEvents(selectedWellId, { top_k: 10 }) : null,
    [selectedWellId],
  );

  const evidenceState = useAsync(
    selectedEvent?.source_event_id ? () => getEventEvidence(selectedEvent.source_event_id!) : null,
    [selectedEvent?.source_event_id],
  );

  function handleSelectWell(wellId: string) {
    setSelectedWellId(wellId);
    setSelectedComparableWellId(null);
    setSelectedEvent(null);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header className="mb-6 border-b border-slate-800 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">NWIS</h1>
        <p className="text-sm text-slate-400">Nearby Wells Intelligence System — decision support, not autonomous drilling control.</p>
      </header>

      {wellListState.status === "error" && (
        <div className="mb-6">
          <StatusMessage tone="error">
            NWIS backend unavailable ({wellListState.message}). Confirm the API is running and VITE_API_BASE_URL is correct.
          </StatusMessage>
        </div>
      )}

      <section className="mb-6">
        <WellSelector wellsState={wellListState} selectedWellId={selectedWellId} onSelect={handleSelectWell} />
      </section>

      <section className="mb-6">
        <CurrentWellOverview wellState={currentWellState} />
      </section>

      {selectedWellId && currentWellState.status === "success" && (
        <>
          <section className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Map / Spatial Context</h2>
              {historicalState.status === "loading" && <StatusMessage tone="loading">Loading comparable wells...</StatusMessage>}
              {historicalState.status === "error" && (
                <StatusMessage tone="error">Historical intelligence unavailable: {historicalState.message}</StatusMessage>
              )}
              {historicalState.status === "success" && (
                <WellMap
                  currentWell={currentWellState.data}
                  comparableWells={historicalState.data.comparable_wells}
                  wellsById={wellsById}
                  selectedComparableWellId={selectedComparableWellId}
                  onSelectComparableWell={(id) => setSelectedComparableWellId(id)}
                />
              )}
            </div>
            <div>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Comparable Historical Wells</h2>
              {historicalState.status === "loading" && <StatusMessage tone="loading">Loading...</StatusMessage>}
              {historicalState.status === "error" && <StatusMessage tone="error">Unavailable: {historicalState.message}</StatusMessage>}
              {historicalState.status === "success" && (
                <ComparableWellsPanel
                  comparableWells={historicalState.data.comparable_wells}
                  historicalEvents={historicalState.data.historical_events}
                  selectedComparableWellId={selectedComparableWellId}
                  onSelectComparableWell={setSelectedComparableWellId}
                />
              )}
            </div>
          </section>

          <section className="mb-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Historical Events</h2>
            {historicalState.status === "loading" && <StatusMessage tone="loading">Loading historical events...</StatusMessage>}
            {historicalState.status === "error" && (
              <StatusMessage tone="error">Historical intelligence unavailable: {historicalState.message}</StatusMessage>
            )}
            {historicalState.status === "success" && (
              <HistoricalEventsPanel
                events={historicalState.data.historical_events}
                selectedComparableWellId={selectedComparableWellId}
                selectedEventId={selectedEvent?.source_event_id ?? null}
                onSelectEvent={setSelectedEvent}
              />
            )}
          </section>

          <section>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Source Evidence</h2>
            <EvidencePanel evidenceState={evidenceState} />
          </section>
        </>
      )}
    </div>
  );
}
