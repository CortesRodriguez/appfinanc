# Registro de decisiones arquitectónicas (ADR)

Formato: la plantilla de Michael Nygard (2011), una de las listadas en https://adr.github.io/adr-templates/. Cada ADR tiene cinco secciones: título, Status, Context, Decision y Consequences. Nygard no incluye una sección de alternativas, así que las opciones descartadas y sus costos se describen dentro de Context y Consequences. Plantilla: [0000-plantilla.md](0000-plantilla.md).

El conjunto de ADR del proyecto es su *decision log*. Varios ADR se redactaron después de tomada la decisión y lo indican en Status ("registrada a posteriori"); no se escribieron con las alternativas a la vista.

| N.º | Decisión | Status |
|---|---|---|
| [0001](0001-monolito-modular.md) | Monolito modular en Flask | Aceptada (a posteriori) |
| [0002](0002-llm-con-fallback-y-validacion.md) | Explicaciones con LLM, plantillas de respaldo y validación de coherencia | Aceptada (2026-10-28) |
| [0003](0003-niveles-adaptativos.md) | Niveles adaptativos con ficha declarativa | Aceptada como heurística, sin validación empírica (a posteriori) |
| [0004](0004-postgresql-como-motor.md) | PostgreSQL como único motor de base de datos | Aceptada (2026-10-28) |
| [0005](0005-cache-ttl-en-memoria.md) | Caché TTL en memoria y precios sin persistir | Aceptada (a posteriori) |
| [0006](0006-jwt-en-cookie-con-csrf.md) | Sesión con JWT en cookie httpOnly y CSRF de doble envío | Aceptada (a posteriori) |
| [0007](0007-sin-modulo-de-encuestas.md) | Retiro del módulo de encuestas pre/post | Aceptada (2026-10-28) |
| [0008](0008-fuentes-de-datos-con-respaldo.md) | Yahoo Finance con Alpha Vantage de respaldo | Aceptada (a posteriori) |
| [0009](0009-js-vanilla-y-jinja2.md) | Interfaz con Jinja2 en el servidor y JavaScript vanilla | Aceptada (a posteriori) |

**Referencias bibliográficas.** Las citas de cada ADR están marcadas "(verificar)": se escribieron de memoria, sin confirmar autor, año ni URL. Confírmalas antes de incluirlas en el informe en formato APA 7.

**Uso de IA.** Estos ADR son borradores redactados con ayuda de una herramienta de IA a partir del código y de la documentación del repositorio. Antes de llevarlos al informe, revísalos, reescríbelos con tus palabras y declara el uso de la herramienta, según las normas de integridad académica de la asignatura.
