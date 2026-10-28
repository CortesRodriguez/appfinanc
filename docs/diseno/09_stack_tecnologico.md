# Fase 9 — Selección y justificación del stack tecnológico

Cada elección técnica del proyecto responde a un criterio específico, no a una preferencia. Esta sección explica *por qué* se eligió cada componente frente a las alternativas razonables.

## Resumen del stack

| Capa | Tecnología | Función en el sistema |
|---|---|---|
| Lenguaje de backend | Python 3.11+ | Base común de todos los módulos |
| Framework web | Flask | Presentador (interfaz web + rutas) |
| ORM y capa de datos | SQLAlchemy 2 + Flask-SQLAlchemy (driver psycopg 3) | Modelo de datos |
| Motor de base de datos | PostgreSQL 14+ (nodo separado) | Persistencia de usuarios, tokens revocados y registros de consulta |
| Migraciones de esquema | Flask-Migrate (Alembic) | Versionado del esquema (`flask db upgrade`) |
| Servidor de aplicación | gunicorn (varios workers) | Ejecución de Flask en producción detrás de proxy HTTPS |
| Fuente primaria de precios | Yahoo Finance vía `yfinance` | Módulo Extractor (RF-02.1) |
| Fuente de respaldo de precios | Alpha Vantage (HTTP + API key) | Fallback ante caída de Yahoo (RNF-09) |
| Fuente de indicadores macro chilenos | mindicador.cl (API pública del Banco Central de Chile) | Módulo Extractor (RF-02.3) |
| Motor de redacción (texto final) | LLM `qwen/qwen3.8-27b` vía Groq, con plantillas en español como respaldo | Procesador NLP: redacta la explicación según la ficha del nivel del usuario (RF-04.1, RF-05.1) |
| Señal de sentimiento (opcional) | FinBERT (Hugging Face Transformers) | Procesador NLP: etiqueta de sentimiento del indicador; desactivado por defecto (RF-04.1) |
| Autenticación | Flask-JWT-Extended + Flask-Bcrypt | Módulo de Autenticación (RF-11, RF-12, RNF-06) |
| Frontend | HTML5 + CSS3 + JS vanilla + Jinja2 | Interfaz web renderizada por Flask |
| Gráficos | TradingView Lightweight Charts v4 | Visualización de tendencia (RF-07) |
| Pruebas | pytest + Flask test client | Cobertura por módulo |

## Marco arquitectónico: modelo 4+1 de Kruchten

El proyecto adopta el **modelo de vistas 4+1** propuesto por Kruchten (1995), que describe la arquitectura desde cinco perspectivas complementarias (ver Fase 1 y Fase 5). Cada elección de tecnología se ubica en al menos una vista:

- **Vista lógica**: Flask (Presentador), LLM con plantillas de respaldo y FinBERT opcional (Procesador NLP), yfinance/Alpha Vantage/mindicador (Extractor).
- **Vista de procesos**: flujo secuencial en tiempo diferido, sin paralelismo entre módulos.
- **Vista de desarrollo**: separación en paquetes Python (`src/extractor/`, `src/nlp/`, `src/web/`, `src/auth/`, `src/profile/` y `src/evaluation/`, que solo contiene los modelos `QueryLog` e `InstrumentVisit`).
- **Vista física**: dos nodos. Un nodo de aplicación (gunicorn con varios workers ejecutando Flask, detrás de un proxy inverso/PaaS que termina HTTPS) y un nodo de base de datos PostgreSQL separado (servicio gestionado, conexión TCP 5432 con TLS). En desarrollo, ambos corren en la máquina del desarrollador (PostgreSQL local vía Homebrew).
- **Vista de escenarios**: dos escenarios representativos (consulta de indicador; validación de coherencia) que amarran las cuatro vistas anteriores mediante casos de uso extendidos (Fase 3).

## Backend

### Python 3.11+

Elegido por tres motivos concretos, en este orden:

1. **Ecosistema científico/financiero maduro**: `pandas`, `numpy`, `yfinance` y los clientes de modelos de lenguaje cubren el 100 % de la extracción de datos, cálculo de indicadores y generación NLP sin necesidad de integrar bindings a otros lenguajes.
2. **Comprensibilidad para lectura crítica académica**: la comisión y el guía pueden leer el código sin fricción; un lenguaje más "de sistemas" (Go, Rust) habría dificultado la revisión.
3. **Curva de entrada del equipo**: el proyecto es de trabajo individual, sin margen para aprender un lenguaje nuevo durante el desarrollo.

### Flask

Elegido frente a **Django** (el otro framework Python dominante) por criterios específicos al proyecto:

- **Explicitidad**: Flask no impone estructura ni ORM. En un proyecto de título, donde la comisión suele preguntar *por qué* cada archivo está donde está, un framework explícito facilita defender cada decisión arquitectónica.
- **Peso proporcional al alcance**: el sistema tiene ~20 rutas HTTP y 5-6 tablas. Django trae infraestructura pensada para aplicaciones mucho más grandes (admin, i18n, ORM propio, template engine propio); las piezas que sí se necesitan (ORM, migraciones) se incorporan como extensiones (Flask-SQLAlchemy, Flask-Migrate).
- **Application Factory pattern**: Flask lo soporta directamente (`create_app(config)`), lo que facilita usar una configuración de test apuntando a una base de datos de pruebas dedicada.
- **Comparación con FastAPI**: FastAPI destaca en APIs REST puras; este proyecto también renderiza plantillas Jinja2 para dashboard, perfil y glosario. Flask maneja HTML + JSON sin fricción.

### SQLAlchemy + Flask-SQLAlchemy

ORM estándar de facto en Python. Se usa SQLAlchemy 2 a través de Flask-SQLAlchemy, con el driver **psycopg 3** (`postgresql+psycopg://`). Los modelos se declaran como clases Python, las consultas son parametrizadas (previenen inyección SQL) y el pool de conexiones se configura con `pool_pre_ping=True` y `pool_recycle=1800`, de modo que las conexiones cerradas por el servidor gestionado se descartan antes de usarse en lugar de producir errores 500.

### Flask-Migrate (Alembic)

El esquema se versiona en `migrations/versions/` y se aplica con `flask db upgrade` (la migración inicial es `0001_esquema_inicial`). La aplicación no crea tablas al arrancar: cada cambio de esquema queda registrado, es revisable y reversible (`downgrade`), y puede aplicarse en producción sin perder datos.

## Fuentes de datos

### Yahoo Finance (`yfinance`) como fuente primaria

- **Sin API key requerida** para el volumen del proyecto.
- **Cobertura completa del IPSA con sufijo `.SN`**: los 30 tickers responden con serie histórica diaria.
- **Precisión suficiente** para explicar un concepto financiero: los datos son los mismos que ven la mayoría de plataformas gratuitas de finanzas retail.

### Alpha Vantage como respaldo (RNF-09)

`yfinance` es un scraper no oficial de Yahoo Finance y puede fallar cuando Yahoo cambia su HTML o rate-limitea. Alpha Vantage ofrece un API oficial con key gratuita (5 requests/minuto, 500/día), suficiente para servir de red de seguridad. La lógica de fallback vive en `src/extractor/sources.py` y satisface el requerimiento RNF-09.

### mindicador.cl (Banco Central de Chile) — RF-02.3

Fuente independiente para UF, dólar observado, TPM e IPC. Es una API pública, gratuita, sin autenticación, mantenida sobre datos oficiales del Banco Central de Chile. Se eligió frente a scraping directo del sitio del Banco Central porque el formato del API es estable y no requiere parsear HTML.

## Motor de generación de explicaciones: LLM con plantillas de respaldo

Este es el punto más pedagógico de la Fase 9 y el que la comisión suele preguntar con detalle.

### Arquitectura elegida

El Procesador NLP redacta cada explicación en tres pasos (`src/nlp/explainer.py`):

1. **Ficha del nivel** (RF-05.2, RF-13.2). Según el usuario, el indicador pasa a un nivel (`basico`, `intermedio`, `avanzado`) cuya ficha (`src/nlp/levels.py`) define audiencia, vocabulario, términos prohibidos, umbrales y máximo de palabras. La misma ficha alimenta el prompt del LLM y las plantillas.
2. **Redacción con LLM** (RF-04.1, RF-05.1). Si `USE_LLM=true` y hay `GROQ_API_KEY`, el modelo `qwen/qwen3.8-27b` (vía Groq) redacta el texto. Se recorta al máximo de palabras del nivel y se acepta solo si contiene la etiqueta de riesgo, el valor del indicador y ningún término prohibido del nivel.
3. **Plantillas de respaldo**. Si el LLM está desactivado, falla o su texto no pasa la verificación, se usan plantillas en español con tres variantes por indicador y nivel (`src/nlp/templates.py`), que se rellenan con los valores reales y por eso son coherentes por construcción. Las variantes permiten la regeneración (RF-06.2).

Después, el **validador de coherencia** (RF-04.2, `src/nlp/validator.py`) contrasta el texto con el valor y los umbrales del indicador (RSI, %B, MACD, medias móviles). Si discrepan, la respuesta lleva `coherent=false` y la interfaz muestra un aviso; no bloquea el texto.

**FinBERT** (`ProsusAI/finbert`) es un componente opcional (`USE_FINBERT`, desactivado por defecto): solo aporta una etiqueta de sentimiento que la interfaz muestra como insignia. No participa en la redacción.

### Fundamento de la elección: LLM con respaldo frente a solo plantillas

| Criterio | Solo plantillas | LLM con plantillas de respaldo (elegido) |
|---|---|---|
| Coherencia con el dato | Alta, por construcción | Menor: el LLM puede errar; se mitiga con la verificación mínima, el validador y el respaldo |
| Fluidez y adaptación al nivel | Limitada a las variantes escritas | Alta: el texto se ajusta a la ficha del nivel |
| Reproducibilidad | Alta | Menor: mismo prompt, salidas distintas |
| Costo por consulta | Cero | Cuota del proveedor (Groq, nivel gratuito) |
| Dependencia de terceros | Ninguna | Groq; si cae, se usan las plantillas sin que el usuario lo note |
| Alucinaciones | Imposibles | Posibles; la verificación mínima solo exige etiqueta, valor y vocabulario del nivel |

Se eligió el LLM como generador principal porque permite ajustar el vocabulario y la profundidad al nivel del usuario, que es el aporte central del proyecto, y se conservaron las plantillas como red de seguridad (RNF-09). La verificación actual es **mínima**: comprueba que aparezcan la etiqueta de riesgo y el valor como texto, pero no que el resto de la redacción sea fiel. Endurecerla (exigir `validate_coherence` antes de aceptar la salida del LLM) está registrado como mejora en `docs/adr/0002-llm-con-fallback-y-validacion.md`.

### Justificación del uso de FinBERT como señal opcional

FinBERT (Huang, Wang & Yang, 2023) es un modelo BERT preentrenado sobre corpus financieros y clasifica información financiera en positivo / neutral / negativo. La revisión de Baghavathi Priya et al. (2025) confirma que sigue siendo un estándar para análisis de sentimiento financiero. Se mantiene como señal complementaria y opcional porque exige instalar `transformers` y `torch` (no están en `requirements.txt`) y añade varios segundos de carga.

### Fallbacks silenciosos (decisión de robustez)

Hay dos niveles de degradación, coherentes con RNF-09: si el LLM no responde o su salida no pasa la verificación, se usan las plantillas; si FinBERT no está instalado o falla, se omite la etiqueta de sentimiento. En ambos casos el usuario recibe una explicación válida.

## Base de datos: PostgreSQL

- **Nodo separado del contenedor de la aplicación**: los datos (usuarios, correos, hashes bcrypt, tokens revocados, registros de consulta) sobreviven a los redespliegues, que reemplazan los contenedores de Flask sin tocar la base.
- **Escrituras concurrentes reales (MVCC)**: varios workers de gunicorn, o varias instancias de la aplicación, escriben en paralelo sin serializarse; los bloqueos son a nivel de fila.
- **Respaldos y recuperación**: el servicio gestionado (Neon, Supabase, Render u otro) ofrece respaldos automáticos y recuperación a un punto en el tiempo; adicionalmente `pg_dump` permite volcados manuales.
- **Seguridad para datos personales**: conexión cifrada con TLS (`sslmode=require`), roles y privilegios por usuario de base de datos, credenciales entregadas solo por la variable de entorno `DATABASE_URL`.
- **Integridad estricta**: PostgreSQL valida tipos y largos (`VARCHAR(n)`, `BOOLEAN`, `TIMESTAMPTZ`). Por eso el largo del ticker se valida antes de llegar a la base (`MAX_SYMBOL_LENGTH = 20`, igual al largo de la columna `instrument`).
- **Marcas de tiempo con zona horaria** (`timestamptz`), relevantes para auditar consultas de usuarios en distintas zonas.
- **Configuración obligatoria**: `DATABASE_URL` es requerida; `config.py` rechaza el arranque si falta o si no es una URL de PostgreSQL, y normaliza las URLs `postgres://` que entregan los PaaS al driver psycopg 3.
- **Volumen esperado**: incluso proyectando cientos de participantes en la validación, el orden de magnitud es ≤ 10⁵ filas totales; holgado para una instancia gestionada pequeña.

Se evaluaron **SQLite** y **MySQL**. SQLite se descartó porque es un archivo acoplado al disco del contenedor (se perdería en cada redespliegue de un PaaS) y admite un único escritor a la vez; MySQL es viable, pero PostgreSQL ofrece tipos más estrictos, mejor apego a SQL estándar y es el motor de referencia en el ecosistema SQLAlchemy/Alembic. El costo asumido es operar un servidor aparte: en desarrollo se usa PostgreSQL local (Homebrew, base `appfint`) y en producción un servicio gestionado.

## Frontend: HTML + CSS + JS vanilla + Jinja2

Elegido explícitamente frente a un framework moderno (React, Vue, Svelte):

- **Alcance funcional**: hay ~10 pantallas, ninguna con estado de aplicación complejo. El estado se maneja en el DOM y en la sesión de Flask sin necesidad de un store.
- **Curva de aprendizaje adicional**: agregar React habría implicado aprender infraestructura de producción (Vite/Webpack, JSX, hooks) sin agregar valor a la propuesta del proyecto.
- **Coherencia con el modelo 4+1 vista de desarrollo**: Jinja2 renderiza HTML en el servidor, el JS solo añade interactividad puntual. Esta separación clara es fácil de defender.

### TradingView Lightweight Charts v4.2.0

Librería de gráficos financieros elegida por criterios específicos:

- **Especialización financiera**: candlestick, líneas de MA, escala temporal, escala de precios están implementados y probados por TradingView.
- **Rendimiento**: renderiza series de cientos de puntos sin degradación perceptible.
- **Tamaño**: ~45 KB minificado, comparable a Chart.js pero especializado.

## Autenticación: Flask-JWT-Extended + Flask-Bcrypt (RF-11, RF-12, RNF-06)

- **JWT en cookie httpOnly**: el token no es accesible desde JS del navegador, mitigando XSS.
- **Protección CSRF por doble envío**: además del JWT, una cookie separada (`csrf_access_token`) legible por JS y enviada en el header `X-CSRF-TOKEN` en cada petición mutante.
- **Bcrypt**: los passwords se guardan hasheados con bcrypt, satisfaciendo RNF-06.1 (mínimo 8 caracteres).
- **Expiración a 24 horas** (RNF-06.2).

Se descartaron sesiones Flask nativas (no incluyen expiración configurable ni revocación individual). Se incorporó posteriormente login/registro con Google (OAuth2/OIDC vía Authlib) como alternativa a la cuenta por contraseña, sin reemplazarla: ambos mecanismos coexisten y las cuentas no se vinculan automáticamente por correo.

## Pruebas: pytest

- **API mínima expresiva**: `assert` estándar de Python, sin necesidad de aprender un DSL.
- **Integración con Flask test client**: cada ruta se prueba sin levantar servidor real (ver `tests/conftest.py`).
- **Fixtures compartidas**: la fixture `app` en `conftest.py` levanta una app contra una base de datos PostgreSQL de pruebas dedicada (`appfint_test`, sobrescribible con `TEST_DATABASE_URL`), creando el esquema con `db.create_all()` al inicio de cada test y eliminándolo con `db.drop_all()` al final, de modo que cada test parte de una base vacía.

## Verificación end-to-end del stack

Todo el stack se verifica corriendo:

```bash
pip install -r requirements-dev.txt
createdb appfint && createdb appfint_test
flask db upgrade       # aplica las migraciones de Alembic
python app.py          # levanta la app en http://127.0.0.1:5001/
pytest                 # tests unitarios y de integración
```

## Referencias

- Baghavathi Priya, S., Kumar, M., Prakash, N. J. D., & Krithika, N. (2025). Advanced financial sentiment analysis using FinBERT to explore sentiment dynamics. *IDCIoT 2025*.
- Huang, A. H., Wang, H., & Yang, Y. (2023). FinBERT: A large language model for extracting information from financial text. *Contemporary Accounting Research*, 40(2), 806–841.
- Kosireddy, T. R., Wall, J. D., & Lucas, E. (2024). Exploring the readiness of prominent small language models for the democratization of financial literacy. arXiv:2410.07118.
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.
