# ADR 0007: retiro del módulo de encuestas pre/post

- Estado: aceptada
- Requerimientos afectados: objetivo específico 5 original, RNF-05.2, CU-06/07/09/10 de la versión anterior de la documentación

## Contexto y problema

La versión inicial incluía encuestas de comprensión pre y post uso, reportes, exportación CSV y un panel de auditoría de coherencia. Ese código (`surveys.py`, `eligibility.py`, `reports.py`, sus plantillas y tests) se eliminó del prototipo. La documentación y el informe seguían describiéndolo.

## Opciones consideradas

### A. Reincorporar las encuestas
- Pro: permitiría medir con datos la efectividad del sistema.
- Contra: exige rediseñar el módulo, el consentimiento y la anonimización, además de reclutar participantes; no cabe en el tiempo restante.

### B. Retirarlas del alcance y de la documentación (elegida)
- Pro: documentación coherente con el código.
- Contra: el proyecto no mide la efectividad del sistema sobre los usuarios.

## Decisión

Se retiran del alcance el objetivo de evaluación con encuestas, RNF-05.2 y los casos de uso asociados. La validación con usuarios queda como trabajo futuro. La coherencia entre texto y dato se sigue comprobando automáticamente (`src/nlp/validator.py`, ADR 0002).

## Consecuencias

- Negativas:
  - No hay evidencia empírica de que las explicaciones mejoren la comprensión.
  - El umbral de regeneraciones del ADR 0003 queda sin forma prevista de validación.
  - Hay que actualizar el informe (`docx`) y el PPT: objetivo, alcance, resultados esperados, Vista lógica y conclusiones. Esos archivos no están en el repositorio.
- Defensa: se puede apoyar en la validación técnica (tests, validador de coherencia) y declarar la validación con usuarios como limitación y proyección.
