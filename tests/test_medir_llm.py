"""El script scripts/medir_llm.py clasifica con la misma regla que usa el sistema. Si alguien cambia las
verificaciones de generate_explanation y no el script, estas pruebas lo delatan."""

import importlib.util
import os

import pytest

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "medir_llm.py")
_spec = importlib.util.spec_from_file_location("medir_llm", _RUTA)
medir_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(medir_llm)

RSI_ALTO = {"indicator": "rsi", "value": 78.5, "risk_level": "alto", "signal": "sobrecomprado", "symbol": "BCI.SN"}
RSI_BAJO = {"indicator": "rsi", "value": 5.0, "risk_level": "alto", "signal": "sobrevendido", "symbol": "BCI.SN"}

CASOS = [
    ("aceptado", RSI_ALTO, "avanzado", "El RSI de BCI está en 78.5 (riesgo alto): sobrecomprado, por encima de 70."),
    ("sin_etiqueta_riesgo", RSI_ALTO, "avanzado", "El RSI de BCI está en 78.5: sobrecomprado, por encima de 70."),
    ("sin_valor", RSI_ALTO, "avanzado", "El RSI de BCI marca riesgo alto: sobrecomprado, por encima de 70."),
    ("termino_prohibido", RSI_ALTO, "basico", "El RSI de BCI está en 78.5 (riesgo alto): sobrecompra con momentum extremo."),
    ("incoherente", RSI_BAJO, "avanzado", "El RSI de BCI está en 5.0 y marca riesgo alto: está sobrecomprado, conviene vigilar."),
    # "15.0" contiene "5.0" pero no es el valor del indicador: cuenta como valor ausente
    ("sin_valor", RSI_BAJO, "avanzado", "El RSI de BCI está en 15.0 y marca riesgo alto: sobreventa, conviene vigilar."),
]


@pytest.mark.parametrize("esperado,dato,nivel,texto", CASOS, ids=[c[0] for c in CASOS])
def test_clasificar_coincide_con_lo_que_hace_generate_explanation(monkeypatch, esperado, dato, nivel, texto):
    from src.nlp.explainer import generate_explanation

    assert medir_llm.clasificar(dato, nivel, texto) == esperado

    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", lambda *a, **k: texto)
    resultado = generate_explanation(dato, use_finbert=False, detail_level=nivel, use_llm=True, llm_api_key="x")
    se_uso_el_texto_del_llm = resultado["text"] == texto
    assert se_uso_el_texto_del_llm == (esperado == "aceptado")


def test_el_modo_simulado_corre_sin_red_ni_clave(capsys, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    args = medir_llm.argparse.Namespace(max_casos=12, pausa=0, salida=None, simulado=True)
    assert medir_llm.medir(args) == 0
    salida = capsys.readouterr().out
    assert "SIMULADO" in salida
    assert "Casos ejecutados: 12 de 12" in salida


def test_sin_clave_no_llama_a_la_red(capsys, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    args = medir_llm.argparse.Namespace(max_casos=3, pausa=0, salida=None, simulado=False)
    assert medir_llm.medir(args) == 2
    assert "GROQ_API_KEY" in capsys.readouterr().err


# --- señales de estilo, comparación y muestreo --------------------------------------------------


def _registro(texto, nivel="intermedio", resultado="aceptado", ms=100):
    return {"nivel": nivel, "resultado": resultado, "texto": texto, "ms": ms}


def test_la_muestra_cubre_los_tres_estilos_y_no_repite_casos():
    todos = list(medir_llm.casos())
    for n in (12, 24, 36):
        elegidos = medir_llm.muestra(todos, n)
        assert len(elegidos) == n
        assert len(set(elegidos)) == n
        estilos = {e[3] for e in elegidos}
        assert estilos == set(range(medir_llm.ESTILOS)), f"con n={n} faltan estilos"
        assert {e[0] for e in elegidos} == set(medir_llm.LEVELS)
    assert medir_llm.muestra(todos, 500) == todos


def test_metricas_cuentan_la_repeticion_de_aperturas_y_del_ipsa():
    registros = [
        _registro("El RSI de Banco BCI marca 50. Conviene mirarlo junto al IPSA."),
        _registro("El RSI de Banco BCI marca 60. Conviene mirarlo junto al IPSA."),
        _registro("Mide la fuerza del precio. Está en 70 y es riesgo alto."),
        _registro("Sin texto", resultado="error_api"),
    ]
    registros[3]["texto"] = ""
    m = medir_llm.metricas(registros)
    assert m["casos"] == 4 and m["con_texto"] == 3
    assert m["apertura_mas_repetida"] == "el rsi de"
    assert m["apertura_pct"] == pytest.approx(200 / 3)
    assert m["aperturas_distintas"] == 2
    assert m["ipsa_pct"] == pytest.approx(200 / 3)
    assert m["aceptados_pct"] == pytest.approx(75.0)


def test_metricas_de_porque_consejo_y_think():
    registros = [
        _registro("Marca 50 porque el precio se movió poco."),
        _registro("Mide la fuerza del precio."),
        _registro("Conviene comprar ahora."),
        _registro("<think>razono</think> Marca 40."),
    ]
    m = medir_llm.metricas(registros)
    assert m["porque_pct"] == pytest.approx(50.0)  # "porque" y "mide"
    assert m["consejo_pct"] == pytest.approx(25.0)
    assert m["think"] == 1


def test_similitud_es_1_entre_textos_iguales_y_0_entre_textos_sin_palabras_en_comun():
    iguales = [_registro("el precio sube hoy"), _registro("el precio sube hoy")]
    distintos = [_registro("el precio sube hoy"), _registro("nada coincide aqui jamas")]
    assert medir_llm.metricas(iguales)["similitud_media"] == pytest.approx(1.0)
    assert medir_llm.metricas(distintos)["similitud_media"] == pytest.approx(0.0)


def test_similitud_ignora_los_textos_de_otros_niveles():
    # Mismo texto en niveles distintos: no se compara entre niveles, así que no hay pares.
    registros = [_registro("el precio sube hoy", nivel="basico"), _registro("el precio sube hoy", nivel="avanzado")]
    assert medir_llm.metricas(registros)["similitud_media"] == 0.0


def test_la_huella_cambia_si_cambia_el_prompt(monkeypatch):
    antes = medir_llm.huella_del_prompt()
    assert antes == medir_llm.huella_del_prompt()  # estable entre llamadas
    monkeypatch.setattr(medir_llm, "build_system_prompt", lambda nivel: "otro prompt " + nivel)
    assert medir_llm.huella_del_prompt() != antes


def _corrida(tmp_path, nombre, huella, simulado=False, apertura_pct=80.0):
    import json

    ruta = tmp_path / f"{nombre}.json"
    ruta.write_text(
        json.dumps(
            {
                "modelo": "m", "simulado": simulado, "etiqueta": nombre, "huella_del_prompt": huella,
                "metricas": {
                    "casos": 36, "con_texto": 36, "aceptados_pct": 90.0, "apertura_pct": apertura_pct,
                    "apertura_mas_repetida": "el rsi de", "aperturas_distintas": 5, "ipsa_pct": 70.0,
                    "similitud_media": 0.3, "porque_pct": 40.0, "consejo_pct": 5.0, "think": 0,
                    "latencia_media_ms": 900.0,
                },
                "registros": [],
            }
        ),
        encoding="utf-8",
    )
    return str(ruta)


def test_comparar_muestra_la_tabla_y_avisa_si_el_prompt_no_cambio(tmp_path, capsys):
    a = _corrida(tmp_path, "v1", "aaa", apertura_pct=80.0)
    b = _corrida(tmp_path, "v2", "aaa", apertura_pct=30.0)
    assert medir_llm.comparar(a, b) == 0
    salida = capsys.readouterr().out
    assert "misma huella de prompt" in salida
    assert "| v1 | v2 |" in salida.replace("Métrica | ", "")
    assert "-50.00" in salida  # apertura más repetida: 80 -> 30


def test_comparar_avisa_si_una_corrida_es_simulada(tmp_path, capsys):
    a = _corrida(tmp_path, "v1", "aaa", simulado=True)
    b = _corrida(tmp_path, "v2", "bbb")
    medir_llm.comparar(a, b)
    salida = capsys.readouterr().out
    assert "SIMULADA" in salida
    assert "misma huella" not in salida
