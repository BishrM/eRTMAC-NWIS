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

## Volve → Wellbore (WITSML trajectory files)

A second real Volve survey export format, in addition to the CSV above —
`ingestion/witsml.py` parses WITSML 1.4.1.1 `<trajectorys>` XML (one or
more `<trajectoryStation>`-bearing `<trajectory>` elements per file).
Same target fields (`md`/`tvd`/`dispNs`/`dispEw`, straight from source,
no incl/azi reconstruction) and the same `attach_volve_survey` loader —
only the parser and identifier source differ:

- The wellbore identifier comes from the `<nameWellbore>` element's text,
  not the filename (real files' filenames are unreliable — one inspected
  file named `9-F-1 C.xml` actually contains wellbore `15/9-F-1 B`; see
  `data/volve/witsml/README.md`).
- Real WITSML headers prefix the name with a country code (`"NO 15/9-F-11
  A"`) — `canonical_wellbore_key` strips this (this was already the
  function's documented contract; the implementation had a gap, fixed
  alongside this ingestion round).
- One real mirror's exporter instead suffixes the primary bore with a
  literal `"- Main Wellbore"` marker — stripped by
  `ingestion/identifiers.py:witsml_identifier_from_name` specifically
  (not a general cross-source convention, so not inside
  `canonical_wellbore_key`).
- Real WITSML data includes technical sidetracks (e.g. `"T2"`) not present
  among SODIR's registered wellbores for that well — `attach_volve_survey`
  rejects these the same way it rejects any unmatched identifier (raises
  `IngestionError`), never force-matching to the nearest wellbore.
- Every station's `md`/`tvd`/`dispNs`/`dispEw` must report `uom="m"`
  (confirmed true of every real file inspected) — a different unit is a
  hard error, not a silent conversion.

CLI: `python -m ingestion.scripts.ingest_volve_trajectory_witsml <xml paths...>`
(accepts multiple files/globs; prints per-file/per-trajectory results plus
a files-found/mapped/unmatched/stations summary). See
`data/volve/witsml/README.md` for exact file provenance and the known
unmatched-sidetrack case.

## Structured historical drilling events (Milestone 5)

`ingestion/events.py` defines the **ingestion contract** for structured
historical drilling events — not an extractor. No raw Volve DDR/PDF data
has been ingested yet; a real, public DDR source has since been located
and audited (`ingestion/VOLVE_DDR_AUDIT.md`) but not yet ingested — that
audit's "recommended next step" is the concrete extraction path for a
future milestone. This module defines
the plain-dict shape a future DDR-XML/report parser must produce, and
validates/loads it exactly the same way regardless of source. Only four
event types are accepted for now (`stuck_pipe`, `lost_circulation`,
`kick_influx`, `wellbore_instability`) — `app.models.event.EventType` has
more (`bha_equipment_issue`, `npt`, `other`) reserved for later, rejected
here until an actual, validated extraction method exists for them.

| Field | Required? | Notes |
|---|---|---|
| `wellbore` | required | matched to an existing `Wellbore` by canonical key (`ingestion/identifiers.py`) — same pattern as Volve survey attachment |
| `event_type` | required | one of `SUPPORTED_EVENT_TYPES` |
| `depth_md_m`, `depth_tvd_m` | optional | ≥0; TVD > MD is a warning, not an error |
| `occurred_at` | optional | `YYYY-MM-DD` (this format's own contract, not SODIR's `DD.MM.YYYY`) |
| `severity` | optional | one of `EventSeverity` (`low`/`medium`/`high`/`critical`) — only ever the source's own stated severity, never inferred |
| `description` | required | the evidence text itself — an event with no description isn't evidence-backed |
| `source_document_id` | required | UUID of an existing `SourceDocument` row — must already exist, never created here |
| `source_location` | required | e.g. "p.4 activity 2" — the source reference |
| `confidence` | optional | `[0, 1]` |
| `source` | required | provenance tag, e.g. `"volve_ddr"`, `"demo"` for test data |
| `source_event_id` | required | stable external id — the upsert/dedup key (`Event.source_event_id`, unique) |
| `extra_metadata` | optional | any JSON object, passed through as-is (`Event.extra_metadata`, JSONB) — for fields not worth their own column yet |

CLI: `python -m ingestion.scripts.ingest_events_csv <events.csv>` (safe to
re-run — upserts by `source_event_id`). `ingestion/loaders.py:
ingest_event_result` raises `IngestionError` if the wellbore doesn't
resolve to exactly one match or the source document doesn't exist —
never fabricates either.

**Schema changes**: `Event.source` (required, provenance — same
convention as `Well.source`/`Wellbore.source`), `Event.source_event_id`
(nullable, unique — the ingestion dedup key), `Event.severity`
(nullable, new `EventSeverity` enum), `Event.extra_metadata` (nullable
JSONB) — migration `84855f85f8ac_extend_events_for_structured_historical_`.

## Volve DDR event extraction (Milestone 7)

`ingestion/volve_ddr.py` extracts real historical drilling events from
the public `bengsoon/volve_daily_drilling_report` Hugging Face dataset —
a CC-BY-4.0 structural (JSON) conversion of the real Volve WITSML
`DrillReport` corpus, found and audited in `ingestion/VOLVE_DDR_AUDIT.md`.
It maps exactly one real, controlled-vocabulary field,
`activity[].stateDetailActivity`, onto our event vocabulary — never
free text (Milestone 6 directly tested keyword matching on this corpus
and found it unreliable: 562 loose matches vs. 21 verified real
incidents in the same sample):

| `stateDetailActivity` | → `EventType` |
|---|---|
| `circulation loss` | `LOST_CIRCULATION` |
| `mud loss` | `LOST_CIRCULATION` |
| `stuck equipment` | `STUCK_PIPE` |

Everything else (`success`, `equipment failure`, `operation failed`,
`injury`, ...) is left alone — not an event, not an error, just outside
this milestone's scope. `extract_candidate_events` is a pure function
(no network/DB) feeding the *existing, unchanged* event-ingestion
pipeline (`parse_event_row` → `ingest_event_result`); the CLI,
`python -m ingestion.scripts.ingest_volve_ddr_events [--max-records N]
[--dry-run]`, fetches the full 1,759-record corpus via Hugging Face's
public `datasets-server` REST API (no auth, no bulk file download) and
adds one new minimal helper, `loaders.py:find_or_create_source_document`
(find-or-create by `uri` — a `SourceDocument` per real DDR, honestly
tagged `hf://bengsoon/...#docName=...`, never presented as the original
WITSML file). Safe to re-run (`Event.source_event_id` is deterministic:
`volve_ddr:<docName>:act<NNN>`, never a random UUID).

Real run against the dev DB (2026-09-26): 213/23,447 activities matched
a supported value; 204 became events (97 `lost_circulation`, 107
`stuck_pipe`) across 8 real wellbores; 9 rejected (real WITSML technical
sidetracks — `T2`/`BT2`/`ST2` — with no matching SODIR wellbore, same
pattern already seen in Milestone 3's trajectory ingestion); 0 rejected
for data-quality reasons (dates/depths/comments were clean across every
matched activity in this corpus). See `ingestion/VOLVE_DDR_AUDIT.md` and
the Milestone 7 report for full detail.

## Source-evidence retrieval (Milestone 9)

`backend/app/services/evidence_service.py` retrieves the actual source
evidence for one historical Event, given its stable `source_event_id`
(e.g. `volve_ddr:15_9_F_1_2013_08_23:act023`) — an exact-equality DB
lookup on the unique `Event.source_event_id` column, **never** a
string/keyword match against `description`. It performs no network
access, no filesystem access, and no new text extraction: it exposes
exactly what ingestion already wrote to the row at ingestion time.

**What evidence is actually available, from the audited derivative
(see `VOLVE_DDR_AUDIT.md`):** for every Volve-DDR-sourced event,
`Event.description` already *is* the real `activity[].comments` text,
captured verbatim by `ingestion/volve_ddr.py` — there is no separate
raw-corpus store to re-fetch from, and none is needed. Depth
(`activity.md`), date (`activity.dTimStart`/`dTimEnd`), document
identity (`docName`), and activity reference (source_location) are all
structured fields already on the row. `extract_candidate_events`
rejects any activity with no `comments` text before it ever becomes an
Event (see that module's "no evidence to store, rejected" path) — so
every ingested `volve_ddr_hf_derivative` event has real text available.
A future, different source type could still load an Event with no
`description` (e.g. a metadata-only manual entry); the evidence layer
reports that case as `evidence_type="metadata_only"` rather than
inventing text.

**Provenance chain preserved explicitly, never conflated:**
original Equinor WITSML `DrillReport` corpus (not directly accessible
from this environment) → the public CC-BY-4.0 `bengsoon/
volve_daily_drilling_report` Hugging Face derivative actually used →
one `SourceDocument` row per real DDR (`hf://...#docName=...`, titled
"... (public derivative, not the original WITSML file)") → one `Event`
row per matched activity → the evidence response's `provenance` object,
which always sets `derivative_is_original_source=False`.

API: `GET /historical-events/{source_event_id}/evidence`
(`backend/app/routes/historical_events.py`). Malformed identifiers
(empty, over 128 chars, or containing characters no id minted by this
project's own ingestion code would ever contain) are rejected with 422
before any DB query; an unknown but well-formed id is a clean 404 — see
`evidence_service.is_well_formed_source_event_id`. Since
`source_event_id` is a DB-level unique column, a lookup can never
resolve to more than one row (no duplicate evidence is possible by
construction), and repeated lookups are deterministic. The lookup is a
single query with `well`/`wellbore`/`source_document` eager-loaded
(`joinedload`) — no N+1, verified directly against the real dev DB.

**Existing `GET /wells/{well_id}/historical-events` response left
unchanged.** It already carries a compact evidence reference per event
(`description`, `source_document_title`, `source_location`, `source`,
`source_event_id`, `confidence`) drawn from the same single query as
the rest of that response — not a second per-event fetch. A caller that
wants the fuller structured `provenance` breakdown follows
`source_event_id` to the dedicated evidence endpoint above, rather than
that being embedded (and duplicated across possibly-many events sharing
one document) into every list entry.

**Limitations:** no page-level provenance exists in this source (DDRs
aren't paginated — see `VOLVE_DDR_AUDIT.md` section E); this layer
cannot provide it either. Only the two DDR-sourced event types
(`stuck_pipe`, `lost_circulation`) currently have real evidence to
retrieve — same scope limit as Milestone 7. This is a deterministic
retrieval layer only, not a RAG/semantic-search system: a future AI
layer may consume `evidence_text` to summarize/explain, but must not
bypass this layer to reconstruct evidence itself.

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

- `test_sodir_mapping.py`, `test_volve_mapping.py`, `test_witsml_mapping.py`, `test_events_mapping.py`, `test_volve_ddr.py` — pure parsing/validation, no DB, run against the fixtures in `tests/fixtures/` (small, realistically-shaped — explicitly synthetic except `volve_ddr_real_sample_15_9_F_4_2008_02_19.json`, a real CC-BY-4.0 DDR record, labeled as such).
- `test_loaders.py`, `test_volve_ddr_loader.py` — exercise the DB upsert path (idempotency, the "wellbore must already exist" guard) against the same `nwis_test` Postgres/PostGIS database `backend/tests` uses. Requires `docker compose up -d`.

## Explicitly not built here

Frontend, OCR, RAG/LLM reasoning, predictive risk models, free-text
event classification (only the one controlled-vocabulary field is
trusted — see Milestone 7 above), and PDF final-well-report extraction
(no accessible PDF source found per `VOLVE_DDR_AUDIT.md`) — all
deferred per scope.
