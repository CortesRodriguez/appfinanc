# Módulo Extractor (`src/extractor/`)

Documento de estudio: explica qué hace cada archivo, cómo fluyen los datos y qué decisiones de diseño hay detrás, con preguntas típicas para una defensa.

## 1. Qué problema resuelve

El Extractor es la **única parte de la app que habla con el mundo exterior** para obtener datos financieros y la **única que calcula indicadores**. El resto de la app (rutas Flask, NLP, perfil) nunca llama a Yahoo ni hace cuentas con precios: le pide al Extractor y recibe diccionarios simples.

Responsabilidades (requisitos de la memoria):

| Requisito | Qué cubre | Dónde |
|---|---|---|
| RF-01 | Selección de instrumento y período | `__init__.py` (validación) |
| RF-02.1 | Extraer desde Yahoo Finance / Alpha Vantage | `sources.py` |
| RF-02.2 | Trazabilidad (fuente, fecha/hora de extracción) | `sources.py`, `__init__.py` |
| RF-03.3 | Normalizar a una estructura común | `sources.py` |
| RF-04.2 / RF-06.1 | Umbrales cualitativos y nivel de riesgo | `indicators.py` |
| RNF-02.2 | Cache para no repetir solicitudes | `cache.py` |
| RNF-08 | Tolerancia a fallos (reintentos, degradación) | `sources.py`, `news.py` |

## 2. Estructura y dependencias

```
src/web/routes.py
      │  (llama solo a la fachada)
      ▼
extractor/__init__.py   ← orquesta: valida, cachea, calcula, agrega trazabilidad
      ├── cache.py        TTLCache (diccionario con expiración)
      ├── sources.py      Yahoo → Alpha Vantage, cotizaciones, mindicador.cl
      ├── indicators.py   RSI, medias móviles, MACD, Bollinger, serie del gráfico
      └── news.py         Google News RSS (usa su propio TTLCache)
```

Regla de capas: `sources.py` **no sabe de indicadores**, `indicators.py` **no sabe de redes**. Se comunican con un formato común:

```python
{"date": "2026-10-30", "open": 1234.5, "high": 1250.0, "low": 1230.0, "close": 1245.0}
```

Eso es la **normalización** (RF-03.3): da igual si vino de Yahoo o Alpha Vantage, el resto del código ve lo mismo.

## 3. `cache.py` — TTLCache

Un diccionario donde cada entrada guarda `(valor, instante_de_expiración)`.

- `set(key, value)`: guarda con `expira = ahora + ttl_seconds`.
- `get(key)`: si no existe devuelve `None`; si expiró, la borra y devuelve `None` (*expiración perezosa*: no hay un hilo limpiando, se limpia al consultar).
- `clear()`: vacía todo.
- Instancia global `price_history_cache` usada por el historial de precios.

**Limitaciones conocidas:**
- Es **por proceso**: con varios workers de gunicorn cada uno tiene su cache.
- No tiene tamaño máximo ni lock (no es thread-safe estrictamente).
- Se pierde al reiniciar. Es aceptable porque son datos efímeros (5 min) y la BD no guarda precios.

## 4. `sources.py` — Fuentes de datos

### 4.1 `_retry(fn, max_retries, ...)`
Ejecuta `fn`; si falla espera `0.5 s × n.º de intento` y reintenta. Al agotar intentos lanza `DataSourceError`. Es la implementación de RNF-08 (tolerancia a fallos de conexión).

### 4.2 `_fetch_yahoo(symbol, days)` — la pieza más compleja
Pasos, en orden:

1. **Descarga** `ticker.history(start=hoy-days, end=mañana)`.
2. **Recorte por calendario** con `cutoff` (no por número de filas). "3 meses" = los últimos 90 días corridos, como lo muestra la Bolsa de Santiago.
3. **Descarta `Close = NaN`**. Si se colaran, se propagarían por `diff()`/`rolling()` hasta dar valores NaN en el indicador y un 500.
4. **Elimina la fila de hoy si `Volume == 0`** (sesión en curso sin cierre). Los días históricos con volumen 0 se conservan (velas planas legítimas).
5. **Detecta datos "placeholder" de Yahoo para tickers `.SN`.** Yahoo a veces sirve datos diarios falsos para la Bolsa de Santiago:
   - `all_bad`: todo el volumen es 0 o el cierre es siempre el mismo.
   - `recent_stale`: el histórico es real pero las últimas ~15 filas tienen volumen 0 y cierre constante.
6. **Fallback horario** si hay datos malos: pide `interval="1h"` (que sí trae precios reales) y lo agrupa por día (`resample("D")`: open=first, high=max, low=min, close=last).
   - Si solo la cola está mala, **conserva el histórico diario real** y reemplaza solo esa cola con datos horarios.
   - Límite de Yahoo: ~730 días de datos horarios, por eso para períodos largos pide `"2y"`.
7. Convierte el DataFrame a la lista de dicts normalizada.

`PERIOD_TO_DAYS` traduce `days` a un `period` de Yahoo (`30→"1mo"`, `3650→"10y"`…), **pero solo se usa en el fallback horario**; la descarga principal usa `start/end`.

### 4.3 `_fetch_alpha_vantage(symbol, days, api_key)`
Fuente de respaldo. Sin API key falla de inmediato. Usa `outputsize=compact` (100 filas) o `full` si `days > 100`, y filtra por fecha de corte. Puede devolver `Note`/`Error Message` (límite de uso gratuito), que se convierte en `DataSourceError`.

### 4.4 `fetch_price_history(symbol, days, ...)` — punto de entrada
```
try  Yahoo (con reintentos)      → source = "Yahoo Finance"
except DataSourceError
     Alpha Vantage (con reintentos) → source = "Alpha Vantage"
```
Devuelve `{symbol, source, fetched_at (UTC ISO), records}`. Aquí nace la **trazabilidad RF-02.2**: cada dato sabe de dónde vino y cuándo.

### 4.5 `fetch_batch_quotes(symbols)`
Precio actual + variación diaria para el sidebar/ticker. Usa `ThreadPoolExecutor` (hasta 10 hilos) con `yf.Ticker(sym).info`. Variación = `(precio − cierre_previo) / cierre_previo × 100`. Un símbolo que falla queda en `None` y **no interrumpe a los demás**. Se evita `yf.download` precisamente por los datos obsoletos de `.SN`.

### 4.6 `fetch_macro_indicators()`
UF, dólar, TPM e IPC desde `mindicador.cl` (basada en cifras del Banco Central). Si falla devuelve `{}`: son un complemento informativo y **no deben tumbar el dashboard**.

## 5. `indicators.py` — Cálculo y riesgo

Todo opera sobre `records`. `_to_series` los convierte en una serie de `close` ordenada por fecha y sin NaN.

### 5.1 Los cuatro indicadores

| Indicador | Cálculo | Señal / tendencia | Riesgo |
|---|---|---|---|
| **RSI** (14, Wilder) | `ewm(com=13)` de ganancias y pérdidas; `RSI = 100 − 100/(1+RS)`. Sin pérdidas ⇒ 100 | >70 sobrecomprado, <30 sobrevendido, resto neutral | alto fuera de 30–70; medio entre 40–60; bajo en el resto |
| **Medias móviles** (50/200) | diferencia % `(SMA corta − SMA larga)/SMA larga` | alcista si corta > larga | alto si \|dif\| ≥ 10 %; medio si < 3 %; bajo entre ambos |
| **MACD** (12/26/9) | MACD = EMA12 − EMA26; señal = EMA9 del MACD; histograma = MACD − señal | alcista si MACD > señal | magnitud = \|hist\| / std(hist): ≥1.5 alto, ≥0.5 medio, resto bajo |
| **Bollinger** (20, 2σ) | %B = (precio − banda inf)/(banda sup − banda inf) | >1 sobrecomprado, <0 sobrevendido, cerca de extremos, normal | alto fuera de bandas; medio en 0–0.2 o 0.8–1; bajo en el centro |

**Idea clave para defender:** el valor numérico, la señal y el nivel de riesgo se calculan aquí y luego el **validador de coherencia** del NLP comprueba que el texto generado no contradiga estos mismos umbrales (RF-04.2). Por eso los umbrales están documentados en el docstring del módulo.

**Decisión de diseño — riesgo del MACD relativo:** no se fija un umbral en pesos porque dependería del precio de cada acción; se compara con la variabilidad histórica del propio histograma.

**Decisión de diseño — riesgo de medias móviles:** diferencia pequeña = sin dirección clara = medio; diferencia grande = movimiento pronunciado = alto. Es un criterio de *incertidumbre/movimiento*, no de "bueno/malo".

### 5.2 Ventanas que se auto-escalan
Con pocos datos, `short_window = min(50, max(2, n//2))` y `long_window = min(200, n)`. Evita que la serie quede toda en `None`, a costa de que "MA50/MA200" pueda ser en realidad "MA10/MA21". El frontend recibe `short_window`/`long_window` reales en la respuesta.

### 5.3 `compute_ma_series(records)`
Construye el JSON del gráfico: listas **alineadas por fecha** (`dates`, `close`, `open`, `high`, `low`, `sma_short`, `sma_long`, Bollinger sup/medio/inf, `rsi`, `macd_line`, `macd_signal`, `macd_histogram`). Los primeros puntos van en `None` (calentamiento de ventana). Reimplementa RSI/MACD/Bollinger pero devolviendo la **serie completa**, no solo el último valor.

### 5.4 `resample_records(records, interval)`
Para velas semanales/mensuales/trimestrales (`1w`→`W`, `1mo`→`MS`, `3mo`→`QS`) con agregación OHLC estándar. `1d` devuelve los datos tal cual. Se hace en el servidor para mantener **una sola ruta de cache** (siempre se bajan datos diarios).

### 5.5 `compute_indicator(name, records)`
Despachador: diccionario `INDICATOR_FUNCTIONS` nombre → función.

## 6. `news.py` — Noticias

Fuente: **RSS no oficial de Google News** (`yfinance` no entrega noticias para `.SN` y los RSS de los medios chilenos son inestables). Ante cualquier fallo devuelve `[]` y el dashboard muestra estado vacío (RNF-08).

**`fetch_news(query)`**:
1. GET al RSS (timeout 8 s, máx. 2 MB) y parseo XML.
2. Solo acepta enlaces `http/https`.
3. Quita el sufijo `" - Fuente"` del título.
4. Descarta fichas automáticas de cotización (`_QUOTE_PAGE`) y portales bloqueados (`BLOCKED_SOURCES`).
5. Elimina duplicados por título normalizado (sin tildes, minúsculas).
6. Parsea la fecha a UTC y ordena de más reciente a más antigua.

**Noticias de empresa (`get_company_news`)**:
- Query: `("alias1" OR "alias2") (términos de negocio) when:14d`. Los términos de negocio evitan homónimos ("Concha y Toro" calle, "Copec" rally).
- Segundo filtro local `mentions()`: el titular debe nombrar a la empresa como **palabra completa**, sin distinguir tildes/mayúsculas, **salvo siglas** (CAP, CCU, SMU) que deben ir en mayúsculas.
- `news_exclude` descarta falsos positivos.
- Se piden 20 titulares y se muestran 5, porque el filtro descarta varios.

**Seguridad:** el texto de búsqueda sale **siempre del catálogo** (`data/instruments.json`), nunca de lo que escribe el usuario (evita inyección en la consulta). Los endpoints solo aceptan símbolos del catálogo.

**Cache:** `news_cache`, 20 min. Si la fuente falla **no se cachea el fallo**, para reintentar en la próxima carga.

## 7. `__init__.py` — La fachada

### 7.1 Constantes
- `VALID_PERIODS = (30, 90, 180, 365)`, `VALID_INTERVALS = ("1d","1w","1mo","3mo")`.
- `MAX_SYMBOL_LENGTH = 20`: igual al `VARCHAR(20)` de la BD; PostgreSQL rechaza más largo y daría un 500. Se corta antes con error 4xx.
- `MAX_CHART_FETCH_DAYS = 3650` (10 años) para que el usuario pueda hacer zoom-out en el gráfico.

### 7.2 Funciones
- **`_validate_inputs`**: valida ticker, período, indicador, intervalo. Lanza `ExtractionError`.
- **`_get_history(symbol, days, ...)`**: consulta cache por `(symbol, days)`; si falla, llama a `fetch_price_history` y traduce `DataSourceError` → `ExtractionError` con mensaje amigable (el usuario nunca ve la traza de Yahoo).
- **`get_indicator(symbol, indicator, days)`**: valida → historial → `compute_indicator` → agrega `symbol`, `source`, `extracted_at`, `period_days`.
- **`get_price_series(symbol, days, interval)`**: siempre baja 3650 días; re-muestrea si `interval != "1d"`; `compute_ma_series`; agrega `visible_days` (lo que pidió el botón, para anclar la vista inicial) y `fetched_days`.
- **`get_quotes` / `get_macro_indicators`**: wrappers con cache (5 min). Clave de cotizaciones: `tuple(sorted(symbols))`.

### 7.3 `ExtractionError` vs `DataSourceError`
- `DataSourceError` (interno, `sources.py`): "las fuentes fallaron".
- `ExtractionError` (público): error de negocio que el Presentador convierte en respuesta HTTP. Así las capas superiores no dependen de detalles de Yahoo o Alpha Vantage.

## 8. Flujos completos

**Gráfico** — `GET /api/chart?symbol=BCI.SN&days=90`
```
routes.api_chart → get_price_series
  → _validate_inputs
  → _get_history(symbol, 3650)  → cache hit?  sí: usa / no: fetch_price_history
        → _fetch_yahoo (con reintentos) → [fallo] → _fetch_alpha_vantage
  → (resample si interval ≠ 1d)
  → compute_ma_series
  → JSON {dates, close, ..., visible_days: 90}
```

**Tarjeta de indicador** — `POST /api/query` con `days=90, indicator=rsi`
```
query_service → get_indicator
  → _validate_inputs → _get_history(symbol, 90) → compute_rsi
  → {value, unit, risk_level, signal, symbol, source, extracted_at, period_days}
  → (luego NLP genera la explicación con ese dict)
```

## 9. Preguntas típicas de defensa

**¿Por qué dos fuentes de datos?** Tolerancia a fallos (RNF-08): si Yahoo falla, Alpha Vantage toma el relevo. Se registra cuál se usó (`source`).

**¿Por qué un fallback horario para Yahoo?** Porque para tickers `.SN` el endpoint diario devuelve a veces datos placeholder (volumen 0, cierre constante). Los datos horarios sí son reales; se agregan por día.

**¿Cómo evitan resultados NaN o errores 500?** Se descartan filas con `Close=NaN` en la fuente y otra vez en `_to_series`; las divisiones por cero se manejan (`avg_loss == 0` ⇒ RSI 100; `band_width <= 0` ⇒ %B 0.5; `hist_std or 1.0`).

**¿Por qué el riesgo es "relativo" y no un consejo de inversión?** El riesgo describe la posición del indicador respecto a umbrales técnicos estándar (RF-06.1), no predice el precio. Es información educativa.

**¿Por qué cachear?** Reduce latencia y evita saturar APIs externas / límites de Alpha Vantage. TTL de 5 min para precios, 20 min para noticias.

**¿Por qué los indicadores no se guardan en la BD?** Son datos efímeros y reproducibles; la BD solo guarda usuarios, consultas e historial.

**¿Cómo se garantiza que el texto no contradiga el dato?** Los umbrales de `indicators.py` son los mismos que usa el validador de coherencia del NLP.

## 10. Puntos débiles detectados (candidatos a mejora)

Estos puntos salen de leer el código; conviene verificarlos antes de afirmarlos en una defensa.

1. **CLAUDE.md y varios docstrings están desactualizados**: describen `tail(days)` por filas, pero hoy se recorta por calendario; `CHART_BUFFER_FACTOR` ya no existe; `fetch_batch_quotes` menciona `fast_info` pero usa `.info`; `fetch_price_history` dice que los records son `{date, close}`.
2. **Cache fragmentado**: las tarjetas usan `(symbol, 30/90/180/365)` y el gráfico `(symbol, 3650)`, así que un mismo instrumento se descarga varias veces. Una sola descarga de 3650 recortada en memoria bastaría.
3. **Ventana de 30 días y MACD**: 30 días corridos son ~21 filas de trading, pero MACD exige 35 (`slow + signal`). Probablemente el período 1M falla para MACD con "No hay suficientes datos". Hay que comprobarlo.
4. **`_retry` reintenta también errores no transitorios**: un `DataSourceError` de "sin datos" se reintenta 3 veces con esperas inútiles antes de caer a Alpha Vantage.
5. **`TTLCache` sin lock ni límite de tamaño**, y `ttl_seconds` se sobrescribe en cada llamada.
6. **Lógica duplicada**: RSI, MACD y Bollinger están implementados dos veces (valor puntual y serie completa). Podría compartirse una función que calcule la serie y el valor puntual sea su último elemento.
7. **`_fetch_yahoo` es una función larga** (~100 líneas) que mezcla descarga, limpieza, detección y fallback; se beneficiaría de dividirse.
8. **`fetch_batch_quotes` oculta todos los errores** con `except Exception: pass`; no deja registro de por qué un símbolo quedó en `None`.
