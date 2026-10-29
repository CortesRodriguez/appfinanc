# 0007. Retiro del módulo de encuestas pre/post

## Status

Aceptada (2026-10-28).

## Context

La versión inicial incluía encuestas de comprensión pre y post uso, reportes, exportación CSV y un panel de auditoría de coherencia. Ese código (`surveys.py`, `eligibility.py`, `reports.py`, sus plantillas y tests) se eliminó del prototipo. La documentación y el informe seguían describiéndolo.

Requerimientos afectados: objetivo específico 5 original, RNF-05.2 y CU-06/07/09/10 de la versión anterior de la documentación.

Alternativas consideradas:

- **Reincorporar las encuestas.** Permitiría medir con datos la efectividad del sistema, pero exige rediseñar el módulo, el consentimiento y la anonimización, además de reclutar participantes. No cabe en el tiempo restante.
- **Retirarlas del alcance y de la documentación.** Deja la documentación coherente con el código. Costo: el proyecto no mide la efectividad del sistema sobre los usuarios.

## Decision

Se retiran del alcance el objetivo de evaluación con encuestas, RNF-05.2 y los casos de uso asociados. La validación con usuarios queda como trabajo futuro. La coherencia entre texto y dato se sigue comprobando automáticamente (`src/nlp/validator.py`, ADR 0002).

## Consequences

Se vuelve más fácil:

- Mantener la documentación alineada con el código.
- Defender el proyecto apoyándose en la validación técnica (tests y validador de coherencia).

Se vuelve más difícil:

- Demostrar que las explicaciones mejoran la comprensión: no hay evidencia empírica y debe declararse como limitación y proyección.
- Justificar el umbral de regeneraciones del ADR 0003, que queda sin forma prevista de validación.
- Entregar un informe consistente: hay que actualizar el informe (`docx`) y el PPT (objetivo, alcance, resultados esperados, Vista lógica y conclusiones). Esos archivos no están en el repositorio.
