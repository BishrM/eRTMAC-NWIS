# eRTMAC-NWIS — SIH 2026

## Project
Problem Statement: SIH26121
Organization: Oil India Limited (OIL)
Name: eRTMAC-NWIS — Nearby Wells Intelligence System

## Goal
Build a 7/10 internal-hackathon prototype that demonstrates:
Current well → similar historical wells → historical drilling events → evidence-backed insights → engineer dashboard.

Do NOT attempt a production-grade 9/10 system yet.
Architecture must remain extensible toward the 9/10 version.

## Core Product
The system helps drilling engineers retrieve relevant historical experience from comparable wells.

Core capabilities:
1. Well metadata ingestion
2. PDF/document ingestion
3. OCR for scanned documents
4. Historical drilling-event extraction
5. Multi-factor well similarity
6. Geospatial visualization
7. Semantic evidence retrieval/RAG
8. Evidence-backed AI explanation
9. Engineer dashboard

## Prototype Data
Primary public analogue data:
- Equinor Volve dataset for detailed drilling/report data
- Norwegian Offshore Directorate/SODIR data for broader well metadata/geospatial data

OIL's confidential historical well corpus is NOT available.
Never claim the prototype is trained or field-validated on confidential OIL data.

## Important Product Positioning
This is decision support, not autonomous drilling control.

Do NOT claim:
- validated future-risk probabilities
- OIL field validation
- confidential OIL training data
- autonomous drilling decisions

Prefer:
"historically similar wells"
"historical drilling-risk insights"
"evidence-backed decision support"
"public analogue data"
"OIL-aligned architecture"

## Target Event Types
Start with:
- stuck pipe
- lost circulation
- kick/influx
- wellbore instability

Optional later:
- BHA/equipment issue
- NPT

Every extracted event should preserve:
well_id, event_type, depth, source_document, page/text location, confidence.

## Similarity
Similarity should NOT rely on geographic distance alone.

Initial factors:
- geographic proximity
- depth
- formation
- trajectory
- drilling context where available

Results must explain why wells are considered similar.

## Architecture
Frontend:
React + TypeScript + Tailwind
Map:
MapLibre or Leaflet

Backend:
FastAPI

Data:
Python, Pandas, NumPy, scikit-learn

Structured DB:
PostgreSQL + PostGIS

Vector DB:
Qdrant

Documents:
Apache Tika
OCRmyPDF + Tesseract

AI:
Embeddings + RAG + LLM API

DevOps:
Docker
Git/GitHub

## Architecture Flow

Raw data
→ ingestion
→ normalization
→ structured well/event data
→ similarity engine
→ historical evidence retrieval
→ RAG/LLM
→ engineer dashboard

## Repository Structure

frontend/
backend/
ingestion/
ml/
data/
tests/
docs/

Keep components modular and avoid unnecessary complexity.

## Engineering Rules

1. Inspect the existing repo before changing anything.
2. Do not rewrite working code unnecessarily.
3. Do not add dependencies unless required.
4. Prefer simple, explainable implementations.
5. Keep data provenance.
6. Never hardcode fake production results.
7. Use realistic demo data when necessary and label it clearly.
8. Write tests for important logic.
9. Keep APIs and data models extensible.
10. Do not build features outside the current milestone without approval.
11. When blocked, investigate the repository and available tools before asking.
12. After implementing a feature, run the relevant tests/checks.

## Demo Goal

The ideal demo flow:

1. Load/select a current well.
2. Display it on a map.
3. Find similar historical wells.
4. Explain similarity.
5. Show historical drilling events.
6. Retrieve supporting report evidence.
7. Generate an evidence-backed insight.
8. Show the engineer-facing recommendation/context.

## Development Philosophy

Build the smallest complete vertical slice first.

Do not build isolated impressive features that cannot connect to the end-to-end workflow.

Prioritize:
working pipeline > feature count
evidence > hallucination
explainability > complexity
demo reliability > theoretical sophistication

## Claude Code Behavior

Act as a senior software engineer working with me.

Default to implementing requested changes rather than only describing them.

Before major architectural changes, inspect the repository and explain the decision briefly.

Keep responses concise.

Do not dump unnecessary explanations or large amounts of code into chat.

When a task is complete:
- state what changed
- state what was tested
- state any remaining issue

Do not claim something works unless you actually tested it.