"""El sistema registra de donde sale cada texto: LLM o plantilla, y por que no fue el LLM."""

import logging

import pytest

from src.nlp import explainer
from src.nlp.llm_explainer import LLMError

RSI = {"indicator": "rsi", "value": 46.59, "risk_level": "medio", "signal": "neutral", "symbol": "BCI.SN"}
BUEN_TEXTO = "El RSI de BCI marca 46.59 (riesgo medio): zona neutral, sin presión fuerte hacia ningún lado."


def _generar(**kw):
    return explainer.generate_explanation(RSI, use_finbert=False, detail_level="intermedio", **kw)


def _llm_devuelve(monkeypatch, texto):
    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", lambda *a, **k: texto)


def test_con_el_llm_apagado_el_origen_es_plantilla_desactivado():
    r = _generar(use_llm=False, llm_api_key="clave")
    assert (r["source"], r["fallback_reason"]) == ("plantilla", "desactivado")


def test_sin_clave_el_origen_es_plantilla_sin_clave():
    r = _generar(use_llm=True, llm_api_key="")
    assert (r["source"], r["fallback_reason"]) == ("plantilla", "sin_clave")


def test_un_texto_valido_del_llm_se_registra_como_llm(monkeypatch):
    _llm_devuelve(monkeypatch, BUEN_TEXTO)
    r = _generar(use_llm=True, llm_api_key="clave")
    assert r["text"] == BUEN_TEXTO
    assert (r["source"], r["fallback_reason"]) == ("llm", None)


@pytest.mark.parametrize(
    "texto,motivo",
    [
        ("El RSI de BCI marca 46.59: zona neutral.", "sin_etiqueta_riesgo"),
        ("El RSI de BCI marca riesgo medio: zona neutral.", "sin_valor"),
        ("El RSI de BCI marca 46.59 (riesgo medio): hay sobrecompra clara.", "incoherente"),
    ],
)
def test_un_texto_rechazado_cae_a_plantilla_con_su_motivo(monkeypatch, texto, motivo):
    _llm_devuelve(monkeypatch, texto)
    r = _generar(use_llm=True, llm_api_key="clave")
    assert r["text"] != texto
    assert (r["source"], r["fallback_reason"]) == ("plantilla", motivo)


def test_el_termino_prohibido_del_nivel_basico_cae_a_plantilla(monkeypatch):
    _llm_devuelve(monkeypatch, "El RSI de BCI marca 46.59 (riesgo medio), sin momentum.")
    r = explainer.generate_explanation(RSI, use_finbert=False, detail_level="basico", use_llm=True, llm_api_key="clave")
    assert (r["source"], r["fallback_reason"]) == ("plantilla", "termino_prohibido")


def test_un_error_de_la_api_cae_a_plantilla_y_no_filtra_la_clave(monkeypatch, caplog):
    def falla(*a, **k):
        raise LLMError("Error al llamar a Groq: 401 con la clave gsk_SECRETA")

    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", falla)
    with caplog.at_level(logging.INFO):
        r = _generar(use_llm=True, llm_api_key="gsk_SECRETA")
    assert (r["source"], r["fallback_reason"]) == ("plantilla", "error_api")
    assert "gsk_SECRETA" not in caplog.text


def test_un_error_inesperado_tampoco_tumba_la_consulta(monkeypatch):
    def rompe(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", rompe)
    r = _generar(use_llm=True, llm_api_key="clave")
    assert (r["source"], r["fallback_reason"]) == ("plantilla", "error_interno")


def test_regenerar_conserva_el_origen(monkeypatch):
    _llm_devuelve(monkeypatch, BUEN_TEXTO)
    r = explainer.regenerate_explanation(RSI, 0, use_finbert=False, detail_level="intermedio", use_llm=True, llm_api_key="clave")
    assert r["source"] == "llm" and r["variant"] == 1


def test_la_consulta_guarda_el_origen_y_lo_devuelve(app, client, monkeypatch):
    import datetime as dt

    def historia(symbol, days, alpha_vantage_key=""):
        start = dt.date(2025, 1, 1)
        records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.3} for i in range(days)]
        return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}

    monkeypatch.setattr("src.extractor.fetch_price_history", historia)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    app.config.update(USE_LLM=False)
    data = client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}).get_json()
    assert data["explanation_source"] == "plantilla"

    from src.profile.models import QueryLog

    with app.app_context():
        fila = QueryLog.query.one()
        assert (fila.explanation_source, fila.fallback_reason) == ("plantilla", "desactivado")
