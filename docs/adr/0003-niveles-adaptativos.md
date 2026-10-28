# ADR 0003: niveles adaptativos con ficha declarativa

- Estado: aceptada como heurística; sin validación empírica
- Requerimientos relacionados: RF-05.2, RF-06.2, RF-13.2, RF-14

## Contexto y problema

El público objetivo va desde quien nunca ha invertido hasta quien tiene experiencia. Una misma explicación no sirve para todos.

## Opciones consideradas

### A. Un solo nivel de explicación
- Pro: simple. Contra: no responde al problema.

### B. Reglas simples con tres niveles (elegida)
- Pro: explicable, testeable, sin entrenar modelos.
- Contra: el umbral de bajada de nivel no tiene respaldo empírico.

### C. Modelo de usuario aprendido
- Contra: requiere datos que el proyecto no tiene.

## Decisión

Tres niveles (`basico`, `intermedio`, `avanzado`) definidos por una ficha en `src/nlp/levels.py` (audiencia, vocabulario, términos prohibidos, umbrales, contexto IPSA, máximo de palabras). La misma ficha alimenta el prompt del LLM y las plantillas.

- Nivel inicial según la experiencia declarada: nunca → básico, poco → intermedio, experiencia → avanzado, sin dato → intermedio.
- Cada `DETAIL_THRESHOLD = 2` regeneraciones ("No entendí esto") de un indicador bajan un nivel, con piso en básico.
- Cambiar la experiencia declarada reinicia el conteo (`users.level_reset_at`).
- `preferred_variant()` recuerda el estilo de redacción donde el usuario dejó de regenerar.

## Consecuencias

- Positivas: una sola fuente de verdad por nivel; tests recorren cada nivel y estilo contra el validador.
- Negativas:
  - Interpretar "No entendí esto" como baja comprensión y fijar el umbral en 2 son supuestos sin validar. El retiro de las encuestas (ADR 0007) quita la forma prevista de comprobarlos.
  - Solo baja de nivel; nunca sube.
- **Decisión sobre estos límites:** se mantiene como una regla heurística y se declara como limitación en el informe. No se agregó una regla para subir de nivel ni se hizo configurable el umbral, porque cualquier valor nuevo tampoco tendría respaldo empírico.
- Mejoras posibles, si hay validación con usuarios: regla para subir de nivel tras N consultas sin regenerar; umbral configurable (`DETAIL_THRESHOLD` está en `src/profile/service.py`).

## Verificación

`tests/test_profile.py`.

## Referencias

- Fuente sobre modelos de usuario en sistemas adaptativos (verificar antes de citar).
