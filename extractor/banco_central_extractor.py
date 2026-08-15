"""Extraccion de indicadores macroeconomicos desde el Banco Central.

RF-02.3: obtiene UF, dolar observado, TPM e IPC desde la API publica
de mindicador.cl. Estos valores alimentan la cinta de precios que se
desarrollara en Sprint 7 (Presentador). El extractor deja el bundle
listo para consumo, sin acoplarlo aun a la vista.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import requests

from .cache import CacheIndicadores, con_reintentos
from .traceability import Trazabilidad
from .validator import ValorInvalidoError, validar_indicador

_LOG = logging.getLogger("extractor.banco_central")
_ENDPOINT = "https://mindicador.cl/api/{codigo}"

# Codigos declarados por mindicador.cl para RF-02.3.
_CODIGOS = {
    "uf": "uf",
    "dolar": "dolar",
    "tpm": "tpm",
    "ipc": "ipc",
}


@dataclass
class IndicadoresMacro:
    """Bundle unificado para la cinta de precios."""

    fecha_extraccion: str
    fuente: str = "Banco Central de Chile (mindicador.cl)"
    valores: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "fecha_extraccion": self.fecha_extraccion,
            "fuente": self.fuente,
            "valores": self.valores,
        }


class BancoCentralExtractor:
    """Cliente HTTP simple para mindicador.cl."""

    def __init__(
        self,
        cache: CacheIndicadores | None = None,
        trazabilidad: Trazabilidad | None = None,
    ) -> None:
        self.cache = cache or CacheIndicadores()
        self.trazabilidad = trazabilidad or Trazabilidad()

    def extraer(self, indicadores: Iterable[str] | None = None) -> IndicadoresMacro:
        objetivos = list(indicadores) if indicadores else list(_CODIGOS)
        bundle = IndicadoresMacro(
            fecha_extraccion=datetime.now(timezone.utc).isoformat(timespec="seconds")
        )

        for nombre in objetivos:
            if nombre not in _CODIGOS:
                _LOG.warning("indicador macro '%s' no soportado", nombre)
                continue

            clave = f"bcch::{nombre}"
            cacheado = self.cache.get(clave)
            if cacheado is not None:
                bundle.valores[nombre] = cacheado
                continue

            try:
                valor = con_reintentos(lambda n=nombre: self._consultar(n))
                valor_validado = validar_indicador(nombre, valor) if nombre != "ipc" else float(valor)
            except (requests.RequestException, ValorInvalidoError, RuntimeError) as exc:
                # RNF-09.1: se informa el fallo, pero el bundle sigue en pie
                # para que la cinta muestre lo que si se pudo obtener.
                _LOG.warning("no se pudo obtener %s: %s", nombre, exc)
                self.trazabilidad.registrar(
                    ticker="MACRO",
                    indicador=nombre,
                    fuente=bundle.fuente,
                    valor=None,
                    exitoso=False,
                    detalle=str(exc),
                )
                continue

            self.cache.set(clave, valor_validado)
            bundle.valores[nombre] = valor_validado
            self.trazabilidad.registrar(
                ticker="MACRO",
                indicador=nombre,
                fuente=bundle.fuente,
                valor=valor_validado,
            )

        return bundle

    def _consultar(self, nombre: str) -> float:
        codigo = _CODIGOS[nombre]
        respuesta = requests.get(_ENDPOINT.format(codigo=codigo), timeout=10)
        respuesta.raise_for_status()
        payload = respuesta.json()
        serie = payload.get("serie") or []
        if not serie:
            raise RuntimeError(
                f"mindicador.cl no devolvio la serie para el indicador '{nombre}'."
            )
        return float(serie[0]["valor"])
