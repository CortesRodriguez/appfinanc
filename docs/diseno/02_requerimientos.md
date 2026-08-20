# Fase 2 — Requerimientos

Los requerimientos están organizados en dos grandes bloques: **requerimientos funcionales (RF)**, agrupados por módulo del sistema, y **requerimientos no funcionales (RNF)**, agrupados por atributo de calidad. Cada requerimiento tiene un identificador único, una descripción verificable y una prioridad (Alta / Media / Baja) que refleja su criticidad para el prototipo.

La trazabilidad hacia los casos de uso extendidos (Fase 3) y hacia las pruebas (Fase 10) se resume al final del documento.

## Requerimientos funcionales

### Módulo Extractor

#### RF-01 — Selección de instrumento y parámetros de consulta · Prioridad: Alta
- **RF-01.1**: El sistema debe permitir seleccionar, desde un listado predefinido, una de las 30 empresas que componen el índice IPSA (Índice de Precios Selectivo de Acciones) de la Bolsa de Santiago, y seleccionar uno de los siguientes rangos temporales para visualizar el gráfico de precios: 1 mes, 3 meses, 6 meses o 1 año.

#### RF-02 — Extracción de indicadores financieros · Prioridad: Alta
- **RF-02.1**: El sistema debe extraer los indicadores RSI, medias móviles, MACD y Bandas de Bollinger desde Yahoo Finance API o Alpha Vantage para el instrumento seleccionado.
- **RF-02.2**: El sistema debe registrar la fecha, hora y fuente de datos (Yahoo Finance o Alpha Vantage) de cada indicador extraído, con fines de trazabilidad.
- **RF-02.3**: El sistema debe extraer los valores de UF, dólar observado, TPM e IPC desde la API pública del Banco Central de Chile (mindicador.cl).

#### RF-03 — Actualización, validación y normalización de datos · Prioridad: Media
- **RF-03.1**: El sistema debe actualizar los indicadores extraídos de forma periódica, respetando los límites de consulta (rate limits) de la API utilizada.
- **RF-03.2**: El sistema debe validar el formato y el rango numérico de cada indicador antes de entregarlo al módulo Procesador NLP.
- **RF-03.3**: El sistema debe normalizar los indicadores extraídos a una estructura de datos interna común, independiente de la API de origen.

### Módulo Procesador NLP

#### RF-04 — Procesamiento de indicadores mediante modelo de lenguaje · Prioridad: Alta
- **RF-04.1**: El sistema debe procesar cada indicador extraído mediante un modelo de lenguaje preentrenado (FinBERT).
- **RF-04.2**: El sistema debe incorporar reglas de validación financiera que contrasten el contenido generado con el valor real del indicador, para mitigar alucinaciones del modelo. El sistema debe verificar que la categoría cualitativa utilizada en la explicación corresponda a los umbrales reales definidos para cada indicador:
  - **RSI**: sobrecomprado si RSI > 70, sobrevendido si RSI < 30.
  - **%B de Bandas de Bollinger**: sobrecomprado si %B > 1, sobrevendido si %B < 0.
  - **MACD**: señal alcista si la línea MACD supera a la línea de señal, bajista en caso contrario.
  - **Medias móviles**: tendencia alcista si MA20 > MA50, bajista en caso contrario.

#### RF-05 — Generación de explicaciones en lenguaje natural · Prioridad: Alta
- **RF-05.1**: El sistema debe generar una explicación comprensible para cada indicador, evitando terminología técnica no explicada.
- **RF-05.2**: El sistema debe adaptar el nivel de detalle de la explicación al perfil de usuario no experto.

#### RF-06 — Clasificación de riesgo y regeneración de explicaciones · Prioridad: Media
- **RF-06.1**: El sistema debe clasificar el nivel de riesgo relativo del indicador procesado en una de tres categorías (bajo, medio, alto).
- **RF-06.2**: El sistema debe permitir la regeneración de una explicación cuando el usuario indique que la primera versión no fue comprendida.

### Módulo Presentador

#### RF-07 — Interfaz web de consulta · Prioridad: Alta
- **RF-07.1**: El sistema debe presentar las explicaciones generadas mediante una interfaz web desarrollada en Flask.
- **RF-07.2**: El sistema debe permitir seleccionar, desde una lista predefinida, el indicador financiero específico que se desea consultar.
- **RF-07.3**: El sistema debe mostrar una cinta de precios en una barra fija en la parte superior de la interfaz, visible en todas las vistas de la aplicación, desplazándose mediante scroll horizontal continuo y pausándose mientras el cursor del usuario permanezca sobre ella.
- **RF-07.4**: La cinta de precios debe mostrar, en el siguiente orden, el IPSA, la UF, el Dólar Observado, la TPM y el IPC, seguidos de las 30 acciones que componen el IPSA con su variación porcentual diaria en verde (variación positiva) o rojo (variación negativa).

#### RF-08 — Presentación de resultados · Prioridad: Alta
- **RF-08.1**: El sistema debe mostrar, junto a cada explicación, el valor numérico del indicador financiero original del cual fue derivada.
- **RF-08.2**: El sistema debe mostrar una etiqueta de color (verde para riesgo bajo, amarillo para riesgo medio, rojo para riesgo alto) acompañada de un ícono distintivo para cada categoría, de modo que el nivel de riesgo no dependa únicamente del color.
- **RF-08.3**: El sistema debe mostrar un indicador de carga (spinner) con el mensaje "Generando explicación…" mientras se procesa la solicitud. Si el tiempo de espera supera el umbral definido en RNF-01.1, el sistema debe presentar el mensaje de error definido en RF-09.1.

#### RF-09 — Manejo de errores y apoyo al usuario · Prioridad: Media
- **RF-09.1**: El sistema debe presentar un mensaje de error que evite terminología técnica y códigos HTTP, describa brevemente lo ocurrido y sugiera una acción concreta al usuario (por ejemplo, reintentar en unos minutos), activado luego de agotar los reintentos definidos en RNF-09.2.
- **RF-09.2**: El sistema debe permitir al usuario acceder a un glosario simplificado de términos financieros desde la interfaz principal.

#### RF-10 — Historial de consultas · Prioridad: Baja
- **RF-10.1**: El sistema debe permitir al usuario visualizar el historial de las últimas 5 consultas realizadas durante la sesión activa, mostrando instrumento, indicador y fecha/hora de cada una.

### Módulo de Autenticación y Perfil

#### RF-11 — Registro de usuario · Prioridad: Alta
- **RF-11.1**: El sistema debe permitir a los usuarios registrarse utilizando nombre de usuario, correo electrónico y contraseña, validando que el correo no esté previamente registrado y encriptando la contraseña mediante Flask-Bcrypt antes de almacenarla.

#### RF-12 — Autenticación de usuario · Prioridad: Alta
- **RF-12.1**: El sistema debe permitir a los usuarios iniciar sesión con correo electrónico y contraseña, generando un token de sesión mediante Flask-JWT-Extended tras una autenticación exitosa, y cerrar sesión invalidando dicho token.

#### RF-13 — Perfil adaptativo de aprendizaje · Prioridad: Alta
- **RF-13.1**: El sistema debe asociar el perfil de aprendizaje del usuario a su cuenta y recuperarlo al iniciar sesión desde cualquier dispositivo.
- **RF-13.2**: El sistema debe ajustar el nivel de detalle de las explicaciones generadas en función del perfil de aprendizaje del usuario.

#### RF-14 — Resumen personalizado de perfil de aprendizaje · Prioridad: Media
- **RF-14.1**: El sistema debe mostrar el indicador con mayor número de solicitudes de regeneración de explicación.
- **RF-14.2**: El sistema debe mostrar los instrumentos financieros más consultados por el usuario.
- **RF-14.3**: El sistema debe mostrar el número total de consultas realizadas desde la creación de la cuenta.
- **RF-14.4**: El sistema debe presentar, junto al indicador identificado en RF-14.1, una explicación generada por el Procesador NLP ajustada al nivel de detalle del usuario (RF-13.2).
- **RF-14.5**: El sistema debe reutilizar la última explicación generada para ese indicador y usuario en lugar de regenerarla en cada visita al perfil, salvo solicitud explícita del usuario.

## Requerimientos no funcionales

### Desempeño y escalabilidad

#### RNF-01 — Tiempo de respuesta · Prioridad: Alta
- **RNF-01.1**: El sistema debe generar una explicación en lenguaje natural en un tiempo no superior a 5 segundos por indicador, en condiciones normales de operación.
- **RNF-01.2**: El sistema debe registrar el tiempo de procesamiento empleado por el modelo de NLP para cada explicación generada, con fines de monitoreo de desempeño.

#### RNF-02 — Capacidad y uso de recursos · Prioridad: Media
- **RNF-02.1**: El sistema debe soportar la interacción simultánea de al menos 5 usuarios durante la etapa de validación.
- **RNF-02.2**: El sistema debe almacenar en caché los indicadores extraídos durante la sesión de consulta, evitando solicitudes repetidas a la API para el mismo instrumento dentro de un intervalo de 5 minutos.

### Usabilidad y accesibilidad

#### RNF-03 — Diseño de interfaz · Prioridad: Alta
- **RNF-03.1**: La interfaz debe presentar un diseño simple y una navegación intuitiva, adecuada para usuarios sin conocimientos financieros previos.
- **RNF-03.2**: La interfaz debe adaptarse a dispositivos móviles y de escritorio (diseño responsivo).

#### RNF-04 — Legibilidad de las explicaciones · Prioridad: Alta
- **RNF-04.1**: Las explicaciones generadas deben alcanzar un nivel de legibilidad accesible, medido mediante un test de legibilidad estándar (Flesch-Kincaid adaptado al español), consistente con el marco teórico revisado (Kosireddy et al., 2024).
- **RNF-04.2**: Cada explicación generada debe tener una extensión máxima de 150 palabras.

### Seguridad y privacidad de datos

#### RNF-05 — Anonimización de datos de evaluación · Prioridad: Alta
- **RNF-05.1**: Los datos de los usuarios participantes en la evaluación deben almacenarse de forma anónima, sin asociar respuestas a información personal identificable.
- **RNF-05.2**: Las respuestas de las encuestas pre-test y post-test deben almacenarse de forma anonimizada, sin asociarlas a información personal identificable, independientemente de la cuenta de usuario con la que se haya iniciado sesión.

#### RNF-06 — Seguridad de credenciales y sesión · Prioridad: Alta
- **RNF-06.1**: Las contraseñas de los usuarios deben almacenarse encriptadas mediante Flask-Bcrypt, con un largo mínimo de 8 caracteres.
- **RNF-06.2**: Los tokens de sesión generados mediante Flask-JWT-Extended deben expirar transcurridas 24 horas desde su emisión.

### Mantenibilidad

#### RNF-07 — Organización modular del código · Prioridad: Media
- **RNF-07.1**: El código del sistema debe estar documentado y organizado de forma modular (extracción, procesamiento, presentación, evaluación), facilitando su mantenimiento y extensión futura.

### Disponibilidad y confiabilidad de datos

#### RNF-08 — Naturaleza de los datos financieros · Prioridad: Media
- **RNF-08.1**: El sistema debe operar con datos financieros históricos y en tiempo diferido, dado que el acceso a datos en tiempo real excede el alcance definido para el prototipo académico.

#### RNF-09 — Tolerancia a fallos de conexión · Prioridad: Alta
- **RNF-09.1**: El sistema debe manejar adecuadamente errores de conexión o falta de respuesta de las APIs financieras externas, informando al usuario en caso de fallo en la obtención de datos.
- **RNF-09.2**: El sistema debe reintentar automáticamente la solicitud a la API financiera hasta 3 veces ante una falla de conexión, antes de reportar el error al usuario.

## Trazabilidad — Módulo → RF → CU

Los casos de uso (CU) están detallados en la Fase 3. Esta tabla resume qué RF cubre cada módulo y a qué CUs se conecta.

| Módulo | RF | Casos de uso principales |
|---|---|---|
| Extractor | RF-01, RF-02, RF-03 | CU-01, CU-02, CU-03, CU-04, CU-05, CU-06, CU-07 |
| Procesador NLP | RF-04, RF-05, RF-06 | CU-08, CU-09, CU-10, CU-11, CU-12, CU-13 |
| Presentador | RF-07, RF-08, RF-09, RF-10 | CU-14, CU-15, CU-16, CU-17, CU-18, CU-19, CU-20, CU-21, CU-22, CU-23 |
| Autenticación y Perfil | RF-11, RF-12, RF-13, RF-14 | CU-24, CU-25, CU-26, CU-27, CU-28, CU-29, CU-30, CU-31, CU-32 |

## Trazabilidad — RNF → mecanismo de verificación

| RNF | Mecanismo de verificación |
|---|---|
| RNF-01.1 | Medición del tiempo de respuesta en pruebas de integración; RNF-01.2 registra `processing_time_ms` en cada consulta. |
| RNF-02.1 | Prueba de concurrencia (`tests/test_concurrency.py`). |
| RNF-02.2 | Caché en memoria con TTL de 5 minutos (implementado en el módulo Extractor). |
| RNF-03 | Revisión de usabilidad y responsividad en dispositivos móviles/escritorio durante la validación con usuarios. |
| RNF-04.1 | Cálculo automático del índice Flesch-Huerta (adaptación al español) en el flujo de generación de la explicación. |
| RNF-04.2 | Truncamiento por número de palabras en la generación. |
| RNF-05 | Diseño del esquema de base de datos con separación estricta entre datos identificables y datos de evaluación. |
| RNF-06 | Uso de Flask-Bcrypt y Flask-JWT-Extended; validación de largo mínimo en el registro. |
| RNF-07 | Estructura por paquetes (`src/extractor/`, `src/nlp/`, `src/web/`, etc.) y suite de pruebas por módulo. |
| RNF-08 | Diseño explícito del sistema sin llamadas en tiempo real; cachés de 5 min. |
| RNF-09 | Política de reintentos en `src/extractor/sources.py` y fallback Yahoo → Alpha Vantage. |
