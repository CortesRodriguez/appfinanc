"""Contrato del prompt del LLM (src/nlp/llm_explainer.py).

Fija lo que NO debe cambiar al reescribir el prompt (reglas del nivel, ausencia de analogias y de consejo) y
lo que el prompt nuevo agrega: hechos verificados de cada indicador, una estructura de contenido, variedad de
aperturas y un IPSA que ya no es obligatorio en cada texto.

Los hechos se comparan contra el codigo del extractor: si alguien cambia un umbral o una formula sin
actualizar el prompt, estas pruebas lo delatan.
"""

import inspect
import re

import pytest

from src.nlp.levels import LEVEL_ORDER, LEVELS
from src.nlp.llm_explainer import (
    _INDICATOR_FACTS,
    _STYLE_HINTS,
    _build_llm_prompt,
    build_system_prompt,
)

INDICADORES = ("rsi", "macd", "medias_moviles", "bandas_bollinger")
DATOS = {
    "rsi": {"indicator": "rsi", "value": 78.5, "risk_level": "alto", "signal": "sobrecomprado"},
    "macd": {"indicator": "macd", "value": 1.2, "risk_level": "alto", "trend": "alcista"},
    "medias_moviles": {"indicator": "medias_moviles", "value": 4.2, "risk_level": "bajo", "trend": "alcista"},
    "bandas_bollinger": {"indicator": "bandas_bollinger", "value": 1.1, "risk_level": "alto", "signal": "sobrecomprado"},
}


# --- lo que debe seguir cumpliendose -------------------------------------------------------------


@pytest.mark.parametrize("nivel", LEVEL_ORDER)
def test_el_prompt_sigue_sin_aconsejar_ni_usar_analogias_ni_avisos(nivel):
    prompt = build_system_prompt(nivel)
    assert "no aconsejar" in prompt
    assert "No uses analogías" in prompt
    assert "ningún aviso legal" in prompt


@pytest.mark.parametrize("nivel", LEVEL_ORDER)
def test_el_prompt_prohibe_pronosticar(nivel):
    prompt = build_system_prompt(nivel).lower()
    assert "no pronostiques" in prompt
    assert "qué hará el precio" in prompt
    for palabra in ("subirá", "bajará", "seguirá", "anticipa"):
        assert palabra in prompt, f"la lista de palabras prohibidas no incluye «{palabra}»"


@pytest.mark.parametrize("nivel", LEVEL_ORDER)
def test_el_prompt_conserva_la_ficha_del_nivel(nivel):
    ficha = LEVELS[nivel]
    prompt = build_system_prompt(nivel)
    assert ficha["audience"] in prompt
    assert ficha["vocabulary"] in prompt
    assert ficha["thresholds"] in prompt
    assert f"Máximo {ficha['max_words']} palabras" in prompt


def test_el_mensaje_de_usuario_conserva_el_numero_y_la_etiqueta_exactos():
    msg = _build_llm_prompt(DATOS["rsi"], "Banco BCI", "intermedio", 0)
    assert '"78.5"' in msg and '"riesgo alto"' in msg


# --- el porqué: hechos verificados del indicador --------------------------------------------------


def test_hay_hechos_para_cada_indicador_en_version_llana_y_tecnica():
    assert set(_INDICATOR_FACTS) == set(INDICADORES)
    for hechos in _INDICATOR_FACTS.values():
        assert set(hechos) == {"llano", "tecnico"}
        assert all(len(texto.split()) >= 12 for texto in hechos.values())


@pytest.mark.parametrize("indicador", INDICADORES)
def test_el_nivel_basico_recibe_hechos_sin_jerga_ni_numeros_de_umbral(indicador):
    texto = _INDICATOR_FACTS[indicador]["llano"].lower()
    for termino in LEVELS["basico"]["forbidden_terms"]:
        assert termino not in texto, f"{indicador}: la version llana usa «{termino}»"
    assert not re.search(r"\b(70|30)\b", texto), f"{indicador}: la version llana nombra un umbral"


def test_los_hechos_no_usan_analogias():
    for indicador, hechos in _INDICATOR_FACTS.items():
        for version, texto in hechos.items():
            assert not re.search(r"\b(como si|es como|igual que un|termómetro|velocímetro)\b", texto.lower()), (
                indicador, version)


def test_los_hechos_coinciden_con_los_umbrales_del_extractor():
    """Si el codigo cambia un corte o una ventana, el prompt tiene que cambiar con el."""
    from src.extractor import indicators

    codigo = inspect.getsource(indicators)
    tecnico = {k: v["tecnico"] for k, v in _INDICATOR_FACTS.items()}
    # RSI: Wilder de 14 sesiones, cortes 70 y 30
    assert "window: int = 14" in codigo and "last_rsi > 70" in codigo and "last_rsi < 30" in codigo
    assert "14" in tecnico["rsi"] and "70" in tecnico["rsi"] and "30" in tecnico["rsi"]
    # MACD: 12, 26 y 9; el valor es el histograma
    assert "fast: int = 12, slow: int = 26, signal_period: int = 9" in codigo
    assert all(n in tecnico["macd"] for n in ("12", "26", "9"))
    assert "histograma" in tecnico["macd"].lower()
    # Bollinger: 20 sesiones, 2 desviaciones, %B sobre 1 / bajo 0
    assert "window: int = 20, num_std: float = 2.0" in codigo and "percent_b > 1" in codigo and "percent_b < 0" in codigo
    assert "20" in tecnico["bandas_bollinger"] and "%B" in tecnico["bandas_bollinger"]
    # Medias moviles: 50 y 200 sesiones; solo se acortan si el instrumento tiene poca historia
    assert "short_window: int = 50, long_window: int = 200" in codigo
    assert "min(short_window, max(2, n_rows // 2))" in codigo
    assert "50" in tecnico["medias_moviles"] and "200" in tecnico["medias_moviles"]
    # el valor es una diferencia porcentual: ((corta - larga) / larga) * 100
    assert "diff_pct = float((sma_short - sma_long) / sma_long * 100)" in codigo
    assert "porcentual" in tecnico["medias_moviles"].lower()


def test_el_riesgo_no_se_describe_como_sinonimo_de_sobrecompra():
    for nivel in LEVEL_ORDER:
        prompt = build_system_prompt(nivel).lower()
        assert "riesgo alto significa" not in prompt and "riesgo alto es sobrecompra" not in prompt
    # el prompt aclara que el riesgo se calcula distinto en cada indicador
    assert "de forma distinta en cada indicador" in build_system_prompt("intermedio")


@pytest.mark.parametrize("indicador", INDICADORES)
def test_el_mensaje_de_usuario_incluye_la_lectura_del_indicador(indicador):
    for nivel in LEVEL_ORDER:
        msg = _build_llm_prompt(DATOS[indicador], "Banco BCI", nivel, 0)
        clave = "llano" if nivel == "basico" else "tecnico"
        assert _INDICATOR_FACTS[indicador][clave] in msg, (indicador, nivel)


def test_el_mensaje_basico_sigue_sin_jerga_con_los_hechos_incluidos():
    for indicador in INDICADORES:
        msg = _build_llm_prompt(DATOS[indicador], "Banco BCI", "basico", 0).lower()
        for termino in ("sobrecompra", "sobrecomprado", "momentum", "histograma", "volatilidad", "umbral"):
            assert termino not in msg, (indicador, termino)


# --- estructura de contenido ----------------------------------------------------------------------


def test_los_niveles_basico_e_intermedio_piden_el_que_mide_y_el_porque():
    for nivel in ("basico", "intermedio"):
        prompt = build_system_prompt(nivel).lower()
        assert "qué mide" in prompt
        assert "por qué" in prompt


def test_el_nivel_avanzado_no_pide_explicar_que_mide():
    prompt = build_system_prompt("avanzado")
    assert "NO expliques qué mide" in prompt
    assert "por qué" in prompt.lower()  # sigue pidiendo la lectura, no la definicion


def test_el_prompt_pide_el_numero_y_la_etiqueta_al_comienzo_para_sobrevivir_al_recorte():
    for nivel in LEVEL_ORDER:
        msg = _build_llm_prompt(DATOS["rsi"], "Banco BCI", nivel, 0).lower()
        assert "primeras dos oraciones" in msg or "primeras oraciones" in msg


# --- IPSA y variedad --------------------------------------------------------------------------------


def test_el_ipsa_ya_no_es_obligatorio_en_cada_texto():
    for nivel in ("basico", "intermedio"):
        prompt = build_system_prompt(nivel)
        assert "Menciona brevemente el IPSA" not in prompt
        assert "IPSA" in prompt and "solo si" in prompt.lower()
    assert "No agregues contexto del IPSA" in build_system_prompt("avanzado")


def test_el_ipsa_de_las_plantillas_no_cambia():
    """El flag ficha['ipsa'] tambien decide si las plantillas anaden la frase del IPSA: no se toca."""
    assert LEVELS["basico"]["ipsa"] is True and LEVELS["intermedio"]["ipsa"] is True
    assert LEVELS["avanzado"]["ipsa"] is False


def test_los_estilos_dan_instrucciones_de_apertura_distintas_y_sin_ejemplos_copiables():
    assert len(_STYLE_HINTS) == 3 and len(set(_STYLE_HINTS.values())) == 3
    for pista in _STYLE_HINTS.values():
        assert len(pista.split()) >= 10, "la pista de estilo es demasiado corta para variar el texto"
        assert "«" not in pista and "\"" not in pista, "las pistas no deben traer frases de ejemplo que el modelo copie"


def test_el_prompt_prohibe_empezar_siempre_igual():
    for nivel in LEVEL_ORDER:
        msg = _build_llm_prompt(DATOS["macd"], "Banco BCI", nivel, 0).lower()
        assert "no empieces" in msg


def test_el_mensaje_avanzado_no_pide_explicar_que_mide():
    msg = _build_llm_prompt(DATOS["macd"], "Banco BCI", "avanzado", 0)
    assert "no expliques qué mide" in msg
    assert "úsala para explicar qué mide" not in msg
    assert "úsala para explicar qué mide" in _build_llm_prompt(DATOS["macd"], "Banco BCI", "intermedio", 0)


def test_el_mensaje_no_trae_marcadores_con_llaves_que_el_modelo_pueda_copiar():
    for nivel in LEVEL_ORDER:
        for estilo in range(3):
            msg = _build_llm_prompt(DATOS["rsi"], "Banco BCI", nivel, estilo)
            assert "{" not in msg and "}" not in msg
