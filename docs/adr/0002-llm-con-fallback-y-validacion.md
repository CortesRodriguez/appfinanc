# ADR 0002: explicaciones con LLM, plantillas de respaldo y validación de coherencia

- Estado: aceptada
- Requerimientos relacionados: RF-04.1, RF-04.2, RF-05.1, RF-06.2, RNF-04, RNF-09

## Contexto y problema

La explicación debe adaptarse al nivel del usuario y citar el valor real del indicador sin contradecirlo. Un LLM redacta con fluidez pero puede equivocarse; las plantillas son exactas pero rígidas.

## Criterios de decisión

- Coherencia con el dato (el aporte central del proyecto).
- Adaptación del vocabulario al nivel del usuario.
- Tolerancia a fallos de un tercero (RNF-09).

## Opciones consideradas

### A. Solo plantillas
- Pro: coherencia por construcción, sin dependencias externas, reproducible.
- Contra: poca flexibilidad para ajustar el texto al nivel y al contexto.

### B. LLM con plantillas de respaldo (elegida)
- Pro: texto ajustado a la ficha del nivel; si el LLM falla, el usuario igual recibe una explicación.
- Contra: dependencia de Groq; la salida puede ser incoherente con el dato.

### C. FinBERT como generador
- Contra: FinBERT es un clasificador de sentimiento, no genera texto. Se mantiene solo como señal opcional.

## Decisión

Se elige B. Flujo en `src/nlp/explainer.py:generate_explanation`:

1. Si `USE_LLM` está activo y hay `GROQ_API_KEY`, el LLM (`qwen/qwen3.8-27b` vía Groq) redacta el texto.
2. Se recorta al máximo de palabras del nivel y se acepta solo si contiene la etiqueta de riesgo, el valor del indicador (como cadena), ningún término prohibido del nivel y **si además pasa `validate_coherence`** (`src/nlp/validator.py`), que contrasta el texto con el valor y los umbrales del indicador.
3. En cualquier otro caso, o ante una excepción, se usa una plantilla.
4. Las rutas vuelven a validar el texto final y devuelven `coherent` y `reason`; la interfaz muestra un aviso si discrepa. Las plantillas son coherentes por construcción, así que ese aviso solo debería aparecer en casos que el validador no cubre.

## Consecuencias

- Positivas: fluidez y adaptación al nivel con una red de seguridad.
- Positivas: un texto del LLM que contradice el dato (por ejemplo, dice "sobrecomprado" con un RSI bajo, o cita "15.0" cuando el valor es 5.0) ya no se muestra: cae a plantilla. Hay un test que lo comprueba y se verificó que falla si se quita el guardarraíl.
- Negativas, verificadas en el código:
  - El validador solo cubre lo que sus reglas conocen: riesgo, valor citado y las categorías cualitativas de RSI, %B, MACD y medias móviles. Una frase falsa fuera de esas reglas (por ejemplo, una causa inventada) no se detecta.
  - La comprobación del valor es una búsqueda de cadena (`value_str in texto`): un valor `5.0` sigue pasando si el texto dice "15.0" y no menciona ninguna categoría contradictoria.
  - El `except Exception: pass` oculta los fallos del LLM; no hay conteo de cuántas veces se usa el respaldo.
  - No se probó contra la API real de Groq: los tests simulan la respuesta del modelo.

## Mejora pendiente (no implementada)

Registrar cuántas salidas del LLM caen al respaldo, para tener un dato en la defensa.

## Verificación

`tests/test_validator.py`, `tests/test_explainer.py` y la validación de cada nivel y estilo de plantilla en `tests/test_profile.py`.

## Referencias

- Nygard, M. (2018). *Release It!* (2.ª ed.). Pragmatic Bookshelf (verificar). Patrones de estabilidad: degradación controlada.
- Kosireddy et al. (2024); Li et al. (2023); Lazarev & Sedov (2024): ya citados en el marco teórico.
