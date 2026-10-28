# ADR 0004: PostgreSQL como único motor de base de datos

- Estado: aceptada
- Requerimientos relacionados: RNF-02.1, RNF-05, RNF-06

## Contexto y problema

La app guarda cuentas (correo, hash bcrypt), tokens revocados, el log de consultas y las visitas por instrumento. Debe soportar a varias personas a la vez y conservar los datos entre despliegues. Cada selección de instrumento dispara cuatro llamadas a `/api/query`, y cada una escribe en `query_logs`, así que las escrituras son frecuentes.

Hasta esta decisión el código usaba SQLite por defecto, mientras `docs/diseno/09_stack_tecnologico.md` y el diagrama de despliegue ya describían PostgreSQL.

## Criterios de decisión

- Escrituras concurrentes de varios usuarios y workers.
- Persistencia fuera del contenedor de la aplicación.
- Una sola configuración para desarrollo, pruebas y producción.

## Opciones consideradas

### A. SQLite
- Pro: sin servidor; arranca con un comando.
- Contra: un solo escritor a la vez (obliga a un worker de gunicorn); el archivo se pierde en cada redespliegue de un PaaS; no valida largos de `VARCHAR`, lo que oculta errores hasta producción.

### B. SQLite en desarrollo y PostgreSQL en producción
- Pro: comodidad local.
- Contra: dos motores con comportamientos distintos (largos, zonas horarias, concurrencia); los tests no probarían lo que se despliega.

### C. PostgreSQL en todos los entornos (elegida)
- Pro: mismo comportamiento en todas partes; escrituras concurrentes; `timestamptz` y tipos estrictos.
- Contra: hace falta un servidor para correr la app y los tests.

## Decisión

PostgreSQL 14+ con el driver psycopg 3. `DATABASE_URL` es obligatoria; `config.py` rechaza otros motores y normaliza `postgres://` y `postgresql://` a `postgresql+psycopg://`. El pool usa `pool_pre_ping=True` y `pool_recycle=1800`. Los tests usan una base dedicada (`TEST_DATABASE_URL`, nombre terminado en `_test`).

## Consecuencias

- Positivas: varios workers pueden escribir a la vez; los datos sobreviven a los redespliegues.
- Negativas: hace falta instalar PostgreSQL para desarrollar y ejecutar `pytest`; la suite es más lenta que con SQLite en memoria.
- Las migraciones 0001–0005 se escribieron con `batch_alter_table` (pensado para SQLite). **No se han ejecutado contra un PostgreSQL real**; hay que correrlas con `flask --app app db upgrade` antes de afirmar que funcionan.
- El caché de precios sigue siendo por proceso (ADR 0005).

## Verificación

`config.py:_database_url`, `tests/conftest.py`, y `flask --app app db upgrade` contra una base vacía.

## Referencias

- Wiggins, A. (2011). *The Twelve-Factor App*, https://12factor.net (verificar). Configuración por variables de entorno y servicios de respaldo como recursos adjuntos.
- ISO/IEC 25010: características de calidad del producto (fiabilidad, eficiencia de desempeño).
