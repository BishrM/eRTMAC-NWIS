"""Parse WITSML 1.4.1.1 directional-survey trajectory XML into
SurveyStation lists — the same target shape as ingestion/volve.py's CSV
parser, since both are Volve directional-survey data, just two different
real export formats.

Source: real Volve WITSML trajectory exports, confirmed against actual
files pulled from three independent public mirrors of the same Equinor
Volve disclosure (see data/volve/witsml/README.md for exact provenance).
A `<trajectorys>` root holds one or more `<trajectory>` elements, each
one wellbore's directional survey as a series of `<trajectoryStation>`
elements. Real files use two different wellbore-naming conventions:

    <nameWellbore>NO 15/9-F-9 A</nameWellbore>            (country prefix)
    <nameWellbore>15/9-F-10 - Main Wellbore</nameWellbore> (main-bore marker)

Both are cleaned by ingestion.identifiers.witsml_identifier_from_name
before canonical-key matching — never by reconstructing a name from the
filename, which real data shows is unreliable (e.g. a file named
"9-F-1 C.xml" actually contains wellbore "15/9-F-1 B").

Per the Volve audit, real stations already supply computed TVD/dispNs/
dispEw — we use those directly (md, tvd, dispNs, dispEw) and do not
reconstruct a trajectory from incl/azi ourselves. incl/azi/dls/etc. are
present in real files but not read here.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from ingestion.identifiers import WellboreIdentifier, witsml_identifier_from_name
from ingestion.schemas import IngestionIssue, SurveyStation, VolveSurveyIngestionResult
from ingestion.validators import required_float

_NS = {"w": "http://www.witsml.org/schemas/1series"}

# Real files consistently report md/tvd/dispNs/dispEw in metres. We trust
# only that unit — a file reporting something else is a hard error rather
# than a silent unit conversion we haven't verified against real data.
_EXPECTED_UOM = "m"


def _station_value(
    station: ET.Element, tag: str, field_name: str, issues: list[IngestionIssue]
) -> float | None:
    el = station.find(f"w:{tag}", _NS)
    if el is None or el.text is None:
        issues.append(IngestionIssue(field_name, "required field is missing", "error"))
        return None
    uom = el.get("uom")
    if uom != _EXPECTED_UOM:
        issues.append(
            IngestionIssue(
                field_name, f"expected uom={_EXPECTED_UOM!r}, got {uom!r} — not converted", "error"
            )
        )
        return None
    return required_float(el.text, field_name, issues, min_value=None)


def _parse_trajectory_element(
    trajectory: ET.Element,
) -> VolveSurveyIngestionResult:
    name_el = trajectory.find("w:nameWellbore", _NS)
    if name_el is None or not (name_el.text or "").strip():
        raise ValueError("<trajectory> element has no <nameWellbore>")

    identifier: WellboreIdentifier = witsml_identifier_from_name(name_el.text)

    stations: list[SurveyStation] = []
    issues: list[IngestionIssue] = []
    previous_md: float | None = None

    for i, station in enumerate(trajectory.findall("w:trajectoryStation", _NS)):
        row_issues: list[IngestionIssue] = []
        md = _station_value(station, "md", "MD", row_issues)
        tvd = _station_value(station, "tvd", "TVD", row_issues)
        ns = _station_value(station, "dispNs", "NS", row_issues)
        ew = _station_value(station, "dispEw", "EW", row_issues)

        if md is not None and previous_md is not None and md < previous_md:
            row_issues.append(
                IngestionIssue(
                    "MD", f"station {i}: MD {md} is less than previous station's {previous_md}", "warning"
                )
            )

        issues.extend(row_issues)
        if any(iss.severity == "error" for iss in row_issues) or None in (md, tvd, ns, ew):
            continue

        stations.append(SurveyStation(md_m=md, tvd_m=tvd, ns_m=ns, ew_m=ew))
        previous_md = md

    # Defensive, same as volve.py: downstream trajectory geometry assumes
    # MD order even though out-of-order input is only a warning above.
    stations.sort(key=lambda s: s.md_m)

    return VolveSurveyIngestionResult(
        source_identifier=identifier.raw,
        canonical_key=identifier.canonical_key,
        stations=stations,
        issues=issues,
    )


def parse_witsml_trajectory_xml(path: str | Path) -> list[VolveSurveyIngestionResult]:
    """One result per <trajectory> element in the file (real files inspected
    so far have exactly one, but the WITSML schema allows more)."""
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()

    trajectories = root.findall("w:trajectory", _NS)
    if not trajectories:
        raise ValueError(f"{path}: no <trajectory> element found (not a WITSML trajectory file?)")

    return [_parse_trajectory_element(t) for t in trajectories]
