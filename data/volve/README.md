# Volve survey sample

`15_9_F_11_A_Survey_Data.csv` — one real Volve directional survey (323
stations, wellbore `15/9-F-11 A`), for the Volve trajectory-ingestion
sanity check. Not committed (`data/*` is gitignored) — this README
documents provenance.

- **Source**: a public research mirror of the original Equinor Volve
  disclosure —
  `raw.githubusercontent.com/jczettl/wellbore-trajectory-uncertainty/main/data/15_9_F_11_A.csv`
  (MIT-licensed repo; its README states the file is "Volve survey with
  MD, inclination, azimuth, and supplied TVD/North/East coordinates").
  This is **not** the official Volve access path — see
  `ingestion/VOLVE_AUDIT.md` for why (the original 2018–2022 Azure
  container has expired; official access is now the Databricks
  Marketplace "Volve Data Village" listing, which needs an account).
  Used here only because it is the same, real, already-published data
  for a single well, small enough to inspect without that access.
- **Fetched**: 2026-09-24.
- **License**: Equinor Open Data Licence (the underlying data);
  MIT (the mirror repo itself).
- **Cross-check**: this file's max MD (3762.0 m) matches exactly
  SODIR's `wlbTotalDepth` for wellbore `15/9-F-11 A` (npdid 7079,
  `data/sodir/wellbore_volve_field.csv`) — confirms the identifier
  match (`ingestion/identifiers.py`) is correct for this well.
