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
