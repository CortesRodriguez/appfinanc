# appfint

Prototipo funcional del proyecto de título **"Desarrollo de un sistema basado en inteligencia artificial para apoyar la comprensión de información financiera técnica en inversionistas principiantes del contexto digital chileno"**.

El sistema extrae indicadores financieros públicos (volatilidad, RSI, medias móviles, rentabilidad), genera una explicación en lenguaje natural y en español para usuarios sin formación financiera, y evalúa su efectividad mediante encuestas de comprensión pre/post-test.

## Arquitectura (modelo de vistas 4+1)

El código sigue la arquitectura modular definida en la memoria: cuatro componentes independientes, orquestados por Flask.

```
src/
  extractor/    # RF-01, RF-02, RF-03 — obtiene y normaliza datos (Yahoo Finance / Alpha Vantage), con cache y reintentos
  nlp/          # RF-04, RF-05, RF-06, RF-13 — genera explicaciones, clasifica riesgo, valida coherencia, glosario
  evaluation/   # RF-11 a RF-15 — encuestas pre/post, logs anonimizados, reportes y exportación CSV
  auth/         # RF-16, RF-17, RNF-09 — registro, login/logout con JWT en cookie, bcrypt
  profile/      # RF-18, RF-19 — perfil adaptativo de aprendizaje (agregaciones sobre QueryLog)
  web/          # RF-07 a RF-10 — Presentador: rutas Flask, plantillas HTML, CSS y JS
data/           # catálogo de instrumentos, glosario y banco de preguntas
tests/          # pruebas unitarias e integración (sin llamadas de red reales)
```

## Requisitos

- Python 3.11+
- (Opcional) una API key gratuita de [Alpha Vantage](https://www.alphavantage.co/support/#api-key), usada como fuente de respaldo si Yahoo Finance falla (RNF-08).

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajusta FLASK_SECRET_KEY, JWT_SECRET_KEY y, si quieres, ALPHAVANTAGE_API_KEY
```

> Si vienes de una versión anterior del proyecto (sin autenticación), borra `appfint.db` antes de levantar la app: se agregaron columnas y tablas nuevas (usuarios, tokens revocados, perfil) y este prototipo no usa migraciones — `db.create_all()` solo crea tablas que no existen, no modifica las existentes.

## Ejecución

```bash
python app.py
```

La aplicación queda disponible en `http://127.0.0.1:5000/`. La base de datos SQLite (`appfint.db`) se crea automáticamente al primer arranque.

## Pruebas

```bash
pytest
```

Las pruebas cubren el cálculo de indicadores, la generación y validación de explicaciones, el flujo de encuestas y el flujo completo de la API `/api/query`, `/api/quotes`, `/api/chart` y `/api/lookup` (con la fuente de datos simulada, para no depender de red externa).

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
| `/encuesta/pre`, `/encuesta/post` | CU-06, CU-07 | RF-11, RF-12, RNF-05 |
| `/admin/coherencia` | CU-08 | RF-13 |
| `/admin/reporte` | CU-09 | RF-15.1 |
| `/admin/reporte/exportar.csv` | CU-10 | RF-15.2 |
| `/registro` | CU-11 | RF-16 |
| `/login`, cerrar sesión en la barra superior | CU-12 | RF-17, RNF-09 |
| `/perfil` | CU-13 | RF-18, RF-19 |
| Cinta de precios (todas las páginas) | CU-01 | RF-01, RF-02 |

## Notas de diseño

- **Extractor**: usa `yfinance` como fuente primaria y Alpha Vantage como respaldo; cachea el historial de precios por instrumento/período durante 5 minutos (RNF-02.2) y reintenta hasta 3 veces ante fallas de conexión (RNF-08.2).
- **Procesador NLP**: genera explicaciones mediante plantillas en español con variantes (para la regeneración de RF-06.2), acotadas a 150 palabras (RNF-04.2) y verificadas con una aproximación del índice de legibilidad Fernández-Huerta (adaptación al español de Flesch, RNF-04.1). Si se instala `transformers`/`torch` y se activa `USE_FINBERT=true`, se agrega una señal adicional de sentimiento de FinBERT (RF-04.1); el sistema sigue funcionando normalmente si esa librería no está disponible.
- **Validador de coherencia**: contrasta el nivel de riesgo y el valor citado en el texto generado contra el valor real del indicador; los casos discordantes quedan marcados como "no concluyente" para revisión manual (RF-13).
- **Evaluación**: toda persistencia (encuestas, logs de consulta, chequeos de coherencia) se asocia a un identificador de sesión anónimo (cookie de Flask), nunca a datos personales (RNF-05).
- **Alcance**: el catálogo de instrumentos, indicadores y preguntas de encuesta está acotado intencionalmente (`data/*.json`), tal como define el alcance del proyecto. El sistema no genera recomendaciones de inversión ni ejecuta transacciones.
- **Dashboard**: el sidebar consulta `/api/quotes` (precio y variación diaria de todo el catálogo en un solo lote, cacheado 5 minutos) y el panel principal combina un gráfico de tendencia (precio, MA50, MA200 vía `/api/chart`) con las cuatro tarjetas de indicadores (una llamada a `/api/query` por indicador, reutilizando toda la lógica de extracción/NLP/validación/logging ya existente). El historial de sesión (RF-10) agrupa las consultas del mismo instrumento en una sola fila en vez de una por indicador.
- **Autenticación**: JWT (`Flask-JWT-Extended`) guardado en cookie httpOnly, con protección CSRF por token de doble envío (cookie `csrf_access_token`, legible por JS, enviada en el header `X-CSRF-TOKEN` — ver `static/js/csrf.js`). Las contraseñas se guardan con `Flask-Bcrypt` (RF-16.3) y el token expira a las 24 horas (RNF-09.2). Cerrar sesión agrega el `jti` del token a una lista de revocación en base de datos (RF-17.3), no solo borra la cookie.
- **Consulta anónima vs. con cuenta**: iniciar sesión es opcional. El dashboard funciona igual sin cuenta (consulta anónima, como antes de agregar autenticación); si hay sesión iniciada, cada consulta y regeneración además queda asociada a la cuenta (`QueryLog.user_id`) para construir el perfil de aprendizaje, sin cambiar el flujo visible de consulta.
- **Perfil adaptativo (RF-18.3)**: cuando un usuario ha regenerado la explicación de un indicador 2 o más veces, las siguientes explicaciones de ese indicador para ese usuario se generan en modo "detallado" (con más contexto y una frase aclaratoria en lenguaje simple), calculado en `src/profile/service.py:get_detail_level`.
- **Cinta de precios**: barra superior (visible en toda la app) con IPSA, UF, dólar, TPM e IPC — estos cuatro últimos desde [mindicador.cl](https://mindicador.cl), la API pública del Banco Central de Chile, independiente de Yahoo Finance/Alpha Vantage — seguida de las 30 acciones del IPSA, desplazándose en loop continuo (`static/js/ticker.js`, `static/css/style.css`). Se actualiza cada 5 minutos, igual que el cache del resto del dashboard; si `mindicador.cl` no responde, la cinta sigue mostrando IPSA y las acciones (RNF-08) y solo omite UF/dólar/TPM/IPC. Las cuatro cifras macro se muestran sin flecha de variación diaria porque la API no entrega el valor del día anterior en la misma llamada; las acciones sí tienen variación real, calculada igual que en el sidebar.
- **Historial sin condición de carrera (RF-10)**: el dashboard dispara varias solicitudes en paralelo al seleccionar un instrumento (una por indicador, más el registro de historial). Como Flask serializa toda la sesión en una sola cookie por respuesta, si esa cookie recién se estuviera creando en ese mismo instante, dos respuestas concurrentes podían pisarse y perder el historial recién escrito. Se resolvió estableciendo la cookie de sesión en la primera carga de página (`before_app_request`), antes de que el dashboard dispare ninguna llamada — y separando el registro del historial (`/api/historial/visita`, una llamada por instrumento) de las cuatro llamadas paralelas a `/api/query`. Por el mismo motivo, esas cuatro llamadas paralelas también podían chocar creando la fila de `EvaluationSession` en la base de datos al mismo tiempo (`IntegrityError` por restricción UNIQUE); `src/evaluation/__init__.py:ensure_evaluation_session` ahora tolera ese choque en vez de dejar caer la solicitud con un error 500.
- **"Consultas totales" del perfil (RF-19.3)**: seleccionar un instrumento dispara cuatro consultas de indicador en paralelo, pero para el usuario es una sola acción. El conteo del perfil ya no sale de `QueryLog` (que tiene esas cuatro filas por selección) sino de una tabla nueva, `InstrumentVisit`, con una fila por instrumento seleccionado; el total mostrado es visitas + regeneraciones explícitas, que es lo que el usuario realmente hizo.
- **Selector de rango temporal**: botones 1M/3M/6M/1A sobre el gráfico (`30/90/180/365` días) que controlan tanto el gráfico de tendencia como las cuatro tarjetas de indicadores para el instrumento seleccionado.
