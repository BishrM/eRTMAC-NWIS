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

# WITSML headers prefix the well name with a country code, e.g.
# "NO 15/9-F-11 A" (confirmed against real Volve WITSML trajectory files —
# see ingestion/witsml.py). Stripped before the alnum-only reduction below
# so it matches the same wellbore's SODIR/Volve-CSV spelling, per this
# function's own documented contract (next line).
_LEADING_COUNTRY_PREFIX = re.compile(r"^\s*NO\s+", re.IGNORECASE)


def canonical_wellbore_key(raw: str) -> str:
    """"15/9-F-11 A", "15_9_F_11_A" and "NO 15/9-F-11 A" all -> "159F11A"."""
    return _NON_ALNUM.sub("", _LEADING_COUNTRY_PREFIX.sub("", raw)).upper()


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


# Some real Volve WITSML trajectory exports (confirmed against actual
# files, not guessed) suffix the primary (non-sidetrack) wellbore's
# <nameWellbore> with a literal, consistent marker rather than a sidetrack
# letter/leg — e.g. "15/9-F-10 - Main Wellbore". Sidetracks from the same
# source use their own real suffix (e.g. "T2", " A") and are left alone;
# only this one confirmed literal marker is stripped.
_WITSML_MAIN_WELLBORE_SUFFIX = re.compile(r"\s*-\s*Main Wellbore\s*$", re.IGNORECASE)


def witsml_identifier_from_name(name_wellbore: str) -> WellboreIdentifier:
    """"NO 15/9-F-11 T2" -> WellboreIdentifier("15/9-F-11 T2", "volve_witsml");
    "15/9-F-10 - Main Wellbore" -> WellboreIdentifier("15/9-F-10", "volve_witsml").

    Input is a WITSML <nameWellbore> element's text content, not a
    filename (real WITSML mirrors name files arbitrarily — see
    ingestion/witsml.py). The "NO " country-code prefix is left for
    canonical_wellbore_key to strip; only the "- Main Wellbore" marker
    (not part of that function's contract) is stripped here.
    """
    cleaned = _WITSML_MAIN_WELLBORE_SUFFIX.sub("", name_wellbore.strip())
    return WellboreIdentifier(raw=cleaned, source="volve_witsml")
