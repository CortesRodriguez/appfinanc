# 0003. Niveles adaptativos con ficha declarativa

## Status

Aceptada como heurística, sin validación empírica (registrada a posteriori).

## Context

El público objetivo va desde quien nunca ha invertido hasta quien tiene experiencia. Una misma explicación no sirve para todos.

Requerimientos relacionados: RF-05.2, RF-06.2, RF-13.2, RF-14.

Alternativas consideradas:

- **Un solo nivel de explicación.** Simple, pero no responde al problema.
- **Reglas simples con tres niveles.** Explicable, testeable y sin entrenar modelos. Costo: el umbral de bajada de nivel no tiene respaldo empírico.
- **Modelo de usuario aprendido.** Descartada: requiere datos que el proyecto no tiene.

Referencia (verificar antes de citar): fuente sobre modelos de usuario en sistemas adaptativos.

## Decision

Tres niveles (`basico`, `intermedio`, `avanzado`) definidos por una ficha en `src/nlp/levels.py` (audiencia, vocabulario, términos prohibidos, umbrales, contexto IPSA, máximo de palabras). La misma ficha alimenta el prompt del LLM y las plantillas.

- Nivel inicial según la experiencia declarada: nunca → básico, poco → intermedio, experiencia → avanzado, sin dato → intermedio.
- Cada `DETAIL_THRESHOLD = 2` regeneraciones ("No entendí esto") de un indicador bajan un nivel, con piso en básico.
- Cambiar la experiencia declarada reinicia el conteo (`users.level_reset_at`).
- `preferred_variant()` recuerda el estilo de redacción donde el usuario dejó de regenerar.

Se mantiene como una regla heurística y se declara como limitación en el informe. No se agregó una regla para subir de nivel ni se hizo configurable el umbral, porque cualquier valor nuevo tampoco tendría respaldo empírico.

## Consequences

Se vuelve más fácil:

- Mantener una sola fuente de verdad por nivel.
- Probar cada nivel y estilo contra el validador (`tests/test_profile.py`).

Se vuelve más difícil:

- Justificar el umbral: interpretar "No entendí esto" como baja comprensión y fijarlo en 2 son supuestos sin validar. El retiro de las encuestas (ADR 0007) quita la forma prevista de comprobarlos.
- Recuperar un nivel perdido: solo baja, nunca sube.

Si hubiera validación con usuarios, se podría agregar una regla para subir de nivel tras N consultas sin regenerar y hacer configurable el umbral (`DETAIL_THRESHOLD` está en `src/profile/service.py`).
