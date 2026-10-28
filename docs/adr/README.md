# Registro de decisiones arquitectónicas (ADR)

Formato: [MADR](https://adr.github.io/madr/) (Markdown Any Decision Records), una de las plantillas listadas en https://adr.github.io/adr-templates/. Cada ADR indica contexto, opciones con pros y contras, decisión y consecuencias. Estado posible: propuesta, aceptada, reemplazada.

| N.º | Decisión | Estado |
|---|---|---|
| [0001](0001-monolito-modular.md) | Monolito modular en Flask | Aceptada |
| [0002](0002-llm-con-fallback-y-validacion.md) | Explicaciones con LLM, plantillas de respaldo y validación de coherencia | Aceptada, con mejora pendiente |
| [0003](0003-niveles-adaptativos.md) | Niveles adaptativos con ficha declarativa | Aceptada, a validar |
| [0004](0004-postgresql-como-motor.md) | PostgreSQL como único motor de base de datos | Aceptada |
| [0005](0005-cache-ttl-en-memoria.md) | Caché TTL en memoria y precios sin persistir | Aceptada |
| [0006](0006-jwt-en-cookie-con-csrf.md) | Sesión con JWT en cookie httpOnly y CSRF de doble envío | Aceptada |
| [0007](0007-sin-modulo-de-encuestas.md) | Retiro del módulo de encuestas pre/post | Aceptada |
| [0008](0008-fuentes-de-datos-con-respaldo.md) | Yahoo Finance con Alpha Vantage de respaldo | Aceptada |

Plantilla para nuevas decisiones: [0000-plantilla.md](0000-plantilla.md).

**Referencias bibliográficas.** Las citas de cada ADR están marcadas "(verificar)": se escribieron de memoria, sin confirmar autor, año ni URL. Confírmalas antes de incluirlas en el informe en formato APA 7.
