from pathlib import Path

import pytest

from ingestion.identifiers import canonical_wellbore_key, witsml_identifier_from_name
from ingestion.witsml import parse_witsml_trajectory_xml

FIXTURES = Path(__file__).parent / "fixtures"
COUNTRY_PREFIX = FIXTURES / "witsml_trajectory_country_prefix.xml"
MAIN_WELLBORE = FIXTURES / "witsml_trajectory_main_wellbore.xml"
UNMATCHED_SIDETRACK = FIXTURES / "witsml_trajectory_unmatched_sidetrack.xml"


# --- identifier cleaning -----------------------------------------------------


def test_witsml_identifier_preserves_country_prefix_in_raw():
    # The "NO " prefix is left for canonical_wellbore_key to strip, not
    # removed here — raw is provenance, not yet a matching key.
    identifier = witsml_identifier_from_name("NO 15/9-F-11 A")
    assert identifier.raw == "NO 15/9-F-11 A"
    assert identifier.source == "volve_witsml"
    assert canonical_wellbore_key(identifier.raw) == "159F11A"


def test_witsml_identifier_strips_main_wellbore_suffix():
    identifier = witsml_identifier_from_name("15/9-F-10 - Main Wellbore")
    assert identifier.raw == "15/9-F-10"
    assert identifier.canonical_key == "159F10"


def test_witsml_identifier_leaves_sidetrack_suffixes_alone():
    identifier = witsml_identifier_from_name("NO 15/9-F-11 T2")
    assert identifier.raw == "NO 15/9-F-11 T2"
    assert identifier.canonical_key == "159F11T2"


# --- trajectory XML parsing ---------------------------------------------------


def test_parses_stations_using_md_tvd_dispns_dispew():
    results = parse_witsml_trajectory_xml(COUNTRY_PREFIX)
    assert len(results) == 1
    result = results[0]

    assert result.ok
    assert result.source_identifier == "NO 15/9-F-11"
    assert result.canonical_key == "159F11"
    assert len(result.stations) == 3

    first, last = result.stations[0], result.stations[-1]
    assert first.md_m == 0
    assert first.tvd_m == 0
    assert last.md_m == 500.0
    assert last.tvd_m == 497.2
    assert last.ns_m == 12.3
    assert last.ew_m == -6.1
    assert result.issues == []


def test_main_wellbore_suffix_file_matches_same_canonical_key_as_country_prefix_file():
    # Two different real WITSML naming conventions for the *same* primary
    # wellbore must resolve to the same canonical key.
    country_prefix = parse_witsml_trajectory_xml(COUNTRY_PREFIX)[0]
    main_wellbore = parse_witsml_trajectory_xml(MAIN_WELLBORE)[0]
    assert country_prefix.canonical_key == main_wellbore.canonical_key == "159F11"


def test_unmatched_sidetrack_parses_but_has_a_key_no_sodir_wellbore_shares():
    # "T2" is a real WITSML technical sidetrack not present in SODIR's
    # 27-row VOLVE-field wellbore list — parsing must still succeed (it's
    # valid survey data), matching is loaders.py's job, not the parser's.
    result = parse_witsml_trajectory_xml(UNMATCHED_SIDETRACK)[0]
    assert result.ok
    assert result.canonical_key == "159F11T2"
    assert result.canonical_key != canonical_wellbore_key("15/9-F-11")
    assert result.canonical_key != canonical_wellbore_key("15/9-F-11 A")


def test_incl_azi_columns_are_ignored_not_required(tmp_path):
    minimal = tmp_path / "minimal.xml"
    minimal.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <trajectory uid="T1">
    <nameWellbore>15/9-F-4</nameWellbore>
    <trajectoryStation uid="S0">
      <md uom="m">0</md>
      <tvd uom="m">0</tvd>
      <dispNs uom="m">0</dispNs>
      <dispEw uom="m">0</dispEw>
    </trajectoryStation>
    <trajectoryStation uid="S1">
      <md uom="m">400</md>
      <tvd uom="m">398</tvd>
      <dispNs uom="m">3</dispNs>
      <dispEw uom="m">-1</dispEw>
    </trajectoryStation>
  </trajectory>
</trajectorys>"""
    )
    result = parse_witsml_trajectory_xml(minimal)[0]
    assert result.ok
    assert len(result.stations) == 2


def test_missing_nameWellbore_raises(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <trajectory uid="T1">
    <trajectoryStation uid="S0">
      <md uom="m">0</md><tvd uom="m">0</tvd><dispNs uom="m">0</dispNs><dispEw uom="m">0</dispEw>
    </trajectoryStation>
  </trajectory>
</trajectorys>"""
    )
    with pytest.raises(ValueError, match="nameWellbore"):
        parse_witsml_trajectory_xml(bad)


def test_no_trajectory_element_raises(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1"></trajectorys>"""
    )
    with pytest.raises(ValueError, match="no <trajectory>"):
        parse_witsml_trajectory_xml(bad)


def test_unexpected_uom_is_rejected_not_converted(tmp_path):
    # A station reporting md in feet would silently corrupt the trajectory
    # if converted with the wrong factor — reject instead (task rule: no
    # fabricated/guessed data).
    bad = tmp_path / "bad.xml"
    bad.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <trajectory uid="T1">
    <nameWellbore>15/9-F-4</nameWellbore>
    <trajectoryStation uid="S0">
      <md uom="ft">0</md><tvd uom="m">0</tvd><dispNs uom="m">0</dispNs><dispEw uom="m">0</dispEw>
    </trajectoryStation>
  </trajectory>
</trajectorys>"""
    )
    result = parse_witsml_trajectory_xml(bad)[0]
    assert len(result.stations) == 0
    assert any(i.severity == "error" and i.field == "MD" for i in result.issues)


def test_non_monotonic_md_is_a_warning_and_stations_are_sorted(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <trajectory uid="T1">
    <nameWellbore>15/9-F-4</nameWellbore>
    <trajectoryStation uid="S0"><md uom="m">0</md><tvd uom="m">0</tvd><dispNs uom="m">0</dispNs><dispEw uom="m">0</dispEw></trajectoryStation>
    <trajectoryStation uid="S1"><md uom="m">500</md><tvd uom="m">498</tvd><dispNs uom="m">10</dispNs><dispEw uom="m">-5</dispEw></trajectoryStation>
    <trajectoryStation uid="S2"><md uom="m">300</md><tvd uom="m">299</tvd><dispNs uom="m">6</dispNs><dispEw uom="m">-3</dispEw></trajectoryStation>
  </trajectory>
</trajectorys>"""
    )
    result = parse_witsml_trajectory_xml(bad)[0]
    assert result.ok
    assert [s.md_m for s in result.stations] == [0, 300, 500]
    assert any(i.severity == "warning" and i.field == "MD" for i in result.issues)


def test_multiple_trajectory_elements_yield_multiple_results(tmp_path):
    multi = tmp_path / "multi.xml"
    multi.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <trajectory uid="T1">
    <nameWellbore>15/9-F-4</nameWellbore>
    <trajectoryStation uid="S0"><md uom="m">0</md><tvd uom="m">0</tvd><dispNs uom="m">0</dispNs><dispEw uom="m">0</dispEw></trajectoryStation>
  </trajectory>
  <trajectory uid="T2">
    <nameWellbore>15/9-F-5</nameWellbore>
    <trajectoryStation uid="S0"><md uom="m">0</md><tvd uom="m">0</tvd><dispNs uom="m">0</dispNs><dispEw uom="m">0</dispEw></trajectoryStation>
  </trajectory>
</trajectorys>"""
    )
    results = parse_witsml_trajectory_xml(multi)
    assert len(results) == 2
    assert {r.canonical_key for r in results} == {"159F4", "159F5"}
