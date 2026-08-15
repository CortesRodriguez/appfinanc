"""Clasificacion de riesgo relativo del indicador.

RF-06.1: el sistema debe clasificar el nivel de riesgo del indicador
procesado en bajo, medio o alto. Se usa volatilidad como driver
principal (segun CU-12) y se ajusta con el RSI cuando el indicador
consultado es un momentum.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NivelRiesgo = Literal["bajo", "medio", "alto"]


@dataclass
class Etiqueta:
    nivel: NivelRiesgo
    color: str
    icono: str


COLORES = {
    "bajo": "#2f9e44",
    "medio": "#f59f00",
    "alto": "#e03131",
}

ICONOS = {
    "bajo": "check-circle",
    "medio": "alert-triangle",
    "alto": "alert-octagon",
}


def clasificar_riesgo(volatilidad: float, rsi: float | None = None) -> Etiqueta:
    """Retorna la etiqueta de riesgo del indicador procesado.

    Cortes empiricos utilizados por la literatura para volatilidad
    anualizada de acciones chilenas del IPSA:
    - < 15 %  -> bajo
    - 15-30 % -> medio
    - >= 30 % -> alto
    Si el RSI esta en extremos (>=75 o <=25) se sube un nivel.
    """

    if volatilidad < 15:
        nivel: NivelRiesgo = "bajo"
    elif volatilidad < 30:
        nivel = "medio"
    else:
        nivel = "alto"

    if rsi is not None and (rsi >= 75 or rsi <= 25):
        nivel = {"bajo": "medio", "medio": "alto", "alto": "alto"}[nivel]

    return Etiqueta(nivel=nivel, color=COLORES[nivel], icono=ICONOS[nivel])
