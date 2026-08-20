import datetime as dt

from src.evaluation.models import CoherenceCheck, QueryLog


def _synthetic_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2026, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.5} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def test_indicator_value_endpoint_does_not_log_or_explain(client, monkeypatch):
    """RF-02.2 / CU-03: `/api/indicador/valor` es la via ligera del dashboard.

    Devuelve el valor + trazabilidad (fuente, extracted_at, indicador literal)
    sin correr FinBERT ni escribir `query_logs` ni `coherence_checks`. Es lo
    que permite que cada `QueryLog` corresponda a una consulta deliberada
    (click en "Ver explicacion en simple") y no a un batch automatico.
    """
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    with client.application.app_context():
        logs_before = QueryLog.query.count()
        checks_before = CoherenceCheck.query.count()

    response = client.get("/api/indicador/valor?symbol=SQM-B.SN&indicator=rsi&days=90")
    assert response.status_code == 200
    data = response.get_json()

    assert data["symbol"] == "SQM-B.SN"
    assert data["indicator"] == "rsi"
    assert data["indicator_label"] == "Índice de Fuerza Relativa (RSI)"
    assert data["source"] == "Yahoo Finance"
    assert data["extracted_at"]
    assert data["period_days"] == 90
    assert isinstance(data["value"], (int, float))
    assert data["risk_level"] in ("bajo", "medio", "alto")
    assert "explanation" not in data  # deliberadamente NO se genera texto

    with client.application.app_context():
        assert QueryLog.query.count() == logs_before  # no persiste
        assert CoherenceCheck.query.count() == checks_before


def test_indicator_value_endpoint_rejects_bad_indicator(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    r = client.get("/api/indicador/valor?symbol=SQM-B.SN&indicator=inventado&days=90")
    assert r.status_code == 502
    assert "error" in r.get_json()


def test_full_query_flow_logs_and_returns_explanation(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    response = client.post(
        "/api/query",
        json={"symbol": "SQM-B.SN", "indicator": "macd", "days": 90},
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
        "/api/query", json={"symbol": "SPY", "indicator": "bandas_bollinger", "days": 90}
    ).get_json()

    second = client.post(
        "/api/regenerate",
        json={"symbol": "SPY", "indicator": "bandas_bollinger", "days": 90, "previous_variant": first["variant"]},
    ).get_json()

    assert "explanation" in second


def test_query_with_invalid_indicator_returns_friendly_error(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _synthetic_history)
    response = client.post("/api/query", json={"symbol": "SPY", "indicator": "no_existe", "days": 90})
    assert response.status_code == 502
    assert "error" in response.get_json()
