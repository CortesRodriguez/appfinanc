# Registro de decisiones arquitectónicas (decision log)

Reúne en un solo documento los nueve ADR de `docs/adr/`. Formato: plantilla de Michael Nygard (2011), una de las listadas en https://adr.github.io/adr-templates/. Cada ADR tiene título, Status, Context, Decision y Consequences. Nygard no incluye una sección de alternativas, así que las opciones descartadas y sus costos se describen dentro de Context y Consequences.

Los archivos individuales de `docs/adr/` son la fuente. Este documento es una copia consolidada: si editas un ADR, actualiza también esta copia.

Varios ADR se redactaron después de tomada la decisión y lo indican en Status ("registrada a posteriori"); no se escribieron con las alternativas a la vista.

## Índice

| N.º | Decisión | Status |
|---|---|---|
| 0001 | Monolito modular en Flask | Aceptada (registrada a posteriori). |
| 0002 | Explicaciones con LLM, plantillas de respaldo y validación de coherencia | Aceptada (2026-10-28). El guardarraíl de coherencia previo a aceptar el texto del LLM se decidió e implementó ese día. |
| 0003 | Niveles adaptativos con ficha declarativa | Aceptada como heurística, sin validación empírica (registrada a posteriori). |
| 0004 | PostgreSQL como único motor de base de datos | Aceptada (2026-10-28). |
| 0005 | Caché TTL en memoria y precios sin persistir | Aceptada (registrada a posteriori). |
| 0006 | Sesión con JWT en cookie httpOnly y CSRF de doble envío | Aceptada (registrada a posteriori). |
| 0007 | Retiro del módulo de encuestas pre/post | Aceptada (2026-10-28). |
| 0008 | Yahoo Finance con Alpha Vantage de respaldo | Aceptada (registrada a posteriori). |
| 0009 | Interfaz con Jinja2 en el servidor y JavaScript vanilla | Aceptada (registrada a posteriori). |

---

## 0001. Monolito modular en Flask

### Status

Aceptada (registrada a posteriori).

### Context

El sistema tiene extracción de datos, generación de explicaciones, autenticación, perfil y presentación. Lo desarrolla una sola persona, con un alcance de prototipo académico. Hay que decidir cómo se despliega y cómo se separan las responsabilidades.

Requerimientos relacionados: RNF-07 (organización modular del código).

Alternativas consideradas:

- **Monolito modular.** Un proceso, un despliegue; los módulos se llaman como funciones Python y la separación en paquetes ya refleja la vista de desarrollo del modelo 4+1. Costo: todos los módulos escalan juntos.
- **Microservicios.** Permiten escalar y desplegar cada parte por separado, pero suman complejidad operativa (red, versionado de contratos, observabilidad) desproporcionada para el alcance.

Se priorizó la simplicidad operativa para un desarrollador y para la defensa oral, la separación clara de responsabilidades (RNF-07.1) y la posibilidad de extraer un módulo más adelante.

Referencias (verificar antes de citar):

- Fowler, M. (2015). *MonolithFirst*. martinfowler.com.
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.

### Decision

Un solo proceso Flask con paquetes en `src/`: `extractor`, `nlp`, `auth`, `profile`, `services` y `web`. Los módulos se comunican por funciones públicas (`get_indicator`, `generate_explanation`, `get_detail_level`).

### Consequences

Se vuelve más fácil:

- Desplegar y depurar: un solo proceso.
- Explicar la arquitectura en la defensa.
- Compartir la orquestación de una consulta (indicador → explicación → registro), que vive en `src/services/query_service.py` y usan `src/web/routes.py` y `src/profile/routes.py`. Antes estaba copiada en tres endpoints.

Se vuelve más difícil:

- Escalar un módulo por separado.
- Mantener las rutas delgadas: siguen accediendo a `db` directamente (deuda del ORM difuso, documentada en `docs/diseno/04_diagrama_componentes.md`).

Tras el ADR 0007, el paquete `src/evaluation/` solo conservaba los modelos `QueryLog` e `InstrumentVisit`; se eliminó y los modelos pasaron a `src/profile/models.py`, sin cambios de esquema.

Verificación: estructura de `src/` y dependencias entre módulos con `git grep "^from src"`.

*Archivo fuente: `docs/adr/0001-monolito-modular.md`*

---

## 0002. Explicaciones con LLM, plantillas de respaldo y validación de coherencia

### Status

Aceptada (2026-10-28). El guardarraíl de coherencia previo a aceptar el texto del LLM se decidió e implementó ese día.

### Context

La explicación debe adaptarse al nivel del usuario y citar el valor real del indicador sin contradecirlo. Un LLM redacta con fluidez pero puede equivocarse; las plantillas son exactas pero rígidas.

Requerimientos relacionados: RF-04.1, RF-04.2, RF-05.1, RF-06.2, RNF-04, RNF-09.

Alternativas consideradas:

- **Solo plantillas.** Coherentes por construcción, sin dependencias externas y reproducibles, pero con poca flexibilidad para ajustar el texto al nivel y al contexto.
- **LLM con plantillas de respaldo.** El texto se ajusta a la ficha del nivel y, si el LLM falla, el usuario igual recibe una explicación. Costo: dependencia de Groq y salida que puede ser incoherente con el dato.
- **FinBERT como generador.** Descartada: FinBERT es un clasificador de sentimiento, no genera texto. Se mantiene solo como señal opcional.

Se priorizó la coherencia con el dato (el aporte central del proyecto), la adaptación del vocabulario al nivel del usuario y la tolerancia a fallos de un tercero (RNF-09).

Referencias (verificar antes de citar):

- Nygard, M. (2018). *Release It!* (2.ª ed.). Pragmatic Bookshelf. Patrones de estabilidad: degradación controlada.
- Kosireddy et al. (2024); Li et al. (2023); Lazarev & Sedov (2024), ya citados en el marco teórico.

### Decision

Un LLM con plantillas de respaldo. Flujo en `src/nlp/explainer.py:generate_explanation`:

1. Si `USE_LLM` está activo y hay `GROQ_API_KEY`, el LLM (`qwen/qwen3.8-27b` vía Groq) redacta el texto.
2. Se recorta al máximo de palabras del nivel y se acepta solo si contiene la etiqueta de riesgo, el valor del indicador (como cadena), ningún término prohibido del nivel y, además, pasa `validate_coherence` (`src/nlp/validator.py`), que contrasta el texto con el valor y los umbrales del indicador.
3. En cualquier otro caso, o ante una excepción, se usa una plantilla.
4. Las rutas vuelven a validar el texto final y devuelven `coherent` y `reason`; la interfaz muestra un aviso si discrepa. Las plantillas son coherentes por construcción, así que ese aviso solo debería aparecer en casos que el validador no cubre.

### Consequences

Se vuelve más fácil:

- Obtener texto fluido y ajustado al nivel con una red de seguridad.
- Evitar que se muestre un texto del LLM que contradice el dato (por ejemplo, "sobrecomprado" con un RSI bajo, o "15.0" cuando el valor es 5.0): cae a plantilla. Un test lo comprueba y se verificó que falla si se quita el guardarraíl.

Se vuelve más difícil, verificado en el código:

- El validador solo cubre lo que sus reglas conocen: riesgo, valor citado y las categorías cualitativas de RSI, %B, MACD y medias móviles. Una frase falsa fuera de esas reglas (por ejemplo, una causa inventada) no se detecta.
- La comprobación del valor es una búsqueda de cadena (`value_str in texto`): un valor `5.0` sigue pasando si el texto dice "15.0" y no menciona ninguna categoría contradictoria.
- El `except Exception: pass` oculta los fallos del LLM y no hay conteo de cuántas veces se usa el respaldo. Mejora pendiente: registrar ese conteo para tener un dato en la defensa.
- No se probó contra la API real de Groq: los tests simulan la respuesta del modelo.

Verificación: `tests/test_validator.py`, `tests/test_explainer.py` y la validación de cada nivel y estilo de plantilla en `tests/test_profile.py`.

*Archivo fuente: `docs/adr/0002-llm-con-fallback-y-validacion.md`*

---

## 0003. Niveles adaptativos con ficha declarativa

### Status

Aceptada como heurística, sin validación empírica (registrada a posteriori).

### Context

El público objetivo va desde quien nunca ha invertido hasta quien tiene experiencia. Una misma explicación no sirve para todos.

Requerimientos relacionados: RF-05.2, RF-06.2, RF-13.2, RF-14.

Alternativas consideradas:

- **Un solo nivel de explicación.** Simple, pero no responde al problema.
- **Reglas simples con tres niveles.** Explicable, testeable y sin entrenar modelos. Costo: el umbral de bajada de nivel no tiene respaldo empírico.
- **Modelo de usuario aprendido.** Descartada: requiere datos que el proyecto no tiene.

Referencia (verificar antes de citar): fuente sobre modelos de usuario en sistemas adaptativos.

### Decision

Tres niveles (`basico`, `intermedio`, `avanzado`) definidos por una ficha en `src/nlp/levels.py` (audiencia, vocabulario, términos prohibidos, umbrales, contexto IPSA, máximo de palabras). La misma ficha alimenta el prompt del LLM y las plantillas.

- Nivel inicial según la experiencia declarada: nunca → básico, poco → intermedio, experiencia → avanzado, sin dato → intermedio.
- Cada `DETAIL_THRESHOLD = 2` regeneraciones ("No entendí esto") de un indicador bajan un nivel, con piso en básico.
- Cambiar la experiencia declarada reinicia el conteo (`users.level_reset_at`).
- `preferred_variant()` recuerda el estilo de redacción donde el usuario dejó de regenerar.

Se mantiene como una regla heurística y se declara como limitación en el informe. No se agregó una regla para subir de nivel ni se hizo configurable el umbral, porque cualquier valor nuevo tampoco tendría respaldo empírico.

### Consequences

Se vuelve más fácil:

- Mantener una sola fuente de verdad por nivel.
- Probar cada nivel y estilo contra el validador (`tests/test_profile.py`).

Se vuelve más difícil:

- Justificar el umbral: interpretar "No entendí esto" como baja comprensión y fijarlo en 2 son supuestos sin validar. El retiro de las encuestas (ADR 0007) quita la forma prevista de comprobarlos.
- Recuperar un nivel perdido: solo baja, nunca sube.

Si hubiera validación con usuarios, se podría agregar una regla para subir de nivel tras N consultas sin regenerar y hacer configurable el umbral (`DETAIL_THRESHOLD` está en `src/profile/service.py`).

*Archivo fuente: `docs/adr/0003-niveles-adaptativos.md`*

---

## 0004. PostgreSQL como único motor de base de datos

### Status

Aceptada (2026-10-28).

### Context

La app guarda cuentas (correo, hash bcrypt), tokens revocados, el log de consultas y las visitas por instrumento. Debe soportar a varias personas a la vez y conservar los datos entre despliegues. Cada selección de instrumento dispara cuatro llamadas a `/api/query` y cada una escribe en `query_logs`, así que las escrituras son frecuentes.

Hasta esta decisión el código usaba SQLite por defecto, mientras `docs/diseno/09_stack_tecnologico.md` y el diagrama de despliegue ya describían PostgreSQL.

Requerimientos relacionados: RNF-02.1, RNF-05, RNF-06.

Alternativas consideradas:

- **SQLite.** Sin servidor y arranca con un comando. Costos: un solo escritor a la vez (obliga a un worker de gunicorn); el archivo se pierde en cada redespliegue de un PaaS; no valida largos de `VARCHAR`, lo que oculta errores hasta producción.
- **SQLite en desarrollo y PostgreSQL en producción.** Cómodo en local, pero son dos motores con comportamientos distintos (largos, zonas horarias, concurrencia) y los tests no probarían lo que se despliega.
- **PostgreSQL en todos los entornos.** Mismo comportamiento en todas partes, escrituras concurrentes, `timestamptz` y tipos estrictos. Costo: hace falta un servidor para correr la app y los tests.

Se priorizó la escritura concurrente de varios usuarios y workers, la persistencia fuera del contenedor y una sola configuración para desarrollo, pruebas y producción.

Referencias (verificar antes de citar):

- Wiggins, A. (2011). *The Twelve-Factor App*. https://12factor.net. Configuración por variables de entorno y servicios de respaldo como recursos adjuntos.
- ISO/IEC 25010: características de calidad del producto (fiabilidad, eficiencia de desempeño).

### Decision

PostgreSQL 14+ con el driver psycopg 3. `DATABASE_URL` es obligatoria; `config.py` rechaza otros motores y normaliza `postgres://` y `postgresql://` a `postgresql+psycopg://`. El pool usa `pool_pre_ping=True` y `pool_recycle=1800`. Los tests usan una base dedicada (`TEST_DATABASE_URL`, nombre terminado en `_test`).

### Consequences

Se vuelve más fácil:

- Que varios workers escriban a la vez.
- Que los datos sobrevivan a los redespliegues.

Se vuelve más difícil:

- Desarrollar y ejecutar `pytest`: hace falta instalar PostgreSQL, y la suite es más lenta que con SQLite en memoria.
- Compartir el caché de precios entre workers: sigue siendo por proceso (ADR 0005).

Las migraciones 0001–0005 se escribieron con `batch_alter_table`, pensado para SQLite. Verificado el 2026-10-28 contra PostgreSQL 16: la base quedó en la revisión `0005`, `flask db check` no detecta cambios pendientes y los tests pasan. Falta repetir `flask db upgrade` sobre una base totalmente vacía.

Verificación: `config.py:_database_url`, `tests/conftest.py` y `flask --app app db upgrade`.

*Archivo fuente: `docs/adr/0004-postgresql-como-motor.md`*

---

## 0005. Caché TTL en memoria y precios sin persistir

### Status

Aceptada (registrada a posteriori).

### Context

Los precios vienen de fuentes externas con límites de uso. Repetir la misma consulta en cada clic es lento y consume cuota.

Requerimientos relacionados: RNF-02.2, RNF-08.1, RNF-09.

Alternativas consideradas:

- **Caché en memoria por proceso con TTL de 5 minutos.** Sin infraestructura adicional, y los datos financieros son efímeros por diseño. Costos: con varios workers cada uno tiene su caché y repite la petición una vez por TTL; no hay límite de tamaño y las entradas vencidas se eliminan solo al leerse.
- **Guardar los precios en la base de datos.** Descartada: obliga a sincronizar datos de terceros y el sistema no lo necesita.
- **Caché compartido (Redis).** Una sola copia para todos los workers, pero es otro servicio que operar; no se justifica en esta etapa.

Referencia (verificar antes de citar): patrón *cache-aside* con TTL.

### Decision

`TTLCache` (`src/extractor/cache.py`) con TTL de 300 s, con cachés separadas para historial, cotizaciones y datos macro. Las noticias usan una caché propia de 20 minutos. La base de datos no almacena precios ni indicadores calculados.

### Consequences

Se vuelve más fácil:

- Implementar y operar el caché: es simple y suficiente para el volumen esperado.

Se vuelve más difícil:

- Evitar peticiones duplicadas entre workers.
- Acotar la memoria: posible crecimiento sin límite. Mejora acotada: añadir `maxsize` y limpieza proactiva.
- Reconstruir qué datos vio el usuario: `query_logs` guarda valor, unidad, riesgo, ventana y fuente de cada consulta, pero no la serie usada.

*Archivo fuente: `docs/adr/0005-cache-ttl-en-memoria.md`*

---

## 0006. Sesión con JWT en cookie httpOnly y CSRF de doble envío

### Status

Aceptada (registrada a posteriori).

### Context

Hay que autenticar usuarios con contraseña (y opcionalmente con Google), poder cerrar sesión de verdad y resistir XSS y CSRF.

Requerimientos relacionados: RF-11, RF-12, RNF-06.

Alternativas consideradas:

- **Sesión nativa de Flask.** Descartada: sin expiración configurable ni revocación individual de tokens.
- **JWT en `localStorage`.** Descartada: es accesible desde JavaScript y un XSS lo roba.
- **JWT en cookie httpOnly con token CSRF de doble envío.** El token no es legible desde JS y el CSRF queda mitigado. Costo: toda petición mutante debe enviar el header `X-CSRF-TOKEN`.

Referencia (verificar URL y año antes de citar): OWASP, *Cross-Site Request Forgery Prevention Cheat Sheet*.

### Decision

Flask-JWT-Extended con el token en cookie httpOnly, expiración de 24 horas y revocación por `jti` en la tabla `revoked_tokens`. Una segunda cookie `csrf_access_token`, legible por JS, se reenvía en `X-CSRF-TOKEN` (ver `static/js/csrf.js`). Contraseñas con Flask-Bcrypt (8 a 64 caracteres y máximo 72 bytes UTF-8). Bloqueo de la cuenta durante 15 minutos tras 5 intentos fallidos. Login con Google mediante Authlib, sin vincular cuentas por correo.

### Consequences

Se vuelve más fácil:

- Cerrar sesión de forma efectiva.
- Frenar la fuerza bruta con el bloqueo por intentos.
- Mitigar XSS y CSRF.

Se vuelve más difícil:

- Desplegar sin HTTPS: `JWT_COOKIE_SECURE` debe estar en `true` bajo HTTPS.
- Reducir la carga en la base: la revocación exige una consulta en cada petición autenticada.

Verificación: `tests/test_auth.py`.

*Archivo fuente: `docs/adr/0006-jwt-en-cookie-con-csrf.md`*

---

## 0007. Retiro del módulo de encuestas pre/post

### Status

Aceptada (2026-10-28).

### Context

La versión inicial incluía encuestas de comprensión pre y post uso, reportes, exportación CSV y un panel de auditoría de coherencia. Ese código (`surveys.py`, `eligibility.py`, `reports.py`, sus plantillas y tests) se eliminó del prototipo. La documentación y el informe seguían describiéndolo.

Requerimientos afectados: objetivo específico 5 original, RNF-05.2 y CU-06/07/09/10 de la versión anterior de la documentación.

Alternativas consideradas:

- **Reincorporar las encuestas.** Permitiría medir con datos la efectividad del sistema, pero exige rediseñar el módulo, el consentimiento y la anonimización, además de reclutar participantes. No cabe en el tiempo restante.
- **Retirarlas del alcance y de la documentación.** Deja la documentación coherente con el código. Costo: el proyecto no mide la efectividad del sistema sobre los usuarios.

### Decision

Se retiran del alcance el objetivo de evaluación con encuestas, RNF-05.2 y los casos de uso asociados. La validación con usuarios queda como trabajo futuro. La coherencia entre texto y dato se sigue comprobando automáticamente (`src/nlp/validator.py`, ADR 0002).

### Consequences

Se vuelve más fácil:

- Mantener la documentación alineada con el código.
- Defender el proyecto apoyándose en la validación técnica (tests y validador de coherencia).

Se vuelve más difícil:

- Demostrar que las explicaciones mejoran la comprensión: no hay evidencia empírica y debe declararse como limitación y proyección.
- Justificar el umbral de regeneraciones del ADR 0003, que queda sin forma prevista de validación.
- Entregar un informe consistente: hay que actualizar el informe (`docx`) y el PPT (objetivo, alcance, resultados esperados, Vista lógica y conclusiones). Esos archivos no están en el repositorio.

*Archivo fuente: `docs/adr/0007-sin-modulo-de-encuestas.md`*

---

## 0008. Yahoo Finance con Alpha Vantage de respaldo

### Status

Aceptada (registrada a posteriori).

### Context

Se necesitan precios históricos de las acciones del IPSA, indicadores macro chilenos y noticias, sin costo y sin una API oficial gratuita completa.

Requerimientos relacionados: RF-02.1, RF-02.3, RNF-08, RNF-09.

Alternativas consideradas:

- **Solo `yfinance`.** Sin clave y con cobertura del IPSA (sufijo `.SN`). Costo: no es una API oficial; puede cambiar o bloquear sin aviso.
- **`yfinance` con Alpha Vantage de respaldo.** Agrega una red de seguridad con una API oficial de clave gratuita. Costo: límites bajos de uso (verificar la cuota vigente).

### Decision

`src/extractor/sources.py` intenta Yahoo Finance y, si falla, Alpha Vantage, con hasta 3 reintentos (RNF-09.2). UF, dólar, TPM e IPC vienen de mindicador.cl. Las noticias usan el RSS no oficial de Google News y se degradan a una lista vacía si falla.

### Consequences

Se vuelve más fácil:

- Seguir mostrando datos cuando una fuente cae.

Se vuelve más difícil:

- Garantizar la disponibilidad: depende de proveedores que el proyecto no controla.
- Gestionar los riesgos asociados, que deben registrarse en el plan de riesgos (`docs/diseno/11_riesgos_cumplimiento.md`): fuentes no oficiales (`yfinance`, Google News RSS) y un tercero para el LLM (Groq).

*Archivo fuente: `docs/adr/0008-fuentes-de-datos-con-respaldo.md`*

---

## 0009. Interfaz con Jinja2 en el servidor y JavaScript vanilla

### Status

Aceptada (registrada a posteriori).

### Context

La interfaz tiene pocas pantallas (siete plantillas en `src/web/templates/`) y ninguna maneja un estado de aplicación complejo. Lo desarrolla una sola persona, sin margen para aprender infraestructura de frontend durante el proyecto.

Requerimientos relacionados: RNF-03 (diseño de interfaz y responsividad), RNF-07 (mantenibilidad).

Alternativa considerada y descartada: un framework moderno (React, Vue o Svelte). Habría exigido aprender infraestructura de producción (Vite o Webpack, JSX, hooks) sin aportar valor a la propuesta del proyecto. Esta justificación proviene de `docs/diseno/09_stack_tecnologico.md`, sección Frontend (que habla de "~10 pantallas"; el recuento actual de plantillas es siete); no hay evidencia en el repositorio de que se hayan evaluado otras alternativas con prototipos o mediciones.

### Decision

Flask renderiza el HTML en el servidor con plantillas Jinja2 (`src/web/templates/`). El JavaScript sin framework (`src/web/static/js/`) solo agrega interactividad puntual. El estado vive en el DOM y en la sesión de Flask, sin un store.

### Consequences

Se vuelve más fácil:

- Desarrollar y desplegar: no hay paso de compilación ni dependencias de frontend que instalar.
- Explicar la separación en la vista de desarrollo del modelo 4+1: el servidor produce la página y el JS solo la anima.

Se vuelve más difícil:

- Crecer en interactividad: `src/web/static/js/dashboard.js` ya concentra la lógica del dashboard en un solo archivo grande, y un framework de componentes la repartiría mejor.
- Reutilizar componentes de interfaz entre pantallas.
- Probar el JavaScript: el repositorio no tiene pruebas automáticas del frontend, solo de las rutas.

*Archivo fuente: `docs/adr/0009-js-vanilla-y-jinja2.md`*

---

## Notas para el informe

- **Referencias.** Las citas marcadas "(verificar)" se escribieron de memoria, sin confirmar autor, año ni URL. Confírmalas antes de incluirlas en formato APA 7.
- **Plantilla.** No afirmes que Nygard es el formato "más común": ni adr.github.io ni el repositorio de la comunidad lo dicen. Se eligió por ser la plantilla original, la enlazada por el docente y la más corta.
- **Uso de IA.** Estos textos son borradores redactados con ayuda de una herramienta de IA a partir del código y de la documentación del repositorio. Antes de llevarlos al informe, revísalos, reescríbelos con tus palabras y declara el uso de la herramienta, según las normas de integridad académica de la asignatura.
