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

## Status

Project scaffolding only. No implementation yet.
