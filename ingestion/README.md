# Ingestion

Parses and validates public well-data sources (SODIR, Volve) into the
`Well`/`Wellbore` schema owned by `backend/app/models`. No large datasets
are downloaded yet — this is the field-mapping and validation framework,
exercised only against small fixture files in `tests/fixtures/`.

## Why ingestion depends on backend (not the other way round)

`backend/app/models` owns the schema. Ingestion's job is to fill it, so it
imports `app.*` (see `_backend_path.py`, which adds `backend/` to
`sys.path`) rather than backend depending on ingestion. This also means
ingestion needs no Python environment of its own — it reuses
`backend/.venv` (already has SQLAlchemy, GeoAlchemy2, psycopg2, pytest).

## Pipeline

```
raw CSV row -> parse + validate (sodir.py / volve.py) -> Normalized* dataclass (schemas.py)
            -> upsert into Well/Wellbore (loaders.py, the only DB-touching module)
```

Every parser function is pure (no I/O beyond reading the given file, no DB)
and returns *every* validation problem it found rather than raising on the
first one — a row with errors is rejected (not loaded) but you still see
every issue, and a row with only warnings still loads.

## SODIR → Well / Wellbore

Source: the "Wellbore: Exploration/Development, all" CSV export from
factpages.sodir.no. One row = one wellbore, grouped under a parent well
name. Field names verified against SODIR's own Wellbore Attributes page
(factpages.sodir.no/en/wellbore/Attributes), 2026-09.

| SODIR field | Parsed as | Target | Required? |
|---|---|---|---|
| `wlbWell` | str | `Well.well_id`, `Well.name` | required |
| `wlbDrillingOperator` | str | `Well.operator` | optional |
| `wlbField` | str | `Well.field` | optional (blank for undiscovered wildcats) |
| `wlbWaterDepth` | float, m, ≥0 | `Well.water_depth_m` | optional |
| `wlbTotalDepth` | float, m MD/RKB, ≥0 | `Well.total_depth_md_m` | optional |
| `wlbFinalVerticalDepth` | float, m TVD/RKB, ≥0 | `Well.total_depth_tvd_m` | optional (warning if > MD) |
| `wlbFormationAtTd` | str | `Well.formation` | optional |
| `wlbEntryDate` | date, `DD.MM.YYYY` | `Well.spud_date` | optional |
| `wlbCompletionDate` | date, `DD.MM.YYYY` | `Well.completion_date` | optional (blank if still active) |
| `wlbNsDecDeg` | float, ±90 | `Well.location` (lat) | optional, but see datum note |
| `wlbEwDecDeg` | float, ±180 | `Well.location` (lon) | optional, but see datum note |
| `wlbGeodeticDatum` | str | drives coordinate transform, not stored | see below |
| *(constant)* | `"Norway"` | `Well.country` | — |
| *(constant)* | `"sodir"` | `Well.source`, `Wellbore.source` | — |
| `wlbWellboreName` | str | `Wellbore.name` | required |
| `wlbNpdidWellbore` | str | `Wellbore.npdid_wellbore` | required — upsert/dedup key |

**Datum handling — revised after real-data sanity check (2026-09-24)**:
the original assumption was that positions would mostly be WGS84 with
ED50 as a rare legacy exception. A real SODIR export showed the
opposite: `wlbGeodeticDatum` is `ED50` for essentially every wellbore
(exploration and development alike), confirmed against SODIR's own field
docs ("wlbGeodeticDatum ... Example of legal values: ED50"). Dropping
ED50 coordinates — the original policy — would leave almost no well with
a position, breaking map visualization entirely. So `ingestion/geodesy.py`
now transforms ED50 (EPSG:4230) → WGS84 (EPSG:4326) via `pyproj`
(standard-accuracy transform, ~1–3 m in NW Europe — plenty for map-scale
display). A blank datum is still accepted with a warning (assumed
WGS84). Any *other* (unrecognized) datum still has its coordinates
dropped with a warning, as a safety net.

**Plausibility check**: coordinates outside the Norwegian Continental
Shelf's rough bounding box (lat 56–82°N, lon −5–35°E) are kept but
flagged as a warning — a soft check, not a hard rule, since other sources
may legitimately fall outside it.

**Schema changes**: `Wellbore.npdid_wellbore` (nullable, unique,
indexed) — SODIR's own stable ID, needed so re-ingesting the same
export is idempotent (migration
`815f8c6c6353_add_wellbore_npdid_wellbore_for_source_`).
`Wellbore.volve_source_id` (nullable) — the raw Volve identifier,
added when the Volve survey ingestion needed somewhere to preserve
provenance for the canonical-key match (migration
`d8d2a40841b4_add_wellbore_volve_source_id_for_volve_`).

## Volve → Wellbore (survey stations)

Source: Volve's per-wellbore directional survey files, named
`<id>_Survey_Data.csv`, columns `MD,Incl,Azi,TVD,NS,EW,VS,DLS,Build,Turn`
— confirmed against a real file (see `ingestion/VOLVE_AUDIT.md`). We use
`MD,TVD,NS,EW` only; `Incl`/`Azi` are read but intentionally not used
(see below), and `VS`/`DLS`/`Build`/`Turn` look like a third party's own
derived QC columns, not guaranteed present in every real file.

**Identifier matching**: an earlier version of this module tried to
reconstruct the SODIR-style name from the filename (assuming only the
quad/block separator became `_`). A real file
(`15_9_F_11_A_Survey_Data.csv`) showed *every* separator becomes `_`,
and SODIR/WITSML/Volve each spell the same wellbore differently — see
`ingestion/identifiers.py`. Matching is now done on a canonical key
(alphanumeric-only, uppercased) computed from both sides; the raw
filename-derived identifier is preserved as-is (never reconstructed)
and stored on `Wellbore.volve_source_id` once a survey is attached, for
provenance.

| Volve field | Parsed as | Target | Required? |
|---|---|---|---|
| filename | str → raw identifier (`ingestion/identifiers.py`) | matched to `Wellbore` by canonical key; raw string → `Wellbore.volve_source_id` | required — the wellbore must already exist (from SODIR ingestion) |
| `MD` | float, m, ≥0 | station MD → `Wellbore.md_top_m` / `md_bottom_m` (min/max across stations) | required per row |
| `TVD` | float, m, ≥0 | station TVD → `Wellbore.tvd_bottom_m` (max across stations) | required per row |
| `NS`, `EW` | float, m (offset from the survey's tie-in point) | combined with the parent `Well.location` via a local equirectangular approximation → each `Wellbore.trajectory` point (PostGIS LineString) | required per row |
| `Incl`, `Azi` | float | read, not used | not used — we use Volve's own supplied MD/TVD/NS/EW rather than reconstructing a trajectory from inclination/azimuth ourselves |

Volve's files already supply computed TVD/NS/EW per station, so no
minimum-curvature reconstruction is needed on our side — just a
NS/EW-offset → absolute-lon/lat conversion (not survey-grade, but
consistent with the accuracy bar used for the ED50→WGS84 transform:
plenty for map-scale display).

Volve well *header* fields (operator, depths, coordinates) are not
separately mapped: Volve's wells are the same NPD/SODIR-registered wells
(block 15/9), so SODIR is the single source of truth for that metadata;
Volve only adds the detailed survey (and, later, daily/report documents)
on top of a wellbore SODIR already created.

## Expected missing/optional fields

- `wlbField` — blank for wildcats before a discovery is named.
- `wlbCompletionDate` — blank for wells still active/drilling per SODIR's data.
- `wlbFormationAtTd` / `wlbFinalVerticalDepth` — sometimes blank, e.g. shallow or aborted wellbores.
- `wlbGeodeticDatum` — sometimes blank on older records (treated as WGS84 with a warning).
- Volve survey inclination/azimuth near MD 0 are often exactly 0 by convention — not an error.

## Tests

```
source backend/.venv/bin/activate
python -m pytest ingestion/tests -v
```

- `test_sodir_mapping.py`, `test_volve_mapping.py` — pure parsing/validation, no DB, run against the fixtures in `tests/fixtures/` (small, realistically-shaped, explicitly **not** real downloaded data).
- `test_loaders.py` — exercises the DB upsert path (idempotency, the "Volve survey needs an existing wellbore" guard) against the same `nwis_test` Postgres/PostGIS database `backend/tests` uses. Requires `docker compose up -d`.

## Explicitly not built here

Similarity, frontend, OCR, RAG, trajectory geometry computation, ED50
coordinate transform, real data download — all deferred per scope.
