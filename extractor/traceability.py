"""Registro de trazabilidad de cada extraccion.

RF-02.2: el sistema debe registrar fecha, hora y fuente de datos
(Yahoo Finance, Alpha Vantage o mindicador.cl) de cada indicador
extraido. Se persisten los eventos en un log JSONL para poder
consultarlos posteriormente durante la validacion de coherencia.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path


class Trazabilidad:
    """Registrador simple de eventos de extraccion."""

    def __init__(self, archivo: str | os.PathLike[str] | None = None) -> None:
        base = Path(__file__).resolve().parent.parent / "logs"
        base.mkdir(parents=True, exist_ok=True)
        self.archivo = Path(archivo) if archivo else base / "trazabilidad.jsonl"
        self._logger = logging.getLogger("extractor.trazabilidad")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def registrar(
        self,
        *,
        ticker: str,
        indicador: str,
        fuente: str,
        valor: float | int | str | None,
        exitoso: bool = True,
        detalle: str | None = None,
    ) -> None:
        evento = {
            "fecha_hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ticker": ticker,
            "indicador": indicador,
            "fuente": fuente,
            "valor": valor,
            "exitoso": exitoso,
            "detalle": detalle,
        }
        with self.archivo.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(evento, ensure_ascii=False) + "\n")
        nivel = self._logger.info if exitoso else self._logger.warning
        nivel(
            "trazabilidad %s %s -> %s (%s)",
            ticker,
            indicador,
            valor,
            fuente,
        )
