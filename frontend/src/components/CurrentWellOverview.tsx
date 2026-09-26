import type { Well } from "../api/types";
import type { AsyncState } from "../hooks/useAsync";
import { StatusMessage } from "./StatusMessage";

interface CurrentWellOverviewProps {
  wellState: AsyncState<Well>;
}

function fmt(value: number | null, unit: string): string {
  return value === null ? "unavailable" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}

/** The current-well header/summary this milestone's task description
 * asked for -- works for whatever well the backend returns, never a
 * hard-coded example. */
export function CurrentWellOverview({ wellState }: CurrentWellOverviewProps) {
  if (wellState.status === "idle") {
    return <StatusMessage tone="empty">Select a well above to begin.</StatusMessage>;
  }
  if (wellState.status === "loading") {
    return <StatusMessage tone="loading">Loading well details...</StatusMessage>;
  }
  if (wellState.status === "error") {
    return <StatusMessage tone="error">Well details unavailable: {wellState.message}</StatusMessage>;
  }

  const well = wellState.data;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-100">{well.well_id}</h2>
        <span className="text-xs uppercase tracking-wide text-slate-500">{well.name}</span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase text-slate-500">Field</dt>
          <dd className="text-slate-200">{well.field ?? "unavailable"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Operator</dt>
          <dd className="text-slate-200">{well.operator ?? "unavailable"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Location</dt>
          <dd className="text-slate-200">
            {well.latitude !== null && well.longitude !== null
              ? `${well.latitude.toFixed(4)}, ${well.longitude.toFixed(4)}`
              : "unavailable"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Depth (MD / TVD)</dt>
          <dd className="text-slate-200">
            {fmt(well.total_depth_md_m, "m")} / {fmt(well.total_depth_tvd_m, "m")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Formation</dt>
          <dd className="text-slate-200">{well.formation ?? "unavailable"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">Source</dt>
          <dd className="text-slate-200">{well.source}</dd>
        </div>
      </dl>
    </div>
  );
}
