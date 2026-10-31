# Comparación de técnicas de inteligencia artificial (C7)

> **Borrador.** Reescríbelo con tus palabras y declara el uso de la herramienta antes de llevarlo al informe. Lo marcado **(verificar)** no está confirmado en una fuente.

## Planteamiento

El sistema debe convertir el valor de un indicador técnico (RSI, MACD, medias móviles o bandas de Bollinger) en una explicación en español, adaptada al nivel de quien la lee y sin contradecir el dato. Se identificaron tres técnicas de inteligencia artificial aplicables a esa tarea y se compararon según los datos que requieren, la disponibilidad de acceso y las restricciones del contexto de implementación: un prototipo académico desarrollado por una persona, sin presupuesto y con datos públicos.

Hay que distinguir qué es IA y qué no. Los indicadores técnicos se calculan con fórmulas matemáticas y la validación de coherencia se hace con reglas fijas: ninguno de los dos aprende de datos, por lo que no se consideran técnicas de IA. Las plantillas con reglas tampoco lo son; se presentan aparte como línea base.

## Técnicas de IA comparadas

- **A. Modelo de lenguaje de gran escala (LLM) en la nube**, servido por una API de terceros. Es la técnica implementada en el proyecto.
- **B. Modelo de lenguaje pequeño (SLM) ejecutado localmente.** Se analizó con base en la literatura; **no se implementó ni se probó** en este proyecto.
- **C. FinBERT**, un modelo preentrenado de la familia BERT para clasificar sentimiento financiero. Está implementado como señal opcional.

**Tabla 2.2** Comparación de técnicas de IA para explicar indicadores financieros.

| Criterio | A. LLM en la nube (Qwen vía Groq) | B. SLM local | C. FinBERT |
|---|---|---|---|
| Qué produce | Texto libre en español | Texto libre; la calidad en español es **(verificar)** | Una etiqueta de sentimiento (positivo, neutral o negativo) con una probabilidad |
| Datos que requiere | Empresa, indicador, valor, nivel de riesgo y una instrucción con el nivel del usuario. Estos datos **salen del servidor propio** hacia el proveedor | Los mismos datos de entrada, que **permanecen en el servidor propio** | Una frase en inglés con terminología financiera que el sistema arma a partir del indicador |
| Disponibilidad y acceso | API externa con clave gratuita y límites de uso por minuto y por día; si la API cae o se excede la cuota, no está disponible | Pesos de modelos de código abierto que se descargan y ejecutan en hardware propio; la licencia de cada modelo es **(verificar)** | Modelo preentrenado de acceso abierto; exige instalar `transformers` y `torch` y descargar el modelo **(verificar tamaño y licencia)** |
| Restricciones del contexto | Dependencia de un proveedor; salida variable ante la misma entrada; puede contradecir el dato | Exige memoria y capacidad de cálculo en el servidor; el tiempo de respuesta debe cumplir el límite de 5 s (RNF-01.1) **(verificar)** | No genera texto; fue entrenado para sentimiento, no para explicar un indicador en español |
| Adaptación al nivel del usuario | Alta, mediante la instrucción | Posible por instrucción; el desempeño no se midió en este proyecto | No aplica |
| Evidencia en la literatura | Resúmenes comprensibles a partir de datos de mercado (Lazarev y Sedov, 2024) | Evaluación de SLM de código abierto para preguntas financieras de personas y estudiantes (Kosireddy et al., 2024) | Rendimiento superior en tareas financieras frente a modelos generales (Huang et al., 2023); vigencia reciente (Baghavathi Priya et al., 2025) |
| Estado en el proyecto | **Implementado** (`src/nlp/llm_explainer.py`) | **No implementado** | **Implementado**, opcional y desactivado por defecto |

*Fuente: elaboración propia a partir del código del proyecto (`src/nlp/`), la documentación de los proveedores y las referencias indicadas.*

## Análisis por técnica

**A. LLM en la nube.** Los modelos de lenguaje de gran escala pueden transformar datos de mercado en resúmenes comprensibles (Lazarev y Sedov, 2024). Las revisiones indican que la mayoría de sus aplicaciones en finanzas se orientan a profesionales (Li et al., 2023) y que la explicabilidad dirigida a usuarios no expertos está poco desarrollada (Martins et al., 2024). Para este proyecto es la técnica que permite ajustar vocabulario y extensión al nivel del usuario. Su acceso es sencillo, pero depende de un tercero: la documentación de Groq indica planes *Free* y *Developer*, con límites medidos en solicitudes y tokens por minuto y por día, y un error 429 al superarlos. La página consultada no informa el costo del plan gratuito, por lo que no se afirma un costo por consulta **(verificar la cuota vigente en console.groq.com)**.

**B. SLM local.** Kosireddy et al. (2024) definen los modelos pequeños como los de menos de tres mil millones de parámetros y evalúan varios de código abierto (OpenELM, Phi, Gemma y TinyLlama) para responder preguntas financieras, midiendo uso de memoria, tiempo de inferencia, similitud con la respuesta correcta y legibilidad. Señalan que pueden ejecutarse en hardware más accesible y preservar la privacidad del usuario, y concluyen que algunos merecen más exploración mientras que otros pueden tener límites. Su ventaja para este proyecto sería que los datos no salen del servidor y que no hay cuota de terceros. Sus riesgos son la calidad en español, que no está documentada en la fuente consultada, y el costo de operar el modelo. El estudio no compara estos modelos con modelos grandes, por lo que **no se puede afirmar que rindan más o menos que la técnica A**.

**C. FinBERT.** Es un modelo de la familia BERT preentrenado con textos financieros, útil para clasificar sentimiento (Huang et al., 2023; Baghavathi Priya et al., 2025). Su salida es una etiqueta, no un texto, así que no resuelve por sí solo el problema de explicar. El proyecto lo usa como una señal opcional que muestra una insignia de sentimiento y no interviene en la redacción. El modelo que carga el código es `ProsusAI/finbert`; el estudio de Huang et al. (2023) describe otro modelo con el mismo nombre, por lo que ambos no deben confundirse. **(verificar el idioma, el corpus y la licencia de `ProsusAI/finbert` en su ficha; no se pudo abrir durante la redacción)**

## Línea base sin IA: plantillas con reglas

Cada indicador y nivel tiene tres redacciones preescritas con huecos para el dato. Son exactas, porque el valor se inserta sin modificarlo, y reproducibles, pero no se ajustan a contextos que no previeron. No se consideran una técnica de IA porque no hay aprendizaje. En el sistema cumplen dos funciones: son el punto de comparación para saber qué aporta la IA y son el respaldo cuando el modelo falla o su texto no pasa la validación.

## Síntesis

Las tres técnicas de IA cubren partes distintas del problema. El LLM en la nube genera el texto y permite adaptar el nivel, a cambio de depender de un tercero y de poder contradecir el dato. El SLM local ofrece más control sobre los datos y la disponibilidad, pero su calidad en español y su desempeño en esta tarea no están demostrados. FinBERT no genera texto y solo aporta una etiqueta. La selección y su justificación se desarrollan en el apartado C8.

## Referencias de este apartado

Las citas corresponden a la bibliografía que ya tiene el informe: Baghavathi Priya et al. (2025), Huang et al. (2023), Kosireddy et al. (2024), Lazarev y Sedov (2024), Li et al. (2023) y Martins et al. (2024). Antes de entregar, agrega DOI o URL a Li et al. (2023), que no los tiene.
