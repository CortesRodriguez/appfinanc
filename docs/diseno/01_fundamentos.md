# Fase 1 — Fundamentos del proyecto

## Problema

El acceso a plataformas de inversión y productos financieros se ha masificado significativamente en Chile, pero no ha sido acompañado de un nivel equivalente de comprensión de la información financiera. Los inversionistas principiantes se enfrentan a indicadores técnicos —MACD, medias móviles, RSI, Bandas de Bollinger— presentados sin contextualización comprensible, y a una terminología financiera que asume una alfabetización que no tienen.

Los datos que respaldan este diagnóstico son concretos:

- La Encuesta Financiera de Hogares 2024 del Banco Central de Chile (2025) reporta que solo el **38,5 %** de la población responde correctamente la pregunta sobre interés real, y el **puntaje promedio de alfabetización financiera es 1,6 sobre 3**.
- La Comisión para el Mercado Financiero (2024) reporta que menos del **40 %** de la población declaró haber ahorrado durante 2023, y solo el **38 %** se siente capaz de cubrir gastos inesperados sin endeudarse.

A esto se suma una dimensión cognitiva: desde la perspectiva de la *Behavioral Finance*, Kahneman (2011) demuestra que los individuos toman decisiones frecuentemente bajo el Sistema 1 —rápido, intuitivo, automático—, lo que los hace propensos a sobreconfianza, aversión a la pérdida e interpretaciones erróneas de información compleja.

La pregunta a responder es:

> ¿Cómo diseñar un sistema basado en inteligencia artificial que permita simplificar la información financiera y apoyar la toma de decisiones de inversionistas principiantes en Chile?

## Justificación

Un análisis de las principales soluciones disponibles en el mercado chileno (Fintual, LarrainVial, eToro) evidencia una brecha específica: **no existe una solución que combine la simplificación del lenguaje financiero con la explicación contextualizada de indicadores técnicos mediante IA, orientada específicamente a usuarios principiantes en español y en el contexto regulatorio chileno**. Fintual simplifica el proceso pero no educa; LarrainVial informa con densidad pensada para expertos; eToro apela a la simplicidad visual pero no traduce indicadores.

Desde el punto de vista de externalidades, el proyecto contribuye a disminuir desigualdades en el acceso a información financiera, impulsa estándares de usabilidad y transparencia en soluciones fintech, y complementa iniciativas de educación financiera del Centro de Políticas Públicas UC.

La viabilidad técnica es favorable: modelos de NLP preentrenados como FinBERT están disponibles de forma abierta y permiten prototipos funcionales sin infraestructura de alto costo.

## Objetivo general

Desarrollar un sistema basado en inteligencia artificial para apoyar la comprensión de información financiera técnica en inversionistas principiantes del contexto digital chileno.

## Objetivos específicos

1. **Analizar** los principales indicadores financieros utilizados en plataformas de inversión, identificando aquellos relevantes para la toma de decisiones de usuarios principiantes.
2. **Identificar** las principales dificultades de comprensión y sesgos cognitivos presentes en inversionistas principiantes, considerando aportes de la teoría de Behavioral Finance asociada a autores como Daniel Kahneman.
3. **Diseñar** un modelo conceptual que permita transformar información financiera técnica en representaciones simplificadas orientadas a usuarios no expertos.
4. **Desarrollar** un prototipo de sistema basado en inteligencia artificial que procese datos financieros y genere interpretaciones comprensibles mediante técnicas de procesamiento de lenguaje natural.
5. **Evaluar** la efectividad del sistema mediante encuestas de comprensión aplicadas a usuarios principiantes, utilizando un análisis comparativo antes/después de la interacción con el sistema.
6. **Validar** la coherencia entre la información entregada por el sistema y los indicadores financieros originales, asegurando que la simplificación no distorsione el contenido técnico.

Los seis objetivos están directamente articulados con las fases del marco metodológico: los objetivos 1 y 2 corresponden a la fase de análisis; el objetivo 3, al diseño; el objetivo 4, al desarrollo; los objetivos 5 y 6, a la evaluación y validación.

## Alcances y limitaciones

### Alcance

El proyecto contempla el diseño y desarrollo de un prototipo funcional de inteligencia artificial orientado a la interpretación y simplificación de información financiera para inversionistas principiantes en Chile.

El sistema procesará un conjunto acotado de **cuatro indicadores financieros básicos**: **RSI, medias móviles, MACD y Bandas de Bollinger**.

Desde el punto de vista técnico, el prototipo utilizará:

- **Python** como lenguaje de desarrollo.
- **Modelos de NLP** mediante la librería Hugging Face Transformers (**FinBERT** preentrenado).
- **Conexión a fuentes de datos financieros públicas**: Yahoo Finance API o Alpha Vantage para instrumentos del IPSA; API pública del Banco Central de Chile (mindicador.cl) para indicadores macroeconómicos.
- **Interfaz de usuario** tipo web, prototipada en Figma y desarrollada en Flask.

El alcance funcional incluye:

- Identificación y extracción de indicadores financieros desde fuentes de datos abiertas.
- Generación de explicaciones en lenguaje natural a partir de los indicadores seleccionados.
- Presentación de la información al usuario mediante una interfaz simplificada.
- Evaluación del sistema mediante encuestas de comprensión aplicadas a un grupo de usuarios principiantes.

**El sistema no incluirá funcionalidades de predicción de mercado, recomendaciones de compra/venta ni ejecución de transacciones financieras.**

### Limitaciones

- **Limitación metodológica**: la evaluación se realizará en un entorno controlado con una muestra reducida de usuarios, lo que limita la generalización de los resultados a contextos reales de uso masivo.
- **Limitación técnica**: la calidad de las explicaciones generadas depende del modelo de NLP seleccionado y de la disponibilidad de datos financieros en español. Los modelos de lenguaje pueden presentar alucinaciones o imprecisiones que deberán ser controladas mediante reglas de validación (RF-04.2).
- **Limitación de datos**: el sistema operará con datos financieros históricos y en tiempo diferido, no en tiempo real, dado que el acceso a APIs de tiempo real tiene costo (RNF-08).
- **Limitación contextual**: el prototipo se desarrollará en el contexto académico de la asignatura, por lo que no estará sometido a los estándares regulatorios de la CMF para herramientas de asesoramiento financiero.

Los supuestos de trabajo incluyen: disponibilidad de acceso a internet para consumo de APIs, uso de herramientas de código abierto sin costo de licencia y contar con un grupo de al menos 5 usuarios principiantes para la evaluación del prototipo.

## Resultados esperados

- Un prototipo funcional de sistema de IA capaz de procesar indicadores financieros y generar explicaciones en lenguaje natural comprensible para usuarios principiantes.
- Un modelo conceptual documentado que describa el proceso de transformación de datos financieros técnicos en representaciones simplificadas.
- Resultados de evaluación cuantitativa que midan el nivel de comprensión de los usuarios antes y después de interactuar con el sistema.
- Un análisis de validación que confirme la coherencia entre las explicaciones generadas y los indicadores financieros originales.

## Metodología de desarrollo

Se adopta **Scrum** (Schwaber & Sutherland, 2020) como marco de trabajo ágil. Scrum organiza el trabajo en **sprints** iterativos de dos semanas, cada uno orientado al cumplimiento de objetivos específicos, lo que permite inspeccionar el progreso, ajustar el rumbo y mejorar continuamente el producto a medida que avanza el desarrollo.

### Roles

- **Product Owner**: responsable de gestionar y priorizar el *Product Backlog*, asegurando que el desarrollo se oriente hacia el valor esperado por el usuario final.
- **Scrum Master**: facilita la correcta implementación del marco de trabajo, elimina impedimentos y promueve la autogestión del equipo.
- **Equipo Scrum**: grupo autogestionado responsable de entregar un incremento funcional del producto al final de cada sprint.

En el contexto de trabajo individual del proyecto de título, los tres roles se ejecutan por una misma persona; se conservan del marco los eventos y artefactos que aportan valor (planificación, revisión y retrospectiva del sprint, backlog priorizado) y se descartan los que no aplican a un equipo unipersonal.

### Artefactos y eventos

- **Product Backlog / Sprint Backlog**: listas priorizadas de tareas (análisis de indicadores, diseño del modelo, desarrollo del prototipo, evaluación con usuarios), derivadas directamente de los objetivos específicos.
- **Sprint**: ciclo de trabajo de dos semanas en el que se desarrolla un incremento funcional del sistema.
- **Revisión y retrospectiva del sprint**: instancias de evaluación del avance y ajuste del plan, coherentes con la naturaleza exploratoria del proyecto.

### Justificación frente a Cascada

| Criterio | Scrum | Cascada |
|---|---|---|
| Estructura | Iterativa, por sprints | Fases fijas (análisis, diseño, desarrollo, pruebas) |
| Adaptación a cambios | Se adapta al cambio, permite ajustar el modelo de NLP entre sprints | Cualquier cambio implica retroceder etapas completas |
| Entrega de valor | Incremental, desde etapas tempranas | Solo al final del ciclo completo |
| Validación con usuarios | Continua, integrada en cada sprint | Únicamente en la fase final de pruebas |
| Adecuación a proyectos exploratorios (IA/NLP) | Alta: los resultados de los modelos pueden requerir ajustes no previstos | Baja: asume requerimientos completamente definidos desde el inicio |

La principal limitación de Cascada para este proyecto es su rigidez: dado que el desarrollo involucra experimentación con modelos de NLP —cuyo desempeño real solo se conoce al probarlos con datos e indicadores financieros reales—, un enfoque secuencial dificultaría incorporar ajustes de diseño surgidos durante la implementación. Scrum permite responder a estos hallazgos sin comprometer todo el cronograma.

### Fundamento de la elección

Se selecciona Scrum por su coherencia con tres características centrales del proyecto:

1. La **naturaleza exploratoria** del trabajo con modelos de lenguaje, donde el desempeño real solo se valida empíricamente y puede requerir ajustes iterativos.
2. La **necesidad de validación temprana y continua con usuarios**, contemplada explícitamente en los objetivos específicos (evaluación de comprensión y validación de coherencia), lo que se alinea naturalmente con la revisión de sprint.
3. La **escala del proyecto**, que —aunque individual— se beneficia de la estructura de trabajo por ciclos cortos para mantener trazabilidad y control de avance.

## Marco arquitectónico: modelo 4+1

El sistema se describe siguiendo el **modelo de vistas 4+1** propuesto por Kruchten (1995), que caracteriza la arquitectura desde cinco perspectivas interrelacionadas:

- **Vista lógica**: componentes funcionales orientados al usuario final. El sistema se organiza en tres componentes principales —**Extractor**, **Procesador NLP** (con FinBERT) y **Presentador** (interfaz web en Flask)— más un **Módulo de Evaluación** que opera como instrumentación transversal.
- **Vista de procesos**: el flujo opera de forma secuencial y en tiempo diferido: el Extractor obtiene los datos, el Procesador NLP genera la explicación, y el Presentador la muestra al usuario.
- **Vista de desarrollo**: el sistema se estructura en capas independientes, lo que facilita su mantenibilidad.
- **Vista física**: el prototipo se despliega en un nodo único, sin infraestructura distribuida, consumiendo las APIs financieras mediante solicitudes HTTP salientes.
- **Vista de escenarios**: se definen dos escenarios arquitectónicos representativos —(1) consulta de un indicador y (2) validación de coherencia entre la explicación generada y el dato original— cuyo detalle funcional se documenta como casos de uso extendidos (Fase 3).

## Relación con el resto de la documentación

- Los objetivos específicos 1 y 2 (**analizar** e **identificar**) alimentan el marco teórico y la selección de indicadores.
- El objetivo 3 (**diseñar**) se materializa en las Fases 3 a 8 de esta documentación (casos de uso, modelo de datos, arquitectura, patrones, secuencia, clases).
- El objetivo 4 (**desarrollar**) es el prototipo de código descrito en la Fase 9 (stack tecnológico) y organizado por sprints según la planificación.
- Los objetivos 5 y 6 (**evaluar** y **validar**) se documentan en la Fase 10 (pruebas y validación) y se sostienen en el Módulo de Evaluación de la vista lógica.

## Referencias

- Banco Central de Chile. (2025). *Encuesta Financiera de Hogares 2024: Informe de resultados*.
- Comisión para el Mercado Financiero. (2024). *Reporte de actividades de educación financiera 2024*.
- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus & Giroux.
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.
- Schwaber, K., & Sutherland, J. (2020). *La guía de Scrum: la guía definitiva de Scrum*. https://scrumguides.org
