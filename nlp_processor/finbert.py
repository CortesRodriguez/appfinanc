"""Envoltorio del modelo FinBERT.

RF-04.1: cada indicador extraido se procesa mediante un modelo de
lenguaje preentrenado (FinBERT). Este wrapper carga el modelo de
Hugging Face de forma perezosa. Si `transformers` / `torch` no estan
disponibles, cae a una clasificacion heuristica basada en el propio
valor del indicador (media movil, rentabilidad, RSI). El resto del
Procesador NLP consume la misma interfaz en ambos casos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

_LOG = logging.getLogger("nlp.finbert")

Sentimiento = Literal["positivo", "neutral", "negativo"]


@dataclass
class ResultadoFinBert:
    """Salida uniforme del procesador (via modelo o heuristica)."""

    sentimiento: Sentimiento
    score: float
    fuente: str  # "finbert" | "heuristica"


class FinBertProcessor:
    """Adapter perezoso para el modelo FinBERT.

    - Si el paquete `transformers` esta disponible carga
      `ProsusAI/finbert` la primera vez que se invoca `procesar`.
    - Si el modelo no puede cargarse (sin dependencias o sin red) se
      utiliza una regla simple derivada del valor del indicador y se
      indica en `fuente`.
    """

    MODELO = "ProsusAI/finbert"

    def __init__(self) -> None:
        self._pipeline = None
        self._intento_carga = False

    def procesar(self, texto: str, valor_referencia: float | None = None) -> ResultadoFinBert:
        pipeline = self._cargar_pipeline()
        if pipeline is not None:
            try:
                salida = pipeline(texto)[0]
                etiqueta = str(salida["label"]).lower()
                score = float(salida["score"])
                mapa: dict[str, Sentimiento] = {
                    "positive": "positivo",
                    "negative": "negativo",
                    "neutral": "neutral",
                }
                return ResultadoFinBert(
                    sentimiento=mapa.get(etiqueta, "neutral"),
                    score=score,
                    fuente="finbert",
                )
            except Exception as exc:  # noqa: BLE001 - queremos fallback ancho
                _LOG.warning("FinBERT fallo, usando heuristica: %s", exc)

        return self._heuristica(valor_referencia)

    # ------------------------------------------------------------------
    def _cargar_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        if self._intento_carga:
            return None
        self._intento_carga = True
        try:
            from transformers import pipeline  # type: ignore
        except ImportError:
            _LOG.info("transformers no disponible; usando heuristica.")
            return None
        try:
            self._pipeline = pipeline("sentiment-analysis", model=self.MODELO)
            return self._pipeline
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("No se pudo cargar %s: %s", self.MODELO, exc)
            return None

    @staticmethod
    def _heuristica(valor: float | None) -> ResultadoFinBert:
        if valor is None:
            return ResultadoFinBert("neutral", 0.5, "heuristica")
        if valor > 5.0:
            return ResultadoFinBert("positivo", 0.7, "heuristica")
        if valor < -5.0:
            return ResultadoFinBert("negativo", 0.7, "heuristica")
        return ResultadoFinBert("neutral", 0.6, "heuristica")
