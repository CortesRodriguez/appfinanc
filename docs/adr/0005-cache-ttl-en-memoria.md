# 0005. Caché TTL en memoria y precios sin persistir

## Status

Aceptada (registrada a posteriori).

## Context

Los precios vienen de fuentes externas con límites de uso. Repetir la misma consulta en cada clic es lento y consume cuota.

Requerimientos relacionados: RNF-02.2, RNF-08.1, RNF-09.

Alternativas consideradas:

- **Caché en memoria por proceso con TTL de 5 minutos.** Sin infraestructura adicional, y los datos financieros son efímeros por diseño. Costos: con varios workers cada uno tiene su caché y repite la petición una vez por TTL; no hay límite de tamaño y las entradas vencidas se eliminan solo al leerse.
- **Guardar los precios en la base de datos.** Descartada: obliga a sincronizar datos de terceros y el sistema no lo necesita.
- **Caché compartido (Redis).** Una sola copia para todos los workers, pero es otro servicio que operar; no se justifica en esta etapa.

Referencia (verificar antes de citar): patrón *cache-aside* con TTL.

## Decision

`TTLCache` (`src/extractor/cache.py`) con TTL de 300 s, con cachés separadas para historial, cotizaciones y datos macro. Las noticias usan una caché propia de 20 minutos. La base de datos no almacena precios ni indicadores calculados.

## Consequences

Se vuelve más fácil:

- Implementar y operar el caché: es simple y suficiente para el volumen esperado.

Se vuelve más difícil:

- Evitar peticiones duplicadas entre workers.
- Acotar la memoria: posible crecimiento sin límite. Mejora acotada: añadir `maxsize` y limpieza proactiva.
- Reconstruir qué datos vio el usuario: `query_logs` guarda valor, unidad, riesgo, ventana y fuente de cada consulta, pero no la serie usada.
