def test_simulate_basic(client, auth_headers):
    resp = client.post(
        "/api/simulate",
        headers=auth_headers,
        json={
            "category": "Nivel B.",
            "contract_type": "indefinido",
            "weekly_hours": 40,
            "region": "madrid",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["coste_total_empresa_mes_eur"] > 0
    assert data["salario_bruto_mensual"] > 0
