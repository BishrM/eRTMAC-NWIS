import type { SimilarWellResult } from "../api/types";

interface SimilarityBreakdownProps {
  well: SimilarWellResult;
}

/** Renders exactly the factor breakdown the backend already computed
 * (SimilarWellResult.factors) -- no factor score, weight, label, or
 * detail here is invented or recalculated. A factor the backend marks
 * unavailable is shown as "Not available", never as a 0% bar, since
 * the backend's own contract is that a missing factor is *excluded*
 * from the overall score, not treated as maximally dissimilar. */
export function SimilarityBreakdown({ well }: SimilarityBreakdownProps) {
  return (
    <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Similarity breakdown</p>

      <ul className="mt-2 flex flex-col gap-2">
        {well.factors.map((factor) => (
          <li key={factor.key}>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300">{factor.label}</span>
              <span className={`font-mono ${factor.available ? "text-slate-200" : "text-slate-500 italic"}`}>
                {factor.available && factor.score !== null ? `${(factor.score * 100).toFixed(0)}%` : "Not available"}
              </span>
            </div>
            {factor.available && factor.score !== null ? (
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-800" aria-hidden="true">
                <div className="h-full rounded-full bg-sky-600" style={{ width: `${factor.score * 100}%` }} />
              </div>
            ) : null}
            {factor.detail && <p className="mt-0.5 text-xs text-slate-500">{factor.detail}</p>}
          </li>
        ))}
      </ul>

      <div className="mt-3 flex items-center justify-between border-t border-slate-800 pt-2 text-xs">
        <span className="font-semibold text-slate-300">Overall similarity</span>
        <span className="font-mono font-semibold text-sky-300">{(well.overall_score * 100).toFixed(1)}%</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Historical similarity, not a risk or failure probability. Unavailable factors are excluded from this score,
        never treated as a mismatch.
      </p>
    </div>
  );
}
