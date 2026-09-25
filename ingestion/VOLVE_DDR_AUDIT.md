# Volve historical drilling-event source audit (2026-09-26)

A data **acquisition and audit** milestone only — no Event rows created,
no extraction code written. Scope: find a real, public, evidence-backed
source for Volve Daily Drilling Report (DDR) content (the source
`ingestion/events.py`'s ingestion contract is meant to eventually be fed
by), inspect its actual structure, and assess extraction feasibility
against what the data really contains — not what was assumed in
`ingestion/VOLVE_AUDIT.md` (Milestone 3, itself DDR-audit-only at the
time: "1,759 files... Later (event extraction — out of scope this
turn)").

## A. Was real Volve historical drilling data accessed? **Yes.**

Two independent, real, public derivatives of the official Volve DDR
corpus were found and inspected. The official access route
(Databricks Marketplace "Equinor ASA — Volve Data Village") still
requires an Equinor/Databricks account and cannot be automated from
this environment — unchanged since the Milestone 3 audit, re-confirmed
here rather than re-assumed. No PDF final-well-report mirror was found
despite a real search (see section F) — reported as a negative result,
not silently dropped.

## B. Exact source / access route

| # | Dataset | Host | License | Access method used |
|---|---|---|---|---|
| 1 | `bengsoon/volve_daily_drilling_report` | Hugging Face Hub | **CC-BY-4.0** | Public REST API (`datasets-server.huggingface.co/rows`), no auth, no download of the full parquet |
| 2 | `bengsoon/volve_alpaca` | Hugging Face Hub | **CC-BY-2.0** | Same, public REST API |

Both are documented (dataset card, fetched verbatim) as: *"Daily
Drilling Reports (DDRs) from Volve field, released by Equinor,
consisting of 1759 files. The original files were in WITSML format"* —
dataset 1 converted to JSON (structure-preserving), dataset 2 converted
to an Alpaca instruction/input/output format for text-summarization
fine-tuning. **1,759 rows in both** — an exact match to the file count
this repo's own `VOLVE_AUDIT.md` already recorded for the real WITSML
`DrillReport` corpus from independent research-paper/dataset-writeup
sources — strong corroborating evidence this is a faithful conversion
of the real corpus, not an unrelated substitute.

No files were bulk-downloaded. Inspection used the Hugging Face
`datasets-server` public row-preview API against a representative
~25–95% sample per dataset (enough for a structural/coverage audit,
not the whole corpus — see D).

## C. File formats encountered

- **Source of truth (per both dataset cards): WITSML XML** — same
  `DrillReport` schema already identified in `VOLVE_AUDIT.md` (not
  independently re-verified as raw XML here — that would need the
  gated Databricks path; both derivatives were used instead).
- **Dataset 1** (`volve_daily_drilling_report`): Parquet, one row per
  DDR, columns are a near-1:1 field-level JSON conversion of the WITSML
  `DrillReport` object (`docName`, `nameWell`, `nameWellbore`,
  `dTimStart`/`dTimEnd`, `wellAlias`, `wellboreInfo`, `statusInfo[]`,
  `fluid[]`, `porePressure[]`, `surveyStation[]`, `activity[]`,
  `lithShowInfo[]`).
- **Dataset 2** (`volve_alpaca`): Parquet, one row per DDR, 3 plain-text
  columns (`instruction`, `input`, `output`) — a lossy text-only
  derivative of the same DDRs (loses per-activity depth/timestamp/state
  structure; keeps the raw activity narrative and the real 24-hour
  summary as free text).

## D. Representative files/rows inspected

- Dataset 2: **1,696 of 1,759 rows** (all 1,596 train rows + first 100
  of 163 test rows) fetched and analyzed programmatically.
- Dataset 1: **450 of 1,759 rows** (~26%, spread across 9 offsets
  covering the full row range) fetched and analyzed programmatically.
- Full single-row structure inspected in detail: `docName:
  "15_9_F_11_B_2013_06_21"`, `nameWellbore: "NO 15/9-F-11 B"`,
  `dTimStart: "2013-06-20T00:00:00+02:00"`, 15 `activity` entries.

## E. What fields/content are actually available

| Requested field | Available? | Where |
|---|---|---|
| Depth | **Yes, structured** | `activity[].md` (dataset 1, clean numeric string per activity) — dataset 2 only has depth as free text inside `input` (regex-extractable, present in 1,314/1,696 ≈ 78% of rows sampled) |
| Date/time | **Yes, structured** | `dTimStart`/`dTimEnd` (report-level, ISO 8601) and `activity[].dTimStart`/`dTimEnd` (per-activity, dataset 1); date embedded in a fixed sentence template in dataset 2's `instruction` (100% of 1,696 sampled rows matched a `for well X on Y` pattern via regex) |
| Operational description | **Yes** | `activity[].comments` (dataset 1) / `input` (dataset 2) — real free-text narrative, e.g. *"Pipe stuck at 4094m. Worked stuck pipe... Worked stuck pipe free"* (`NO 15/9-19 B`, 1998-01-09/10) |
| Event/risk terminology | **Yes, but two very different signal qualities — see below** | |
| Wellbore identifier | **Yes, structured** | `nameWellbore`/`wellAlias.name` (dataset 1); `NO <well>` in the `instruction` template (dataset 2) — same `"NO "`-prefixed WITSML naming convention already handled by `ingestion/identifiers.py`'s `canonical_wellbore_key`/`witsml_identifier_from_name` (Milestone 3); confirmed directly reusable, not re-derived |
| Report/page/section provenance | **Yes, but DDR-level not page-level** | `docName` (exact original source filename, e.g. `15_9_F_11_B_2013_06_21` — same underscore-joined convention as the real Volve trajectory filenames already audited), `statusInfo[].reportNo` (sequential report number) — no page numbers (WITSML/JSON isn't paginated) |
| Confidence | **No** | not a source field — any confidence value would have to come from whatever extraction method is eventually built, never fabricated as if the source provided it |

**Event/risk terminology — the important nuance, found by direct
inspection, not assumed:**

- Dataset 1's `activity[].state` / `activity[].stateDetailActivity` is a
  **structured, evidently controlled-vocabulary field**, not free text.
  Across the 450-row/5,716-activity sample: `state` ∈ {`ok` (5,651),
  `fail` (65)}; `stateDetailActivity` ∈ {`success` (5,225), `equipment
  failure` (375), `operation failed` (105), `circulation loss` (6),
  `mud loss` (3), `stuck equipment` (2)}. `circulation loss`/`mud loss`
  map directly to `lost_circulation`; `stuck equipment` maps directly
  to `stuck_pipe`; `equipment failure` maps to the existing (not yet
  in-scope) `bha_equipment_issue` type. This is a **deterministic
  signal already present in the source**, not a classifier we'd have
  to build and validate.
- A naive keyword search over the free-text `comments`/`input` (e.g.
  `\bstuck\b`, `\bkick\b`, `\bbridge\b`) matched **562/1,696** rows —
  but manual inspection of the matches showed most are **false
  positives**: "kick drill" (a routine safety drill, not a kick),
  "overpull" during routine tool-setting, "bridge plug" (equipment
  name, not wellbore bridging). Tightening to exact incident phrasing
  (`"stuck pipe"`, `"lost circulation"`, `"got influx"`,
  `"cavings"`/`"hole instability"`) found only **21 high-confidence
  real incidents** in the same sample — e.g. a genuine stuck-pipe
  recovery (`NO 15/9-19 B`, 1998-01-09/10, depth 4094 m), a genuine
  lost-circulation event with an LCM pill pumped (`NO 15/9-19 S`,
  1992-12-24, depth ~2,938–3,018 m), a genuine BOP-test influx (`NO
  15/9-19 S`, 1993-04-09). **Conclusion: free-text keyword matching on
  this corpus is unreliable on its own** (high false-positive rate)
  — confirming, from actual observed data rather than assumption, why
  this milestone correctly stops short of building a classifier.

## F. Is XML/PDF/text extraction feasible?

- **Structured (dataset 1, JSON — a lossless-in-content conversion of
  the real WITSML XML fields): feasible now, largely deterministic.**
  Depth, date, wellbore, document provenance are all clean typed
  fields, no parsing ambiguity. `stateDetailActivity` gives a
  deterministic pre-filter for several target event types before any
  text analysis is needed at all.
- **Free text (dataset 2, or `comments`/`input` in general): feasible
  only with a properly validated classifier**, not naive keyword
  matching — evidenced above, not assumed.
- **PDF final well reports: not evaluated — no real sample found.**
  Searched GitHub code/repo search (`volve final well report`, `volve
  geological report`, "Final Well Report" volve) and Hugging Face
  dataset search; found notebooks referencing "RAG over reports" as a
  concept (e.g. `yohanesnuwara/PetroRAG`) but **no actual PDF file or
  text-extracted derivative committed anywhere found**. Official access
  remains the Databricks Marketplace listing only (~162 MB compressed,
  per Milestone 3's audit) — genuinely blocked from this environment,
  not silently skipped. **No comparison between XML/JSON-derived DDR
  data and PDF reports is possible this milestone** — only one source
  (DDR) was actually accessible to inspect (task item G answers "PDF
  suitability" as "unknown — inaccessible," not "worse," since no real
  PDF sample was seen).

## G. Approximate usable corpus size

**1,759 DDRs total** (both HF datasets, matching the independently
documented real WITSML corpus size). Of these, **23 of the 27 real
SODIR VOLVE-field wellbores are covered** (cross-checked programmatically
against `data/sodir/wellbore_volve_field.csv`): missing only `15/9-19
SR`, `15/9-19 SR2`, `15/9-F-10 A`, `15/9-F-10 B` in the sampled rows —
markedly better wellbore coverage than the trajectory data (10/27,
Milestone 3). Date range observed: 1979-12-31 to 2018-01-24 (the
1979 date is a clear outlier/likely placeholder — real Volve field
production ran 2008–2016 per Equinor's own description; flagged as a
data-quality note, not corrected or dropped here since no ingestion
happened this milestone). 1,688/1,696 sampled rows (99.5%) have
non-empty activity content.

## H. Is OCR actually necessary? **No — not for this source.**

Both DDR derivatives are already plain structured text/JSON, not
scanned images. OCR was never invoked or needed. (PDF final well
reports remain unassessed per F — if/when they become accessible, that
question would need re-asking against actual PDF pages, not assumed
answered here.)

## I. Recommended next extraction step (from observed data only)

Not built this milestone (audit-only), but the evidence points at a
concrete, low-risk first cut for a *future* extraction milestone:

1. Ingest dataset 1's structured `activity[]` rows where
   `state == "fail"` **and** `stateDetailActivity` is one of the
   already-observed controlled-vocabulary values that map cleanly onto
   `ingestion/events.py`'s `SUPPORTED_EVENT_TYPES` (`circulation loss`/
   `mud loss` → `lost_circulation`; `stuck equipment` → `stuck_pipe`).
   This is deterministic field-matching, not NLP — reuses the existing
   `ingestion/events.py` contract unchanged, with `comments` as the
   required `description`/evidence text and `docName` + `activity`
   timestamp as `source_location`.
2. Treat `kick_influx` and `wellbore_instability` as **not yet
   deterministically extractable** from this field alone (no
   controlled-vocabulary value observed maps to them in the sample) —
   would need validated text-pattern rules over `comments` first
   (e.g. the `"got influx"` / `"cavings"` exact-phrase patterns found
   in E, expanded and precision-checked over the full corpus before
   trusting them).
3. Do not attempt PDF-report extraction until real PDF access is
   obtained (Databricks Marketplace account) — nothing to extract from
   yet.

## J. Limitations / blockers

- Official Databricks Marketplace access still requires an
  Equinor/Databricks account — not obtainable/automatable from this
  environment. Everything here comes from third-party
  research-published derivatives of the same disclosure, same caveat
  already logged in `VOLVE_AUDIT.md`.
- Only a sample (not the full 1,759 rows) was inspected per dataset —
  sufficient for structural/coverage audit, not a claim that every row
  was checked.
- The 1979-12-31 date outlier (dataset 2) suggests at least one
  placeholder/bad date in the corpus — a real data-quality issue to
  validate against, not ignore, whenever ingestion is actually built.
- No PDF report sample was found or inspected — section F's answers
  about PDF suitability are "unassessed," not "assessed as worse."
- Nothing was ingested into the database this milestone. `events`
  table remains at 0 rows by design.
