# Documentación de diseño — appfint

Documentación estructurada del proyecto de título **"Desarrollo de un sistema basado en inteligencia artificial para apoyar la comprensión de información financiera técnica en inversionistas principiantes del contexto digital chileno"**, organizada según la guía de 11 fases del proyecto de título.

## Estructura

- `diseno/` — Un archivo por fase de diseño. Cada archivo es autosuficiente y puede leerse en la memoria de título o citarse en la defensa.
- `diagramas/` — Diagramas UML y de arquitectura en formato Mermaid.

## Índice por fase

| Fase | Documento | Diagramas asociados |
|---|---|---|
| 1. Fundamentos | [`diseno/01_fundamentos.md`](diseno/01_fundamentos.md) | — |
| 2. Requerimientos | [`diseno/02_requerimientos.md`](diseno/02_requerimientos.md) | — |
| 3. Casos de uso | [`diseno/03_casos_de_uso.md`](diseno/03_casos_de_uso.md) | `diagramas/casos_de_uso/` |
| 4. Modelo de datos | [`diseno/04_modelo_de_datos.md`](diseno/04_modelo_de_datos.md) | `diagramas/bd/` |
| 5. Arquitectura | [`diseno/05_arquitectura.md`](diseno/05_arquitectura.md) | `diagramas/componentes/`, `diagramas/despliegue/` |
| 6. Patrones de diseño | [`diseno/06_patrones_de_diseno.md`](diseno/06_patrones_de_diseno.md) | — |
| 7. Diagramas de secuencia | [`diseno/07_diagramas_de_secuencia.md`](diseno/07_diagramas_de_secuencia.md) | `diagramas/secuencia/` |
| 8. Diagrama de clases | [`diseno/08_diagrama_de_clases.md`](diseno/08_diagrama_de_clases.md) | `diagramas/clases/` |
| 9. Stack tecnológico | [`diseno/09_stack_tecnologico.md`](diseno/09_stack_tecnologico.md) | — |
| 10. Pruebas y validación | [`diseno/10_pruebas_y_validacion.md`](diseno/10_pruebas_y_validacion.md) | — |

## Mapeo a capítulos de la memoria

| Fase de esta documentación | Capítulo de la memoria |
|---|---|
| 1, 2 | Introducción / Planteamiento del problema |
| 2 (marco de calidad ISO 25010) | Marco teórico |
| 3, 4, 5, 6, 7, 8 | Diseño / Desarrollo de la solución |
| 9 | Diseño / Tecnologías utilizadas |
| 10 | Resultados / Validación |

## Estándares ISO citados en esta documentación

- **ISO/IEC/IEEE 12207** — Procesos del ciclo de vida del software (Fase 1: metodología de desarrollo).
- **ISO/IEC 25010** — Modelo de calidad de producto de software (Fase 2: categorización de requerimientos no funcionales).
- **ISO/IEC/IEEE 29148** — Ingeniería de requisitos (Fase 2: proceso de levantamiento de RF/RNF).
- **Familia ISO/IEC 27000** — Principios de seguridad de la información (Fase 5 y RNF de seguridad).

## Trazabilidad transversal

Todo requerimiento funcional debe:
1. Estar en la tabla de RF de la Fase 2.
2. Ser realizado por al menos un caso de uso de la Fase 3.
3. Aparecer en al menos un diagrama de secuencia (Fase 7) si es prioritario.
4. Estar cubierto por al menos una prueba (Fase 10).
