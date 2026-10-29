# 0004. PostgreSQL como único motor de base de datos

## Status

Aceptada (2026-10-28).

## Context

La app guarda cuentas (correo, hash bcrypt), tokens revocados, el log de consultas y las visitas por instrumento. Debe soportar a varias personas a la vez y conservar los datos entre despliegues. Cada selección de instrumento dispara cuatro llamadas a `/api/query` y cada una escribe en `query_logs`, así que las escrituras son frecuentes.

Hasta esta decisión el código usaba SQLite por defecto, mientras `docs/diseno/09_stack_tecnologico.md` y el diagrama de despliegue ya describían PostgreSQL.

Requerimientos relacionados: RNF-02.1, RNF-05, RNF-06.

Alternativas consideradas:

- **SQLite.** Sin servidor y arranca con un comando. Costos: un solo escritor a la vez (obliga a un worker de gunicorn); el archivo se pierde en cada redespliegue de un PaaS; no valida largos de `VARCHAR`, lo que oculta errores hasta producción.
- **SQLite en desarrollo y PostgreSQL en producción.** Cómodo en local, pero son dos motores con comportamientos distintos (largos, zonas horarias, concurrencia) y los tests no probarían lo que se despliega.
- **PostgreSQL en todos los entornos.** Mismo comportamiento en todas partes, escrituras concurrentes, `timestamptz` y tipos estrictos. Costo: hace falta un servidor para correr la app y los tests.

Se priorizó la escritura concurrente de varios usuarios y workers, la persistencia fuera del contenedor y una sola configuración para desarrollo, pruebas y producción.

Referencias (verificar antes de citar):

- Wiggins, A. (2011). *The Twelve-Factor App*. https://12factor.net. Configuración por variables de entorno y servicios de respaldo como recursos adjuntos.
- ISO/IEC 25010: características de calidad del producto (fiabilidad, eficiencia de desempeño).

## Decision

PostgreSQL 14+ con el driver psycopg 3. `DATABASE_URL` es obligatoria; `config.py` rechaza otros motores y normaliza `postgres://` y `postgresql://` a `postgresql+psycopg://`. El pool usa `pool_pre_ping=True` y `pool_recycle=1800`. Los tests usan una base dedicada (`TEST_DATABASE_URL`, nombre terminado en `_test`).

## Consequences

Se vuelve más fácil:

- Que varios workers escriban a la vez.
- Que los datos sobrevivan a los redespliegues.

Se vuelve más difícil:

- Desarrollar y ejecutar `pytest`: hace falta instalar PostgreSQL, y la suite es más lenta que con SQLite en memoria.
- Compartir el caché de precios entre workers: sigue siendo por proceso (ADR 0005).

Las migraciones 0001–0005 se escribieron con `batch_alter_table`, pensado para SQLite. Verificado el 2026-10-28 contra PostgreSQL 16: la base quedó en la revisión `0005`, `flask db check` no detecta cambios pendientes y los tests pasan. Falta repetir `flask db upgrade` sobre una base totalmente vacía.

Verificación: `config.py:_database_url`, `tests/conftest.py` y `flask --app app db upgrade`.
