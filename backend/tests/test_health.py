def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"status", "database", "qdrant"}
    assert body["database"] == "ok"
    # Qdrant may or may not be reachable depending on the environment;
    # just assert the field is populated with a known value.
    assert body["qdrant"] in {"ok", "error"}
