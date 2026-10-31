# Selección y justificación de la técnica de IA (C8)

> **Borrador.** Reescríbelo con tus palabras y declara el uso de la herramienta antes de llevarlo al informe. Lo marcado **(verificar)** o **pendiente** no está confirmado.

## Técnica seleccionada

La técnica de IA seleccionada es un **modelo de lenguaje de gran escala (LLM) en la nube**: el identificador en el código es `qwen/qwen3.8-27b`, servido por Groq. Redacta cada explicación según el nivel del usuario.

**(verificar en la consola de Groq que el identificador `qwen/qwen3.8-27b` existe y copiarlo exacto al informe; en otros documentos aparece como "Qwen3")**

## Qué parte del sistema es IA y qué parte no

| Componente | ¿Es IA? | Función |
|---|---|---|
| LLM en la nube (Qwen vía Groq) | **Sí** | Redacta la explicación |
| FinBERT (`ProsusAI/finbert`) | **Sí**, opcional y desactivado por defecto | Etiqueta de sentimiento; no redacta |
| Cálculo de indicadores (RSI, MACD, medias móviles, bandas de Bollinger) | No: fórmulas matemáticas | Obtener el valor y el nivel de riesgo |
| Validación de coherencia (`validate_coherence`) | No: reglas fijas | Comprobar que el texto no contradiga el dato |
| Plantillas con reglas | No: textos preescritos | Respaldo cuando el LLM falla o su texto no pasa la validación |

El sistema es **híbrido**: la IA genera el texto y los componentes deterministas lo controlan. Esto responde al riesgo central de la técnica seleccionada, que es poder contradecir el dato.

## Criterios de selección

Los criterios derivan de los requerimientos del proyecto:

| Criterio | Requerimiento | Qué se exige |
|---|---|---|
| Exactitud con el dato | RF-04.2 | El texto no puede contradecir el valor ni la categoría del indicador |
| Adaptación al nivel | RF-05.2, RF-13.2 | El vocabulario y la extensión cambian según el nivel del usuario |
| Legibilidad y extensión | RNF-04.1, RNF-04.2 | Texto accesible y de hasta 150 palabras |
| Tolerancia a fallos | RNF-09 | Si una dependencia externa cae, el sistema sigue respondiendo |
| Privacidad de los datos | RNF-05 | No exponer datos personales a terceros |
| Factibilidad | Alcance | Sin presupuesto, con datos públicos y desarrollo individual |

## Valoración de las técnicas frente a los criterios

Valoración cualitativa basada en la comparación del apartado C7. No es una medición: ninguna técnica se probó en las mismas condiciones.

| Criterio | A. LLM en la nube | B. SLM local | C. FinBERT |
|---|---|---|---|
| Genera la explicación | Sí | Sí | **No** |
| Adaptación al nivel | Sí, por instrucción | Posible; no medido | **No** |
| Exactitud con el dato | Requiere control externo | Requiere control externo | No aplica |
| Privacidad de los datos de entrada | Salen al proveedor (solo empresa, indicador, valor y riesgo) | Permanecen en el servidor | No aplica |
| Facilidad de acceso | Alta: clave gratuita y sin hardware propio | Media: descargar modelos y operar hardware **(verificar)** | Media: instalar librerías y modelo |
| Calidad en español | No medida | **No documentada** | No aplica |
| Evidencia en el proyecto | Implementado, probado con respuestas simuladas | **Ninguna** | Implementado, opcional |

## Justificación

Solo las técnicas A y B generan el texto, y solo ellas permiten ajustarlo al nivel; FinBERT no cumple esos dos criterios. Entre A y B, se eligió A por su **facilidad de acceso**: no exige hardware propio ni operar un modelo, lo que se ajusta a un prototipo individual sin presupuesto. No se eligió B porque no hay en este proyecto evidencia de su calidad en español ni de que cumpla el límite de 5 s de RNF-01.1, y porque implementarla habría requerido un trabajo de evaluación que el alcance no contemplaba. **Esta decisión se basó en la facilidad de implementación y en el análisis de la literatura, no en una prueba comparativa entre ambas técnicas.**

El costo de A es el primer criterio, la exactitud, y por eso el diseño no confía en el modelo sino que lo rodea de controles:

1. El pedido al modelo incluye solo los datos necesarios y exige citar el valor y la etiqueta de riesgo.
2. El texto se recorta al máximo de palabras del nivel.
3. Se acepta únicamente si contiene la etiqueta de riesgo, el valor, ningún término prohibido del nivel y si además pasa `validate_coherence`.
4. En cualquier otro caso, o ante un error de la API, se usa una plantilla, que es coherente por construcción.

El flujo está en `src/nlp/explainer.py` (`generate_explanation`).

## Datos y fuentes necesarios

| Dato | Fuente | Uso |
|---|---|---|
| Precios históricos diarios | Yahoo Finance (`yfinance`), con Alpha Vantage de respaldo | Calcular los cuatro indicadores |
| Indicadores macro (UF, dólar, TPM, IPC) | mindicador.cl | Cinta de precios |
| Noticias | Google News RSS | Portada |
| Valor, riesgo, empresa e indicador | Calculados por el sistema | Entrada del LLM |
| Nivel del usuario | Experiencia declarada y comportamiento (regeneraciones) | Instrucción del LLM |

El detalle de datos, preprocesamiento y privacidad está en C11.

## Riesgos y mitigación

| Riesgo | Tipo | Mitigación implementada | Evidencia | Brecha restante |
|---|---|---|---|---|
| El texto contradice el dato (alucinación) | Daño | `validate_coherence` antes de aceptar el texto; si falla, plantilla | `src/nlp/explainer.py`; prueba `test_llm_text_contradicting_the_data_falls_back_to_templates` | El validador solo cubre riesgo, valor y las categorías de los cuatro indicadores; una afirmación falsa sobre otro tema no se detecta |
| El texto se lee como recomendación de inversión | Daño y ética | El rol del modelo prohíbe aconsejar (`_BASE_ROLE`); pie de página "No constituye asesoría de inversión" | `src/nlp/llm_explainer.py`; `src/web/templates/base.html` | No hay verificación automática de que el modelo no aconseje |
| Lenguaje demasiado técnico para un principiante | Sesgo de audiencia | La ficha del nivel básico define términos prohibidos; si el texto los usa, se descarta. Los niveles intermedio y avanzado no tienen lista de términos prohibidos | `src/nlp/levels.py`; prueba `test_llm_output_with_jargon_falls_back_to_basico_templates` | La lista es finita y solo existe en el nivel básico |
| Respuestas distintas ante la misma entrada | Factibilidad | Validación determinista del resultado, no del proceso | `temperature = 0,7` en `llm_explainer.py` | No se midió la variabilidad con el modelo real |
| Caída, cuota o clave inválida de Groq | Factibilidad | Cualquier error cae a plantillas | `src/nlp/explainer.py` | El error se oculta, no hay conteo de cuántas veces se usa el respaldo y la llamada no define un tiempo límite propio, por lo que una respuesta lenta puede acercarse al límite de 5 s de RNF-01.1 |
| Los datos de entrada salen a un tercero | Privacidad | Solo viajan empresa, indicador, valor, riesgo y nivel; no se envían correo, usuario ni sesión | `_build_llm_prompt` en `src/nlp/llm_explainer.py` | Aun así, las consultas quedan sujetas a los términos del proveedor **(verificar)** |
| El usuario no sabe que el texto lo escribe una IA | Ética | Ninguna | — | **La interfaz no lo indica.** Brecha reconocida |
| Dependencia de un proveedor | Factibilidad | La aplicación funciona sin el LLM | `USE_LLM=false` por defecto | Sin LLM la adaptación se limita a las variantes preescritas |

### Sobre el sesgo

El proyecto no entrena un modelo, así que no introduce sesgo de datos propio. Los sesgos relevantes son los de los modelos preentrenados, que no se auditaron, y el de idioma: se verificó que el sistema arma para FinBERT una frase en inglés, mientras que las plantillas y el LLM trabajan en español **(verificar el idioma y el corpus de `ProsusAI/finbert` en su ficha; no se pudo abrir durante la redacción)**. El diseño mitiga el riesgo con la validación contra el dato, no con una corrección del sesgo.

## Lo que no se midió

- El comportamiento del LLM real: las pruebas simulan su respuesta. Nunca se ejecutó el sistema con `USE_LLM=true` contra la API.
- El desempeño de un SLM local: no se implementó ni se probó.
- La adaptación al nivel con usuarios: no hay datos de comprensión (ver ADR 0007).

## Referencias de este apartado

Huang et al. (2023), Baghavathi Priya et al. (2025), Kosireddy et al. (2024), Lazarev y Sedov (2024), Li et al. (2023) y Martins et al. (2024), ya presentes en la bibliografía del informe.
