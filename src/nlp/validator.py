"""Validacion de coherencia semantica (RF-04.2, RF-13).

Contrasta la explicacion generada contra el dato real del indicador, para
mitigar alucinaciones del modelo. Reglas:

  Siempre:             cita la etiqueta de riesgo calculada ("riesgo alto") y el
                       valor del indicador (como numero completo, no como parte de otro)
  RSI:                 no afirmar sobrecompra salvo senal sobrecomprado o RSI > 70;
                       no afirmar sobreventa salvo senal sobrevendido o RSI < 30
  Bandas de Bollinger: lo mismo con %B > 1 y %B < 0
  MACD, medias:        no afirmar la tendencia opuesta a la calculada (alcista/bajista)

Principio de diseno: solo se rechaza una AFIRMACION clara que contradice el dato. Una
mencion negada ("no hay sobrecompra"), condicional o que define un umbral ("sobre 70 se
considera sobrecompra") no es una afirmacion, y ante la duda el texto se acepta: rechazar
un texto correcto descarta una explicacion buena del LLM para poner una plantilla.

Limitaciones conocidas (no se detectan):
  - un texto que cita dos etiquetas de riesgo (basta con que cite la correcta);
  - la direccion de la frase (que diga "sube" cuando baja): no hay regla simple y fiable;
  - una contradiccion escrita en una oracion que ademas tiene una negacion o condicional.

El validador consume el dict `indicator_data` ya calculado por el Extractor (llegan por
parametro `signal`, `trend`, `value`, etc.). No importa nada del Extractor: la coherencia
se comprueba solo con lo que recibe, respetando la separacion entre componentes de dominio.
"""

import re
from decimal import Decimal, InvalidOperation

from .explainer import RISK_LABELS

# Terminos de sobrecompra / sobreventa en cualquiera de sus formas (-a, -ado, -ada). El LLM
# recibe "sobrecompra" y "sobreventa" en el prompt; "sobrevenida" es como aparece en una
# de sus descripciones de senal.
_OVERBOUGHT = re.compile(r"sobrecompr\w*")
_OVERSOLD = re.compile(r"sobreven\w*")

# Oraciones: se corta tras . ! ? ; seguidos de espacio (el punto de un decimal no corta) y
# en los saltos de linea.
_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n+")

# Palabras que vuelven una mencion NO afirmativa: negacion, definicion, hipotesis o
# aproximacion. Si la oracion tiene alguna, sus menciones no se tratan como afirmacion.
_HEDGE = re.compile(
    r"\b(?:"
    r"no|ni|sin|nunca|tampoco|ning[uú]n\w*|lej\w+|alej\w+|descart\w+|evit\w+|falta\w*|"
    r"si|cuando|suele\w*|sol[ií]a\w*|se considera\w*|se llama\w*|se habla|se dice|se entiende|significa\w*|"
    r"ser[ií]a\w*|indicar[ií]a\w*|se[nñ]alar[ií]a\w*|podr[ií]a\w*|habr[ií]a\w*|"
    r"entre|antes de|hasta que|en caso de|riesgo de|posible\w*|posibilidad\w*|"
    r"tiend\w+|tender\w*|acerc\w+|aproxim\w+|cerca de|pr[oó]xim\w+|"
    r"todav[ií]a|a[uú]n|para|llegar\w*|llegue\w*|a partir de|"
    r"por debajo de|por encima de|debajo de|encima de|fuera de|dentro de|"
    r"bajo (?:el|la|los|las) \w+(?: \w+)? de|bajo (?:el|la|los|las) (?:zona|nivel|umbral|l[ií]nea)"
    r")\b"
)

# Un umbral numerico ANTES del termino ("sobre 70 se considera sobrecompra") es una definicion.
# Despues del termino ("en sobrecompra (sobre 70)") es una afirmacion apoyada en el umbral, y se
# valida: es justo lo que escribiria un modelo que alucina la lectura.
_THRESHOLD_BEFORE = re.compile(
    r"\b(?:sobre|bajo|encima de|debajo de|m[aá]s de|menos de|superior a|inferior a|"
    r"mayor que|menor que|supera\w*|pasa\w*)\s+(?:el |los |la )?\d"
)


def _asserts(text_lower: str, term: re.Pattern) -> bool:
    """True si alguna oracion usa `term` como afirmacion (ni negada, ni condicional, ni definida por umbral)."""
    for sentence in _SENTENCES.split(text_lower):
        if _HEDGE.search(sentence):
            continue
        for match in term.finditer(sentence):
            if not _THRESHOLD_BEFORE.search(sentence[: match.start()]):
                return True
    return False


def _value_regex(value):
    """Patron que reconoce `value` como numero completo, o None si no es un numero finito.

    Acepta coma o punto decimal, ceros finales ("46.50" para 46.5, "5" para 5.0) y los
    signos menos tipograficos. No acepta el valor dentro de otro numero ("15.0" no cita 5.0).
    """
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    digits = format(abs(number), "f")
    if "." in digits:
        digits = digits.rstrip("0")
    whole, _, frac = digits.partition(".")
    start = r"[-−–]" if number < 0 else r"(?<!\d)(?<!\d[.,])"
    body = re.escape(whole) + (rf"[.,]{frac}0*" if frac else r"(?:[.,]0+)?")
    return re.compile(start + body + r"(?!\d)(?![.,]\d)")


def cites_risk_label(indicator_data: dict, text: str) -> bool:
    """True si el texto cita la etiqueta de riesgo calculada ("riesgo alto")."""
    label = RISK_LABELS.get(indicator_data["risk_level"], "")
    return bool(label) and label in text.lower()


def cites_value(indicator_data: dict, text: str) -> bool:
    """True si el texto cita el valor real del indicador como numero completo."""
    value = indicator_data["value"]
    pattern = _value_regex(value)
    if pattern is None:
        return str(value) in text
    return pattern.search(text) is not None


def _check_extremes(text_lower: str, overbought_ok: bool, oversold_ok: bool, over_msg: str, under_msg: str):
    if not overbought_ok and _asserts(text_lower, _OVERBOUGHT):
        return False, over_msg
    if not oversold_ok and _asserts(text_lower, _OVERSOLD):
        return False, under_msg
    return True, None


def _check_rsi_terms(indicator_data: dict, text_lower: str):
    value = indicator_data["value"]
    signal = indicator_data.get("signal", "neutral")
    # `value` viene redondeado a 2 decimales y `signal` se calculo sin redondear: un 70.004
    # es sobrecompra aunque su valor se muestre como 70.0.
    return _check_extremes(
        text_lower,
        overbought_ok=signal == "sobrecomprado" or value > 70,
        oversold_ok=signal == "sobrevendido" or value < 30,
        over_msg="El texto afirma sobrecompra pero el RSI no supera 70.",
        under_msg="El texto afirma sobreventa pero el RSI no cae bajo 30.",
    )


def _check_bollinger_terms(indicator_data: dict, text_lower: str):
    percent_b = indicator_data["value"]
    signal = indicator_data.get("signal", "normal")
    return _check_extremes(
        text_lower,
        overbought_ok=signal == "sobrecomprado" or percent_b > 1,
        oversold_ok=signal == "sobrevendido" or percent_b < 0,
        over_msg="El texto afirma sobrecompra pero %B no supera 1.",
        under_msg="El texto afirma sobreventa pero %B no es negativo.",
    )


def _check_trend(subject: str):
    """Regla de tendencia (MACD y medias moviles, RF-04.2): el texto no debe afirmar la opuesta.

    Basta con que el texto nombre la tendencia correcta para aceptarlo: puede mencionar la
    otra para descartarla ("no es bajista").
    """

    def check(indicator_data: dict, text_lower: str):
        trend = indicator_data.get("trend", "")
        opposite = {"alcista": "bajista", "bajista": "alcista"}.get(trend)
        if opposite is None or trend[:-1] in text_lower:
            return True, None
        if _asserts(text_lower, re.compile(opposite[:-1] + r"\w*")):
            return False, f"El texto describe una senal {opposite} pero {subject} calculado es {trend}."
        return True, None

    return check


_INDICATOR_CHECKS = {
    "rsi": _check_rsi_terms,
    "macd": _check_trend("el MACD"),
    "bandas_bollinger": _check_bollinger_terms,
    "medias_moviles": _check_trend("el cruce de medias"),
}


def validate_coherence(indicator_data: dict, explanation_text: str):
    """Retorna (es_coherente: bool, motivo: str | None).

    Regla base: el texto debe citar el nivel de riesgo calculado y el valor numerico real.

    Regla especifica por indicador: las categorias cualitativas que el texto afirma
    (sobrecompra, alcista, etc.) deben ser consistentes con el dato segun los umbrales de
    RF-04.2. Ver el docstring del modulo para lo que cuenta como afirmacion.
    """
    expected_label = RISK_LABELS.get(indicator_data["risk_level"], "")
    if expected_label and not cites_risk_label(indicator_data, explanation_text):
        return False, f"El texto no menciona el nivel de riesgo esperado ({expected_label})."

    if not cites_value(indicator_data, explanation_text):
        return False, "El texto no cita el valor numerico real del indicador."

    check = _INDICATOR_CHECKS.get(indicator_data["indicator"])
    if check is not None:
        ok, reason = check(indicator_data, explanation_text.lower())
        if not ok:
            return False, reason

    return True, None
