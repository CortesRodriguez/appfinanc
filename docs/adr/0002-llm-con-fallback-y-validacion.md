# ADR 0002: explicaciones con LLM, plantillas de respaldo y validación de coherencia

- Estado: aceptada, con mejora pendiente
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
2. Se recorta al máximo de palabras del nivel y se acepta solo si contiene la etiqueta de riesgo, el valor del indicador (como cadena) y ningún término prohibido del nivel.
3. En cualquier otro caso, o ante una excepción, se usa una plantilla.
4. Después, `validate_coherence` (`src/nlp/validator.py`) contrasta el texto con el valor y los umbrales. Su resultado se informa (`coherent`, `reason`) pero **no bloquea** el texto.

## Consecuencias

- Positivas: fluidez y adaptación al nivel con una red de seguridad.
- Negativas, verificadas en el código:
  - La comprobación del valor es una búsqueda de cadena (`_val_str in llm_text`): un valor `5` pasa si el texto dice "15".
  - Un texto que cumple la verificación mínima pero contradice el dato solo se marca, no se reemplaza.
  - El `except Exception: pass` oculta los fallos del LLM; no hay conteo de cuántas veces se usa el respaldo.

## Mejoras pendientes (no implementadas)

1. Llamar a `validate_coherence` antes de aceptar la salida del LLM y caer a plantillas si falla. Haría cierta la afirmación "nunca se muestra una explicación incoherente".
2. Registrar cuántas salidas del LLM caen al respaldo.

## Verificación

`tests/test_validator.py`, `tests/test_explainer.py` y la validación de cada nivel y estilo de plantilla en `tests/test_profile.py`.

## Referencias

- Nygard, M. (2018). *Release It!* (2.ª ed.). Pragmatic Bookshelf (verificar). Patrones de estabilidad: degradación controlada.
- Kosireddy et al. (2024); Li et al. (2023); Lazarev & Sedov (2024): ya citados en el marco teórico.
