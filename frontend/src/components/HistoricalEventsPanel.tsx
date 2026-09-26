import type { HistoricalEventResult } from "../api/types";
import { StatusMessage } from "./StatusMessage";

interface HistoricalEventsPanelProps {
  events: HistoricalEventResult[];
  selectedComparableWellId: string | null;
  selectedEventId: string | null;
  onSelectEvent: (event: HistoricalEventResult) => void;
}

const EVENT_TYPE_LABEL: Record<string, string> = {
  stuck_pipe: "DOCUMENTED STUCK PIPE",
  lost_circulation: "DOCUMENTED LOST CIRCULATION",
  kick_influx: "DOCUMENTED KICK / INFLUX",
  wellbore_instability: "DOCUMENTED WELLBORE INSTABILITY",
  bha_equipment_issue: "DOCUMENTED BHA / EQUIPMENT ISSUE",
  npt: "DOCUMENTED NON-PRODUCTIVE TIME",
  other: "DOCUMENTED EVENT",
};

function eventLabel(eventType: string): string {
  return EVENT_TYPE_LABEL[eventType] ?? `DOCUMENTED ${eventType.toUpperCase()}`;
}

/** Real events on historically comparable wells -- deliberately labeled
 * as documented history, never as a predicted or current risk. */
export function HistoricalEventsPanel({ events, selectedComparableWellId, selectedEventId, onSelectEvent }: HistoricalEventsPanelProps) {
  const visible = selectedComparableWellId ? events.filter((e) => e.historical_well_id === selectedComparableWellId) : events;

  if (events.length === 0) {
    return <StatusMessage tone="empty">Historical intelligence unavailable: no documented events on any comparable well.</StatusMessage>;
  }
  if (visible.length === 0) {
    return <StatusMessage tone="empty">No documented events on {selectedComparableWellId}.</StatusMessage>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {visible.map((event) => {
        const key = event.source_event_id ?? `${event.historical_well_id}-${event.depth_md_m}-${event.occurred_at}`;
        const isSelected = event.source_event_id !== null && event.source_event_id === selectedEventId;
        return (
          <li key={key}>
            <button
              type="button"
              onClick={() => onSelectEvent(event)}
              disabled={event.source_event_id === null}
              className={`w-full rounded-md border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${
                isSelected ? "border-sky-500 bg-sky-950/30" : "border-slate-800 bg-slate-900 hover:border-slate-700"
              }`}
            >
              <div className="text-xs font-semibold tracking-wide text-amber-400">{eventLabel(event.event_type)}</div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-400">
                <span className="font-medium text-slate-200">{event.historical_well_id}</span>
                {event.historical_wellbore_id && <span>· {event.historical_wellbore_id}</span>}
                {event.depth_md_m !== null && <span>· {event.depth_md_m.toLocaleString()} m MD</span>}
                {event.occurred_at && <span>· {event.occurred_at}</span>}
                <span>· similarity {(event.similarity_score * 100).toFixed(1)}%</span>
              </div>
              {event.description && <p className="mt-1 line-clamp-2 text-xs text-slate-500">{event.description}</p>}
              {event.source_event_id === null && (
                <p className="mt-1 text-xs italic text-slate-600">No stable source reference -- evidence unavailable.</p>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
