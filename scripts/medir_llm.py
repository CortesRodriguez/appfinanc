"""Mide al LLM real (Groq) con el mismo criterio con que el sistema acepta o rechaza su texto.

Para cada combinacion nivel x indicador x riesgo x estilo (108 casos) pide una explicacion al modelo,
aplica las mismas verificaciones que `generate_explanation` (src/nlp/explainer.py) y clasifica el resultado:

  aceptado             el texto se mostraria al usuario
  sin_etiqueta_riesgo  no cita "riesgo bajo/medio/alto"  -> caeria a plantilla
  sin_valor            no cita el valor del indicador     -> caeria a plantilla
  termino_prohibido    usa jerga prohibida en el nivel    -> caeria a plantilla
  incoherente          lo rechaza validate_coherence      -> caeria a plantilla
  error_api            Groq fallo (red, cuota, clave)     -> caeria a plantilla

Uso (desde la raiz del repo):

    export GROQ_API_KEY=...                              # tu clave; no se lee del .env ni se imprime
    python scripts/medir_llm.py --max-casos 12           # prueba corta primero
    python scripts/medir_llm.py --salida resultados.json # corrida completa, guarda cada texto

    python scripts/medir_llm.py --simulado               # ensaya el script SIN red ni clave

Comparar dos corridas (por ejemplo, prompt anterior y prompt nuevo), sin red ni clave:

    python scripts/medir_llm.py --max-casos 36 --etiqueta v1 --salida docs/informe/evidencia/llm_prompt_v1.json
    python scripts/medir_llm.py --comparar docs/informe/evidencia/llm_prompt_v1.json docs/informe/evidencia/llm_prompt_v2.json

Ademas de aceptar o rechazar, el script calcula senales de estilo de los textos: repeticion (aperturas,
mencion del IPSA, similitud entre textos), marcadores de explicacion y lenguaje de consejo o pronostico.
Son indicadores AUTOMATICOS y debiles: cuentan palabras, no entienden el texto. Lo decisivo es leer los
textos guardados.

Que sale a internet: solo nombre de empresa de ejemplo, indicador, valor de ejemplo, nivel de riesgo y
nivel de explicacion. No hay datos de usuarios. Cada caso es una llamada a la API y consume cuota del plan.

Limites que deben declararse al citar los resultados:
  - Los valores de entrada son de EJEMPLO, no precios reales.
  - temperature = 0,7: otra corrida puede dar resultados distintos. Para estimar la variabilidad,
    repite la corrida y compara.
  - La latencia es de la llamada al modelo desde esta maquina y esta red; no es el tiempo de punta a punta.
  - Con --simulado no se mide al modelo: sirve solo para comprobar que el script funciona.
"""

import argparse
import hashlib
import itertools
import json
import os
import re
import statistics
import sys
import time
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

from medir_calidad_explicaciones import dato_de_ejemplo  # noqa: E402

from src.nlp.explainer import _trim_to_max_words, generate_explanation, llm_rejection_reason  # noqa: E402
from src.nlp.levels import LEVELS, level_max_words  # noqa: E402
from src.nlp.llm_explainer import LLMError, _build_llm_prompt, build_system_prompt, generate_explanation_llm  # noqa: E402
from src.nlp.readability import fernandez_huerta_score  # noqa: E402
from src.nlp.templates import STYLE_LABELS, TEMPLATES  # noqa: E402

MODELO = "qwen/qwen3.8-27b"  # el mismo por defecto de generate_explanation_llm
MOTIVOS = ["aceptado", "sin_etiqueta_riesgo", "sin_valor", "termino_prohibido", "incoherente", "error_api"]
ERRORES_SEGUIDOS_MAX = 3
ESTILOS = len(STYLE_LABELS)

# Senales de estilo. Son listas finitas de palabras: indicadores, no pruebas.
MARCADORES_PORQUE = ("porque", "ya que", "es decir", "significa", "mide", "indica que")
TERMINOS_CONSEJO = ("subirá", "bajará", "seguirá", "anticipa", "recomend", "conviene", "comprar", "vender")


def huella_del_prompt() -> str:
    """Resumen corto del texto exacto de las instrucciones que se envian al modelo (todos los niveles y
    estilos). Dos corridas con la misma huella usaron el mismo prompt; si cambia, el prompt cambio."""
    partes = [build_system_prompt(nivel) for nivel in LEVELS]
    for nivel in LEVELS:
        for estilo in range(ESTILOS):
            partes.append(_build_llm_prompt(dato_de_ejemplo("rsi", "alto"), "Banco BCI", nivel, estilo))
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()[:12]


def muestra(todos: list, n: int) -> list:
    """Muestra de n casos repartida entre niveles, indicadores, riesgos y estilos.

    Los casos vienen en grupos de ESTILOS consecutivos (un grupo = mismo nivel, indicador y riesgo). Tomar
    "uno de cada k" con k multiplo de ESTILOS dejaria siempre el mismo estilo; por eso se elige un grupo
    equiespaciado y dentro de el se rota el estilo.
    """
    if n >= len(todos):
        return list(todos)
    elegidos = []
    for k in range(n):
        inicio = (k * len(todos)) // n
        inicio -= inicio % ESTILOS
        elegidos.append(todos[inicio + k % ESTILOS])
    return elegidos


def _letras(texto: str) -> list:
    return re.findall(r"[a-záéíóúüñ]+", texto.lower())


def _bigramas(texto: str) -> set:
    palabras = re.findall(r"[a-záéíóúüñ0-9.%]+", texto.lower())
    return set(zip(palabras, palabras[1:]))


def metricas(registros: list) -> dict:
    """Senales de estilo sobre los textos que el modelo escribio (aceptados o no)."""
    con_texto = [r for r in registros if r.get("texto")]
    n = len(con_texto)
    resultado = {
        "casos": len(registros),
        "con_texto": n,
        "aceptados_pct": 100 * sum(r["resultado"] == "aceptado" for r in registros) / len(registros) if registros else 0.0,
    }
    if n == 0:
        return resultado

    aperturas = Counter(" ".join(_letras(r["texto"])[:3]) for r in con_texto)
    apertura, veces = aperturas.most_common(1)[0]
    resultado["apertura_mas_repetida"] = apertura
    resultado["apertura_pct"] = 100 * veces / n
    resultado["aperturas_distintas"] = len(aperturas)
    resultado["ipsa_pct"] = 100 * sum("ipsa" in r["texto"].lower() for r in con_texto) / n

    similitudes = []
    for nivel in LEVELS:  # entre textos del mismo nivel: entre niveles se espera que difieran
        grupo = [_bigramas(r["texto"]) for r in con_texto if r["nivel"] == nivel]
        for a, b in itertools.combinations(grupo, 2):
            union = a | b
            similitudes.append(len(a & b) / len(union) if union else 0.0)
    resultado["similitud_media"] = statistics.mean(similitudes) if similitudes else 0.0

    resultado["porque_pct"] = 100 * sum(any(m in r["texto"].lower() for m in MARCADORES_PORQUE) for r in con_texto) / n
    resultado["consejo_pct"] = 100 * sum(any(t in r["texto"].lower() for t in TERMINOS_CONSEJO) for r in con_texto) / n
    resultado["think"] = sum("<think" in r["texto"].lower() for r in con_texto)
    tiempos = [r["ms"] for r in registros if r["resultado"] != "error_api"]
    if tiempos:
        resultado["latencia_media_ms"] = statistics.mean(tiempos)
    return resultado


def clasificar(dato: dict, nivel: str, texto: str) -> str:
    """Misma secuencia de verificaciones que generate_explanation (comparten llm_rejection_reason)."""
    return llm_rejection_reason(dato, nivel, _trim_to_max_words(texto, level_max_words(nivel))) or "aceptado"


def casos():
    for nivel in LEVELS:
        for indicador, por_riesgo in TEMPLATES[nivel].items():
            for riesgo, variantes in por_riesgo.items():
                for estilo in range(len(variantes)):
                    yield nivel, indicador, riesgo, estilo


def generador_simulado():
    """Texto de plantilla, estropeado de formas conocidas, para ensayar el script sin red."""
    contador = {"n": 0}

    def generar(dato, nombre, nivel, api_key, variant=0):
        i = contador["n"]
        contador["n"] += 1
        base = generate_explanation(dato, variant=variant, use_finbert=False, detail_level=nivel, display_name=nombre)["text"]
        modo = i % 6
        if modo == 3:
            return base.lower().replace("riesgo", "nivel")
        if modo == 4:
            prohibidos = LEVELS[nivel]["forbidden_terms"]
            return f"{base} {prohibidos[0]}" if prohibidos else base.replace(str(dato["value"]), "")
        if modo == 5:
            raise LLMError("error simulado")
        return base

    return generar


def percentil(valores, p):
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p / 100 * (len(ordenados) - 1)))]


def medir(args) -> int:
    simulado = args.simulado
    if simulado:
        generar, clave = generador_simulado(), "simulada"
    else:
        clave = os.environ.get("GROQ_API_KEY", "")
        if not clave:
            print("Falta GROQ_API_KEY. Exporta la variable (export GROQ_API_KEY=...) o usa --simulado.", file=sys.stderr)
            return 2
        generar = generate_explanation_llm

    todos = list(casos())
    if args.max_casos:
        todos = muestra(todos, args.max_casos)

    registros, seguidos = [], 0
    for numero, (nivel, indicador, riesgo, estilo) in enumerate(todos, 1):
        dato = dato_de_ejemplo(indicador, riesgo)
        inicio = time.perf_counter()
        try:
            texto = generar(dato, "Banco BCI", nivel, clave, variant=estilo)
            ms = (time.perf_counter() - inicio) * 1000
            motivo = clasificar(dato, nivel, texto)
            seguidos = 0
        except LLMError as exc:
            ms, texto, motivo = (time.perf_counter() - inicio) * 1000, "", "error_api"
            seguidos += 1
            print(f"[{numero}/{len(todos)}] error_api: {str(exc)[:160]}", file=sys.stderr)
        registro = {
            "nivel": nivel, "indicador": indicador, "riesgo": riesgo, "estilo": estilo,
            "resultado": motivo, "ms": round(ms), "texto": texto,
        }
        if texto:
            recortado = _trim_to_max_words(texto, level_max_words(nivel))
            registro["recortado"] = recortado != texto
            registro["legibilidad"] = fernandez_huerta_score(recortado)
            registro["palabras"] = len(recortado.split())
        registros.append(registro)
        if seguidos >= ERRORES_SEGUIDOS_MAX:
            print(f"\nSe detuvo: {ERRORES_SEGUIDOS_MAX} errores seguidos (cuota, clave o modelo). Revisa el primer mensaje.", file=sys.stderr)
            break
        if not simulado and args.pausa:
            time.sleep(args.pausa)

    informe(registros, simulado, len(todos))
    if args.salida:
        contenido = {
            "modelo": MODELO,
            "simulado": simulado,
            "etiqueta": args.etiqueta,
            "huella_del_prompt": huella_del_prompt(),
            "metricas": metricas(registros),
            "registros": registros,
        }
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
        print(f"\nTextos y resultados guardados en {args.salida} (huella del prompt: {contenido['huella_del_prompt']})")
    return 0


def informe(registros, simulado, planificados):
    modo = "SIMULADO (no es una medición del modelo)" if simulado else f"REAL, modelo {MODELO}"
    print(f"Modo: {modo}")
    print(f"Casos ejecutados: {len(registros)} de {planificados}\n")
    if not registros:
        return

    print("| Nivel | n | Aceptados | % | Sin riesgo | Sin valor | Prohibido | Incoherente | Error API |")
    print("|---|---|---|---|---|---|---|---|---|")
    for nivel in list(LEVELS) + ["TOTAL"]:
        sub = registros if nivel == "TOTAL" else [r for r in registros if r["nivel"] == nivel]
        if not sub:
            continue
        c = Counter(r["resultado"] for r in sub)
        print(
            f"| {nivel} | {len(sub)} | {c['aceptado']} | {100 * c['aceptado'] / len(sub):.0f} % | "
            f"{c['sin_etiqueta_riesgo']} | {c['sin_valor']} | {c['termino_prohibido']} | "
            f"{c['incoherente']} | {c['error_api']} |"
        )

    aceptados = [r for r in registros if r["resultado"] == "aceptado"]
    if aceptados:
        fh = [r["legibilidad"] for r in aceptados]
        pal = [r["palabras"] for r in aceptados]
        print(f"\nTextos aceptados: legibilidad Fernández-Huerta media {statistics.mean(fh):.1f} "
              f"(mín {min(fh):.1f}, máx {max(fh):.1f}); palabras media {statistics.mean(pal):.1f} (máx {max(pal)}).")
    recortados = sum(1 for r in registros if r.get("recortado"))
    print(f"Textos que el modelo escribió por encima del límite del nivel y hubo que recortar: {recortados}.")

    tiempos = [r["ms"] for r in registros if r["resultado"] != "error_api"]
    if tiempos:
        print(f"\nLatencia de la llamada al modelo (ms): media {statistics.mean(tiempos):.0f}, "
              f"mediana {statistics.median(tiempos):.0f}, p95 {percentil(tiempos, 95)}, máx {max(tiempos)} "
              f"(límite de RNF-01.1: 5000 ms para toda la solicitud).")


FILAS = [
    ("aceptados_pct", "Aceptados (%)", "{:.0f}", "más"),
    ("apertura_pct", "Textos con la apertura más repetida (%)", "{:.0f}", "menos"),
    ("aperturas_distintas", "Aperturas distintas", "{:.0f}", "más"),
    ("ipsa_pct", "Textos que mencionan el IPSA (%)", "{:.0f}", "menos"),
    ("similitud_media", "Similitud media entre textos del mismo nivel (0 a 1)", "{:.2f}", "menos"),
    ("porque_pct", "Textos con un marcador de explicación (%)", "{:.0f}", "más"),
    ("consejo_pct", "Textos con lenguaje de consejo o pronóstico (%)", "{:.0f}", "menos"),
    ("think", "Textos con etiquetas <think>", "{:.0f}", "menos"),
    ("latencia_media_ms", "Latencia media de la llamada (ms)", "{:.0f}", "menos"),
]


def comparar(ruta_a: str, ruta_b: str) -> int:
    """Tabla lado a lado de dos corridas guardadas con --salida. No usa red ni clave."""
    corridas = []
    for ruta in (ruta_a, ruta_b):
        with open(ruta, encoding="utf-8") as f:
            corridas.append(json.load(f))
    a, b = corridas

    for nombre, c in (("A", a), ("B", b)):
        if c.get("simulado"):
            print(f"AVISO: la corrida {nombre} es SIMULADA; sus números no describen al modelo.")
    if a.get("huella_del_prompt") == b.get("huella_del_prompt"):
        print("AVISO: las dos corridas tienen la misma huella de prompt; no hay un prompt distinto que comparar.")
    ma, mb = a["metricas"], b["metricas"]
    if ma["casos"] != mb["casos"]:
        print(f"AVISO: distinto número de casos ({ma['casos']} y {mb['casos']}); la comparación pierde fuerza.")

    nombre_a, nombre_b = a.get("etiqueta") or "A", b.get("etiqueta") or "B"
    print(f"\n| Métrica | {nombre_a} | {nombre_b} | Cambio | Mejor si es |")
    print("|---|---|---|---|---|")
    for clave, titulo, formato, mejor in FILAS:
        if clave not in ma or clave not in mb:
            continue
        va, vb = ma[clave], mb[clave]
        print(f"| {titulo} | {formato.format(va)} | {formato.format(vb)} | {vb - va:+.2f} | {mejor} |")
    print(f"| Apertura más repetida | «{ma.get('apertura_mas_repetida', '-')}» | «{mb.get('apertura_mas_repetida', '-')}» | | |")
    print("\nLeer los textos guardados sigue siendo la comprobación principal: estas cifras cuentan palabras.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mide al LLM real con el criterio de aceptación del sistema.")
    parser.add_argument("--max-casos", type=int, default=None, help="usa una muestra repartida de N casos (por defecto, los 108)")
    parser.add_argument("--pausa", type=float, default=1.0, help="segundos entre llamadas para no exceder el límite por minuto (por defecto 1)")
    parser.add_argument("--salida", help="archivo JSON donde guardar cada texto y su resultado")
    parser.add_argument("--etiqueta", default="", help="nombre de la corrida en el JSON y en la comparación (por ejemplo v1)")
    parser.add_argument("--simulado", action="store_true", help="ensaya el script con un generador falso, sin red ni clave")
    parser.add_argument("--comparar", nargs=2, metavar=("A.json", "B.json"), help="compara dos corridas guardadas; no usa red ni clave")
    args = parser.parse_args()
    if args.comparar:
        return comparar(*args.comparar)
    return medir(args)


if __name__ == "__main__":
    sys.exit(main())
