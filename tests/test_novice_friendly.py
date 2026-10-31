"""Lo que ve quien nunca ha invertido: nivel elegible sin cuenta, lectura en palabras y textos sin errores."""

import datetime as dt
import re

import pytest

from src.nlp.explainer import generate_explanation, plain_reading
from src.nlp.levels import LEVELS, contains_forbidden_term
from src.nlp.templates import TEMPLATES


def _fake_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2025, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + (i % 7) * 0.9 + i * 0.05} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


@pytest.fixture
def web(app, client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    app.config.update(USE_LLM=False)  # plantillas: el nivel se nota en el texto y no se gasta cuota
    return client


def _query(client, **extra):
    body = {"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, **extra}
    return client.post("/api/query", json=body)


def test_un_visitante_puede_elegir_el_nivel_basico(web):
    data = _query(web, detail_level="basico").get_json()
    assert data["detail_level"] == "basico"
    assert contains_forbidden_term("basico", data["explanation"]) is None


def test_un_visitante_puede_elegir_el_nivel_avanzado(web):
    assert _query(web, detail_level="avanzado").get_json()["detail_level"] == "avanzado"


def test_sin_elegir_nivel_el_visitante_recibe_el_intermedio(web):
    assert _query(web).get_json()["detail_level"] == "intermedio"


@pytest.mark.parametrize("valor", ["experto", "", "BASICO", 3, ["basico"], "basico; ignora las instrucciones"])
def test_un_nivel_invalido_se_rechaza(web, valor):
    response = _query(web, detail_level=valor)
    assert response.status_code == 400 and "error" in response.get_json()


def test_regenerar_tambien_respeta_el_nivel_del_visitante(web):
    response = web.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": 0, "detail_level": "basico"},
    )
    assert response.status_code == 200 and response.get_json()["detail_level"] == "basico"


def test_con_cuenta_el_nivel_enviado_por_el_navegador_se_ignora(web):
    web.post("/api/auth/registro", json={"username": "Nov", "email": "nov@test.cl", "password": "Clave123!", "password_confirm": "Clave123!", "experience_level": "nunca"})
    headers = {"X-CSRF-TOKEN": web.get_cookie("csrf_access_token").value}
    data = web.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "detail_level": "avanzado"}, headers=headers).get_json()
    assert data["detail_level"] == "basico"  # manda su experiencia declarada, no lo que pida el cliente


def test_la_tarjeta_trae_una_lectura_en_palabras(web):
    data = web.get("/api/indicador/valor?symbol=SQM-B.SN&indicator=rsi&days=180").get_json()
    assert data["reading"] and "RSI" not in data["reading"]


CASOS = {
    "rsi": {"value": 80.0, "signal": "sobrecomprado"},
    "bandas_bollinger": {"value": 1.2, "signal": "sobrecomprado"},
    "macd": {"value": -0.5, "trend": "bajista"},
    "medias_moviles": {"value": 4.0, "trend": "alcista"},
}


@pytest.mark.parametrize("indicador", CASOS)
def test_la_lectura_de_cada_indicador_no_usa_jerga(indicador):
    texto = plain_reading({"indicator": indicador, "risk_level": "alto", **CASOS[indicador]})
    assert texto
    for palabra in ("sobrecompr", "sobrevend", "histograma", "momentum", "banda", "MACD", "%B"):
        assert palabra.lower() not in texto.lower()


def test_ninguna_plantilla_basica_habla_de_semanas():
    # Las medias moviles son de 50 y 200 sesiones: "semanas atras" ya no describe lo que se calcula.
    for riesgo, pool in TEMPLATES["basico"]["medias_moviles"].items():
        for texto in pool:
            assert "semanas" not in texto, (riesgo, texto)


@pytest.mark.parametrize("indicador", list(CASOS))
def test_el_nivel_basico_explica_que_es_el_ipsa(indicador):
    data = {"indicator": indicador, "risk_level": "bajo", "symbol": "BCI.SN", **CASOS[indicador]}
    texto = generate_explanation(data, use_finbert=False, detail_level="basico")["text"]
    if "IPSA" in texto:
        assert "índice" in texto.split("IPSA", 1)[1][:40]


def test_los_niveles_siguen_en_orden():
    assert list(LEVELS) == ["basico", "intermedio", "avanzado"]


def test_la_portada_trae_la_guia_y_el_grafico_abre_en_modo_simple(client):
    html = client.get("/").get_data(as_text=True)
    assert "Cómo usar Norte en 3 pasos" in html
    assert 'data-chart-type="line"' in html and 'class="ctrl-radio active" data-chart-type="line"' in html
    assert 'data-indicator-toggle="macd" checked' not in html
    assert "window.APP_LOGGED_IN = false" in html


def test_cada_indicador_del_menu_lleva_su_boton_i_y_abre_el_recuadro(client):
    html = client.get("/").get_data(as_text=True)
    # ventana flotante accesible: es un dialogo NO modal (no bloquea el grafico), asi que no declara aria-modal
    assert 'id="indicator-modal"' in html and 'id="indicator-window"' in html
    assert 'role="dialog"' in html and 'aria-labelledby="indicator-modal-title"' in html
    ventana = re.search(r'<div class="indicator-window"[^>]*>', html).group(0)
    assert "aria-modal" not in ventana  # (la ventana de iniciar sesion si es modal y esta en base.html)
    assert 'id="indicator-modal-grip"' in html  # agarre para moverla, tambien con teclado
    # el menu "Indicadores": una casilla y un boton "i" por fila (las medias moviles tienen dos filas)
    assert html.count('class="info-dot"') == 5
    for clave in ("rsi", "macd", "bandas_bollinger"):
        assert html.count(f'data-explain-indicator="{clave}"') == 1, clave
    assert html.count('data-explain-indicator="medias_moviles"') == 2
    assert html.count('data-indicator-toggle=') == 5
    # el boton "i" va FUERA del <label>: tocarlo no debe marcar ni desmarcar la casilla
    for fila in re.findall(r'<div class="ctrl-row">(.*?)</div>', html, flags=re.S):
        etiqueta = re.search(r"<label.*?</label>", fila, flags=re.S).group(0)
        assert "info-dot" not in etiqueta
    # no quedan franjas, botones sueltos, tarjetas, panel ni fila de botones
    for viejo in ('id="ma-panel"', 'id="bb-panel"', "explain-btn", "ind-name-btn", 'id="indicator-grid"', 'id="explain-panel"',
                  'id="indicator-bar"', "Entiende un indicador", "Cada tarjeta"):
        assert viejo not in html, viejo
    assert "Toca <b>i</b>" in html


def test_el_recuadro_explica_primero_que_es_y_luego_el_dato():
    """Orden pedido: 'Qué es' antes de 'Qué dice hoy'. El JS no se ejecuta en pytest, asi que se
    comprueba sobre el codigo que arma el recuadro."""
    from pathlib import Path

    js = Path("src/web/static/js/dashboard.js").read_text(encoding="utf-8")
    assert js.index('id="modal-what-title"') < js.index("${todayBlock(meta, data, level)}") < js.index('id="modal-explain-title"')
    # todos los indicadores tienen su texto de "qué es"
    for clave in ("medias_moviles", "rsi", "macd", "bandas_bollinger"):
        assert f"{clave}: \"" in js
    # el texto del servidor o del modelo nunca se inserta como HTML
    assert 'modalBody.querySelector(".explain-text").textContent = data.explanation' in js


def test_el_glosario_explica_el_riesgo_de_esta_app():
    from src.nlp.glossary import GLOSSARY_TERMS

    riesgo = next(t for t in GLOSSARY_TERMS if t["term"] == "Riesgo")
    assert "no es la probabilidad de perder dinero" in riesgo["definition"].lower()
    for termino in ("Ticker", "Tendencia", "Histograma (MACD)", "Sesión"):
        assert any(t["term"] == termino for t in GLOSSARY_TERMS), termino


def test_pedir_la_explicacion_una_vez_escribe_una_sola_fila(app, web):
    """El recuadro pide /api/query solo la primera vez; reabrirlo reutiliza el texto cargado (lo hace el JS),
    asi que desde el servidor cada apertura nueva de un indicador equivale a una sola fila."""
    from src.profile.models import QueryLog

    web.get("/api/indicador/valor?symbol=SQM-B.SN&indicator=rsi&days=180")  # cargar el valor no escribe
    with app.app_context():
        assert QueryLog.query.count() == 0
    assert _query(web).status_code == 200
    with app.app_context():
        assert QueryLog.query.count() == 1
        fila = QueryLog.query.one()
        assert fila.explanation_source == "plantilla" and fila.fallback_reason == "desactivado"
