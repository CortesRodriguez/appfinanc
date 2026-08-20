# Guía profesional de diseño — Proyecto de título

**Proyecto:** Aplicación web con IA que traduce indicadores técnicos financieros (media móvil, RSI, etc.) a lenguaje comprensible para usuarios principiantes.
**Stack declarado:** Flask (Python), patrón MVC.

## Cómo usar esta guía

Sigue las fases en orden. Cada una es el insumo de la siguiente — si saltas una, la que viene después queda "colgando" (ese es el origen del spaghetti que sentías). Al final hay una sección de estándares ISO que puedes citar en tu marco teórico para justificar por qué hiciste las cosas como las hiciste, y un checklist para la defensa.

---

## Fase 1 — Fundamentos del proyecto

- **Problema y justificación**: qué dolor real resuelves (usuarios principiantes no entienden indicadores técnicos y por eso no pueden usarlos para decidir).
- **Objetivo general** (uno) y **objetivos específicos** (3-5, medibles, cada uno debería poder mapearse después a un requerimiento o un capítulo de resultados).
- **Alcance**: qué indicadores vas a cubrir (media móvil, RSI, ¿MACD, Bandas de Bollinger?), qué NO vas a cubrir (trading automático, recomendaciones de compra/venta, múltiples mercados).
- **Metodología de desarrollo**: declara una (Incremental, Cascada, o una adaptación simplificada de Scrum para trabajo individual). Esto lo vas a justificar citando **ISO/IEC/IEEE 12207** (ciclo de vida del software) — le da peso académico a tu elección.

---

## Fase 2 — Requerimientos

**Requerimientos funcionales (RF):** qué hace el sistema. Ejemplo de granularidad: "El sistema debe calcular el RSI de un activo a partir de datos históricos" / "El sistema debe generar una explicación en lenguaje simple del resultado del RSI calculado".

**Requerimientos no funcionales (RNF):** en tu proyecto pesan bastante porque el valor central es la experiencia para un principiante. Categorías a cubrir, apoyándote en el modelo de calidad **ISO/IEC 25010**:

| Característica ISO 25010 | Aplicación en tu proyecto |
|---|---|
| Adecuación funcional | ¿Cubre los indicadores que promete? |
| Usabilidad | Lenguaje simple, sin jerga financiera — tu diferenciador |
| Fiabilidad | La traducción de la IA no debe contradecir el dato numérico real |
| Eficiencia de desempeño | Tiempo de respuesta al calcular/traducir un indicador |
| Seguridad | Si guardas datos del usuario (portafolio, preferencias), cómo los proteges |
| Mantenibilidad | Que el código permita agregar un indicador nuevo sin reescribir todo |
| Portabilidad | Si corre en distintos navegadores/dispositivos |
| Compatibilidad | Integración con la API de datos financieros que elijas |

No necesitas cubrir las 8 a fondo, pero elige las 4-5 relevantes y redacta un RNF por cada una. El estándar de referencia para todo este proceso de levantamiento es **ISO/IEC/IEEE 29148** (ingeniería de requisitos) — cítalo cuando expliques tu metodología de levantamiento.

---

## Fase 3 — Casos de uso

1. **Identifica actores**: usuario principiante (el principal), quizás un actor "sistema externo" (API de datos financieros) si usas notación extendida.
2. **Diagrama de casos de uso simple** primero: actor + óvalos + relaciones `<<include>>` / `<<extend>>`. Esto es tu mapa general.
3. **Casos de uso extendidos**: la versión detallada que pide tu profesor, uno por cada caso relevante. Formato típico:

| Campo | Contenido |
|---|---|
| Nombre | Ej: "Consultar indicador RSI" |
| Actor(es) | Usuario principiante |
| Precondición | Usuario ha ingresado un ticker válido |
| Flujo principal | Pasos numerados del camino feliz |
| Flujos alternos | Ticker inválido, sin datos históricos suficientes, error de API externa |
| Postcondición | Se muestra el indicador + su traducción en lenguaje simple |

Este documento es el que después vas a usar directamente para armar el diagrama de secuencia de ese mismo caso.

---

## Fase 4 — Modelo de datos

- **Modelo conceptual**: entidades principales y sus relaciones (ej: Usuario, Activo, Indicador, Consulta/Historial).
- **Modelo lógico**: atributos de cada entidad, tipos generales, cardinalidades.
- **Modelo físico**: el que pide tu profesor. Motor de BD elegido (PostgreSQL, MySQL, SQLite), tablas con tipos de dato exactos, llaves primarias/foráneas, índices si aplica.

---

## Fase 5 — Arquitectura de software

- **Patrón arquitectónico (MVC)**: justifícalo, pero ten ojo con un detalle que suele preguntar la comisión — **Flask no impone MVC de forma nativa** (a diferencia de Django). Tienes que explicar cómo tú *mapeaste* MVC sobre Flask:
  - Model → tus clases SQLAlchemy
  - View → tus templates (Jinja2) o las respuestas JSON si es una API
  - Controller → tus funciones de ruta (`@app.route`), idealmente separadas en Blueprints
- **Application Factory pattern**: patrón recomendado en Flask para crear la app (`create_app()`), útil para testing y para organizar configuración. Vale la pena mencionarlo como decisión de diseño.
- **Blueprints**: cómo organizas módulos (ej: blueprint de indicadores, blueprint de usuarios) — esto es lo que después se refleja en tu diagrama de componentes.
- **Dónde vive el módulo de IA**: decisión arquitectónica clave. ¿Es un módulo interno que llama a una API externa de IA (OpenAI, Anthropic, Gemini) para generar la traducción en lenguaje simple? ¿O es un modelo/reglas propias? Esto determina si tu diagrama de componentes tiene una "caja externa" con la que te integras vía API, o todo es interno.
- **Diagrama de componentes**: con lo anterior ya resuelto, este diagrama debería salir solo — módulos internos (rutas, servicios, acceso a datos) + integraciones externas (API de datos financieros, API de IA).
- **Diagrama de despliegue** (opcional pero suma puntos): dónde corre cada pieza — servidor Flask, base de datos, servicios externos.

---

## Fase 6 — Patrones de diseño a nivel de código

Estos son patrones más finos que MVC, a nivel de cómo organizas las clases dentro de cada capa. No necesitas usarlos todos — elige los que realmente resuelven un problema en tu proyecto:

| Patrón | Para qué te sirve en este proyecto |
|---|---|
| Service Layer | Sacar la lógica de negocio (cálculo de indicadores, orquestación con la IA) fuera de las funciones de ruta |
| Repository | Abstraer el acceso a la base de datos, para no acoplar tu lógica a SQLAlchemy directamente |
| DTO (Data Transfer Object) | Pasar datos limpios entre capas sin exponer el modelo de BD completo |
| Adapter | Envolver la API externa de IA y la API de datos financieros, para poder cambiar de proveedor sin tocar el resto del sistema |
| Strategy | Si cada indicador (media móvil, RSI, etc.) tiene una lógica de cálculo distinta, cada uno puede ser una "estrategia" intercambiable |
| Factory | Instanciar el "traductor" o el "calculador" correcto según el indicador solicitado |

Este es exactamente el tipo de contenido que impresiona en una defensa: mostrar que no solo elegiste MVC porque "es lo que se enseña", sino que resolviste problemas concretos con patrones concretos.

---

## Fase 7 — Diagramas de secuencia

Con los insumos de las Fases 3, 4 y 5 ya resueltos, arma un diagrama de secuencia por cada caso de uso relevante (no todos, prioriza los 3-4 más importantes). Cada lifeline del diagrama debería corresponder a un componente real de tu Fase 5, y cada mensaje de datos debería ser consistente con tu modelo físico de la Fase 4.

---

## Fase 8 — Diagrama de clases

Opcional pero recomendado: muestra tus clases de dominio (Indicador, Activo, Usuario) y sus relaciones, coherente con el modelo de datos. Si usaste Strategy o Adapter en la Fase 6, este es el diagrama donde se ve reflejado.

---

## Fase 9 — Selección y justificación del stack tecnológico

Para cada elección, ten lista una razón técnica (no solo "porque lo conozco"):

- **Backend**: Flask — liviano, buena integración con librerías de Python para IA/datos.
- **IA**: API externa vs. modelo propio — justifica costo, tiempo de desarrollo, precisión.
- **Fuente de datos financieros**: qué API (Yahoo Finance, Alpha Vantage, etc.), límites de uso, confiabilidad.
- **Base de datos**: motor elegido y por qué (relacional tiene sentido dado que tus datos son estructurados).
- **Frontend**: HTML/CSS/JS plano, o algún framework — justifica según tu nivel de experiencia y el tiempo disponible.

---

## Fase 10 — Pruebas y validación

- **Pruebas unitarias** (pytest): sobre todo en el cálculo de indicadores — ahí no puedes fallar, es matemática verificable.
- **Pruebas de integración**: flujo completo desde la consulta hasta la respuesta traducida.
- **Validación de usabilidad con usuarios principiantes**: dado que tu propuesta de valor ES la comprensión para principiantes, una validación cualitativa (aunque sea con 5-8 personas) es evidencia fuerte para tu memoria — muestra que mediste tu objetivo principal, no solo que "el código corre".

---

## Fase 11 — Mapeo a los capítulos de la memoria

| Fase de esta guía | Típicamente va en |
|---|---|
| 1, 2 | Introducción / Planteamiento del problema |
| 2 (marco de calidad) | Marco teórico |
| 3, 4, 5, 6, 7, 8 | Diseño / Desarrollo de la solución |
| 9 | Diseño / Tecnologías utilizadas |
| 10 | Resultados / Validación |
| 11 (esta tabla) | — (uso interno, no va en la memoria) |

---

## Estándares ISO que puedes citar

- **ISO/IEC/IEEE 12207** — Procesos del ciclo de vida del software. Justifica tu metodología de desarrollo.
- **ISO/IEC 25010** — Modelo de calidad de producto de software. Justifica tus RNF.
- **ISO/IEC/IEEE 29148** — Ingeniería de requisitos. Justifica cómo levantaste RF/RNF.
- **Principios de seguridad de la información** (referencia general a familia ISO/IEC 27000) — si tu app guarda datos del usuario, aunque sea básicos, mencionar principios de confidencialidad/integridad suma puntos, especialmente viniendo de tu experiencia en seguridad SAP.

---

## Checklist rápido para la defensa

- [ ] ¿Puedo explicar por qué elegí MVC y cómo lo mapeé a Flask específicamente?
- [ ] ¿Puedo explicar qué patrón de diseño resuelve qué problema concreto (no solo nombrarlos)?
- [ ] ¿Mis RNF están conectados a características ISO 25010 concretas?
- [ ] ¿Mis diagramas de secuencia usan los mismos nombres de componentes que mi diagrama de componentes?
- [ ] ¿Tengo evidencia de validación con usuarios reales, no solo pruebas técnicas?
