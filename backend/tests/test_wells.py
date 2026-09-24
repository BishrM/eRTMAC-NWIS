import pytest


def test_list_wells_empty(client):
    resp = client.get("/wells")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_wells_returns_created_well(client, make_well):
    well = make_well(well_id="DEMO-001", name="Demo Alpha")
    resp = client.get("/wells")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["well_id"] == "DEMO-001"
    assert item["name"] == "Demo Alpha"
    assert item["source"] == "demo"
    # location round-tripped through PostGIS
    assert item["longitude"] == pytest.approx(2.34)
    assert item["latitude"] == pytest.approx(58.44)


def test_get_well_by_well_id(client, make_well):
    make_well(well_id="DEMO-002", name="Demo Beta")
    resp = client.get("/wells/DEMO-002")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Demo Beta"


def test_get_well_with_slash_in_well_id(client, make_well):
    # Real SODIR/NPD well IDs contain '/' (e.g. "1/3-10") — the route must
    # use a :path converter, not the default single-segment matcher.
    make_well(well_id="1/3-10", name="Real-shaped ID")
    resp = client.get("/wells/1%2F3-10")
    assert resp.status_code == 200
    assert resp.json()["well_id"] == "1/3-10"


def test_get_well_not_found(client):
    resp = client.get("/wells/does-not-exist")
    assert resp.status_code == 404


def test_list_wells_pagination(client, make_well):
    for i in range(3):
        make_well(well_id=f"DEMO-P{i}", name=f"Demo Page {i}")
    resp = client.get("/wells", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0
