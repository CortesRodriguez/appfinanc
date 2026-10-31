"""Fija el comportamiento de los tres flujos que comparten "indicador -> explicacion -> log":
/api/query, /api/regenerate y /api/perfil/regenerar. Cubre sobre todo las ramas de error."""

import datetime as dt

from src.extractor.sources import DataSourceError


def _fake_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2025, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.3} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def _failing_history(symbol, days, alpha_vantage_key=""):
    raise DataSourceError("fuente caida")


def _login(client, email="flujo@test.cl"):
    client.post(
        "/api/auth/registro",
        json={"username": "Flujo", "email": email, "password": "Clave123!", "password_confirm": "Clave123!"},
    )
    return {"X-CSRF-TOKEN": client.get_cookie("csrf_access_token").value}


def _prepare(monkeypatch, history=_fake_history):
    monkeypatch.setattr("src.extractor.fetch_price_history", history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()


def _log_count(app):
    from src.profile.models import QueryLog

    with app.app_context():
        return QueryLog.query.count()


def test_query_response_has_the_documented_fields(client, monkeypatch):
    _prepare(monkeypatch)
    data = client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}).get_json()
    for key in (
        "symbol", "indicator", "indicator_label", "value", "unit", "risk_level", "source",
        "extracted_at", "processing_time_ms", "explanation", "variant", "detail_level",
        "coherent", "readability_score", "finbert_signal", "trend", "signal",
    ):
        assert key in data, key


def test_query_returns_502_and_writes_nothing_when_source_fails(client, monkeypatch, app):
    _prepare(monkeypatch, _failing_history)
    response = client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180})
    assert response.status_code == 502
    assert response.get_json()["error"]
    assert _log_count(app) == 0


def test_query_returns_502_and_writes_nothing_when_value_is_nan(client, monkeypatch, app):
    _prepare(monkeypatch)
    nan = float("nan")
    monkeypatch.setattr(
        "src.services.query_service.get_indicator",
        lambda *a, **k: {
            "indicator": "rsi", "value": nan, "unit": "", "risk_level": "medio", "source": "Yahoo Finance",
            "extracted_at": "2026-01-01T00:00:00+00:00", "period_days": 180, "symbol": "SQM-B.SN",
        },
    )
    response = client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180})
    assert response.status_code == 502
    assert "datos suficientes" in response.get_json()["error"]
    assert _log_count(app) == 0


def test_regenerate_response_has_the_documented_fields_and_logs_a_regeneration(client, monkeypatch, app):
    _prepare(monkeypatch)
    first = client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}).get_json()
    response = client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
    )
    assert response.status_code == 200
    data = response.get_json()
    for key in (
        "symbol", "indicator", "indicator_label", "value", "unit", "risk_level", "trend", "signal",
        "explanation", "variant", "detail_level", "coherent", "finbert_signal", "unchanged",
    ):
        assert key in data, key
    assert data["variant"] != first["variant"]
    assert data["unchanged"] is False

    from src.profile.models import QueryLog

    with app.app_context():
        assert QueryLog.query.filter_by(is_regeneration=True).count() == 1


def test_regenerate_rejects_non_numeric_params(client, monkeypatch):
    _prepare(monkeypatch)
    response = client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": "abc", "previous_variant": 0},
    )
    assert response.status_code == 400


def test_regenerate_returns_502_when_source_fails(client, monkeypatch, app):
    _prepare(monkeypatch, _failing_history)
    response = client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": 0},
    )
    assert response.status_code == 502
    assert _log_count(app) == 0


def test_profile_regenerate_returns_502_when_source_fails(client, monkeypatch, app):
    _prepare(monkeypatch)
    headers = _login(client)
    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )
    before = _log_count(app)

    _prepare(monkeypatch, _failing_history)  # la fuente cae justo antes de pedir el resumen
    response = client.post("/api/perfil/regenerar", headers=headers)
    assert response.status_code == 502
    assert _log_count(app) == before


def test_profile_regenerate_always_uses_a_180_day_window(app, client, monkeypatch):
    _prepare(monkeypatch)
    headers = _login(client, email="ventana@test.cl")
    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 90}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 90, "previous_variant": first["variant"]},
        headers=headers,
    )

    assert client.post("/api/perfil/regenerar", headers=headers).status_code == 200

    from src.profile.models import QueryLog

    with app.app_context():
        last = QueryLog.query.order_by(QueryLog.id.desc()).first()
        # La ventana del perfil es fija (decision de producto), distinta de la del dashboard (90).
        assert last.period_days == 180
