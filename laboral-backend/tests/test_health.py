def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_health_has_version(client):
    resp = client.get("/api/health")
    data = resp.json()
    assert "version" in data
