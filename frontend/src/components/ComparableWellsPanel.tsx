import { useState } from "react";
import type { HistoricalEventResult, SimilarWellResult } from "../api/types";
import { SimilarityBreakdown } from "./SimilarityBreakdown";
import { StatusMessage } from "./StatusMessage";

function breakdownId(wellId: string): string {
  return `similarity-breakdown-${wellId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

interface ComparableWellsPanelProps {
  comparableWells: SimilarWellResult[];
  historicalEvents: HistoricalEventResult[];
  selectedComparableWellId: string | null;
  onSelectComparableWell: (wellId: string | null) => void;
}

/** A ranked list straight from the backend's similarity output -- the
 * ranking, scores, and factor breakdown are never recomputed here. Event
 * counts are derived from the historical-events response already in
 * hand, never invented, since the similarity API itself doesn't return one. */
export function ComparableWellsPanel({
  comparableWells,
  historicalEvents,
  selectedComparableWellId,
  onSelectComparableWell,
}: ComparableWellsPanelProps) {
  const [expandedWellIds, setExpandedWellIds] = useState<Set<string>>(new Set());

  if (comparableWells.length === 0) {
    return <StatusMessage tone="empty">No historically comparable wells found for this well.</StatusMessage>;
  }

  function toggleBreakdown(wellId: string) {
    setExpandedWellIds((prev) => {
      const next = new Set(prev);
      if (next.has(wellId)) next.delete(wellId);
      else next.add(wellId);
      return next;
    });
  }

  const eventCountByWell = new Map<string, number>();
  for (const e of historicalEvents) {
    eventCountByWell.set(e.historical_well_id, (eventCountByWell.get(e.historical_well_id) ?? 0) + 1);
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-slate-500">
        Historical similarity ranking (decision support, not a validated probability or prediction).
      </p>
      <ul className="flex flex-col gap-2">
        {comparableWells.map((cw) => {
          const isSelected = cw.well_id === selectedComparableWellId;
          const isExpanded = expandedWellIds.has(cw.well_id);
          const eventCount = eventCountByWell.get(cw.well_id) ?? 0;
          const panelId = breakdownId(cw.well_id);
          return (
            <li key={cw.well_id}>
              <div
                className={`rounded-md border px-3 py-2 text-sm transition ${
                  isSelected ? "border-orange-500 bg-orange-950/30" : "border-slate-800 bg-slate-900"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectComparableWell(isSelected ? null : cw.well_id)}
                  className="w-full text-left hover:opacity-90"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-100">{cw.well_id}</span>
                    <span className="font-mono text-sky-300">{(cw.overall_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                    <span>{cw.distance_km.toFixed(1)} km away{cw.field ? ` · ${cw.field}` : ""}</span>
                    <span>{eventCount} documented event{eventCount === 1 ? "" : "s"}</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => toggleBreakdown(cw.well_id)}
                  aria-expanded={isExpanded}
                  aria-controls={panelId}
                  className="mt-2 text-xs font-medium text-sky-400 hover:text-sky-300 hover:underline focus:outline-none focus-visible:underline"
                >
                  {isExpanded ? "Hide similarity breakdown ▲" : "Why similar? ▼"}
                </button>

                {isExpanded && (
                  <div id={panelId}>
                    <SimilarityBreakdown well={cw} />
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
