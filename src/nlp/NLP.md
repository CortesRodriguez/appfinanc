# Módulo NLP (`src/nlp/`)

Documento de estudio: qué hace cada archivo, dónde está realmente la inteligencia artificial del proyecto, qué hay que decir en la defensa y cómo medir si funciona.

Todo lo que dice "medido" se ejecutó en esta sesión con datos de ejemplo. Lo que dice "por lectura" sale de leer el código y no se probó. **Nunca se ha ejecutado el LLM contra la API real de Groq**, así que nada de lo que sigue describe lo que el modelo escribe de verdad.

## 1. Qué problema resuelve

El Extractor entrega un número ("RSI = 46.59, riesgo medio"). El módulo NLP lo convierte en una explicación en español, adaptada al nivel del usuario, sin que el texto contradiga el dato.

```
dict del indicador ──► ¿USE_LLM activo y hay API key?
{value, risk_level,       │ sí                            │ no, o falla
 signal, trend...}        ▼                               ▼
                    Groq (LLM) redacta           Plantillas rellenan huecos
                          │                               │
                          ▼                               │
              ¿pasa los filtros?  ── no ──────────────────┤
              · sin términos prohibidos del nivel         │
              · validate_coherence (riesgo, valor,        ▼
                 afirmaciones contra el dato)      recorte a max_words
                          │ sí                            │
                          └─────────────►  {texto, legibilidad, finbert...}
```

Las plantillas son el plan B garantizado: frases fijas con huecos, correctas por construcción. El LLM da variedad, pero solo se muestra si pasa los filtros.

## 2. Dónde está realmente la IA 
Conviene tener esta tabla clara, porque "sistema basado en inteligencia artificial" es el título del proyecto.

| Componente | ¿Es IA? | Qué es en realidad |
|---|---|---|
| **LLM (Groq, `qwen/qwen3.8-27b`)** | **Sí** | Modelo de lenguaje generativo que redacta el texto |
| Plantillas (`templates.py`) | No | 108 frases escritas a mano con huecos |
| Validador (`validator.py`) | No | Reglas y expresiones regulares |
| Niveles (`levels.py`) | No | Diccionario de configuración |
| Legibilidad (`readability.py`) | No | Fórmula matemática |
| Niveles adaptativos (`profile/`) | No | Contadores: cada 2 regeneraciones baja un nivel |
| **FinBERT** | Sí, pero **no participa** | Clasificador de sentimiento, opcional, apagado por defecto |

Dos hechos que hay que decir con claridad, porque un evaluador los verá en el código:

1. **La IA generativa es una sola pieza: el LLM.** Todo lo demás es ingeniería de software clásica alrededor de él. Eso no es un defecto; es un patrón común (un LLM con guardarraíles), pero hay que presentarlo así.
2. **Por defecto el sistema usa IA, pero solo si hay clave.** `USE_LLM` viene en `true`. Sin `GROQ_API_KEY` el sistema funciona igual, pero cada texto sale de una plantilla. Para demostrar la IA hay que tener la clave en el entorno. Cada consulta guarda de dónde salió su texto (`query_logs.explanation_source` y `fallback_reason`) y `/api/query` lo devuelve en `explanation_source`, así que se puede comprobar en vez de suponer.

**FinBERT.** Sirve para añadir una etiqueta de sentimiento (positivo, negativo, neutral) al lado del texto. No escribe nada. Además:
- Está comentado en `requirements.txt` (`transformers`/`torch` no se instalan), así que en la práctica no se ejecuta.
- Se alimenta con una frase en inglés construida a mano ("BCI RSI at 46.59, neutral"). Por razonamiento, no por prueba: FinBERT se entrenó con noticias financieras, no con descripciones de indicadores técnicos, así que su etiqueta sobre esa frase probablemente no aporta información propia.
- Si el requisito RF-04.1 exige FinBERT, hay que declarar que está implementado como componente opcional y desactivado.

## 3. Archivo por archivo

### `levels.py` — Los tres niveles (94 líneas)
Fuente única de qué significa cada nivel. Cada uno tiene una "ficha":

| | Básico | Intermedio | Avanzado |
|---|---|---|---|
| Audiencia | nunca ha invertido | sabe qué es una acción | conoce análisis técnico |
| Explica qué mide el indicador | siempre | una frase | no |
| Vocabulario | sin jerga (lista `forbidden_terms`) | técnico, traducido | técnico libre |
| Umbrales (70, 30...) | no los menciona | los nombra | los cita |
| Contexto IPSA | sí | sí | no |
| Máx. palabras | 90 | 60 | 40 |

La misma ficha alimenta al LLM (como instrucciones) y a las plantillas. También mapea la experiencia declarada al nivel inicial (`nunca→basico`, `poco→intermedio`, `experiencia→avanzado`). `contains_forbidden_term` revisa si un texto usa una palabra prohibida del nivel.

### `explainer.py` — El orquestador (≈ 320 líneas)
Es la API pública del módulo: `generate_explanation` y `regenerate_explanation`.
- **`_ZONA` y `_LLANO`**: la lectura de cada señal en versión técnica ("en sobrecompra (sobre 70)") y en lenguaje cotidiano ("subió muy rápido"). Rellenan los huecos `{zona}` y `{llano}` de las plantillas.
- **`_reading_key`**: decide qué lectura corresponde (la señal para RSI y Bollinger, la tendencia para MACD y medias).
- **`generate_explanation`**: intenta el LLM, aplica los filtros y, si no pasan, usa la plantilla `TEMPLATES[nivel][indicador][riesgo][variante % 3]`. Añade la frase del IPSA (solo básico e intermedio) y recorta al máximo de palabras.
- **`regenerate_explanation`**: el botón "No entendí esto". Pasa a la siguiente variante, `(anterior + 1) % 3`.
- **FinBERT**: se carga una sola vez por proceso; si falla, no reintenta y devuelve `None`.
- **`_trim_to_max_words`**: recorta en el último fin de oración que conserve al menos el 60 % del texto.

### `llm_explainer.py` — El LLM y su prompt (≈ 270 líneas)
Aquí vive la parte de IA. Detalle en la sección 4.

### `validator.py` — El guardarraíl (≈ 190 líneas)
`validate_coherence(datos, texto)` devuelve `(ok, motivo)`. Comprueba:
1. que el texto cite la etiqueta de riesgo calculada ("riesgo medio");
2. que cite el valor real **como número completo** ("15.0" no cuenta como 5.0; acepta coma decimal y ceros finales);
3. que no **afirme** algo contrario al dato.

El concepto central es *afirmación*. Una mención negada ("no hay sobrecompra"), condicional ("si superara 70...") o que define un umbral ("sobre 70 se considera sobrecompra") **no** se trata como afirmación. Así solo se rechaza una contradicción clara, y ante la duda el texto se acepta, para no descartar explicaciones buenas.

Reglas por indicador:
- **RSI y Bollinger:** no afirmar sobrecompra salvo señal `sobrecomprado` o valor sobre el umbral; lo mismo para sobreventa.
- **MACD y medias móviles:** no afirmar la tendencia opuesta a la calculada.

**Limitaciones declaradas en su docstring** (decirlas antes de que las encuentren): no detecta un texto con dos etiquetas de riesgo, no comprueba la dirección de la frase ("sube" cuando baja), y no ve una contradicción escrita dentro de una oración que también tenga una negación o condicional.

No importa nada del Extractor: comprueba solo con el diccionario que recibe.

### `templates.py` — El plan B (246 líneas)
`TEMPLATES[nivel][indicador][riesgo]` es una lista de 3 redacciones ordenadas por estilo (0 directa, 1 conversacional, 2 con contexto): 3 × 4 × 3 × 3 = **108 frases**. El índice es el `variant`. Los marcadores `{symbol} {value} {risk_label} {trend} {zona} {llano} {dir}` se rellenan en `_fill_template`. Las plantillas de riesgo "alto" no afirman sobrecompra por su cuenta: eso lo aporta `{zona}`/`{llano}` según la señal real.

### `readability.py` — Legibilidad (39 líneas)
Índice de Fernández-Huerta (adaptación al español del de Flesch): `206.84 − 60 × sílabas/palabra − 1.02 × palabras/oración`. Las sílabas se aproximan contando grupos de vocales. Se calcula y se envía al frontend, pero **ninguna parte del flujo lo usa para decidir nada**. Un matiz medido: el punto de un decimal cuenta como fin de oración, y baja un poco el puntaje (103.51 con `46.6`, 101.13 con `46,6`).

### `glossary.py` — Glosario (27 líneas)
Carga `data/glossary.json` y ofrece listar y buscar. No tiene relación con las explicaciones; vive aquí por historia. Lo usan la página y la búsqueda del Glosario.

### `__init__.py`
Exporta `generate_explanation`, `regenerate_explanation` y `validate_coherence`.

## 4. El system prompt

### Qué se le envía al modelo (medido)
Hay dos mensajes por llamada:

**Mensaje de sistema** (≈ 290 a 320 palabras según el nivel). Es siempre el mismo salvo el bloque final del nivel:
1. *Rol*: educador financiero del mercado chileno; explica el dato, no aconseja.
2. *Qué debe tener*: (1) qué mide el indicador, (2) qué dice el número, (3) por qué se lee así. Para 1 y 3, **solo** usar la lectura que se le entrega; no agregar fórmulas ni cifras.
3. *Qué no debe hacer*: no pronosticar ("subirá", "bajará"), no aconsejar comprar/vender, no inventar causas, no poner descargos legales, no usar analogías.
4. *Ficha del nivel*: audiencia, qué explicar, vocabulario, umbrales, contexto IPSA, máximo de palabras.

**Mensaje de usuario**: empresa, indicador, valor con su señal, nivel de riesgo, una "lectura verificada" del indicador (`_INDICATOR_FACTS`, con versión `llano` para básico y `tecnico` para el resto), el estilo pedido (0, 1 o 2), y los requisitos: "incluye el número exactamente como `46.59` y la frase `riesgo medio` en las primeras dos oraciones".

Parámetros de la llamada: `temperature=0.7`, `max_tokens=300`, un solo intento, sin reintentos.

### Qué decisiones de diseño tiene (para defender)
- **El modelo no calcula nada.** Recibe el valor, el riesgo y la señal ya calculados por el Extractor. Esto elimina el riesgo de que invente cifras y concentra el trabajo del modelo en lo que sabe hacer: redactar.
- **La "lectura verificada" es una guía anclada al código.** `_INDICATOR_FACTS` está escrita a partir de `indicators.py` y `tests/test_llm_prompt.py` compara ese texto con el código fuente: si cambia una fórmula o ventana, el test falla hasta actualizar el prompt. (Esto ya nos pasó con las medias móviles en esta sesión.)
- **No hay ejemplos en el prompt (sin *few-shot*), a propósito.** El comentario del código dice que el modelo los copiaría y la repetición empeoraría. Es una hipótesis razonable, **no está medida**.
- **Cada estilo cambia cómo abre y cierra el texto**, para evitar que todo salga con el mismo molde.
- **Defensa en capas.** El prompt *pide* coherencia; el validador la *comprueba*. El prompt solo no basta, porque un LLM puede ignorar una instrucción.

### ¿Hay que profundizar en el system prompt? Sí, con un orden
Es donde está tu aporte de IA y el único componente generativo, así que sí. Pero **no empieces reescribiéndolo**:

1. **Primero mide la línea base.** Sin una corrida real de Groq no sabes si hay un problema que arreglar. Hoy no existe ningún dato del modelo real.
2. **Después cambia una sola cosa a la vez** y compara con `scripts/medir_llm.py --comparar` (usa una huella del prompt para saber qué versión corrió cada vez). Si cambias cinco cosas, no sabrás cuál ayudó.
3. **Más reglas no es mejor.** El prompt ya tiene ≈ 300 palabras y muchas prohibiciones. Cada regla nueva compite con las demás.

Cosas concretas que valen la pena revisar (todas **por lectura**, sin probar):
- **Razonamiento (`<think>`).** La documentación de Groq dice que `qwen/qwen3.8-27b` soporta razonamiento (parámetros `reasoning_effort` y `reasoning_format`), pero sus dos páginas no coinciden sobre el comportamiento por omisión: una dice que con `default` el modelo no devuelve tokens de razonamiento, y la otra lo describe como "modo de pensamiento". `generate_explanation_llm` no envía ninguno de los dos parámetros y **no elimina** bloques `<think>`. Si el modelo los devuelve, un texto con razonamiento que cite el valor y el riesgo podría pasar los filtros y mostrarse. Solo una corrida real lo resuelve.
- **`max_tokens=300`.** La documentación no aclara si los tokens de razonamiento cuentan contra ese límite. Mismo motivo para medirlo.
- **El identificador `qwen/qwen3.8-27b` existe**, pero Groq lo lista como modelo **Preview**: "para evaluación, no para producción". Puede cambiar o retirarse. Hay que declararlo.
- **Sin reintento:** si el texto no pasa los filtros, se cae a plantilla sin pedirle otra versión al modelo.
- **La instrucción "nunca incluyas avisos legales"** es una decisión de producto (la plataforma ya informa aparte). Conviene poder justificarla.

## 5. Cómo medir la IA

### La pregunta que más importa
Cualquier métrica de calidad del texto del LLM es poco útil sola. La pregunta que justifica usar IA es: **¿mejora algo frente a las plantillas, que son gratis, instantáneas y siempre correctas?** Por eso casi todas las métricas deberían medirse **para los dos motores sobre los mismos casos** y compararse.

Hoy lo medido (en `docs/informe/c12_metricas_mvp.md`) son solo las plantillas, y que den 100 % de coherencia es casi tautológico: son frases fijas.

### Métricas propuestas

| # | Qué mide | Métrica | Cómo se obtiene | Estado |
|---|---|---|---|---|
| 1 | **Fiabilidad del LLM** | % de textos aceptados, y desglose por motivo (sin riesgo, sin valor, término prohibido, incoherente, error de API) | `scripts/medir_llm.py` | Script existe; **sin corrida real** |
| 2 | **Uso real del LLM en producción** | % de explicaciones servidas por el LLM frente a plantilla | Requiere registrar de dónde sale cada texto (hoy `except Exception: pass` lo oculta) | **No existe** |
| 3 | **Calidad del validador** | % de contradicciones inyectadas que rechaza (prueba de mutación) | Tomar textos válidos, cambiarles el número, la tendencia o "sobrecompra" por "sobreventa", y contar cuántos rechaza | **No existe**; barato de construir |
| 4 | **Adherencia al nivel** | Palabras prohibidas en básico (debe ser 0), % sobre el máximo de palabras, diferencia de legibilidad entre niveles | `scripts/medir_llm.py` ya guarda palabras y legibilidad | Parcial |
| 5 | **Variedad** | Apertura más repetida, aperturas distintas, similitud entre textos del mismo nivel | `scripts/medir_llm.py` | Script existe; sin corrida real |
| 6 | **Seguridad** | % de textos con lenguaje de consejo o pronóstico | Lista de palabras en `scripts/medir_llm.py` | Indicador débil (cuenta palabras, no entiende) |
| 7 | **Latencia** | Mediana y p95 de la llamada, contra el límite de RNF-01.1 (5 s) | `scripts/medir_llm.py` y `query_logs.processing_time_ms` | Script existe; sin corrida real |
| 8 | **Repetibilidad** | Mismos casos repetidos 3 veces (la temperatura 0.7 da resultados distintos): media y rango | Correr el script varias veces | Pendiente |
| 9 | **Valor para la persona** | Calificación 1-5 de claridad, exactitud y utilidad, **a ciegas**, LLM contra plantilla | 3 a 5 personas, ~20 textos | **No evaluado** (el ADR 0007 retiró las encuestas) |

### Qué haría yo, en este orden
1. **Una corrida real** de `medir_llm.py` con tus 108 casos (≈ 108 llamadas): da las métricas 1, 4, 5, 6 y 7 de una vez. Es el dato que hoy falta y el más importante.
2. **La prueba de mutación** (métrica 3): responde "¿el validador sirve de verdad?" con un número, y es objetiva. Es lo más defendible del proyecto si se hace bien.
3. **Un contador de origen del texto** (métrica 2): sin él no puedes afirmar cuánto del sistema en uso es IA.
4. **Una comparación ciega con 3 a 5 personas** (métrica 9): es la única que responde si la IA ayuda. Es una decisión tuya; el ADR 0007 la sacó del alcance, pero es la que más valor tiene para el objetivo de "comprensión".

### Cómo reportarlas con honestidad
- Di siempre **cuántos casos** y **con qué datos**: los valores de entrada son de ejemplo, no precios reales.
- **Repite la corrida**: con temperatura 0.7, un solo resultado no es una medida.
- Las métricas 5 y 6 **cuentan palabras**, no entienden el texto. Lo decisivo es leer los textos guardados.
- No presentes el índice de Fernández-Huerta como prueba de comprensión: es una aproximación y no sustituye una prueba con personas.

## 6. Preguntas típicas de defensa

**¿Dónde está la IA del proyecto?** En el LLM que redacta las explicaciones. El resto (validador, plantillas, niveles) es ingeniería clásica que lo rodea para hacerlo confiable. FinBERT está implementado como componente opcional y desactivado.

**¿Por qué un LLM y no solo plantillas?** Las plantillas son exactas pero rígidas: siempre dicen lo mismo. El LLM varía y se adapta al contexto. *Pero hay que poder mostrar que aporta algo*: ese es el sentido de comparar los dos motores con las mismas métricas.

**¿Cómo evitan que el modelo se equivoque con los números?** El modelo no calcula: recibe el valor ya calculado. Además, un validador comprueba que el texto cite el valor exacto y el riesgo correcto, y que no afirme algo contrario al dato. Si no pasa, se usa una plantilla.

**¿Y si el validador se equivoca?** Tiene limitaciones declaradas: no detecta dos etiquetas de riesgo en un texto ni la dirección de la frase. Por diseño prefiere aceptar ante la duda, para no descartar buenos textos. La prueba de mutación (métrica 3) mediría exactamente cuánto deja pasar.

**¿Qué pasa si Groq se cae?** El usuario recibe igual una explicación, de la plantilla. Es tolerancia a fallos (RNF-09).

**¿Cómo saben que el prompt es bueno?** Hoy no lo sabemos con datos reales: nunca se ejecutó contra Groq. El script de medición y la huella del prompt permiten comparar versiones; falta la primera corrida.

**¿Por qué el texto no incluye un aviso legal?** Decisión de producto: la plataforma informa eso por separado y el prompt prohíbe pronosticar y aconsejar. Hay que poder justificarla.

**¿El nivel se adapta solo?** Sí, pero con reglas simples, no con IA: cada 2 regeneraciones de un indicador ("No entendí esto") baja un nivel. El umbral de 2 es un supuesto sin validar (ADR 0003).

## 7. Qué ya se corrigió y qué sigue pendiente

**Corregido en esta revisión (validador):**
- el valor se buscaba como subcadena ("15.0" aceptaba 5.0);
- no detectaba `sobrecompra` ni `sobreventa`, las formas que el prompt le pide al modelo;
- la regla de medias móviles comparaba dos datos entre sí y no miraba el texto;
- rechazaba textos correctos con negaciones, coma decimal o el signo menos tipográfico.

**Pendiente (por orden de importancia para la tesis):**
1. Una corrida real contra Groq (el contador de origen del texto ya existe; falta ejecutar y leer los datos).
2. Comprobar el manejo de `<think>` y `max_tokens` con el modelo real.
3. Registrar por qué cae el LLM a plantilla, en vez de `except Exception: pass`.
4. Las plantillas de medias móviles del nivel básico dicen "semanas atrás", pero ahora son ventanas de 50 y 200 sesiones.
5. Quitar la duplicación en `explainer.py` (arma el resultado dos veces) y mover `RISK_LABELS`, `_ZONA` y `_LLANO` a un módulo propio para eliminar las importaciones circulares.
6. Sacar `glossary.py` del módulo.
7. Un typo en el prompt: "sobrevenida" en lugar de "sobreventa".
