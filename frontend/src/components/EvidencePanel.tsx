import type { EventEvidenceResponse } from "../api/types";
import type { AsyncState } from "../hooks/useAsync";
import { StatusMessage } from "./StatusMessage";

interface EvidencePanelProps {
  evidenceState: AsyncState<EventEvidenceResponse>;
}

/** The most important interaction in the demo: turning a documented
 * event into the actual, verbatim source text it came from. Evidence is
 * only ever shown exactly as the backend returned it -- never rewritten,
 * summarized, or paraphrased here. */
export function EvidencePanel({ evidenceState }: EvidencePanelProps) {
  if (evidenceState.status === "idle") {
    return <StatusMessage tone="empty">Select a historical event above to view its source evidence.</StatusMessage>;
  }
  if (evidenceState.status === "loading") {
    return <StatusMessage tone="loading">Retrieving source evidence...</StatusMessage>;
  }
  if (evidenceState.status === "error") {
    return <StatusMessage tone="error">Evidence unavailable: {evidenceState.message}</StatusMessage>;
  }

  const evidence = evidenceState.data;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-amber-400">Historical Evidence</div>

      <div className="mt-1 flex flex-wrap items-baseline gap-x-2 text-sm text-slate-300">
        <span className="font-semibold text-slate-100">{evidence.event_type.replace(/_/g, " ").toUpperCase()}</span>
        <span>{evidence.well_id}</span>
        {evidence.wellbore_id && <span>· {evidence.wellbore_id}</span>}
        {evidence.depth_md_m !== null && <span>· {evidence.depth_md_m.toLocaleString()} m</span>}
        {evidence.occurred_at && <span>· {evidence.occurred_at}</span>}
      </div>

      <blockquote className="mt-3 border-l-2 border-sky-600 pl-3 text-sm italic text-slate-200">
        {evidence.evidence_type === "verbatim_source_text" && evidence.evidence_text
          ? `"${evidence.evidence_text}"`
          : "No verbatim source text captured for this event -- metadata only."}
      </blockquote>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="uppercase text-slate-500">Source document</dt>
          <dd className="text-slate-300">{evidence.provenance.source_document_title ?? "unavailable"}</dd>
        </div>
        <div>
          <dt className="uppercase text-slate-500">Source location</dt>
          <dd className="text-slate-300">{evidence.source_location ?? "unavailable"}</dd>
        </div>
        <div>
          <dt className="uppercase text-slate-500">Evidence type</dt>
          <dd className="text-slate-300">{evidence.evidence_type === "verbatim_source_text" ? "Verbatim source text" : "Metadata only"}</dd>
        </div>
        <div>
          <dt className="uppercase text-slate-500">Source event id</dt>
          <dd className="font-mono text-slate-300">{evidence.source_event_id}</dd>
        </div>
      </dl>

      <p className="mt-3 border-t border-slate-800 pt-3 text-xs text-slate-500">{evidence.disclaimer}</p>
    </div>
  );
}
