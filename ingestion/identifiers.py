"""Cross-source wellbore identifier matching.

Confirmed by the Volve audit (ingestion/VOLVE_AUDIT.md): the same
wellbore is spelled differently across sources —

    SODIR wlbWellboreName   "15/9-F-11 A"
    Volve filename           "15_9_F_11_A"   (every separator -> '_')
    WITSML header            "NO 15/9-F-11 A"

Trying to reconstruct one spelling from another by guessing where the
'/' vs '-' vs ' ' go is ambiguous and was a real bug in an earlier
version of this module. Instead, every identifier is reduced to a
deterministic canonical key (letters/digits only, uppercased) and
matching is done on that key. The *original* identifier string is
always kept alongside the key so provenance is never lost.
"""

import re
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def canonical_wellbore_key(raw: str) -> str:
    """"15/9-F-11 A", "15_9_F_11_A" and "NO 15/9-F-11 A" all -> "159F11A"."""
    return _NON_ALNUM.sub("", raw).upper()


@dataclass(frozen=True)
class WellboreIdentifier:
    """An identifier as found in some source, plus its canonical key.

    `source` is preserved so provenance is explicit (e.g. "volve",
    "sodir") — see NormalizedWellbore.volve_source_id / Wellbore.source.
    """

    raw: str
    source: str

    @property
    def canonical_key(self) -> str:
        return canonical_wellbore_key(self.raw)


def volve_identifier_from_filename(filename: str) -> WellboreIdentifier:
    """"15_9_F_11_A_Survey_Data.csv" -> WellboreIdentifier("15_9_F_11_A", "volve").

    Deliberately does *not* try to turn '_' back into '/' or '-' — see
    module docstring. The raw identifier is kept exactly as found in
    the filename.
    """
    stem = filename
    for suffix in (".csv", ".CSV"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for marker in ("_Survey_Data", "_survey_data"):
        if stem.endswith(marker):
            stem = stem[: -len(marker)]
            break
    return WellboreIdentifier(raw=stem, source="volve")
