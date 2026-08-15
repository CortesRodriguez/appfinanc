"""Cache y reintentos de las llamadas al Extractor.

RF-03.1: actualizar respetando el rate limit de las APIs.
RNF-02.2: reutilizar el valor obtenido durante los ultimos 5 minutos
antes de solicitar nuevamente el mismo instrumento a la API.
RNF-09.2: reintentar hasta 3 veces ante fallos de conexion antes de
propagar el error.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .config import CACHE_TTL_SEG, REINTENTOS_MAX, REINTENTO_ESPERA_SEG


@dataclass
class _EntradaCache:
    valor: Any
    timestamp: float


class CacheIndicadores:
    """Cache en memoria con TTL configurable (RNF-02.2)."""

    def __init__(self, ttl_seg: int = CACHE_TTL_SEG) -> None:
        self.ttl_seg = ttl_seg
        self._store: dict[str, _EntradaCache] = {}

    def get(self, clave: str) -> Any | None:
        entrada = self._store.get(clave)
        if entrada is None:
            return None
        if (time.time() - entrada.timestamp) > self.ttl_seg:
            self._store.pop(clave, None)
            return None
        return entrada.valor

    def set(self, clave: str, valor: Any) -> None:
        self._store[clave] = _EntradaCache(valor=valor, timestamp=time.time())

    def invalidar(self, clave: str | None = None) -> None:
        if clave is None:
            self._store.clear()
        else:
            self._store.pop(clave, None)


def con_reintentos(
    accion: Callable[[], Any],
    *,
    reintentos: int = REINTENTOS_MAX,
    espera_seg: float = REINTENTO_ESPERA_SEG,
    excepciones: tuple[type[BaseException], ...] = (Exception,),
) -> Any:
    """Ejecuta `accion` con hasta `reintentos` intentos (RNF-09.2)."""

    ultimo_error: BaseException | None = None
    for intento in range(1, reintentos + 1):
        try:
            return accion()
        except excepciones as exc:
            ultimo_error = exc
            if intento == reintentos:
                break
            time.sleep(espera_seg * intento)
    assert ultimo_error is not None
    raise ultimo_error
