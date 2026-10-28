# ADR 0005: caché TTL en memoria y precios sin persistir

- Estado: aceptada
- Requerimientos relacionados: RNF-02.2, RNF-08.1, RNF-09

## Contexto y problema

Los precios vienen de fuentes externas con límites de uso. Repetir la misma consulta en cada clic es lento y consume cuota.

## Opciones consideradas

### A. Caché en memoria por proceso con TTL de 5 minutos (elegida)
- Pro: sin infraestructura adicional; los datos financieros son efímeros por diseño.
- Contra: con varios workers, cada uno tiene su caché y repite la petición una vez por TTL; no hay límite de tamaño y las entradas vencidas se eliminan solo al leerse.

### B. Guardar precios en la base de datos
- Contra: obliga a sincronizar datos de terceros; el sistema no lo necesita.

### C. Caché compartido (Redis)
- Pro: una sola copia para todos los workers.
- Contra: otro servicio que operar; no se justifica en esta etapa.

## Decisión

`TTLCache` (`src/extractor/cache.py`) con TTL de 300 s, con cachés separadas para historial, cotizaciones y datos macro. Las noticias usan una caché propia de 20 minutos. La base de datos no almacena precios ni indicadores calculados.

## Consecuencias

- Positivas: simple y suficiente para el volumen esperado.
- Negativas: duplicación de peticiones entre workers; posible crecimiento de memoria. Mejora acotada: añadir `maxsize` y limpieza proactiva.
- `query_logs` guarda valor, unidad, riesgo, ventana y fuente de cada consulta, pero no la serie usada.

## Referencias

- Patrón *cache-aside* con TTL (verificar fuente antes de citar).
