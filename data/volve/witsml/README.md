# Volve WITSML trajectory files

Real Volve WITSML 1.4.1.1 directional-survey trajectory exports (`<trajectorys>`
root, one `<trajectory>` per wellbore, `<trajectoryStation>` per survey
station with `md`/`tvd`/`dispNs`/`dispEw` already computed — same "no
minimum-curvature reconstruction needed" situation as the CSV survey file
in `data/volve/README.md`). Not committed (`data/*` is gitignored) — this
README documents provenance. Parsed by `ingestion/witsml.py`.

**Important**: the file naming below is our own (renamed on download for
clarity) and does **not** reliably indicate which wellbore is inside —
several original filenames are wrong (see per-file notes). Matching is
always done on the `<nameWellbore>` element's text content via
`ingestion/identifiers.py`'s canonical key, never the filename.

**Not the official access path** — see `ingestion/VOLVE_AUDIT.md` for why
(official access is now the Databricks Marketplace "Volve Data Village"
listing, which needs an account). These are the same, real, already
publicly re-published WITSML files, sourced from independent public
GitHub mirrors of the same Equinor disclosure. Underlying data:
Equinor Open Data Licence. Fetched 2026-09-25.

| File | Source repo (mirror) | Original path | `<nameWellbore>` (ground truth) | Matches SODIR wellbore |
|---|---|---|---|---|
| `F-1_from-RoboIOTers.xml` | `RoboIOTers/volve-wells-trajectory` (MIT) | `9-F-1 C.xml` | `NO 15/9-F-1 B` | `15/9-F-1 B` (npdid 7264) — filename says "C", content says "B"; content wins |
| `F-4_from-RoboIOTers.xml` | same | `9-F-4.xml` | `NO 15/9-F-4` | `15/9-F-4` (npdid 5693) |
| `F-5_from-RoboIOTers.xml` | same | `9-F-5.xml` | `NO 15/9-F-5` | `15/9-F-5` (npdid 5769) |
| `F-7_from-RoboIOTers.xml` | same | `9-F-7.xml` | `NO 15/9-F-7` | `15/9-F-7` (npdid 5610) |
| `F-9_from-RoboIOTers.xml` | same | `9-F-9.xml` | `NO 15/9-F-9 A` | `15/9-F-9 A` (npdid 6163) |
| `F-11_from-RoboIOTers.xml` | same | `9-F-11.xml` | `NO 15/9-F-11 T2` | **none** — "T2" is a real technical sidetrack not in SODIR's 27-row VOLVE-field list; ingestion must reject this, not force-match it to `15/9-F-11` or `15/9-F-11 A` |
| `F-12_from-RoboIOTers.xml` | same | `9-F-12.xml` | `NO 15/9-F-12` | `15/9-F-12` (npdid 5599) |
| `F-14_from-RoboIOTers.xml` | same | `9-F-14.xml` | `NO 15/9-F-14` | `15/9-F-14` (npdid 5351) |
| `F-15_from-RoboIOTers.xml` | same | `9-F-15.xml` | `NO 15/9-F-15 C` | `15/9-F-15 C` (npdid 5794) — filename says just "15", content says "C" |
| `F-10_from-viandika.xml` | `viandika/volve_horizon_trajectory` (no explicit license file; public repo) | `witsml/Norway-StatoilHydro-15_$47$_9-F-10/trajectory/1.xml` | `15/9-F-10 - Main Wellbore` | `15/9-F-10` (npdid 6099) — "- Main Wellbore" is this exporter's own literal marker for the primary bore, stripped by `ingestion/identifiers.py:witsml_identifier_from_name` |

## Two real, distinct WITSML naming conventions found

- RoboIOTers' files prefix every `<nameWellbore>` with `NO ` (a country
  code) — `canonical_wellbore_key` strips this (fixed as part of this
  ingestion round; the function's own docstring already documented this
  as expected behavior, but the implementation didn't do it until now).
- viandika's file suffixes the primary bore with literal `- Main
  Wellbore` — not a sidetrack marker, stripped by
  `witsml_identifier_from_name` specifically (not inside
  `canonical_wellbore_key`, since it isn't a general cross-source
  convention, just this one exporter's).

## Units

All inspected stations report `md`/`tvd`/`dispNs`/`dispEw` in `uom="m"`
consistently (confirmed per-file, not assumed) — `incl`/`azi` units vary
between files (`rad` in RoboIOTers' files, `dega` in viandika's) but
those two fields are read by nobody; only the four metre-denominated
fields are used, straight from source, same policy as the CSV survey
data.

## Not fetched — no public mirror found (searched, not just assumed)

Searched GitHub code/repo search for the remaining VOLVE-field
wellbores; found nothing for: `15/9-F-1`, `15/9-F-1 A`, `15/9-F-9`
(base), `15/9-F-10 A`, `15/9-F-10 B`, `15/9-F-11` (base), `15/9-F-11 A`
(already covered by the CSV survey, see `data/volve/README.md`),
`15/9-F-11 B`, `15/9-F-15` (base), `15/9-F-15 A`, `15/9-F-15 B`,
`15/9-F-15 D`, and all five `15/9-19 *` exploration wellbores. These
remain without survey coverage in this round — not fabricated.
