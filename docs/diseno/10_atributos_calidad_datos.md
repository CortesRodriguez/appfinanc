# Fase 10 — Atributos de calidad y gestión de datos (C12)

Atributos según ISO/IEC 25010. Cada fila indica cómo lo cumple el sistema y dónde se comprueba. Lo que no está implementado o verificado aparece como **pendiente**.

## Atributos de calidad

| Atributo | Requerimiento | Mecanismo en el sistema | Evidencia |
|---|---|---|---|
| Eficiencia de desempeño | RNF-01, RNF-02 | Caché TTL de 5 min por proceso; se registra `processing_time_ms` en cada consulta | `src/extractor/cache.py`, `query_logs.processing_time_ms`. **Pendiente**: medir el tiempo ≤ 5 s con carga y registrarlo |
| Escalabilidad | RNF-02.1 | PostgreSQL admite varios workers de gunicorn escribiendo a la vez (ADR 0004). El caché no se comparte entre workers | `tests/test_concurrency.py`. **Pendiente**: prueba con 5 usuarios reales sobre PostgreSQL |
| Seguridad | RNF-06 | Contraseñas con bcrypt (8–64 caracteres); JWT en cookie httpOnly con expiración de 24 h; CSRF de doble envío; revocación de tokens; bloqueo tras 5 intentos fallidos (ADR 0006) | `tests/test_auth.py` |
| Fiabilidad y disponibilidad | RNF-09 | Reintentos (hasta 3) y respaldo Yahoo → Alpha Vantage; el LLM cae a plantillas; FinBERT y noticias se omiten sin error (ADR 0002, 0008) | `tests/test_news.py`, `tests/test_explainer.py` |
| Recuperación | RNF-09 | Respaldos del servicio gestionado de PostgreSQL y `pg_dump` manual. **Pendiente**: elegir el proveedor y probar una restauración | — |
| Usabilidad y legibilidad | RNF-03, RNF-04 | Índice Fernández-Huerta por explicación; máximo 150 palabras; niveles adaptativos; etiqueta de riesgo no solo por color | `src/nlp/readability.py`, `tests/test_validator.py` |
| Mantenibilidad | RNF-07 | Paquetes por responsabilidad; migraciones versionadas; ficha de nivel única (ADR 0001, 0003) | `src/`, `migrations/` |
| Corrección funcional | RF-04.2 | `validate_coherence` contrasta riesgo, valor y umbrales; marca `coherent=false`, no bloquea (ADR 0002) | `tests/test_validator.py` |

## Gestión de datos

| Dato | Dónde vive | Retención | Notas |
|---|---|---|---|
| Cuenta (nombre, correo, hash bcrypt, experiencia declarada) | `users` | Mientras exista la cuenta | Único dato identificable (RNF-05.1) |
| Tokens revocados | `revoked_tokens` | Hasta que se limpien | **Pendiente**: purga de tokens ya expirados |
| Consultas (instrumento, indicador, valor, riesgo, ventana, fuente, tiempo) | `query_logs` | Indefinida | Lleva `session_id` y, si hay sesión, `user_id` |
| Visitas por instrumento | `instrument_visits` | Indefinida | Alimenta el perfil |
| Precios, indicadores calculados, noticias | Memoria (`TTLCache`, `news_cache`) | 5 min (precios), 20 min (noticias) | No se persisten (RNF-08.1) |

- **Consistencia**: el esquema cambia solo con migraciones Alembic (`flask db upgrade`); la app no ejecuta `db.create_all()`. PostgreSQL valida tipos y largos; el ticker se valida antes de llegar a la base (`MAX_SYMBOL_LENGTH`).
- **Trazabilidad**: cada consulta guarda fuente, marca de tiempo y tiempo de procesamiento. No guarda la serie de precios usada ni el resultado de la validación de coherencia.
- **Integridad de la fuente**: los datos provienen de proveedores externos no controlados (ver `11_riesgos_cumplimiento.md`).
