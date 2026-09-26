# NWIS frontend (Milestone 10)

React + TypeScript + Tailwind (Vite), per `CLAUDE.md`'s architecture. Map:
Leaflet + `react-leaflet` (neither was previously installed; Leaflet was
chosen over MapLibre GL as the simpler option for a small number of
point markers on public OSM tiles — no vector style JSON, no API key).

The dashboard displays the backend's existing deterministic intelligence
(well similarity, historical events, source evidence) end to end. It
does not recompute similarity, event extraction, or evidence text itself
— see `src/api/client.ts`, the only place the backend is called from.

## Run it

```
cd frontend
npm install
cp .env.example .env      # VITE_API_BASE_URL, defaults to http://localhost:8000
npm run dev                # http://localhost:5173
```

Requires the backend running separately (`cd backend && uvicorn
app.main:app --reload`, plus `docker compose up -d` for Postgres). The
backend's `CORSMiddleware` (`backend/app/main.py`) explicitly allows
`http://localhost:5173` / `http://127.0.0.1:5173` — the Vite dev server's
default origins — for local development.

```
npm run build   # type-checks + production bundle
npm run test    # vitest + React Testing Library
```

## Demo scenario

Select `15/9-F-4` → comparable well `15/9-F-1` (similarity 87.3%) → click
"Why similar?" to see its per-factor breakdown (geography/MD/TVD/
trajectory, straight from `comparable_wells[].factors` — never
recalculated in the frontend) → `DOCUMENTED STUCK PIPE` at 2,601 m,
2013-08-22 → click it → real verbatim evidence text, source document,
and source location appear.
This is a real, already-ingested scenario (Milestones 8–9) used only as
an acceptance check — it is never hard-coded into the app; any well the
backend returns works the same way.

## Known limitations

- Only wells/wellbores with a real DDR-sourced event have anything to
  show in the Historical Events / Source Evidence panels (204 real
  events across 8 real wellbores — see `ingestion/README.md`).
- No page-level provenance exists in the source DDRs, so source location
  is a document + activity-timestamp reference, not a page number.
- No RAG/embeddings/LLM/predictive risk scoring — by design, this
  milestone only makes the existing deterministic retrieval visible.
- Desktop-first layout; usable but not specifically optimized on mobile.
