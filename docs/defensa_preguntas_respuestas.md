# Preguntas y Respuestas — Defensa de Título

Preparación para defensa del proyecto **appfint**: sistema de IA para comprensión de información financiera en inversionistas principiantes chilenos.

---

## Tecnologías — Preguntas generales

**¿Por qué eligió este stack tecnológico y no otro?**
Se priorizó un stack que fuera simple de desarrollar pero que se pudiera llevar a producción sin rehacerlo. Python tiene ecosistema robusto para IA/datos, Flask es ligero y directo, PostgreSQL entrega una base de datos relacional robusta (concurrencia real, integridad estricta, respaldos) con SQLAlchemy como capa de acceso, y JavaScript vanilla evita dependencias de frontend innecesarias.

**¿Consideró otras alternativas antes de elegir estas tecnologías?**
Sí. Se consideró Django (más complejo, innecesario para el alcance), Node.js (menor ecosistema de IA), React (sobrecarga para el dashboard), y como motores de base de datos SQLite y MySQL. SQLite se descartó por ser un archivo local acoplado al contenedor de la aplicación y con un único escritor a la vez; MySQL por ofrecer menos garantías de tipos y menos funcionalidades SQL que PostgreSQL para el mismo costo operativo. Las alternativas fueron descartadas por no aportar beneficio concreto frente a la opción elegida.

**¿Cuál fue el criterio principal de selección de cada tecnología?**
Tres criterios: (1) adecuación al problema (Python para IA/datos), (2) simplicidad de configuración (Flask, SQLAlchemy), (3) capacidad de operar en producción real: datos personales de usuarios que deben sobrevivir a los redespliegues, varios workers atendiendo en paralelo y respaldos gestionados (PostgreSQL).

**¿Este stack es adecuado para producción o solo para prototipo?**
Sí es adecuado para producción. La aplicación se sirve con gunicorn (varios workers) detrás de un proxy inverso con HTTPS, y la base de datos PostgreSQL corre en un nodo separado (servicio gestionado con TLS y respaldos automáticos), de modo que los datos no dependen del contenedor de la aplicación. Para cargas mayores se escalaría horizontalmente con más instancias Flask y se sustituiría la caché en memoria por una distribuida. Python y Flask son ampliamente usados en producción.

---

## Python / Backend

**¿Por qué Python y no Java, Node.js o C#?**
Python tiene el ecosistema más maduro para inteligencia artificial y procesamiento de datos (scikit-learn, transformers, pandas, yfinance). Para un sistema que integra NLP y análisis financiero, Python es la elección natural.

**¿Cuáles son las ventajas de Python para sistemas con componentes de IA?**
Bibliotecas especializadas maduras (transformers, torch, numpy), sintaxis concisa, gran comunidad científica, integración directa con modelos como FinBERT sin necesidad de wrappers.

**¿Qué desventajas tiene Python frente a otros lenguajes backend?**
Es más lento que Java o Go en ejecución pura. El GIL limita la paralelización de threads. Para sistemas de alta concurrencia o procesamiento intensivo en CPU, otros lenguajes son superiores.

**¿Python es un lenguaje compilado o interpretado? ¿Qué implica eso?**
Interpretado. El código se ejecuta línea a línea sin compilación previa a binario nativo, lo que facilita el desarrollo pero sacrifica velocidad de ejecución respecto a lenguajes compilados como C++ o Java.

**¿Cómo maneja Python la concurrencia? ¿Tuvo problemas de concurrencia en su sistema?**
Sí, se detectó una condición de carrera en la creación de sesiones cuando múltiples llamadas AJAX llegaban simultáneamente al inicio de sesión. Se resolvió estableciendo la cookie de sesión en `before_app_request`, antes de que el dashboard dispare las llamadas paralelas a `/api/query`.

**¿Qué es el GIL en Python y cómo afecta el rendimiento?**
El Global Interpreter Lock es un mutex que permite que solo un thread ejecute código Python a la vez, incluso en sistemas multi-core. Limita el paralelismo real en operaciones CPU-bound. Para I/O-bound (como peticiones HTTP a Yahoo Finance), el impacto es menor.

---

## Flask

**¿Qué es Flask y qué rol cumple en su sistema?**
Flask es un microframework web para Python. En el sistema recibe las peticiones HTTP del navegador, las enruta a las funciones Python correspondientes, ejecuta la lógica de negocio y devuelve respuestas JSON o páginas HTML.

**¿Por qué Flask y no Django, FastAPI u otro framework?**
Django incluye ORM propio, sistema de admin, autenticación integrada y muchas otras funcionalidades que no se necesitaban, añadiendo complejidad innecesaria. FastAPI es excelente pero orientado a APIs asíncronas; Flask es suficiente para el alcance del proyecto y más familiar en el contexto académico.

**¿Cuál es la diferencia entre Flask y Django?**
Django es un framework "batteries included": incluye ORM, panel de administración, sistema de autenticación, formularios. Flask es minimalista y deja al desarrollador elegir cada componente. Django impone más convenciones; Flask da más libertad.

**¿Qué significa que Flask sea un "microframework"?**
Que su núcleo es pequeño y no impone estructura ni componentes por defecto. No incluye ORM, autenticación ni formularios. El desarrollador agrega solo lo que necesita mediante extensiones (Flask-JWT-Extended, Flask-Bcrypt, SQLAlchemy).

**¿Qué son los Blueprints en Flask y para qué los usó?**
Los Blueprints son módulos que agrupan rutas relacionadas. Se usaron para separar las rutas de autenticación (`auth`), perfil (`profile`) y la web principal (`web`), permitiendo organización modular sin acoplar todo en un solo archivo.

**¿Cómo maneja Flask las rutas y los métodos HTTP?**
Mediante el decorador `@app.route()` o `@blueprint.route()` especificando la URL y los métodos aceptados (GET, POST, etc.). Flask asocia cada URL con una función Python que procesa la petición y retorna una respuesta.

**¿Flask es adecuado para una aplicación en producción con muchos usuarios?**
Flask en sí es adecuado, pero debe desplegarse con un servidor WSGI como gunicorn y detrás de un proxy como nginx. Para alta concurrencia se usarían múltiples workers. El servidor de desarrollo integrado de Flask no es apto para producción.

---

## PostgreSQL / Base de datos

**¿Por qué usó PostgreSQL y no SQLite o MySQL?**
Porque la aplicación guarda datos personales (correos, hashes bcrypt) que deben persistir entre despliegues y ser atendidos por varios workers de gunicorn al mismo tiempo. PostgreSQL corre como un servidor separado, por lo que los datos sobreviven a que el contenedor de la aplicación se destruya y se recree; permite escrituras concurrentes reales (MVCC); ofrece respaldos gestionados y recuperación a un punto en el tiempo; maneja roles y TLS; y valida estrictamente tipos y largos. SQLite es un archivo local acoplado al disco del contenedor y serializa las escrituras; MySQL es viable, pero PostgreSQL tiene tipos más estrictos (`timestamptz`, `boolean`), mejor cumplimiento de SQL estándar y es el estándar de facto con SQLAlchemy.

**¿Cuáles son las limitaciones o costos de PostgreSQL?**
Requiere un servidor aparte: hay que aprovisionarlo (en local con Homebrew, en producción como servicio gestionado como Neon, Supabase o Render), configurar `DATABASE_URL` y gestionar credenciales. Agrega una salida de red por consulta (latencia, TLS) y un punto de falla adicional, y hay un límite de conexiones simultáneas que obliga a usar un pool. A cambio se obtiene robustez y escalabilidad, que para este sistema compensan el costo.

**¿Qué ocurre con PostgreSQL cuando hay múltiples usuarios accediendo simultáneamente?**
PostgreSQL usa MVCC (Multi-Version Concurrency Control): las lecturas no bloquean a las escrituras y varias escrituras pueden avanzar en paralelo, bloqueándose solo cuando tocan la misma fila. Cada worker de gunicorn toma conexiones de un pool de SQLAlchemy. Las restricciones únicas (usuario, correo) las garantiza el motor, y la aplicación tolera `IntegrityError` cuando dos peticiones intentan crear el mismo registro a la vez.

**¿Cómo maneja las conexiones a la base de datos?**
Con el pool de conexiones de SQLAlchemy, configurado con `pool_pre_ping=True` (verifica que la conexión siga viva antes de usarla) y `pool_recycle=1800` (recicla conexiones cada 30 minutos). Esto es necesario porque los servicios gestionados cierran las conexiones inactivas; sin ello se producirían errores 500 tras periodos de baja actividad.

**¿PostgreSQL es una base de datos relacional? ¿Qué significa eso?**
Sí, es relacional (y objeto-relacional). Significa que los datos se organizan en tablas con filas y columnas, y las relaciones entre tablas se expresan mediante claves foráneas (por ejemplo `query_logs.user_id` y `instrument_visits.user_id` referencian a `users.id`). Se consulta con SQL (Structured Query Language) y ofrece transacciones ACID.

**¿Por qué una base de datos SQL y no NoSQL?**
Los datos son pocos, estructurados y están relacionados con el usuario. `query_logs` e `instrument_visits` tienen claves foráneas a `users`, y `username` y `email` son únicos. Necesito que esas restricciones las garantice el motor, y que el historial y el perfil adaptativo se consulten con filtros y agregaciones, por ejemplo las regeneraciones de un indicador posteriores a `level_reset_at`. Un modelo relacional resuelve eso directamente. NoSQL habría sido útil para documentos sin esquema fijo o para series de precios masivas, pero el sistema no guarda precios: son efímeros en caché en memoria.

**¿Qué es SQLAlchemy y por qué lo usó?**
SQLAlchemy es un ORM (Object-Relational Mapper) para Python. Permite interactuar con la base de datos usando clases y objetos Python en lugar de escribir SQL directamente. Se usa la versión 2 a través de Flask-SQLAlchemy, con el driver psycopg 3 (`postgresql+psycopg://`). Facilita el mantenimiento y evita errores de SQL manual.

**¿Qué diferencia hay entre usar SQLAlchemy y escribir SQL directo?**
Con SQLAlchemy se definen modelos como clases Python y se realizan consultas con métodos Python. Con SQL directo se escriben strings de consulta. SQLAlchemy es más mantenible y seguro (consultas parametrizadas que previenen inyección SQL), pero añade una capa de abstracción.

**¿Cómo gestiona los cambios en el esquema? ¿Usó migraciones?**
Sí, con Flask-Migrate (Alembic). El esquema vive versionado en `migrations/versions/` y se aplica con `flask db upgrade`; la migración `0001_esquema_inicial` crea las tablas. Así el esquema puede evolucionar en producción sin perder datos y cada cambio queda registrado y es reversible (`downgrade`). La aplicación no crea tablas al arrancar.

**¿Qué ocurre con los datos cuando se redespliega la aplicación?**
Nada: la base de datos es un nodo independiente del contenedor de Flask. Al redesplegar se reemplazan los contenedores de la aplicación y se ejecuta `flask db upgrade` si hay migraciones nuevas; los usuarios, tokens revocados y registros de consultas siguen en PostgreSQL. Lo único que se pierde es la caché de precios en memoria, que es efímera por diseño.

**¿Cómo se respaldan los datos?**
El servicio gestionado de PostgreSQL realiza respaldos automáticos y permite recuperación a un punto en el tiempo. Adicionalmente se puede generar un volcado manual con `pg_dump`.

**¿Cómo protege los datos personales en la base de datos?**
Las contraseñas nunca se guardan en claro: solo el hash bcrypt (`password_hash`). La conexión a la base se hace con TLS (`sslmode=require`), con credenciales entregadas por variable de entorno (`DATABASE_URL`) y no incluidas en el código. Además, PostgreSQL permite roles con privilegios mínimos separados del propietario del esquema.

**¿Qué tablas tiene su base de datos y qué guarda cada una?**
Cuatro tablas más la de control de Alembic (`alembic_version`): `users` (credenciales y perfil, con soporte de login con Google), `revoked_tokens` (JTI de tokens JWT revocados al cerrar sesión), `query_logs` (registro de cada consulta de indicador: instrumento, indicador, fuente, tiempo de procesamiento, texto de la explicación, variante y si fue una regeneración) e `instrument_visits` (visitas de cada usuario a instrumentos). Los datos de precios no se guardan: son efímeros en caché en memoria.

**¿Por qué validó el largo del ticker antes de consultar la base?**
Porque PostgreSQL aplica estrictamente los largos de `VARCHAR` y rechaza valores que excedan la columna (por ejemplo `instrument` es `VARCHAR(20)`). Se valida `MAX_SYMBOL_LENGTH = 20` en las rutas y en el extractor para responder con un error 400 claro en lugar de un error de base de datos.

**¿Si el proyecto escalara, qué cambiaría en la capa de datos?**
Se mantiene PostgreSQL, que ya escala bien: se agregarían más instancias de la aplicación apuntando al mismo nodo, un pooler de conexiones (por ejemplo PgBouncer) si el número de conexiones creciera, réplicas de lectura para consultas analíticas y un plan de partición/archivo para `query_logs`, que es la tabla de mayor crecimiento.

---

## Frontend

**¿Por qué usó JavaScript vanilla y no React, Vue o Angular?**
El frontend no requiere estado complejo ni componentes reutilizables a gran escala. JavaScript vanilla evita la sobrecarga de un framework, reduce dependencias y es suficiente para un dashboard con llamadas AJAX y actualización de DOM.

**¿Qué ventajas tiene no usar un framework frontend?**
Sin proceso de build, sin dependencias de npm, menor tamaño de carga, código más directo y fácil de auditar. Apropiado cuando la interactividad es moderada y no se necesita gestión de estado compleja.

**¿Qué desventajas tiene JavaScript vanilla frente a React?**
Más código manual para manipulación del DOM, sin reactividad automática, sin componentes reutilizables estructurados, más difícil de escalar si la UI crece en complejidad.

**¿Qué es Jinja2 y cómo lo usó?**
Jinja2 es el motor de templates de Flask. Permite generar HTML dinámico insertando variables Python en archivos `.html`. Se usó para las páginas base, glosario e índice, inyectando datos del servidor directamente en el HTML antes de enviarlo al navegador.

**¿Cuál es la diferencia entre renderizado del lado del servidor y del cliente?**
Servidor: el HTML llega completo al navegador (Jinja2). Cliente: el navegador recibe HTML vacío y JavaScript construye el contenido dinámicamente (React/Vue). El sistema usa ambos: páginas base por servidor, datos del dashboard por cliente vía AJAX.

**¿Qué es TradingView Lightweight Charts y por qué lo eligió?**
Es una biblioteca JavaScript especializada en gráficos financieros de alto rendimiento. Se eligió porque provee nativamente gráficos de velas japonesas (candlestick) y series de líneas con interactividad, lo que sería complejo de implementar desde cero.

**¿Cómo se comunica el frontend con el backend?**
Mediante peticiones HTTP asíncronas (fetch API). El frontend envía `GET /api/chart` y `POST /api/query` con parámetros JSON; el backend responde con JSON que el JavaScript procesa para actualizar la UI sin recargar la página.

**¿Qué es JSON y cómo fluye entre frontend y backend en su sistema?**
JSON (JavaScript Object Notation) es un formato de texto para intercambiar datos estructurados. El frontend envía parámetros en JSON, el backend procesa y devuelve indicadores, explicaciones y datos de precios en JSON, y el frontend los renderiza en el dashboard.

---

## Seguridad

**¿Qué es JWT y cómo lo implementó?**
JWT (JSON Web Token) es un token firmado que contiene la identidad del usuario. Al hacer login, el servidor genera un JWT y lo almacena en una cookie httpOnly. En cada petición protegida, Flask-JWT-Extended verifica automáticamente la firma del token.

**¿Por qué usó JWT y no sesiones de servidor?**
Ambas opciones eran válidas para una aplicación monolítica con navegador. Elegí JWT porque Flask-JWT-Extended resuelve la firma, la expiración de 24 horas y la protección de rutas con `@jwt_required()`. El logout es real porque el `jti` del token se guarda en la tabla `revoked_tokens`. Reconozco el trade-off: al guardar tokens revocados, la aplicación mantiene un estado en el servidor, igual que con sesiones. Una sesión de Flask tradicional también habría funcionado. La `session` por defecto de Flask no es de servidor: es una cookie firmada. Para revocación real con sesiones de servidor habría que usar Flask-Login con almacenamiento en Redis o en base de datos. Si la aplicación creciera, esa migración sería una opción.

**¿Por qué guardó el JWT en una cookie httpOnly y no en localStorage?**
Una cookie httpOnly no es accesible desde JavaScript, lo que previene que un ataque XSS pueda robar el token. localStorage es vulnerable a XSS porque cualquier script en la página puede leerlo.

**¿Qué es CSRF y cómo lo previno en su sistema?**
CSRF (Cross-Site Request Forgery) es un ataque donde un sitio malicioso hace peticiones en nombre del usuario autenticado. Se previno con un segundo token CSRF en una cookie legible por JS (`csrf_access_token`); todas las peticiones mutantes deben incluir este token en el header `X-CSRF-TOKEN`. Además, la cookie del JWT usa `SameSite=Lax` y `Secure`, de modo que no se envía en peticiones cruzadas mutantes ni por HTTP sin cifrar.

**¿Qué es bcrypt y para qué lo usó?**
Bcrypt es un algoritmo de hash diseñado para contraseñas. A diferencia de MD5 o SHA, es intencionalmente lento y agrega un "salt" aleatorio, lo que hace inviables los ataques de fuerza bruta y rainbow tables. Se usó con Flask-Bcrypt para almacenar contraseñas de forma segura.

**¿Cómo protegió las rutas que requieren autenticación?**
Con el decorador `@jwt_required()` de Flask-JWT-Extended. Las rutas marcadas con este decorador rechazan peticiones sin un JWT válido, devolviendo HTTP 401.

**¿Validó los inputs del usuario? ¿Cómo?**
Sí. Los parámetros críticos como `days` se validan contra `VALID_PERIODS = (30, 90, 180, 365)` antes de procesarlos. Valores fuera del conjunto permitido generan un error `ExtractionError` que devuelve HTTP 502.

**¿Cómo protegió el login contra ataques de fuerza bruta?**
Con un bloqueo por cuenta: tras 5 intentos fallidos seguidos para un mismo correo, `authenticate_user` fija `users.locked_until` a 15 minutos y responde HTTP 429. Un login correcto resetea el contador. Los valores viven en `config.py` (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCK_MINUTES`) y las columnas se agregaron con la migración `0002`. Al ser un contador en la base de datos y no en memoria, sobrevive a reinicios y funciona con varios procesos.

**¿Por qué el mensaje de error del login es genérico?**
Para no revelar si un correo está registrado: un correo inexistente y una contraseña incorrecta devuelven el mismo 401 ("Correo o contraseña incorrectos"). Evita la enumeración de usuarios.

**¿Por qué la contraseña tiene un máximo de 64 caracteres?**
Un tope razonable evita abusos (hashear textos enormes) sin limitar frases largas. Además bcrypt solo acepta 72 *bytes*, y 64 caracteres con tildes o emojis pueden superarlos; por eso el servicio valida también el largo en bytes UTF-8 y responde 400 en vez de dejar que bcrypt lance un error (500).

**¿Qué códigos HTTP usa el registro y el login y por qué?**
400 para errores de validación (contraseña débil, confirmación distinta), 409 para conflicto (correo o usuario ya existente), 401 para credenciales inválidas y 429 para cuenta bloqueada temporalmente. `AuthError` lleva el código en un atributo `status`.

**¿Qué pasa si alguien se registra con Google usando un correo que ya tiene cuenta con contraseña?**
No se vinculan automáticamente: se responde 409. Vincular por correo sin verificar la propiedad de la cuenta existente permitiría tomar el control de una cuenta ajena.

**¿Cómo evitó un open redirect en el parámetro `?next=`?**
`next` no es una URL: es una clave que se busca en una lista blanca de destinos internos (`NEXT_DESTINATIONS`). Cualquier otro valor, incluida una URL externa, se ignora y se redirige a `/`.

**¿Cómo se calcula el perfil de aprendizaje y el nivel de detalle adaptativo?**
El total de consultas es el número de filas de `query_logs` del usuario (explicaciones pedidas más regeneraciones "No entendí esto"); los instrumentos revisados se registran aparte en `InstrumentVisit`. La explicación se adapta con dos señales: la experiencia que el usuario declara al registrarse (opcional) y su comportamiento observado. Quien declara "nunca he invertido" parte con explicaciones detalladas en todos los indicadores; si el usuario regeneró un indicador 2 o más veces, ese indicador pasa a "detallado" aunque haya declarado experiencia. El comportamiento solo puede subir el nivel; la experiencia fija el punto de partida.

**¿Cómo se adapta el estilo de la explicación a cada usuario?**
Cada indicador tiene tres redacciones ordenadas por estilo: directa, conversacional y con contexto (qué suele pasar después de esa lectura). Cuando el usuario pide "No entendí esto" rota de una a otra; el sistema guarda en cuál se detuvo y esa pasa a ser el punto de partida de sus próximas consultas. Es un heurístico explicable, no un modelo de aprendizaje automático: se puede mostrar al usuario qué estilo se le aplica y por qué (sección "Cómo se adaptan tus explicaciones" del perfil).

**¿Por qué no usó un modelo de recomendación o aprendizaje automático para personalizar?**
Con pocos usuarios y pocas interacciones por persona no hay datos para entrenar nada confiable, y un modelo opaco no se puede explicar a un principiante ni defender ante la comisión. Un heurístico con reglas visibles es verificable con pruebas, y si hubiera más datos se podría reemplazar `_level_for` y `preferred_variant` sin tocar el resto. La limitación es real: con tres redacciones por pool la señal es gruesa.

**¿Qué pasa con un usuario nuevo que aún no tiene historial?**
Es el problema de arranque en frío. Se resuelve con la pregunta opcional "¿Has invertido antes?" del registro, que fija el nivel inicial; las cuentas de Google o anteriores pueden declararla después desde el perfil. Sin respuesta se usa el nivel estándar.

**¿Cómo se asegura que cambiar el estilo no haga que la explicación contradiga el dato?**
Todas las redacciones pasan por el mismo validador de coherencia (valor numérico citado, nivel de riesgo y señales cualitativas consistentes). Hay un test que recorre las 72 combinaciones de indicador × riesgo × estilo × nivel de detalle y exige que todas sean coherentes.

---

**¿De dónde salen las noticias de la portada y qué limitaciones tienen?**
Las noticias se obtienen del feed RSS público de Google News filtrado para Chile en español, que agrega titulares de medios chilenos con fuente y fecha. No es una API oficial: puede cambiar o limitar sus respuestas, por lo que el módulo está aislado y, si falla, la portada simplemente muestra que no hay noticias sin romper el resto. La cobertura por empresa es desigual; el sistema solo muestra titulares que mencionan a la empresa (por nombre o alias), así que algunas acciones aparecen como "Sin noticias recientes". Los titulares describen hechos, pero no explican por sí solos la causa de una variación de precio, y el sistema no analiza su sentimiento.

---

## IA / NLP

**¿Qué es FinBERT y para qué sirve en su sistema?**
FinBERT es un modelo de lenguaje BERT pre-entrenado en textos financieros en inglés. En el sistema se usa opcionalmente para añadir una señal de sentimiento (positivo/negativo/neutro) a las explicaciones de indicadores.

**¿Por qué FinBERT es opcional y no obligatorio?**
Requiere descargar modelos de varios GB y las bibliotecas `transformers` y `torch`. Para facilitar la instalación y ejecución del prototipo sin GPU ni conexión robusta, se dejó como opt-in mediante la variable `USE_FINBERT=true` en `.env`.

**¿Qué es el procesamiento de lenguaje natural (NLP)?**
NLP es la rama de la IA que permite a los computadores entender, interpretar y generar texto en lenguaje humano. En este sistema se usa para generar explicaciones en español de indicadores financieros técnicos que sean comprensibles para usuarios no expertos.

**¿Cómo genera el sistema explicaciones en español de indicadores financieros?**
Primero intenta un LLM (Groq) con un *system prompt* que depende del nivel del usuario; si falla, si no cita el valor exacto y el "riesgo X" calculado, o si en el nivel básico usa jerga, cae a plantillas en español redactadas para ese mismo nivel. En ambos casos el validador de coherencia contrasta el texto con el dato real. Opcionalmente, FinBERT añade una señal de sentimiento.

**¿Cómo se adaptan las explicaciones?**
Hay tres niveles, definidos en una sola "ficha" (`src/nlp/levels.py`) que usan tanto el LLM (como instrucciones del *system prompt*) como las plantillas de respaldo:

| | Básico (nunca invirtió) | Intermedio (invirtió un poco) | Avanzado (tiene experiencia) |
|---|---|---|---|
| Qué mide el indicador | siempre, con palabras simples y el dato concreto (sin analogías) | una frase corta | no se explica |
| Vocabulario | cotidiano; sin "sobrecompra", "histograma", "momentum", "volatilidad"… | se nombra el término y se traduce | técnico |
| Umbrales (70/30, %B 0–1) | no se mencionan | se nombran | umbral + lectura (cruce, agotamiento) |
| Contexto IPSA | sí | sí | no |
| Máx. palabras | 90 | 60 | 40 |

El nivel inicial lo fija la experiencia declarada al registrarse (sin respuesta → intermedio). Luego el comportamiento lo ajusta por indicador: cada 2 "No entendí esto" en un indicador baja un nivel (avanzado → intermedio → básico). Si la persona cambia su experiencia declarada, el conteo se reinicia (`users.level_reset_at`) y todos los indicadores parten del nivel nuevo. Además, el sistema aprende el estilo de redacción en que la persona se queda (directa, conversacional o con contexto) y parte por ese. El perfil muestra el nivel de cada indicador y por qué se aplica.

**¿Por qué un *system prompt* por nivel y no un solo prompt?**
Porque el nivel cambia *cómo* se habla (a quién, con qué palabras, cuánto), no *qué* dato se entrega. Separarlo deja el mensaje de usuario solo con los datos (empresa, indicador, valor, riesgo, estilo), y permite que las plantillas de respaldo y los tests usen la misma ficha: un test verifica que ninguna plantilla básica contenga jerga, que todas respeten el máximo de palabras y que todas pasen el validador.

**¿Qué tan confiables son las explicaciones generadas?**
Las explicaciones basadas en templates son deterministas y precisas dentro del dominio definido. La confiabilidad de FinBERT depende del texto de entrada y su entrenamiento. El sistema no pretende reemplazar asesoría financiera profesional; su objetivo es educativo.

---

## Arquitectura general

**¿Qué es una arquitectura MVC y la aplicó en su sistema?**
MVC (Model-View-Controller) separa la aplicación en tres capas: Model (datos y lógica de negocio), View (presentación), Controller (intermediario). En el sistema: los modelos SQLAlchemy son el Model, los templates Jinja2 y JS son la View, y las rutas Flask son el Controller.

**¿Qué es un monolito y cuándo conviene usarlo vs microservicios?**
Un monolito es una aplicación donde todos los módulos corren en el mismo proceso. Conviene para proyectos pequeños/medianos porque es más simple de desarrollar, depurar y desplegar. Los microservicios convienen cuando distintos componentes necesitan escalar de forma independiente o son desarrollados por equipos separados.

**¿Por qué eligió un monolito y no microservicios en su sistema?**
Es un proyecto individual con un solo despliegue. Los microservicios agregarían comunicación por red entre servicios, varios despliegues, observabilidad distribuida y consistencia eventual, sin un beneficio real a esta escala. El sistema es un monolito modular: `extractor/`, `nlp/`, `auth/` y `profile/` están separados por responsabilidad y se comunican por funciones públicas, como `get_price_series` o `generate_explanation`. Si en el futuro hiciera falta, cada módulo podría extraerse como servicio.

**¿Qué es una API REST?**
REST (Representational State Transfer) es un estilo de arquitectura para APIs web. Usa HTTP con URLs que identifican recursos (`/api/chart`, `/api/query`) y métodos que indican la operación (GET para consultar, POST para crear/procesar). Las respuestas son generalmente JSON.

**¿Cómo fluye un dato desde que el usuario hace clic hasta que ve el resultado?**
1. Usuario hace clic en período (ej. 3M) → JS envía `GET /api/chart?symbol=FALABELLA.SN&days=90` → Flask enruta a `api_chart()` → verifica caché TTL → si miss, llama a Yahoo Finance → calcula indicadores → devuelve JSON → JS renderiza gráfico de velas + líneas MA en pantalla.

**¿Qué es una TTLCache y por qué la usó?**
TTLCache es un caché en memoria con tiempo de expiración (Time To Live). Se usó para almacenar temporalmente los datos de precios de Yahoo Finance con TTL de 5 minutos, evitando llamadas repetidas a la API externa para el mismo instrumento y período.

---

## Decisiones de diseño

**¿Qué cambiaría del stack si tuviera que rehacer el proyecto?**
Consideraría FastAPI en lugar de Flask para mejor soporte asíncrono y documentación automática de API. Podría evaluar un servicio de colas para generar explicaciones con LLM de forma asíncrona. En el frontend, posiblemente HTMX para interactividad sin la complejidad de React.

**¿Qué deuda técnica dejó pendiente y por qué?**
Una caché de precios distribuida (hoy `TTLCache` en memoria, propia de cada worker) y migraciones con pruebas automáticas contra datos reales. FinBERT no descargado en el entorno de desarrollo. El legend del gráfico MA es estático y no refleja las ventanas reales calculadas dinámicamente.

**¿Cómo garantizó que el sistema funciona correctamente?**
Mediante 96 tests automatizados con pytest que cubren autenticación, concurrencia, extracción de indicadores y rutas principales. Los tests se ejecutan con `pytest` desde la raíz del proyecto.

**¿Cómo manejaría el despliegue en producción de este sistema?**
Flask con gunicorn (varios workers) detrás de un proxy inverso o PaaS que termina HTTPS. La base de datos es un nodo PostgreSQL gestionado y separado (TLS `sslmode=require`, respaldos automáticos). El esquema se aplica con `flask db upgrade` en cada despliegue. Variables de entorno (`DATABASE_URL`, `FLASK_SECRET_KEY`, etc.) gestionadas de forma segura. Contenedorizado con Docker para portabilidad.

**¿Qué haría diferente si el sistema debiera soportar 10.000 usuarios concurrentes?**
Dimensionar el pool de conexiones de PostgreSQL (o añadir PgBouncer y réplicas de lectura), usar Redis para caché distribuida en lugar de TTLCache en memoria, desplegar múltiples instancias Flask con un balanceador de carga, y posiblemente separar el módulo NLP/IA como un microservicio independiente dado su costo computacional.

**¿Por qué el historial está en el perfil y no en una página aparte?**
Porque es información personal de la cuenta. Antes vivía en la cookie de sesión (se perdía al cerrar el navegador y solo guardaba las últimas 5 consultas). Ahora cada explicación pedida se guarda en `query_logs` con su valor, riesgo, fuente y ventana, y se muestra en la pestaña "Historial" de `/perfil`, junto a las acciones revisadas. El costo es que un visitante sin cuenta ya no tiene historial; es coherente con que el perfil de aprendizaje también requiere sesión.
