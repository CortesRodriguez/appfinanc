# 0002. Explicaciones con LLM, plantillas de respaldo y validación de coherencia

## Status

Aceptada (2026-10-28). El guardarraíl de coherencia previo a aceptar el texto del LLM se decidió e implementó ese día.

## Context

La explicación debe adaptarse al nivel del usuario y citar el valor real del indicador sin contradecirlo. Un LLM redacta con fluidez pero puede equivocarse; las plantillas son exactas pero rígidas.

Requerimientos relacionados: RF-04.1, RF-04.2, RF-05.1, RF-06.2, RNF-04, RNF-09.

Alternativas consideradas:

- **Solo plantillas.** Coherentes por construcción, sin dependencias externas y reproducibles, pero con poca flexibilidad para ajustar el texto al nivel y al contexto.
- **LLM con plantillas de respaldo.** El texto se ajusta a la ficha del nivel y, si el LLM falla, el usuario igual recibe una explicación. Costo: dependencia de Groq y salida que puede ser incoherente con el dato.
- **FinBERT como generador.** Descartada: FinBERT es un clasificador de sentimiento, no genera texto. Se mantiene solo como señal opcional.

Se priorizó la coherencia con el dato (el aporte central del proyecto), la adaptación del vocabulario al nivel del usuario y la tolerancia a fallos de un tercero (RNF-09).

Referencias (verificar antes de citar):

- Nygard, M. (2018). *Release It!* (2.ª ed.). Pragmatic Bookshelf. Patrones de estabilidad: degradación controlada.
- Kosireddy et al. (2024); Li et al. (2023); Lazarev & Sedov (2024), ya citados en el marco teórico.

## Decision

Un LLM con plantillas de respaldo. Flujo en `src/nlp/explainer.py:generate_explanation`:

1. Si `USE_LLM` está activo y hay `GROQ_API_KEY`, el LLM (`qwen/qwen3.8-27b` vía Groq) redacta el texto.
2. Se recorta al máximo de palabras del nivel y se acepta solo si contiene la etiqueta de riesgo, el valor del indicador (como cadena), ningún término prohibido del nivel y, además, pasa `validate_coherence` (`src/nlp/validator.py`), que contrasta el texto con el valor y los umbrales del indicador.
3. En cualquier otro caso, o ante una excepción, se usa una plantilla.
4. Las rutas vuelven a validar el texto final y devuelven `coherent` y `reason`; la interfaz muestra un aviso si discrepa. Las plantillas son coherentes por construcción, así que ese aviso solo debería aparecer en casos que el validador no cubre.

## Consequences

Se vuelve más fácil:

- Obtener texto fluido y ajustado al nivel con una red de seguridad.
- Evitar que se muestre un texto del LLM que contradice el dato (por ejemplo, "sobrecomprado" con un RSI bajo, o "15.0" cuando el valor es 5.0): cae a plantilla. Un test lo comprueba y se verificó que falla si se quita el guardarraíl.

Se vuelve más difícil, verificado en el código:

- El validador solo cubre lo que sus reglas conocen: riesgo, valor citado y las categorías cualitativas de RSI, %B, MACD y medias móviles. Una frase falsa fuera de esas reglas (por ejemplo, una causa inventada) no se detecta.
- La comprobación del valor es una búsqueda de cadena (`value_str in texto`): un valor `5.0` sigue pasando si el texto dice "15.0" y no menciona ninguna categoría contradictoria.
- El `except Exception: pass` oculta los fallos del LLM y no hay conteo de cuántas veces se usa el respaldo. Mejora pendiente: registrar ese conteo para tener un dato en la defensa.
- No se probó contra la API real de Groq: los tests simulan la respuesta del modelo.

Verificación: `tests/test_validator.py`, `tests/test_explainer.py` y la validación de cada nivel y estilo de plantilla en `tests/test_profile.py`.
