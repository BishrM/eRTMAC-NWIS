import { useMemo } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { SimilarWellResult, Well } from "../api/types";
import { StatusMessage } from "./StatusMessage";

interface WellMapProps {
  currentWell: Well;
  comparableWells: SimilarWellResult[];
  /** every known well's coordinates, from the same well-list fetch that
   * feeds the selector -- reused here rather than issuing a new API
   * call per comparable well. */
  wellsById: Map<string, Well>;
  selectedComparableWellId: string | null;
  onSelectComparableWell: (wellId: string) => void;
}

/** Plots the current well and its comparable wells using real
 * coordinates only -- never fabricated. Wells with no surface location
 * on file are reported, not silently placed at (0, 0). */
export function WellMap({
  currentWell,
  comparableWells,
  wellsById,
  selectedComparableWellId,
  onSelectComparableWell,
}: WellMapProps) {
  const points = useMemo(() => {
    const list: { wellId: string; label: string; lat: number; lon: number; kind: "current" | "comparable"; score?: number }[] = [];
    if (currentWell.latitude !== null && currentWell.longitude !== null) {
      list.push({ wellId: currentWell.well_id, label: currentWell.well_id, lat: currentWell.latitude, lon: currentWell.longitude, kind: "current" });
    }
    for (const cw of comparableWells) {
      const well = wellsById.get(cw.well_id);
      if (well?.latitude != null && well?.longitude != null) {
        list.push({ wellId: cw.well_id, label: cw.well_id, lat: well.latitude, lon: well.longitude, kind: "comparable", score: cw.overall_score });
      }
    }
    return list;
  }, [currentWell, comparableWells, wellsById]);

  if (currentWell.latitude === null || currentWell.longitude === null) {
    return <StatusMessage tone="empty">No surface location on file for {currentWell.well_id} -- map unavailable.</StatusMessage>;
  }

  const missingCoords = comparableWells.length - (points.length - 1);

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="h-80 overflow-hidden rounded-lg border border-slate-800 sm:h-96">
        <MapContainer center={[currentWell.latitude, currentWell.longitude]} zoom={11} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {points.map((p) => (
            <CircleMarker
              key={p.wellId}
              center={[p.lat, p.lon]}
              radius={p.kind === "current" ? 9 : p.wellId === selectedComparableWellId ? 8 : 6}
              pathOptions={{
                color: p.kind === "current" ? "#38bdf8" : p.wellId === selectedComparableWellId ? "#f97316" : "#94a3b8",
                fillColor: p.kind === "current" ? "#38bdf8" : p.wellId === selectedComparableWellId ? "#f97316" : "#64748b",
                fillOpacity: 0.85,
              }}
              eventHandlers={p.kind === "comparable" ? { click: () => onSelectComparableWell(p.wellId) } : undefined}
            >
              <Popup>
                <span className="font-semibold">{p.label}</span>
                {p.kind === "current" ? " (current well)" : ` — similarity ${(p.score! * 100).toFixed(1)}%`}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      {missingCoords > 0 && (
        <p className="text-xs text-slate-500">
          {missingCoords} comparable well{missingCoords === 1 ? "" : "s"} not shown on the map (no surface location on file).
        </p>
      )}
    </div>
  );
}
