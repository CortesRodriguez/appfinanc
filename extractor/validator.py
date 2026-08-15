"""Validacion de formato y rango numerico de los indicadores.

RF-03.2: antes de entregar un indicador al Procesador NLP se debe
verificar que sea numerico y este dentro de un rango coherente para
ese indicador. Los limites por indicador se definen en config.py.
"""

from __future__ import annotations

import math

from .config import RANGOS_VALIDOS


class ValorInvalidoError(ValueError):
    """El valor extraido no es numerico o esta fuera de rango."""


def validar_indicador(nombre: str, valor: float | int | None) -> float:
    """Valida un valor puntual y lo devuelve como float.

    - Rechaza None, NaN o valores no numericos.
    - Rechaza valores fuera del rango declarado para el indicador.
    - Devuelve el valor convertido a `float` en caso valido.
    """

    if valor is None:
        raise ValorInvalidoError(f"Indicador '{nombre}' no fue extraido (None).")

    try:
        valor_float = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValorInvalidoError(
            f"Indicador '{nombre}' no es numerico: {valor!r}"
        ) from exc

    if math.isnan(valor_float) or math.isinf(valor_float):
        raise ValorInvalidoError(f"Indicador '{nombre}' contiene NaN/inf.")

    rango = RANGOS_VALIDOS.get(nombre)
    if rango is not None:
        minimo, maximo = rango
        if not (minimo <= valor_float <= maximo):
            raise ValorInvalidoError(
                f"Indicador '{nombre}' fuera de rango [{minimo}, {maximo}]: "
                f"{valor_float}"
            )
    return valor_float
