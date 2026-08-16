import datetime as dt


def _fake_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2025, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.3} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def _register_and_login(client, email="perfil@test.cl"):
    client.post("/api/auth/registro", json={"username": "Perfil", "email": email, "password": "12345678"})
    return client.get_cookie("csrf_access_token").value


def test_authenticated_visit_is_attributed_to_user_profile(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client)
    headers = {"X-CSRF-TOKEN": csrf}

    # Seleccionar un instrumento en el dashboard = una visita, aunque por
    # detras dispare cuatro consultas (una por indicador) via /api/query.
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    for indicator in ("volatilidad", "rsi", "medias_moviles", "rentabilidad"):
        client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": indicator, "days": 180}, headers=headers)

    response = client.get("/api/perfil", headers=headers)
    data = response.get_json()
    assert data["total_queries"] == 1  # 1 visita, no 4 (RF-19.3 no debe inflarse por indicador)
    assert data["top_instruments"][0]["instrument"] == "SQM-B.SN"
    assert data["top_instruments"][0]["count"] == 1


def test_total_queries_counts_visits_plus_explicit_regenerations(client, monkeypatch):
    """Reproduce el reporte del usuario: seleccionar un instrumento (que
    dispara 4 consultas de indicador detras de escena) y pedir 'No
    entendi esto' una vez debe sumar 2 al total, no 5."""
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="totales@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    results = {}
    for indicator in ("volatilidad", "rsi", "medias_moviles", "rentabilidad"):
        results[indicator] = client.post(
            "/api/query", json={"symbol": "SQM-B.SN", "indicator": indicator, "days": 180}, headers=headers
        ).get_json()

    client.post(
        "/api/regenerate",
        json={
            "symbol": "SQM-B.SN",
            "indicator": "rsi",
            "days": 180,
            "previous_variant": results["rsi"]["variant"],
        },
        headers=headers,
    )

    profile = client.get("/api/perfil", headers=headers).get_json()
    assert profile["total_queries"] == 2


def test_regeneration_count_identifies_hardest_indicator(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="hard@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )
    client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rentabilidad", "days": 180}, headers=headers
    )

    profile = client.get("/api/perfil", headers=headers).get_json()
    assert profile["top_indicator"] == "rsi"
    assert profile["top_indicator_regenerations"] == 1
    assert profile["top_indicator_explanation"]


def test_queries_without_login_are_not_attributed_to_any_profile(client, monkeypatch, app):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    client.post("/api/query", json={"symbol": "SPY", "indicator": "rsi", "days": 180})

    from src.evaluation.models import QueryLog

    with app.app_context():
        log = QueryLog.query.order_by(QueryLog.id.desc()).first()
        assert log.user_id is None


def test_profile_regenerate_requires_previous_activity(client):
    csrf = _register_and_login(client, email="empty@test.cl")
    response = client.post("/api/perfil/regenerar", headers={"X-CSRF-TOKEN": csrf})
    assert response.status_code == 404


def test_profile_regenerate_produces_new_explanation(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="regen@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    # El perfil solo identifica un "indicador mas dificil" una vez que el
    # usuario ha pedido regenerar al menos una explicacion (RF-19.1).
    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )

    response = client.post("/api/perfil/regenerar", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["indicator"] == "rsi"
    assert data["explanation"]
