# SODIR sample slice

`wellbore_exploration_sample.csv` — 26 real wellbore records, for a
real-data ingestion sanity check (not for production use, and not
committed — `data/*` is gitignored).

- **Source**: Norwegian Offshore Directorate FactPages, official CSV
  export endpoint —
  `https://factpages.sodir.no/public?/Factpages/external/tableview/wellbore_exploration_all&rs:Format=CSV&Top100=true`
  (the "Export: CSV" link on
  https://factpages.sodir.no/en/wellbore/tableview/exploration/all, with
  `Top100=true` for SODIR's own small/sample mode — SODIR returned ~300
  rows for that mode; this file is the first 25 of those plus one extra
  row (`2/5-14 A`, `STATUS=WILL NEVER BE DRILLED`) picked in because it
  exercises every nullable field at once.
- **Fetched**: 2026-09-24.
- **License**: NLOD 2.0 (Norwegian Licence for Open Government Data).
- **Real-data finding**: every row's `wlbGeodeticDatum` is `ED50`, not
  `WGS84` — confirmed against SODIR's own field docs
  (factpages.sodir.no/en/wellbore/Attributes: "wlbGeodeticDatum — ...
  Example of legal values: ED50"). This is the norm for SODIR wellbore
  positions, not an edge case, so `ingestion/sodir.py` now transforms
  ED50 → WGS84 (`ingestion/geodesy.py`) instead of dropping ED50 rows.

## wellbore_volve_field.csv

27 real wellbores (11 distinct wells) — every SODIR wellbore tied to
`wlbField == "VOLVE"`, for attaching the Volve directional-survey
ingestion sanity check to.

- **Source**: same official CSV export endpoint as above, both
  `wellbore_development_all` (22 rows) and `wellbore_exploration_all`
  (5 rows, the `15/9-19` discovery well and its sidetracks), with
  `Top100=false` (full table, filtered client-side to `wlbField ==
  "VOLVE"` — not a bulk ingestion of either full table).
- **Fetched**: 2026-09-24.
- **Real-data finding**: `wellbore_development_all` has no
  `wlbFormationAtTd` column at all (present only in
  `wellbore_exploration_all`) — a genuine schema difference between
  the two SODIR tables, not a missing value. `ingestion/sodir.py`
  already treats a missing column as an absent optional field via
  `dict.get`, so no parser change was needed.
- **Cross-check**: `15/9-F-11 A`'s `wlbTotalDepth` (3762.0 m) matches
  exactly the maximum MD in its real Volve survey file
  (`15_9_F_11_A.csv`, see `ingestion/VOLVE_AUDIT.md`) — good evidence
  the SODIR/Volve identifier match for this wellbore is correct.
