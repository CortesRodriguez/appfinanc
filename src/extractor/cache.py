"""Cache en memoria de datos extraidos (RNF-02.2).

Evita repetir solicitudes a la API financiera para el mismo instrumento
dentro de un intervalo configurable (por defecto 5 minutos).
"""

import time


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store = {}

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key, value):
        self._store[key] = (value, time.time() + self.ttl_seconds)

    def clear(self):
        self._store.clear()


price_history_cache = TTLCache()
