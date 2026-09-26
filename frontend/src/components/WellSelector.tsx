import { useMemo, useState } from "react";
import type { Well } from "../api/types";
import type { AsyncState } from "../hooks/useAsync";
import { StatusMessage } from "./StatusMessage";

interface WellSelectorProps {
  wellsState: AsyncState<Well[]>;
  selectedWellId: string | null;
  onSelect: (wellId: string) => void;
}

/** A searchable well list -- the entry point for the whole dashboard.
 * The selected well becomes the "current well" everything else is
 * built around. Only ever shows wells the backend actually returned. */
export function WellSelector({ wellsState, selectedWellId, onSelect }: WellSelectorProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (wellsState.status !== "success") return [];
    const q = query.trim().toLowerCase();
    if (!q) return wellsState.data;
    return wellsState.data.filter(
      (w) => w.well_id.toLowerCase().includes(q) || w.name.toLowerCase().includes(q) || (w.field ?? "").toLowerCase().includes(q),
    );
  }, [wellsState, query]);

  return (
    <div className="w-full max-w-sm">
      <label htmlFor="well-search" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-400">
        Current Well
      </label>
      <input
        id="well-search"
        type="text"
        placeholder="Search wells by id, name, or field..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
      />

      {wellsState.status === "loading" && (
        <div className="mt-2">
          <StatusMessage tone="loading">Loading well list...</StatusMessage>
        </div>
      )}
      {wellsState.status === "error" && (
        <div className="mt-2">
          <StatusMessage tone="error">Well list unavailable: {wellsState.message}</StatusMessage>
        </div>
      )}
      {wellsState.status === "success" && filtered.length === 0 && (
        <div className="mt-2">
          <StatusMessage tone="empty">No wells match "{query}".</StatusMessage>
        </div>
      )}

      {wellsState.status === "success" && filtered.length > 0 && (
        <ul className="mt-2 max-h-64 overflow-y-auto rounded-md border border-slate-800">
          {filtered.map((w) => (
            <li key={w.well_id}>
              <button
                type="button"
                onClick={() => onSelect(w.well_id)}
                className={`flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-slate-800 ${
                  w.well_id === selectedWellId ? "bg-sky-900/40" : "bg-slate-900"
                }`}
              >
                <span className="font-medium text-slate-100">{w.well_id}</span>
                <span className="text-xs text-slate-400">{[w.field, w.source].filter(Boolean).join(" · ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
