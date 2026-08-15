"""Validacion de coherencia entre explicacion y dato real.

RF-04.2: el sistema debe verificar que las categorias cualitativas
usadas en la explicacion correspondan a los umbrales reales del
indicador (por ejemplo el RSI: sobrevendido, neutral, sobrecomprado).
"""

from __future__ import annotations

from extractor.config import UMBRALES_RSI


class CoherenciaError(ValueError):
    """La explicacion generada contradice el valor real del indicador."""


def categoria_rsi(valor: float) -> str:
    """Devuelve la categoria cualitativa del RSI segun UMBRALES_RSI."""

    for nombre, (minimo, maximo) in UMBRALES_RSI.items():
        if minimo <= valor <= maximo:
            return nombre
    return "neutral"


def validar_coherencia(indicador: str, valor: float, texto: str) -> None:
    """Verifica que el texto no contradiga el valor real del indicador.

    Reglas actuales:
    - Para RSI: si el texto menciona "sobrecomprado", "sobrevendido" o
      "neutral", esa palabra debe coincidir con la categoria real.
    - Para rentabilidad: si menciona "positiva/ganancia" el valor debe
      ser > 0; si menciona "negativa/perdida" debe ser < 0.
    """

    texto_bajo = texto.lower()

    if indicador == "rsi":
        categoria_real = categoria_rsi(valor)
        for otra in ("sobrecomprado", "sobrevendido", "neutral"):
            if otra in texto_bajo and otra != categoria_real:
                raise CoherenciaError(
                    f"RSI={valor:.1f} es '{categoria_real}', pero la "
                    f"explicacion afirma '{otra}'."
                )

    if indicador == "rentabilidad":
        if valor <= 0 and any(t in texto_bajo for t in ("ganancia", "positiva")):
            raise CoherenciaError(
                f"Rentabilidad={valor:.2f}% no es positiva pero el texto "
                "la describe como positiva/ganancia."
            )
        if valor >= 0 and any(t in texto_bajo for t in ("perdida", "negativa")):
            raise CoherenciaError(
                f"Rentabilidad={valor:.2f}% no es negativa pero el texto "
                "la describe como negativa/perdida."
            )
