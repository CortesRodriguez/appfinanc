"""Mide la calidad de las explicaciones generadas con las plantillas (RF-04.2, RNF-04).

Recorre todas las combinaciones nivel x indicador x riesgo x estilo, genera la explicacion por el
mismo camino que usa la aplicacion (`generate_explanation`, sin LLM ni FinBERT) y reporta, por nivel:

  - incoherentes: textos que `validate_coherence` rechaza
  - sobre el limite: textos que superan el maximo de palabras del nivel
  - legibilidad: indice Fernandez-Huerta (media, minimo, maximo)
  - palabras: media y maximo

Uso (desde la raiz del repo):

    python scripts/medir_calidad_explicaciones.py

Limites de esta medicion, que deben declararse al citarla:
  - Mide las PLANTILLAS, no al LLM: nunca se ha probado contra la API real de Groq.
  - Los valores de entrada son de EJEMPLO (uno por indicador y riesgo), no precios reales.
  - Fernandez-Huerta aqui es una aproximacion (cuenta grupos vocalicos) y puede salir de 0-100
    con frases muy cortas.
"""

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nlp.explainer import generate_explanation  # noqa: E402
from src.nlp.levels import LEVELS, level_max_words  # noqa: E402
from src.nlp.templates import STYLE_LABELS, TEMPLATES  # noqa: E402
from src.nlp.validator import validate_coherence  # noqa: E402

# (senal, valor) de ejemplo para cada indicador y nivel de riesgo.
EJEMPLOS = {
    "rsi": {"alto": ("sobrecomprado", 78.5), "medio": ("neutral", 62.0), "bajo": ("neutral", 50.0)},
    "macd": {"alto": ("alcista", 1.2), "medio": ("neutral", 0.1), "bajo": ("neutral", 0.0)},
    "bandas_bollinger": {"alto": ("sobrecomprado", 1.1), "medio": ("neutral", 0.8), "bajo": ("neutral", 0.5)},
    "medias_moviles": {"alto": ("alcista", 1.0), "medio": ("neutral", 0.2), "bajo": ("neutral", 0.0)},
}


def dato_de_ejemplo(indicador: str, riesgo: str) -> dict:
    senal, valor = EJEMPLOS[indicador][riesgo]
    dato = {
        "indicator": indicador,
        "value": valor,
        "risk_level": riesgo,
        "signal": senal,
        "symbol": "BCI.SN",
        "unit": "",
        "period_days": 180,
    }
    if indicador == "medias_moviles":
        dato.update({"trend": "alcista" if senal == "alcista" else "lateral", "sma_short": 105.0, "sma_long": 100.0})
    if indicador == "macd":
        dato["trend"] = senal
    return dato


def medir_nivel(nivel: str) -> dict:
    legibilidad, palabras = [], []
    total = incoherentes = sobre_limite = 0
    limite = level_max_words(nivel)
    for indicador, por_riesgo in TEMPLATES[nivel].items():
        for riesgo, variantes in por_riesgo.items():
            dato = dato_de_ejemplo(indicador, riesgo)
            for variante in range(len(variantes)):
                resultado = generate_explanation(
                    dato, variant=variante, use_finbert=False, detail_level=nivel, display_name="Banco BCI"
                )
                texto = resultado["text"]
                total += 1
                incoherentes += not validate_coherence(dato, texto)[0]
                n = len(texto.split())
                sobre_limite += n > limite
                legibilidad.append(resultado["readability_score"])
                palabras.append(n)
    return {
        "n": total,
        "incoherentes": incoherentes,
        "sobre_limite": sobre_limite,
        "fh": (statistics.mean(legibilidad), min(legibilidad), max(legibilidad)),
        "palabras": (statistics.mean(palabras), max(palabras), limite),
    }


def main() -> None:
    print(f"Niveles: {', '.join(LEVELS)} | estilos: {', '.join(STYLE_LABELS.values())}\n")
    print("| Nivel | n | Incoherentes | Sobre el límite | Fernández-Huerta (media / mín / máx) | Palabras (media / máx / límite) |")
    print("|---|---|---|---|---|---|")
    for nivel in LEVELS:
        r = medir_nivel(nivel)
        fm, fmin, fmax = r["fh"]
        pm, pmax, lim = r["palabras"]
        print(
            f"| {nivel} | {r['n']} | {r['incoherentes']} | {r['sobre_limite']} | "
            f"{fm:.1f} / {fmin:.1f} / {fmax:.1f} | {pm:.1f} / {pmax} / {lim} |"
        )


if __name__ == "__main__":
    main()
