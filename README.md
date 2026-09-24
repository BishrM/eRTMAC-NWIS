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

Endpoints: `GET /health`, `GET /wells`, `GET /wells/{well_id}`.

## Status

Infra (Postgres+PostGIS, Qdrant) and the initial backend data layer are up:
SQLAlchemy models + Alembic migrations for wells/wellbores/events/source_documents,
a FastAPI app with health + well list/read endpoints, and tests.
No frontend, ingestion, OCR, or RAG yet.
