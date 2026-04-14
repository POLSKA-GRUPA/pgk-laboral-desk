def test_list_convenios(client, auth_headers):
    resp = client.get("/api/convenios", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
