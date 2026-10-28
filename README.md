# appfint

Prototipo funcional del proyecto de título **"Desarrollo de un sistema basado en inteligencia artificial para apoyar la comprensión de información financiera técnica en inversionistas principiantes del contexto digital chileno"**.

El sistema extrae indicadores financieros públicos (volatilidad, RSI, medias móviles, rentabilidad), y genera una explicación en lenguaje natural y en español, adaptada al nivel de cada usuario, para quienes no tienen formación financiera.

## Arquitectura (modelo de vistas 4+1)

El código sigue la arquitectura modular definida en la memoria: cuatro componentes independientes, orquestados por Flask.

```
src/
  extractor/    # RF-01, RF-02, RF-03 — obtiene y normaliza datos (Yahoo Finance / Alpha Vantage), con cache y reintentos
  nlp/          # RF-04, RF-05, RF-06 — genera explicaciones (LLM con plantillas de respaldo), clasifica riesgo, valida coherencia, glosario
  auth/         # RF-16, RF-17, RNF-09 — registro, login/logout con JWT en cookie, bcrypt
  profile/      # RF-18, RF-19 — perfil adaptativo de aprendizaje; modelos QueryLog (RNF-01.2) e InstrumentVisit
  web/          # RF-07 a RF-10 — Presentador: rutas Flask, plantillas HTML, CSS y JS
data/           # catálogo de instrumentos y glosario
tests/          # pruebas unitarias e integración (sin llamadas de red reales)
```

## Requisitos

- Python 3.11+
- PostgreSQL 14+ (único motor soportado, driver psycopg 3). Permite escrituras concurrentes de varios usuarios y workers, y los datos sobreviven a los redespliegues. Necesitas una base para la app (`appfint`) y otra solo para los tests (`appfint_test`).
- (Opcional) una API key gratuita de [Alpha Vantage](https://www.alphavantage.co/support/#api-key), usada como fuente de respaldo si Yahoo Finance falla (RNF-08).

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # en producción basta requirements.txt
createdb appfint && createdb appfint_test
cp .env.example .env   # ajusta DATABASE_URL, TEST_DATABASE_URL, FLASK_SECRET_KEY, JWT_SECRET_KEY y, si quieres, ALPHAVANTAGE_API_KEY

flask --app app db upgrade   # aplica las migraciones de migrations/ sobre DATABASE_URL
```

El esquema se versiona con Flask-Migrate (Alembic). Al cambiar un modelo:

```bash
flask --app app db migrate -m "descripcion del cambio"   # genera la migración; revisarla antes de aplicar
flask --app app db upgrade
```

## Ejecución

```bash
python app.py
```

La aplicación queda disponible en `http://127.0.0.1:5001/`. En producción se sirve con gunicorn (aplicando antes las migraciones):

```bash
flask --app app db upgrade
gunicorn -w 2 --threads 4 -b 0.0.0.0:8000 app:app
```

PostgreSQL admite varios workers escribiendo a la vez. Cada worker tiene su propio caché en memoria de precios (TTL de 5 minutos), por lo que un mismo instrumento puede consultarse una vez por worker dentro de ese intervalo.

## Pruebas

```bash
pytest
```

Corren contra la base PostgreSQL de `TEST_DATABASE_URL`. Cada test crea y borra todas las tablas, por eso `conftest.py` exige que el nombre de la base termine en `_test` y nunca uses la base de la app.

Las pruebas cubren el cálculo de indicadores, la generación y validación de explicaciones, la autenticación, el perfil adaptativo y el flujo completo de la API `/api/query`, `/api/quotes`, `/api/chart` y `/api/lookup` (con la fuente de datos simulada, para no depender de red externa).

## Verificar el catálogo de instrumentos

El catálogo (`data/instruments.json`) son exactamente las 30 acciones que componen el IPSA — sin ETF ni el índice IPSA mismo, que ya se muestra por separado en la cinta de precios. Los tickers se tomaron de la nómina oficial de constituyentes del IPSA y se les agregó el sufijo `.SN` para Yahoo Finance; conviene verificarlos con datos reales antes de una demo:

```bash
python scripts/validate_tickers.py
```

Imprime qué tickers responden en Yahoo Finance y cuáles no, para poder corregir o quitar del catálogo los que hayan cambiado o estén deslistados. Además del catálogo fijo, la barra de búsqueda del dashboard permite consultar directamente cualquier otro ticker de Yahoo Finance vía `/api/lookup`, sin necesidad de agregarlo al catálogo.

## Recorrido funcional (mapeo a casos de uso)

| Página / endpoint | Caso de uso | Requerimientos |
|---|---|---|
| `/` — Dashboard (sidebar + gráfico + tarjetas) | CU-01, CU-02 | RF-01, RF-02, RF-07, RF-08, RNF-01 |
| Botón "No entendí esto" en cada tarjeta | CU-04 | RF-06.2 |
| `/history` | CU-03 | RF-10 |
| `/glosario` | CU-05 | RF-09.2 |
| `/registro` | CU-11 | RF-16 |
| `/login`, cerrar sesión en la barra superior | CU-12 | RF-17, RNF-09 |
| `/perfil` | CU-13 | RF-18, RF-19 |
| Cinta de precios (todas las páginas) | CU-01 | RF-01, RF-02 |

## Notas de diseño

- **Extractor**: usa `yfinance` como fuente primaria y Alpha Vantage como respaldo; cachea el historial de precios por instrumento/período durante 5 minutos (RNF-02.2) y reintenta hasta 3 veces ante fallas de conexión (RNF-08.2).
- **Procesador NLP**: con `USE_LLM=true` y `GROQ_API_KEY`, un LLM (Groq, `qwen/qwen3.8-27b`) redacta la explicación según la ficha del nivel del usuario; si falla o su salida no pasa la verificación mínima (etiqueta de riesgo, valor y términos prohibidos), se usan plantillas en español con variantes (regeneración de RF-06.2). Toda explicación se acota a 150 palabras (RNF-04.2) y se mide con una aproximación del índice Fernández-Huerta (RNF-04.1). Con `transformers`/`torch` y `USE_FINBERT=true` se agrega además una etiqueta de sentimiento de FinBERT (RF-04.1); el sistema funciona igual sin esa librería.
- **Validador de coherencia**: contrasta el nivel de riesgo y el valor citado en el texto generado contra el valor real del indicador; si discrepan, la respuesta marca `coherent=false` y la interfaz muestra un aviso.
- **Trazabilidad**: cada consulta queda en `query_logs` (fuente, tiempo de procesamiento, valor, riesgo y ventana); si hay sesión iniciada, se asocia a la cuenta para el historial y el perfil adaptativo.
- **Alcance**: el catálogo de instrumentos e indicadores está acotado intencionalmente (`data/*.json`), tal como define el alcance del proyecto. El sistema no genera recomendaciones de inversión ni ejecuta transacciones.
- **Dashboard**: el sidebar consulta `/api/quotes` (precio y variación diaria de todo el catálogo en un solo lote, cacheado 5 minutos) y el panel principal combina un gráfico de tendencia (precio, MA50, MA200 vía `/api/chart`) con las cuatro tarjetas de indicadores (una llamada a `/api/query` por indicador, reutilizando toda la lógica de extracción/NLP/validación/logging ya existente). El historial de sesión (RF-10) agrupa las consultas del mismo instrumento en una sola fila en vez de una por indicador.
- **Autenticación**: JWT (`Flask-JWT-Extended`) guardado en cookie httpOnly, con protección CSRF por token de doble envío (cookie `csrf_access_token`, legible por JS, enviada en el header `X-CSRF-TOKEN` — ver `static/js/csrf.js`). Las contraseñas se guardan con `Flask-Bcrypt` (RF-16.3) y el token expira a las 24 horas (RNF-09.2). Cerrar sesión agrega el `jti` del token a una lista de revocación en base de datos (RF-17.3), no solo borra la cookie.
- **Consulta anónima vs. con cuenta**: iniciar sesión es opcional. El dashboard funciona igual sin cuenta (consulta anónima, como antes de agregar autenticación); si hay sesión iniciada, cada consulta y regeneración además queda asociada a la cuenta (`QueryLog.user_id`) para construir el perfil de aprendizaje, sin cambiar el flujo visible de consulta.
- **Perfil adaptativo (RF-18.3)**: cuando un usuario ha regenerado la explicación de un indicador 2 o más veces, las siguientes explicaciones de ese indicador para ese usuario se generan en modo "detallado" (con más contexto y una frase aclaratoria en lenguaje simple), calculado en `src/profile/service.py:get_detail_level`.
- **Cinta de precios**: barra superior (visible en toda la app) con IPSA, UF, dólar, TPM e IPC — estos cuatro últimos desde [mindicador.cl](https://mindicador.cl), la API pública del Banco Central de Chile, independiente de Yahoo Finance/Alpha Vantage — seguida de las 30 acciones del IPSA, desplazándose en loop continuo (`static/js/ticker.js`, `static/css/style.css`). Se actualiza cada 5 minutos, igual que el cache del resto del dashboard; si `mindicador.cl` no responde, la cinta sigue mostrando IPSA y las acciones (RNF-08) y solo omite UF/dólar/TPM/IPC. Las cuatro cifras macro se muestran sin flecha de variación diaria porque la API no entrega el valor del día anterior en la misma llamada; las acciones sí tienen variación real, calculada igual que en el sidebar.
- **Historial sin condición de carrera (RF-10)**: el dashboard dispara varias solicitudes en paralelo al seleccionar un instrumento (una por indicador, más el registro de historial). Como Flask serializa toda la sesión en una sola cookie por respuesta, si esa cookie recién se estuviera creando en ese mismo instante, dos respuestas concurrentes podían pisarse y perder el historial recién escrito. Se resolvió estableciendo la cookie de sesión en la primera carga de página (`before_app_request`), antes de que el dashboard dispare ninguna llamada — y separando el registro del historial (`/api/historial/visita`, una llamada por instrumento) de las cuatro llamadas paralelas a `/api/query`.- **"Consultas totales" del perfil (RF-19.3)**: seleccionar un instrumento dispara cuatro consultas de indicador en paralelo, pero para el usuario es una sola acción. El conteo del perfil ya no sale de `QueryLog` (que tiene esas cuatro filas por selección) sino de una tabla nueva, `InstrumentVisit`, con una fila por instrumento seleccionado; el total mostrado es visitas + regeneraciones explícitas, que es lo que el usuario realmente hizo.
- **Selector de rango temporal**: botones 1M/3M/6M/1A sobre el gráfico (`30/90/180/365` días) que controlan tanto el gráfico de tendencia como las cuatro tarjetas de indicadores para el instrumento seleccionado.
