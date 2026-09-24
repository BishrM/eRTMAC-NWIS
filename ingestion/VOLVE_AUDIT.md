# Volve dataset audit (2026-09-24)

A data audit only — nothing downloaded or ingested. Scope: identify the
official source, inspect a small representative subset of real files
(via public research mirrors, since bulk access needs a Databricks
Marketplace/Equinor account), and check overlap with the SODIR sample
already in the dev DB.

## Official dataset/source

- **Current official distribution**: **Databricks Marketplace**, listing
  "Equinor ASA — Volve Data Village"
  (`marketplace.databricks.com/details/5c3558ef-315c-44dd-baef-7062ac301f22/Equinor-ASA_Volve-Data-Village`),
  linked from Equinor's own page (`equinor.com/energy/volve-data-sharing`).
  This **replaces** the original 2018–2022 direct Azure Blob Storage
  container (that access window has expired — several older
  how-to-download pages from 2018–2021 pointing at a direct Azure
  connection string are now stale).
- **Access mechanism**: requires a Databricks account/workspace to
  mount the marketplace share (not an anonymous public URL like SODIR's
  CSV export). This is real friction to flag for whoever does the actual
  bulk ingestion later — it is not a plain `curl`-able endpoint.
- **License**: Equinor Open Data Licence — "all academic institutions,
  students and researchers permission to use this dataset... additional
  letters of permission are not required."
- **Scale**: ~40,000 files total, field produced 2008–2016.
- Because full access is gated, this audit's file-level inspection used
  small individual files already extracted from the same official
  disclosure and published in public research repos (see citations per
  section below) — clearly third-party mirrors, not our intended
  ingestion source. The real bulk ingestion should go through the
  Databricks Marketplace listing directly.

## Relevant file groups

| Group | Format | Scale (per public sources) | Relevant to NWIS now? |
|---|---|---|---|
| WITSML directional surveys (`trajectory` folders) | XML, one file per run | 4,217 survey stations across the field | **Yes** — wellbore trajectory |
| Daily Drilling Reports (DDR) | XML, WITSML 1.4.0.0 `DrillReport` | 1,759 files | Later (event extraction — out of scope this turn) |
| WITSML real-time drilling mechanics (`log` folders) | XML | large (ROP/WOB/torque/RPM/mud weight/ECD/d-exponent time series) | No — too granular for the current vertical slice |
| Reports (final well reports, geological/completion reports) | PDF | ~162 MB compressed | Later (RAG evidence source — out of scope this turn) |
| Production data | Excel | 7 wells, daily, Sep 2007–Dec 2016 | No — not in CLAUDE.md's current capability list |
| Well logs (LAS) | LAS | per-well petrophysical logs | No — not needed for the current vertical slice |
| Seismic, static/dynamic reservoir models | SEG-Y, Eclipse | large | No |

Sources: Equinor's own dataset description, the TADI paper (arXiv
2605.00060) which built an ingestion pipeline over this exact dataset,
and `frombitumentobinary.com`'s WITSML folder-structure writeup.

## Identifier mapping — Volve ↔ SODIR

**This needs a fix before real ingestion — our current filename parser
is wrong.** `ingestion/volve.py`'s `wellbore_name_from_filename` assumes
only the quad/block separator is replaced with `_` (e.g.
`"15_9-F-11_Survey_Data.csv"` → `"15/9-F-11"`). Inspecting a real Volve
survey file (`15_9_F_11_A.csv`, from a public research mirror — see
below) shows **every** separator is replaced with `_`, including the
one between block and slot: real filenames look like `15_9_F_11_A`, not
`15_9-F-11_A`. Confirmed independently by the TADI paper, which
documents **three incompatible naming conventions** across Volve's own
file groups:

| Source | Example | Separator pattern |
|---|---|---|
| DDR filenames | `15_9_F_11_T2` | all separators → `_` |
| WITSML headers | `NO 15/9-F-11 T2` | slash + hyphen + space, with an `NO ` prefix |
| Production data | `15/9-F-11` | slash + hyphen (matches SODIR) |
| SODIR `wlbWellboreName` (ground truth, confirmed against real data) | `15/9-F-11 A` | slash + hyphen + **space** before a sidetrack suffix |

Reconstructing the exact SODIR-style name from an all-underscore
filename is ambiguous (is `15_9_F_11_A`'s last part a hyphen-joined or
space-joined suffix?). The robust fix is **not** to guess the
separator positions but to match on a **normalized key** — strip every
non-alphanumeric character and uppercase both sides
(`15/9-F-11 A` and `15_9_F_11_A` both → `159F11A`) — before comparing a
Volve filename to a SODIR `Wellbore.name`. Not implemented this turn
(this is an audit); flagged here as the concrete fix the next ingestion
step needs, in `ingestion/volve.py` (`wellbore_name_from_filename`) and
`ingestion/loaders.py` (`attach_volve_survey`'s lookup).

## Inspected files (small representative subset)

**Trajectory/survey** — `15_9_F_11_A.csv`, 324 rows, from a public
research repo (`jczettl/wellbore-trajectory-uncertainty`, MIT-licensed,
explicitly described in its README as "Volve survey with MD,
inclination, azimuth, and **supplied** TVD/North/East coordinates").
Real header:

```
MD,Incl,Azi,TVD,NS,EW,VS,DLS,Build,Turn
145.9,0.0,0.0,145.9,4.65,-0.93,0.0,0.0,0.0,0.0
150.0,0.09,227.76,150.0,4.65,-0.93,0.0,0.659,0.659,0.0
...
```

**Important correction to our earlier design**: the original
`ingestion/volve.py` assumed raw files carry only `md,inc,azi` and that
building `Wellbore.trajectory`/`tvd_bottom_m` would need us to
implement a minimum-curvature calculation ourselves. Real data shows
Volve's own survey files **already supply `TVD`, `NS`, `EW`** per
station (`NS`/`EW` are metre offsets from a tie-in point, not absolute
coordinates — confirmed by the source README). So the actual follow-up
work is smaller than planned: convert each station's `(NS, EW)` offset
to an absolute lon/lat (simple local-tangent-plane offset from the
wellhead's known SODIR position) and take `TVD` directly — no
minimum-curvature reconstruction needed from our side. `DLS`/`Build`/
`Turn` in this particular file look like the repo's own QC output, not
guaranteed to be in every raw Volve file — treat as optional/derived,
not something to depend on.

**Drilling/operational data** — not directly opened (gated behind
Databricks access), but its schema is well-documented: WITSML 1.4.0.0
`DrillReport` objects (Energistics WITSML spec + the TADI paper, which
parsed all 1,759 of them with zero errors). Key elements: `DTimStart`/
`DTimEnd` (reporting period), `ExtendedReport` (24-hour narrative),
`DrillActivity` (0..*, activity breakdown), `SurveyStation` (0..*,
embedded surveys), `BitRecord`, `Fluid` (0..*, mud properties: type,
density, viscosity, yield point), plus specialized sub-objects
`ControlIncidentInfo`, `EquipFailureInfo`, `LithShowInfo`, `CoreInfo` —
these map directly onto our `EventType` enum
(`stuck_pipe`/`lost_circulation`/`kick_influx`/`bha_equipment_issue`)
for a *later* event-extraction step, not this one.

**Reports/documents** — not opened; confirmed to exist (~162 MB
compressed "Reports" folder per public sources) but no per-file
listing found without Databricks access. Treat as a later RAG
evidence source.

## Which Volve wellbores overlap with our SODIR sample

**Zero overlap today.** Our currently-ingested 26-row SODIR sample
(`data/sodir/wellbore_exploration_sample.csv`) came from SODIR's
alphabetically-first wellbores — all in quads 1–2 (`1/2-*`, `1/3-*`,
`1/5-*`, `1/6-*`, `2/5-14`). Volve is entirely in block **15/9**, a
completely different part of the NCS. None of our 25 ingested wells are
Volve wells.

To fetch the actual overlap set (needed before any real Volve
ingestion), I pulled the authoritative SODIR wellbore list for
`wlbField == "VOLVE"` — same official CSV export endpoint used for the
SODIR sample, no bulk Volve data involved:

- **22 development wellbores** (10 distinct wells: `15/9-F-1` (+A, B,
  C), `15/9-F-4`, `15/9-F-5`, `15/9-F-7`, `15/9-F-9` (+A), `15/9-F-10`
  (+A, B), `15/9-F-11` (+A, B), `15/9-F-12`, `15/9-F-14`, `15/9-F-15`
  (+A, B, C, D))
- **5 exploration/discovery wellbores** (1 well: `15/9-19` — A, B, S,
  SR, SR2)
- **27 wellbores / 11 wells total** — consistent with the "26 wellbore
  sections" and "17 unique wells [in the WITSML subset]" figures cited
  by third-party sources, a good cross-check that this list is right.

This list itself is not yet in the dev DB (our SODIR sample didn't
include it) — see recommended subset below.

## Exact useful fields (survey files)

| Volve field | Type | Maps to |
|---|---|---|
| `MD` | float, m | survey station MD → `Wellbore.md_top_m`/`md_bottom_m` (already exists) |
| `TVD` | float, m | survey station TVD → `Wellbore.tvd_bottom_m` at the last station (column exists, unpopulated so far) |
| `NS`, `EW` | float, m (offset from tie-in) | station offset → absolute lon/lat, combined with the well's SODIR surface position → `Wellbore.trajectory` (LineString, column exists, unpopulated so far) |
| `Incl`, `Azi` | float, deg | kept for QC / recomputation if needed, not persisted (no per-station table) |

## Missing/optional fields

- `DLS`/`Build`/`Turn` in the inspected file may be a third party's own
  derived QC columns, not guaranteed present in the pristine Equinor
  file — don't depend on them.
- Not every wellbore has every file group; the WITSML subset covers 17
  of ~24 drilled Volve wells per public sources — some wellbores (e.g.
  `15/9-F-15` sidetracks) may have partial or no directional-survey
  coverage.
- DDR narrative quality/completeness varies by report; some fields
  (`BitRecord`, `CoreInfo`) are naturally sparse (not every day has a
  bit run or a core).

## Recommended smallest useful Volve subset (for the *next* ingestion step, not now)

1. **First fetch the 27-row SODIR VOLVE-field wellbore list** (above)
   into the dev DB — the same pattern as the existing SODIR sanity
   check. Without this, no Volve file can attach to anything (our
   loader requires an existing `Wellbore` row by name).
2. **Then, one wellbore's directional survey only** — `15/9-F-11`
   (already used in our fixtures/tests) — to validate the real
   MD/TVD/NS/EW → trajectory mapping end-to-end on a single well before
   scaling to all 27.
3. Defer DDR/event-extraction and Reports/RAG entirely — both need
   real feature work (XML parsing against the WITSML `DrillReport`
   schema; document chunking/embedding), not just field mapping, and
   are explicitly out of scope until the similarity/RAG milestones.

## Schema changes genuinely required

**None.** `Wellbore.trajectory`, `md_top_m`, `md_bottom_m`, and
`tvd_bottom_m` already exist (added in the initial backend slice) and
are exactly what the real Volve survey fields need. The
`SourceDocument`/`Event` tables needed for DDRs/Reports already exist
too, unused so far — no reason to touch them until event extraction is
actually built.
