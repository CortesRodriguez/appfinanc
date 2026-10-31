# Criterios y métricas de evaluación del MVP (C12)

> **Borrador.** Reescríbelo con tus palabras y declara el uso de la herramienta antes de llevarlo al informe. Las metas marcadas **(propuesta)** las propuse yo y no vienen de un requerimiento: confírmalas o cámbialas. Lo marcado **pendiente** no está medido.

## Qué se evalúa y por qué

El MVP debe demostrar que genera explicaciones en español que no contradicen el dato, son legibles, respetan la extensión de su nivel y se entregan en un tiempo razonable. Cada criterio se vincula con un objetivo específico y un requerimiento del informe.

| Criterio | Objetivo / requerimiento | Métrica | Meta | Estado |
|---|---|---|---|---|
| Coherencia con el dato | Objetivo específico 3; RF-04.2 | Porcentaje de textos que `validate_coherence` acepta | 100 % | **Medido** (plantillas) |
| Legibilidad | Objetivo específico 2; RNF-04.1 | Índice Fernández-Huerta medio por nivel | ≥ 60 **(propuesta)** | **Medido** (plantillas) |
| Extensión | RNF-04.2 | Textos que superan el máximo de palabras de su nivel | 0 | **Medido** (plantillas) |
| Tiempo de respuesta | RNF-01.1 | `processing_time_ms` registrado en cada consulta | ≤ 5 000 ms | **Pendiente** con carga real; 12 consultas de prueba |
| Regresión automática | RNF-07 | Pruebas automáticas aprobadas | 118 de 118 | **Medido** |
| Comprensión del usuario | Objetivo general | — | — | **No evaluado** (ver apartado 5) |

## Definición y método de cada métrica

**Coherencia con el dato.** `validate_coherence` (`src/nlp/validator.py`) comprueba que el texto cite la etiqueta de riesgo y el valor del indicador, y que las categorías cualitativas que mencione (sobrecomprado, alcista, etc.) correspondan a los umbrales (por ejemplo, RSI superior a 70 para sobrecompra). Se aplica a todas las combinaciones de nivel, indicador, riesgo y estilo.

**Legibilidad.** El índice de Fernández-Huerta es la adaptación al español del índice de Flesch: `206,84 − 60 × (sílabas por palabra) − 1,02 × (palabras por oración)`. Mayor valor significa texto más fácil. El código documenta rangos orientativos: más de 90 muy fácil, 70–90 fácil, 50–70 normal y menos de 50 difícil (`src/nlp/readability.py`). Las sílabas se aproximan contando grupos vocálicos, por lo que el valor es una estimación y puede salir del rango de 0 a 100 con frases muy cortas.

**Extensión.** Palabras por texto frente al máximo del nivel: 90 en básico, 60 en intermedio y 40 en avanzado (`src/nlp/levels.py`). El requerimiento general es de 150.

**Tiempo de respuesta.** Cada consulta guarda en `query_logs.processing_time_ms` el tiempo de obtener el indicador y redactar la explicación. Se evalúa con la media y el máximo por tipo de fuente.

## Resultados preliminares

Medición reproducible con `python scripts/medir_calidad_explicaciones.py`, sobre 108 textos generados con las plantillas (3 niveles × 4 indicadores × 3 riesgos × 3 estilos).

**Tabla 12.1** Calidad de las explicaciones generadas con plantillas.

| Nivel | n | Incoherentes | Sobre el límite | Fernández-Huerta (media / mín / máx) | Palabras (media / máx / límite) |
|---|---|---|---|---|---|
| Básico | 36 | 0 | 0 | 87,7 / 81,6 / 93,3 | 49,5 / 66 / 90 |
| Intermedio | 36 | 0 | 0 | 88,7 / 74,9 / 99,3 | 43,5 / 59 / 60 |
| Avanzado | 36 | 0 | 0 | 85,0 / 60,7 / 106,6 | 20,7 / 35 / 40 |

*Fuente: elaboración propia con el script `scripts/medir_calidad_explicaciones.py`.*

**Lectura.** Los 108 textos son coherentes con el dato, ninguno supera el límite de su nivel y todos alcanzan una legibilidad de al menos 60,7, por encima de la meta propuesta. El nivel avanzado tiene la media más baja de palabras (20,7) y el valor máximo de legibilidad más alto (106,6), consistente con frases muy cortas.

**Tiempo de respuesta.** La base de desarrollo tiene 12 consultas, todas con Yahoo Finance como fuente: media de 3,6 ms, mínimo de 3 ms y máximo de 5 ms. **Esta cifra no es representativa:** pertenecen a una sola sesión y, por lo rápidas que son, es probable que no incluyan la espera de la red ni la generación con LLM (no lo verifiqué), por lo que no demuestra el cumplimiento de los 5 s. **(pendiente: medir con red y con `USE_LLM=true`)**

**Pruebas automáticas.** La suite tiene 118 pruebas y todas pasan contra PostgreSQL 16 (ejecución del 29-oct-2026). Incluye la prueba de que un texto del LLM que contradice el dato se sustituye por una plantilla.

### Límites de esta medición

1. **Mide plantillas, no al LLM.** El texto generado por el modelo real nunca se evaluó con estas métricas. Es el hallazgo más importante que falta.
2. **Los valores de entrada son de ejemplo** (uno por indicador y nivel de riesgo), no precios reales.
3. **Los textos son los mismos cada vez:** una cobertura del 100 % de las plantillas no implica que el validador sea suficiente frente a un texto libre.
4. **El índice de legibilidad es una aproximación** y no sustituye una prueba de comprensión con personas.

## Cómo repetir y ampliar la medición

1. Coherencia, legibilidad y extensión: ejecutar el script de la sección anterior.
2. Tiempo de respuesta: usar el sistema con red y consultar `select source, count(*), round(avg(processing_time_ms)), max(processing_time_ms) from query_logs group by source;`.
3. LLM real: activar `USE_LLM=true` con la clave de Groq, generar el mismo conjunto de casos y registrar cuántos textos pasan la validación y cuántos caen a plantilla. Hoy ese conteo no existe.

## 5. Evaluación con usuarios

Una evaluación de la comprensión con personas (cuestionario antes y después del uso) estaba prevista originalmente y se retiró del alcance de este avance (ADR 0007). Por ello el criterio "comprensión del usuario" figura como no evaluado. **Si el docente exige validación con usuarios para esta entrega, este es el criterio que falta.** Una alternativa mínima sería una prueba corta con 3 a 5 personas que lean una explicación y respondan qué significa el indicador; esos datos tendrían que recogerse y no se pueden inferir.
