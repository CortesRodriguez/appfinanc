import datetime as dt


def _fake_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2025, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.3} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def _fake_batch(symbols, days=5, max_retries=2):
    return {s: {"price": 100.5, "daily_change_pct": 1.2} for s in symbols}


def test_quotes_returns_all_catalog_instruments(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_batch_quotes", _fake_batch)
    from src.extractor import quotes_cache

    quotes_cache.clear()

    response = client.get("/api/quotes")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) > 20  # catalogo ampliado
    assert all("price" in row and "daily_change_pct" in row for row in data)


def test_quotes_degrades_gracefully_when_batch_fails(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_batch_quotes", lambda symbols, **_: {s: None for s in symbols})
    from src.extractor import quotes_cache

    quotes_cache.clear()

    response = client.get("/api/quotes")
    assert response.status_code == 200
    data = response.get_json()
    assert all(row["price"] is None for row in data)


def test_chart_returns_price_and_ma_series(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    response = client.get("/api/chart?symbol=SQM-B.SN&days=365")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["close"]) == len(data["dates"])
    assert len(data["sma_short"]) == len(data["close"])
    assert len(data["sma_long"]) == len(data["close"])


def test_lookup_finds_symbol_not_in_catalog(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    response = client.get("/api/lookup?symbol=AAPL")
    assert response.status_code == 200
    assert response.get_json()["symbol"] == "AAPL"


def test_lookup_returns_404_for_unknown_symbol(client, monkeypatch):
    from src.extractor.sources import DataSourceError

    def _fail(symbol, days, alpha_vantage_key=""):
        raise DataSourceError("simbolo invalido")

    monkeypatch.setattr("src.extractor.fetch_price_history", _fail)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    response = client.get("/api/lookup?symbol=NOEXISTE123")
    assert response.status_code == 404


def test_session_cookie_is_established_on_first_page_load(client):
    """La cookie de sesion debe quedar fijada desde la primera carga de
    pagina (before_app_request), antes de que el dashboard dispare
    llamadas en paralelo. Si esto no se cumple, varias peticiones
    concurrentes pueden crear "sid" al mismo tiempo y pisarse entre si,
    perdiendo escrituras de sesion como el historial (RF-10)."""
    response = client.get("/")
    assert client.get_cookie("session") is not None
    assert response.status_code == 200


def test_log_visit_creates_exactly_one_row_per_instrument(client):
    """Selecciona dos instrumentos distintos: debe quedar exactamente una
    fila de historial por cada uno (RF-10), sin duplicados ni filas de mas."""
    r1 = client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"})
    assert r1.status_code == 200

    r2 = client.post("/api/historial/visita", json={"symbol": "FALABELLA.SN"})
    assert r2.status_code == 200

    hist = client.get("/history")
    body = hist.data.decode()
    assert body.count("SQM-B.SN") == 1
    assert body.count("FALABELLA.SN") == 1


def test_log_visit_lists_instrument_in_history(client):
    """/api/historial/visita registra la visita al instrumento (RF-10).
    La pagina /history la muestra en la seccion "Instrumentos visitados".
    """
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"})
    hist = client.get("/history")
    body = hist.data.decode()
    assert "SQM-B.SN" in body
    assert "Instrumentos visitados" in body


def _fake_macro(max_retries=2):
    return {
        "uf": {"label": "UF", "value": 40844.79, "date": "2026-08-04"},
        "dolar": {"label": "Dólar", "value": 924.89, "date": "2026-08-04"},
        "tpm": {"label": "TPM", "value": 4.75, "date": "2026-08-04"},
        "ipc": {"label": "IPC", "value": 0.4, "date": "2026-08-04"},
    }


def test_ticker_includes_macro_and_all_catalog_instruments(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_batch_quotes", _fake_batch)
    monkeypatch.setattr("src.extractor.fetch_macro_indicators", _fake_macro)
    from src.extractor import macro_cache, quotes_cache

    quotes_cache.clear()
    macro_cache.clear()

    response = client.get("/api/ticker")
    assert response.status_code == 200
    items = response.get_json()

    labels = [item["label"] for item in items]
    assert "IPSA" in labels
    assert "UF" in labels
    assert "Dólar" in labels
    assert "SQM-B" in labels  # ".SN" se quita para mostrar solo el ticker
    assert len([i for i in items if i["kind"] == "instrument"]) >= 30


def test_ticker_degrades_gracefully_when_macro_source_fails(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_batch_quotes", _fake_batch)
    monkeypatch.setattr("src.extractor.fetch_macro_indicators", lambda **_: {})
    from src.extractor import macro_cache, quotes_cache

    quotes_cache.clear()
    macro_cache.clear()

    response = client.get("/api/ticker")
    assert response.status_code == 200
    items = response.get_json()
    assert any(item["label"] == "IPSA" for item in items)  # sigue viniendo de Yahoo, no de mindicador.cl


def test_query_records_traceability_in_session_history(client, monkeypatch):
    """RF-02.2 / CU-03: cada `/api/query` (consulta deliberada de un
    indicador con explicacion) queda registrada en el historial de sesion
    con la trazabilidad completa — indicador literal, fuente, extraccion y
    marca de consulta. La pagina /history la renderiza en formato legible.
    """
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180})

    body = client.get("/history").data.decode()
    # Debe aparecer el nombre literal del indicador y el simbolo consultado
    assert "SQM-B.SN" in body
    assert "Índice de Fuerza Relativa (RSI)" in body
    # Y no debe mostrar el mensaje de "aun no has realizado consultas"
    assert "Aún no has realizado consultas" not in body
