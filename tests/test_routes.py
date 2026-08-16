import datetime as dt

from src.evaluation.models import CoherenceCheck, QueryLog


def _synthetic_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2026, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.5} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def test_full_query_flow_logs_and_returns_explanation(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    response = client.post(
        "/api/query",
        json={"symbol": "SQM-B.SN", "indicator": "rentabilidad", "days": 90},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["symbol"] == "SQM-B.SN"
    assert data["source"] == "Yahoo Finance"
    assert data["explanation"]
    assert data["risk_level"] in ("bajo", "medio", "alto")

    with client.application.app_context():
        assert QueryLog.query.count() == 1
        assert CoherenceCheck.query.count() == 1

    # El historial (RF-10) ya no se registra dentro de /api/query (ver
    # /api/historial/visita): el dashboard lo llama por separado, una vez
    # por instrumento seleccionado, para evitar la condicion de carrera de
    # cuatro consultas paralelas escribiendo la misma cookie de sesion.
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"})
    hist = client.get("/history")
    assert b"SQM-B.SN" in hist.data


def test_regenerate_returns_alternative_text(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    first = client.post(
        "/api/query", json={"symbol": "SPY", "indicator": "volatilidad", "days": 90}
    ).get_json()

    second = client.post(
        "/api/regenerate",
        json={"symbol": "SPY", "indicator": "volatilidad", "days": 90, "previous_variant": first["variant"]},
    ).get_json()

    assert "explanation" in second


def test_query_with_invalid_indicator_returns_friendly_error(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    response = client.post("/api/query", json={"symbol": "SPY", "indicator": "no_existe", "days": 90})
    assert response.status_code == 502
    assert "error" in response.get_json()
