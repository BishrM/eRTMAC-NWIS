# eRTMAC-NWIS

Nearby Wells Intelligence System — SIH 2026 (Problem Statement SIH26121), for Oil India Limited (OIL).

Internal hackathon prototype demonstrating:
current well → similar historical wells → historical drilling events → evidence-backed insights → engineer dashboard.

Built on public analogue data (Equinor Volve, Norwegian Offshore Directorate/SODIR) — not OIL's confidential well corpus.
See [CLAUDE.md](./CLAUDE.md) for full project scope, architecture, and engineering rules.

## Repository Structure

- `frontend/` — React + TypeScript + Tailwind UI, map view
- `backend/` — FastAPI service
- `ingestion/` — well metadata, PDF/document ingestion, OCR
- `ml/` — similarity engine, embeddings/RAG
- `data/` — local/demo datasets (not committed)
- `tests/` — test suites
- `docs/` — project documentation

## Development

Start infrastructure (Postgres+PostGIS, Qdrant):

```
docker compose up -d
```

Backend (FastAPI):

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head        # apply DB migrations
uvicorn app.main:app --reload
pytest                      # run tests (requires docker compose up)
```

Endpoints: `GET /health`, `GET /wells`, `GET /wells/{well_id}`,
`GET /wells/{well_id}/similar`, `GET /wells/{well_id}/historical-events`,
`GET /historical-events/{source_event_id}/evidence`.

Frontend (React + TypeScript + Tailwind, Leaflet map) — see `frontend/README.md`:

```
cd frontend
npm install
npm run dev          # http://localhost:5173, requires the backend running
```

## Status

Infra (Postgres+PostGIS, Qdrant), the backend data layer (wells/wellbores/
events/source_documents), the deterministic well-similarity engine,
historical-event retrieval, and source-evidence retrieval are all up and
tested against real public Volve/SODIR data (see `ingestion/README.md`).
A first end-to-end dashboard (well selection → map → comparable wells →
historical events → source evidence) is now live in `frontend/`.
No OCR or RAG/embeddings/LLM yet.
