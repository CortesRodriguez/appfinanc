# Fase 9 — Selección y justificación del stack tecnológico

Cada elección técnica del proyecto responde a un criterio específico, no a una preferencia. Esta sección explica *por qué* se eligió cada componente frente a las alternativas razonables.

## Resumen del stack

| Capa | Tecnología | Función en el sistema |
|---|---|---|
| Lenguaje de backend | Python 3.11+ | Base común de todos los módulos |
| Framework web | Flask | Presentador (interfaz web + rutas) |
| ORM y capa de datos | SQLAlchemy + Flask-SQLAlchemy | Modelo de datos |
| Motor de base de datos | SQLite (embebido) | Persistencia local del prototipo |
| Fuente primaria de precios | Yahoo Finance vía `yfinance` | Módulo Extractor (RF-02.1) |
| Fuente de respaldo de precios | Alpha Vantage (HTTP + API key) | Fallback ante caída de Yahoo (RNF-09) |
| Fuente de indicadores macro chilenos | mindicador.cl (API pública del Banco Central de Chile) | Módulo Extractor (RF-02.3) |
| Motor de NLP (clasificación) | **FinBERT** (Hugging Face Transformers) | Procesador NLP: clasifica sentimiento y categorías cualitativas (RF-04.1) |
| Motor de redacción (texto final) | Plantillas en español con variantes | Procesador NLP: redacta la explicación final a partir de la clasificación de FinBERT (RF-05.1) |
| Autenticación | Flask-JWT-Extended + Flask-Bcrypt | Módulo de Autenticación (RF-11, RF-12, RNF-06) |
| Frontend | HTML5 + CSS3 + JS vanilla + Jinja2 | Interfaz web renderizada por Flask |
| Gráficos | TradingView Lightweight Charts v4 | Visualización de tendencia (RF-07) |
| Pruebas | pytest + Flask test client | Cobertura por módulo |

## Marco arquitectónico: modelo 4+1 de Kruchten

El proyecto adopta el **modelo de vistas 4+1** propuesto por Kruchten (1995), que describe la arquitectura desde cinco perspectivas complementarias (ver Fase 1 y Fase 5). Cada elección de tecnología se ubica en al menos una vista:

- **Vista lógica**: Flask (Presentador), FinBERT (Procesador NLP), yfinance/Alpha Vantage/mindicador (Extractor).
- **Vista de procesos**: flujo secuencial en tiempo diferido, sin paralelismo entre módulos.
- **Vista de desarrollo**: separación en paquetes Python (`src/extractor/`, `src/nlp/`, `src/web/`, `src/auth/`, `src/evaluation/`, `src/profile/`).
- **Vista física**: despliegue en un nodo único (máquina del desarrollador o servidor local); base de datos SQLite embebida en el mismo proceso.
- **Vista de escenarios**: dos escenarios representativos (consulta de indicador; validación de coherencia) que amarran las cuatro vistas anteriores mediante casos de uso extendidos (Fase 3).

## Backend

### Python 3.11+

Elegido por tres motivos concretos, en este orden:

1. **Ecosistema científico/financiero maduro**: `pandas`, `numpy`, `yfinance` y `transformers` cubren el 100 % de la extracción de datos, cálculo de indicadores y generación NLP sin necesidad de integrar bindings a otros lenguajes.
2. **Comprensibilidad para lectura crítica académica**: la comisión y el guía pueden leer el código sin fricción; un lenguaje más "de sistemas" (Go, Rust) habría dificultado la revisión.
3. **Curva de entrada del equipo**: el proyecto es de trabajo individual, sin margen para aprender un lenguaje nuevo durante el desarrollo.

### Flask

Elegido frente a **Django** (el otro framework Python dominante) por criterios específicos al proyecto:

- **Explicitidad**: Flask no impone estructura ni ORM. En un proyecto de título, donde la comisión suele preguntar *por qué* cada archivo está donde está, un framework explícito facilita defender cada decisión arquitectónica.
- **Peso proporcional al alcance**: el sistema tiene ~20 rutas HTTP y 5-6 tablas. Django trae infraestructura pensada para aplicaciones mucho más grandes (admin, migraciones, i18n, ORM propio, template engine propio).
- **Application Factory pattern**: Flask lo soporta directamente (`create_app(config)`), lo que facilita usar una configuración de test en memoria en las pruebas.
- **Comparación con FastAPI**: FastAPI destaca en APIs REST puras; este proyecto también renderiza plantillas Jinja2 para dashboard, encuestas y panel de auditoría. Flask maneja HTML + JSON sin fricción.

### SQLAlchemy + Flask-SQLAlchemy

ORM elegido por su neutralidad respecto al motor de BD: el mismo código funciona sobre SQLite, PostgreSQL o MySQL cambiando solo la cadena de conexión. Esa portabilidad es lo que permite usar SQLite en el prototipo sin comprometer una migración futura a PostgreSQL.

## Fuentes de datos

### Yahoo Finance (`yfinance`) como fuente primaria

- **Sin API key requerida** para el volumen del proyecto.
- **Cobertura completa del IPSA con sufijo `.SN`**: los 30 tickers responden con serie histórica diaria.
- **Precisión suficiente** para explicar un concepto financiero: los datos son los mismos que ven la mayoría de plataformas gratuitas de finanzas retail.

### Alpha Vantage como respaldo (RNF-09)

`yfinance` es un scraper no oficial de Yahoo Finance y puede fallar cuando Yahoo cambia su HTML o rate-limitea. Alpha Vantage ofrece un API oficial con key gratuita (5 requests/minuto, 500/día), suficiente para servir de red de seguridad. La lógica de fallback vive en `src/extractor/sources.py` y satisface el requerimiento RNF-09.

### mindicador.cl (Banco Central de Chile) — RF-02.3

Fuente independiente para UF, dólar observado, TPM e IPC. Es una API pública, gratuita, sin autenticación, mantenida sobre datos oficiales del Banco Central de Chile. Se eligió frente a scraping directo del sitio del Banco Central porque el formato del API es estable y no requiere parsear HTML.

## Motor de generación de explicaciones: FinBERT + plantillas

Este es el punto más pedagógico de la Fase 9 y el que la comisión suele preguntar con detalle.

### Arquitectura elegida

El Procesador NLP funciona en dos pasos, coherente con CU-08 y CU-10 del documento oficial:

1. **Clasificación con FinBERT** (RF-04.1, CU-08). El modelo preentrenado `ProsusAI/finbert` recibe el indicador normalizado y clasifica su sentimiento o categoría cualitativa (por ejemplo: "positivo", "neutral", "negativo").
2. **Redacción por plantillas** (RF-05.1, CU-10). Un motor de generación basado en plantillas en español combina la categoría clasificada por FinBERT con los valores reales del indicador y produce el texto final, con al menos tres variantes de redacción por indicador para permitir la regeneración (RF-06.2).

Entre ambos pasos, un **validador de coherencia** (RF-04.2) verifica que la categoría cualitativa usada en la explicación corresponda a los umbrales reales del indicador (RSI, %B, MACD, medias móviles), descartando cualquier alucinación del modelo.

### Fundamento de la elección frente a un LLM externo (OpenAI, Anthropic, Gemini)

| Criterio | FinBERT + plantillas | LLM externo generativo |
|---|---|---|
| Control de coherencia con el dato | Alto — validador determinista compara valor y umbrales | Bajo — el LLM puede alucinar el valor |
| Reproducibilidad | Alta — misma entrada, misma salida por variante | Baja — mismo prompt, distintas salidas |
| Costo por consulta | Cero (modelo local) | Pago por token, escala con uso |
| Dependencia de terceros para la defensa | No hay | Sí — corte del servicio invalida la demo |
| Legibilidad ≥ 60 (RNF-04.1) | Garantizada por diseño de las plantillas | No garantizada, requeriría post-procesamiento |
| Alucinaciones factuales | Imposibles por construcción | Posibles y difíciles de detectar |
| Complejidad de la defensa | Baja — se muestra la plantilla | Alta — requiere justificar prompt engineering |

Un LLM externo aporta fluidez y variedad de redacción, pero introduce un riesgo estructural sobre la afirmación central del proyecto: si el LLM se equivoca al citar el valor del indicador, la explicación contradice al dato y el sistema pierde su propósito. La combinación FinBERT + plantillas mantiene la fluidez del contenido semántico (dado por FinBERT) y garantiza coherencia matemática (dado por las plantillas + validador).

Esta arquitectura satisface el requerimiento **RF-04.1** ("procesar cada indicador mediante FinBERT") citado explícitamente en el anteproyecto.

### Justificación del uso de FinBERT específicamente

FinBERT (Huang, Wang & Yang, 2023) es un modelo BERT preentrenado sobre corpus financieros. Aporta ventajas concretas frente a un BERT genérico:

- **Vocabulario financiero**: reconoce términos y jerga del dominio que un BERT genérico ignora o interpreta mal.
- **Sentimiento financiero**: fue entrenado específicamente para clasificar información financiera en positivo / neutral / negativo, lo cual mapea directamente a los niveles de riesgo (RF-06.1).
- **Vigencia**: la revisión de Baghavathi Priya et al. (2025) confirma que FinBERT sigue siendo un estándar de facto para tareas de análisis de sentimiento financiero.

### Fallback silencioso (decisión de robustez)

Aunque FinBERT es el componente central por diseño, el módulo NLP incluye un **fallback silencioso**: si por cualquier motivo (`transformers` no instalado, error de carga del modelo, timeout) FinBERT no responde, el motor de plantillas continúa operando con una clasificación por defecto y el sistema entrega una explicación válida. Esta decisión de diseño garantiza que un fallo puntual del modelo no invalide toda la sesión del usuario, coherente con el principio de tolerancia a fallos de RNF-09.

## Base de datos: SQLite

- **Cero infraestructura**: se guarda como archivo, no requiere servidor separado.
- **Volumen esperado**: incluso proyectando cientos de participantes en la validación, el orden de magnitud es ≤ 10⁵ filas totales — muy dentro del sweet-spot de SQLite.
- **Portabilidad hacia PostgreSQL sin cambios de código**: gracias a SQLAlchemy, migrar requiere cambiar solo la cadena de conexión.

Se descartó **PostgreSQL** para el prototipo por razones de proporcionalidad: la comisión evaluadora no debería tener que levantar un servidor de BD para revisar el código.

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

Se descartaron sesiones Flask nativas (no incluyen expiración configurable ni revocación individual) y OAuth externo (agrega complejidad de infraestructura sin beneficio en el contexto académico).

## Pruebas: pytest

- **API mínima expresiva**: `assert` estándar de Python, sin necesidad de aprender un DSL.
- **Integración con Flask test client**: cada ruta se prueba sin levantar servidor real (ver `tests/conftest.py`).
- **Fixtures compartidas**: la fixture `app` en `conftest.py` levanta una app con SQLite en memoria por test.

## Verificación end-to-end del stack

Todo el stack se verifica corriendo:

```bash
pip install -r requirements.txt
python app.py          # levanta la app en http://127.0.0.1:5000/
pytest                 # tests unitarios y de integración
```

## Referencias

- Baghavathi Priya, S., Kumar, M., Prakash, N. J. D., & Krithika, N. (2025). Advanced financial sentiment analysis using FinBERT to explore sentiment dynamics. *IDCIoT 2025*.
- Huang, A. H., Wang, H., & Yang, Y. (2023). FinBERT: A large language model for extracting information from financial text. *Contemporary Accounting Research*, 40(2), 806–841.
- Kosireddy, T. R., Wall, J. D., & Lucas, E. (2024). Exploring the readiness of prominent small language models for the democratization of financial literacy. arXiv:2410.07118.
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.
