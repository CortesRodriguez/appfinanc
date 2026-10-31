"""Cache en memoria de datos extraidos (RNF-02.2).

Evita repetir solicitudes a la API financiera para el mismo instrumento
dentro de un intervalo configurable (por defecto 5 minutos).
"""

import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key, value, ttl_seconds: int = None):
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def get_or_load(self, key, loader, ttl_seconds: int = None, cacheable=None):
        """Valor cacheado de `key`; si no hay, lo obtiene con `loader()` y lo guarda.

        `cacheable(valor)` permite no guardar resultados que no valen la pena
        repetir (p. ej. un lote donde todo fallo): la proxima llamada reintenta.
        Si `loader` lanza, nada se guarda y la excepcion sube.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        value = loader()
        if cacheable is None or cacheable(value):
            self.set(key, value, ttl_seconds)
        return value

    def clear(self):
        with self._lock:
            self._store.clear()


price_history_cache = TTLCache()
