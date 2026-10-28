# Decisiones arquitectónicas: revisión para defender o corregir

> **Reemplazado por `docs/adr/`.** Este borrador se conserva como registro de la revisión. La decisión 4 asumía SQLite; la decisión vigente es PostgreSQL como único motor (`docs/adr/0004-postgresql-como-motor.md`).

Archivo de trabajo. Cada decisión tiene:
- **Qué hace el código hoy**, verificado en el repo (con archivo y línea).
- **Convención o patrón reconocido** en el que se apoya. La idea es defender con patrones conocidos, no con ideas inventadas.
- **Discrepancias** entre código, documentos e informe.
- **Opciones** y casillas para decidir.

Las referencias bibliográficas listadas son las que conozco, pero **no las verifiqué en línea**. Confirma autor, año y URL antes de citarlas en APA 7.

> **Corrección a mi respuesta anterior.** Dije que `validate_coherence` garantiza que el LLM no contradiga el dato, y eso no es cierto. Lo que el código hace de verdad está en la decisión 2. También dije que `evaluation/` mezcla el log con el chequeo de coherencia; hoy solo contiene los modelos `QueryLog` e `InstrumentVisit`.

---

## Decisión 1: monolito modular (Flask) con módulos por responsabilidad

**Qué hace el código hoy**
- Un solo proceso Flask. Los módulos `extractor`, `nlp`, `auth`, `profile`, `evaluation` y `web` están en `src/` y se llaman entre sí como funciones Python.
- El front es JS vanilla con plantillas Jinja2.
- `src/evaluation/` contiene únicamente `models.py` (`QueryLog`, `InstrumentVisit`), y `__init__.py` es una línea. Lo importan `web/routes.py`, `profile/service.py` y `profile/routes.py`.

**Convención en la que se apoya**
- *Modular monolith* / *Monolith First* (Fowler, 2015): empezar con un monolito bien modularizado y extraer servicios solo si hace falta.
- Arquitectura en capas y separación de responsabilidades. Es el lenguaje que pide C11 y que ya usa tu vista de desarrollo 4+1 (Kruchten, 1995).
- Posible cita: Fowler, M. (2015). *MonolithFirst*. martinfowler.com. (verificar)

**Discrepancias**
| Dónde | Dice | Realidad |
|---|---|---|
| `CLAUDE.md` (árbol de módulos) | `evaluation/` = "pre/post survey persistence, query logging, coherence checking" | Solo log de consultas y visitas. La coherencia está en `nlp/validator.py`. |
| `CLAUDE.md` línea de "Session race condition", `README.md:111`, `docs/defensa_preguntas_respuestas.md:38` | Mencionan `ensure_evaluation_session()` y `EvaluationSession` | **No existen en el código.** Son restos de las encuestas eliminadas. |
| Informe oficial | Tres módulos más un "Módulo de Evaluación" para encuestas y validación manual | Ese módulo ya no existe. |
| `docs/diseno/04_diagrama_componentes.md:202` | Reconoce doble orquestación: `profile/routes.py` y `web/routes.py` | Deuda técnica documentada, sin resolver. |

**Opciones**
- [ ] A. Mantener el monolito y **renombrar** `evaluation/` (por ejemplo `history/` o `logging/`), o moverlo a `profile/`, para que el nombre sea honesto. Cuesta imports y una migración sin cambio de tablas.
- [ ] B. Mantener el nombre y solo corregir la documentación (`CLAUDE.md`, README, defensa, informe). Es lo más barato.
- [ ] C. Extraer la orquestación duplicada a un servicio (`query_service.py`), como sugiere el doc 04. Cuesta medio día y mejora C11.

**Defensa lista:** el alcance es un prototipo individual. Un monolito modular evita la complejidad operativa de microservicios, y los módulos se comunican por interfaces (`get_indicator`, `generate_explanation`), así que se pueden extraer después.

**Mi decisión / notas:**
>

---

## Decisión 2: explicación con LLM, respaldo en plantillas y validación de coherencia

**Qué hace el código hoy** (`src/nlp/explainer.py:222-290`, `src/web/routes.py:394`)
1. Si `USE_LLM` está activo y hay API key, el LLM (Groq, `qwen/qwen3.8-27b`) genera el texto.
2. Se recorta al máximo de palabras del nivel. Luego una **verificación mínima** acepta el texto solo si cumple las tres condiciones:
   - contiene la etiqueta de riesgo (por ejemplo "riesgo alto"),
   - contiene el valor numérico como cadena de texto,
   - no tiene términos prohibidos (solo aplica en nivel básico).
3. Si falla, o si hay cualquier excepción, cae **en silencio** a las plantillas (`except Exception: pass`).
4. `validate_coherence` (`nlp/validator.py`) corre **después**, en `_log_and_validate`. Su resultado **no bloquea nada**: solo marca `coherent=false`, y el front muestra "Marcado para revisión de coherencia".
5. Las plantillas se llenan con los datos reales, por lo que son coherentes por construcción.

**Convención en la que se apoya**
- *Graceful degradation* / *Fallback*: patrones de estabilidad en Nygard, M. (2018). *Release It!* (2.ª ed.). Pragmatic Bookshelf. (verificar)
- Guardarraíles deterministas sobre la salida de un modelo generativo (validación de salida). Se puede justificar con tu marco teórico: Kosireddy et al. (2024), Li et al. (2023), Lazarev & Sedov (2024).
- XAI: Martins et al. (2024). La explicación se deriva del valor del indicador, no del modelo.

**Discrepancias (las más graves)**
| Dónde | Dice | Realidad |
|---|---|---|
| `docs/diseno/09_stack_tecnologico.md:91-103` | Defiende **no** usar un LLM externo: "alucinaciones imposibles por construcción", "sin dependencia de terceros", "costo cero" | El sistema **sí** usa un LLM externo (Groq). El doc argumenta contra tu propio diseño. |
| Informe oficial y PPT | "NLP con FinBERT" genera las explicaciones; RF-04.1 "procesar mediante FinBERT" | FinBERT es opcional (`USE_FINBERT`) y solo aporta una etiqueta de sentimiento. Qwen redacta. |
| Mi respuesta anterior | `validate_coherence` evita contradecir el dato | El LLM solo pasa la verificación mínima; el validador completo lo marca, no lo frena. |
| Verificación mínima | `_val_str in llm_text` | Si el valor es `5` y el texto dice "15", pasa. La redacción puede decir otra cosa distinta al valor y aun así pasar. |

**Opciones**
- [ ] A. **Documentar la realidad**: el LLM es el generador principal y las plantillas el respaldo. Reescribir RF-04.1/05.1, el stack doc, el informe y el PPT. Cuesta redacción.
- [ ] B. **Subir el guardarraíl**: llamar a `validate_coherence` *antes* de aceptar la salida del LLM (junto a la verificación mínima), y caer a plantillas si falla. Son pocas líneas, con un test nuevo. Hace verdadera la defensa "nunca se muestra una explicación incoherente".
- [ ] C. **Medir**: registrar cuántas salidas del LLM caen al respaldo (log o contador) para tener un dato en la defensa.
- [ ] D. Volver a "plantillas primero, LLM opcional" (más cercano al doc original). Cambia el diseño actual.

Recomendación: A + B (y C si hay tiempo). B es lo que sostiene el argumento central del proyecto.

**Defensa lista (si haces B):** el LLM aporta fluidez, y toda salida pasa por validación determinista antes de mostrarse; si falla, se usa una plantilla coherente por construcción.

**Mi decisión / notas:**
>

---

## Decisión 3: adaptación por niveles (básico, intermedio, avanzado) con "ficha" declarativa

**Qué hace el código hoy** (`src/nlp/levels.py`, `src/profile/service.py`)
- Una **ficha por nivel** (audiencia, vocabulario, términos prohibidos, umbrales, contexto IPSA, máximo de palabras) alimenta tanto el prompt del LLM como las plantillas.
- Nivel inicial por experiencia declarada: nunca → básico, poco → intermedio, experiencia → avanzado, sin dato → intermedio.
- Cada `DETAIL_THRESHOLD = 2` regeneraciones ("No entendí esto") de un indicador bajan un nivel, con piso en básico.
- Cambiar la experiencia declarada reinicia el conteo (`users.level_reset_at`).
- `preferred_variant()` recuerda el estilo de redacción donde el usuario dejó de regenerar.

**Convención en la que se apoya**
- *Modelo de usuario* simple basado en reglas, de los sistemas adaptativos (adaptive hypermedia / tutores inteligentes). Es un modelo de superposición (*overlay*): nivel por tema. Elige una fuente verificada antes de citar.
- Declaración explícita más inferencia implícita por comportamiento.
- Regla declarativa en una sola fuente de verdad: evita que prompt y plantillas se desalineen. Esto es un principio de diseño (*single source of truth*), no un invento.

**Discrepancias y huecos**
- El umbral 2 y la idea de que "No entendí esto" significa baja comprensión **no tienen respaldo empírico**. Sin las encuestas no hay cómo validarlos.
- Solo baja de nivel: nunca sube, aunque el usuario no regenere durante mucho tiempo.
- RF-05.2 y RF-13.2 en el informe no describen la ficha ni el umbral.

**Opciones**
- [ ] A. Mantenerlo y presentarlo como **regla heurística a validar**, con el umbral como parámetro configurable. Citar teoría de aprendizaje adaptativo o carga cognitiva.
- [ ] B. Añadir regla para **subir** de nivel (por ejemplo N consultas sin regenerar). Cuesta código y tests.
- [ ] C. Hacer la validación con usuarios (aunque sean 5), registrando el cambio de comprensión, y usar los datos para fundamentar el umbral. Es la opción más fuerte, pero requiere tiempo.

**Defensa lista:** es una regla simple, explicable y testeable, sin entrenar modelos. Hay una ficha única por nivel y tests que validan cada nivel por estilo.

**Mi decisión / notas:**
>

---

## Decisión 4: SQLite sin precios y caché TTL en memoria

**Qué hace el código hoy**
- SQLite (archivo local `appfint.db`) guarda usuarios, revocaciones JWT, `query_logs` e `instrument_visits`. Los precios no se guardan.
- **Por qué SQLite:** es un prototipo académico de un solo usuario. No exige instalar ni operar un servidor, y el proyecto corre con un solo comando. El esquema no usa tipos propios de un motor (sin JSONB ni ARRAY) y las migraciones usan `batch_alter_table`, así que migrar a PostgreSQL es definir `DATABASE_URL` e instalar el driver.
- **Límite conocido:** SQLite serializa las escrituras, por lo que no soporta bien varios procesos escribiendo a la vez. Por eso el despliegue documentado usa un solo worker de gunicorn (`-w 1 --threads 4`). Para múltiples usuarios simultáneos en producción, el paso siguiente es PostgreSQL.
- `TTLCache` (`src/extractor/cache.py`) es un diccionario en memoria **por proceso**, con TTL de 300 s. Hay cachés separadas para historial de precios, cotizaciones y macro.
- Fuente: Yahoo Finance (`yfinance`), con Alpha Vantage como respaldo.
- El despliegue documentado en `README.md` usa un solo worker (`gunicorn -w 1 --threads 4`), así que hay un único caché por proceso. Con más workers habría un caché independiente por cada uno.
- No hay límite de tamaño (`maxsize`) en el caché ni limpieza proactiva: las entradas vencidas se eliminan solo al leerse.
- `query_logs` guarda valor, unidad, riesgo y ventana (`period_days`), pero no la serie de precios usada.

**Convención en la que se apoya**
- *Cache-aside* con TTL.
- *Twelve-Factor App* (Wiggins, 2011): configuración por variables de entorno (`DATABASE_URL`), servicios de respaldo como recursos adjuntos, y migraciones versionadas (Alembic). Cita posible: https://12factor.net (verificar). El mismo documento pide procesos *stateless*, y un caché en memoria por proceso es una excepción tolerable si es solo caché, no estado.
- Elegir PostgreSQL frente a SQLite por concurrencia de escritores: es un argumento estándar y ya está en el stack doc.
- ISO/IEC 25010 (calidad del producto) para C12: rendimiento, fiabilidad, seguridad, mantenibilidad. Puedes mapear cada decisión a una característica.

**Discrepancias**
| Dónde | Dice | Realidad |
|---|---|---|
| Informe oficial (Vista física, despliegue, Conclusiones) | SQLite | PostgreSQL |
| Informe, Conclusiones | "SQLite no soporta múltiples usuarios" como limitación | Ya no aplica |
| Informe, mejoras | "PostgreSQL para múltiples usuarios" como trabajo futuro | Ya está hecho |
| Cache | RNF-02.2 habla de "no repetir solicitudes a la API" | Con varios workers cada uno repite la petición una vez por TTL. Es aceptable, pero hay que decirlo. |

**Riesgos que conviene tener escritos (para C13)**
- `yfinance` no es una API oficial y puede cambiar o bloquear sin aviso. Mitigación existente: Alpha Vantage de respaldo y caché. Falta documentarla.
- Google News RSS no oficial (noticias): se degrada a lista vacía si falla.
- Groq es un tercero para el LLM: se degrada a plantillas.

**Opciones**
- [ ] A. Mantener el caché en memoria y **documentar** la limitación (por proceso, alcance de prototipo). Es la opción más barata y honesta.
- [ ] B. Añadir `maxsize` y limpieza al caché para acotar memoria. Es un cambio pequeño.
- [ ] C. Caché compartido (Redis). Es una mejora a futuro, no para esta entrega.
- [ ] D. Guardar en `query_logs` la fuente y la hora de los datos para trazabilidad. Ya hay `source`; revisar si basta para C12 ("trazabilidad").

**Defensa lista:** los precios son efímeros por diseño. No se almacenan datos de terceros ni hay que sincronizarlos. La base guarda solo lo que pertenece a la app. Se eligió SQLite por ser un prototipo académico de un solo usuario; la migración a PostgreSQL está preparada y solo se necesita para escritura concurrente de varios workers.

**Mi decisión / notas:**
>

---

## Resumen de acciones por prioridad

| # | Acción | Decisión | Esfuerzo | Criterio rúbrica |
|---|---|---|---|---|
| 1 | Hacer que `validate_coherence` filtre la salida del LLM (2-B) | 2 | Bajo | C10, C12, C26 |
| 2 | Reescribir FinBERT → LLM en informe, PPT y `09_stack_tecnologico.md` (2-A) | 2 | Medio | C10, C26 |
| 3 | Corregir SQLite → PostgreSQL en informe (4) | 4 | Bajo | C9, C10 |
| 4 | Quitar `ensure_evaluation_session` y el módulo de encuestas de CLAUDE.md, README, defensa e informe (1-B) | 1 | Bajo | C10, C11 |
| 5 | Documentar límites del caché y riesgos de terceros (4-A) | 4 | Bajo | C12, C13 |
| 6 | Presentar los niveles como regla a validar (3-A) | 3 | Bajo | C26 |
| 7 | Renombrar `evaluation/` o unificar orquestación (1-A / 1-C) | 1 | Medio | C11 |

## Cómo conectarlo con la rúbrica

- **C10 (arquitectura):** estas cuatro decisiones, más los diagramas 4+1 que ya tienes, cubren componentes, tecnologías y relación con los requerimientos. Falta ajustar el informe a lo que existe hoy.
- **C11 (diseño estructural):** la decisión 1 es el argumento de "justificar decisiones de diseño".
- **C12 (calidad y datos):** las decisiones 2 (confiabilidad y recuperación ante fallos), 3 (extensibilidad) y 4 (rendimiento, disponibilidad, trazabilidad de datos).
- **C26 (fundamentación oral):** cada decisión con su convención citada y su limitación reconocida.
