# Fase 4 — Diagrama de componentes

**Notación**: UML 2.5, sintaxis PlantUML. Componentes con estereotipo `<<component>>`; interfaces provistas/requeridas mediante notación *ball-and-socket*; líneas simples (`--`) para conexiones (la comunicación HTTP es petición/respuesta, no dirigida).

**Grounding**: cada componente y cada línea de este diagrama corresponde a un módulo o import verificable en `src/`. La tabla de trazabilidad al final lista el paquete Python asociado a cada componente.

## Diagrama

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam packageStyle rectangle
skinparam shadowing false
skinparam defaultFontName "Helvetica"

skinparam component {
  BackgroundColor<<arch>>     #FFE4B5
  BorderColor<<arch>>         #C79020
  BackgroundColor<<negocio>>  #D8BFD8
  BorderColor<<negocio>>      #7B4B94
}

actor Usuario

interface "Consultas HTTP"           as IWeb
interface "Precios Históricos"       as IPrecios
interface "Indicadores Macro Chile"  as IMacro
interface "Cuentas y Consultas"      as IBD

package "Aplicación web (Flask · Jinja2 · Vanilla JS)" {

  ' --- Componentes de arquitectura genérica (routing, auth, sesión) ---
  component "Enrutar Consulta y\nRegenerar Explicación"   <<arch>>  as Consulta
  component "Registro Cuenta Nueva"                       <<arch>>  as Registro
  component "Iniciar / Cerrar Sesión"                     <<arch>>  as Sesion

  ' --- Componentes de lógica de negocio específica ---
  component "Obtener Precios"                                          <<negocio>>  as ObtenerPrecios
  component "Calcular Indicadores\n(RSI · MACD · MA · Bollinger)"     <<negocio>>  as CalcularInd
  component "Obtener Indicadores Macro"                                <<negocio>>  as ObtenerMacro
  component "Clasificar Sentimiento\n(FinBERT, opcional)"              <<negocio>>  as Clasificar
  component "Generar Explicación\n(LLM + Plantillas ES de respaldo)"   <<negocio>>  as Generar
  component "Validar Coherencia"                                      <<negocio>>  as Validar
  component "Perfil Adaptativo\n(nivel de detalle por historial)"     <<negocio>>  as Perfil
}

package "PostgreSQL (SQLAlchemy)" as PackBD {
  [Cuentas de Usuario]                      as TCuentas
  [Registro de Consultas]                   as TConsultas
}

package "Servicios Externos" as PackExt {
  [yfinance / Yahoo Finance]  as Yahoo
  [Alpha Vantage]             as Alpha
  [Groq (LLM)]                as Groq
  [mindicador.cl (BCCh)]      as BCCh
}

' El usuario accede al sistema por HTTP
Usuario -- IWeb
IWeb -- Consulta
IWeb -- Registro
IWeb -- Sesion

' Las rutas orquestan la lógica de negocio
Consulta -- ObtenerPrecios
Consulta -- CalcularInd
Consulta -- Clasificar
Consulta -- Generar
Consulta -- Validar
Consulta -- Perfil
Consulta -- ObtenerMacro
Sesion -- Perfil

' Dependencias internas de la lógica de negocio (composición del texto)
Generar -- Clasificar : "sentimiento como insumo"
Generar -- Validar    : "coherencia post-redacción"
Generar -- Groq       : "redacción (opcional, con respaldo)"

' La lógica de negocio consume servicios externos vía interfaces nombradas
ObtenerPrecios -- IPrecios
IPrecios -- Yahoo
IPrecios -- Alpha
ObtenerMacro -- IMacro
IMacro -- BCCh

' Persistencia
Registro       -- IBD
Sesion         -- IBD
Consulta       -- IBD
Perfil         -- IBD
IBD -- PackBD

note right of Clasificar
  FinBERT es opcional (USE_FINBERT=false
  por defecto) y solo aporta una etiqueta
  de sentimiento. Si no está disponible,
  el sistema sigue sin ella (RNF-09).
end note

note right of Generar
  Si el LLM no responde o su salida no
  pasa la verificación, se usan las
  plantillas, coherentes por construcción
  (RNF-09).
end note

@enduml
```

## Responsabilidades por componente

| Componente | Estereotipo | Responsabilidad |
|---|---|---|
| **Enrutar Consulta y Regenerar Explicación** | arch | Recibe las peticiones HTTP del dashboard y las regeneraciones; compone la respuesta con datos financieros + explicación NLP + registro de la consulta (RF-07, RF-08, RF-06.2). |
| **Registro Cuenta Nueva** | arch | Crea cuentas con nombre de usuario, correo y contraseña (o Google). Hashea la contraseña con bcrypt (RF-11, RNF-06.1). |
| **Iniciar / Cerrar Sesión** | arch | Autenticación por correo/contraseña con JWT en cookie httpOnly; logout revoca el token (RF-12, RNF-06.2). |
| **Obtener Precios** | negocio | Consulta precios históricos vía yfinance; si Yahoo falla, hace fallback automático a Alpha Vantage (RF-02.1, RNF-09). |
| **Calcular Indicadores** | negocio | Calcula los cuatro indicadores oficiales: RSI, medias móviles, MACD y Bandas de Bollinger, con los umbrales cualitativos de RF-04.2. |
| **Obtener Indicadores Macro** | negocio | Consulta UF, dólar, TPM e IPC a mindicador.cl para la cinta de precios (RF-02.3, RF-07.4). |
| **Clasificar Sentimiento (FinBERT)** | negocio | Componente opcional (RF-04.1, `USE_FINBERT`). Clasifica el sentimiento del indicador y entrega una etiqueta que la interfaz muestra como insignia; no redacta el texto. Si el modelo no está disponible, se omite sin afectar la explicación. |
| **Generar Explicación** | negocio | Redacta la explicación en español según la ficha del nivel del usuario: con el LLM (Groq, `qwen/qwen3.8-27b`) si está activo y su salida pasa la verificación mínima (riesgo, valor, términos prohibidos); si no, con plantillas con variantes que usan los valores reales del indicador (RF-04.1, RF-05.1). |
| **Validar Coherencia** | negocio | Contrasta la explicación generada con el dato numérico y con los umbrales cualitativos; marca como no coherentes (`coherent=false`) los casos discordantes; la interfaz muestra un aviso (RF-04.2). |
| **Perfil Adaptativo** | negocio | Ajusta el nivel de detalle de las explicaciones al historial del usuario (RF-13.2). |
| **Cuentas de Usuario** | (dato) | Tablas `users` (con nivel de experiencia declarado y bloqueo por intentos fallidos) y `revoked_tokens`. |
| **Registro de Consultas** | (dato) | Tabla `query_logs` + `instrument_visits`; cada fila lleva el `session_id` de Flask y, si hay sesión iniciada, el `user_id`. |

## Dependencias (qué transporta cada línea)

| Origen ↔ Destino | Qué transporta |
|---|---|
| Usuario ↔ IWeb ↔ (Consulta, Registro, Sesión) | Peticiones HTTP y respuestas (Flask maneja la conversación completa) |
| Consulta ↔ Obtener Precios | Símbolo del instrumento y rango temporal → serie de precios |
| Consulta ↔ Calcular Indicadores | Serie de precios → valor + nivel de riesgo del indicador |
| Consulta ↔ Obtener Indicadores Macro | (sin datos de entrada) → UF, dólar, TPM, IPC |
| Consulta ↔ Perfil Adaptativo | `user_id` + indicador → nivel de detalle a usar |
| Generar Explicación ↔ Clasificar Sentimiento | Frase del indicador → etiqueta de sentimiento (opcional, solo informativa) |
| Generar Explicación ↔ Groq | Prompt con la ficha del nivel + datos del indicador → texto (opcional, con respaldo en plantillas) |
| Generar Explicación ↔ Validar Coherencia | Texto generado + dato del indicador → veredicto de coherencia |
| Obtener Precios ↔ IPrecios ↔ (Yahoo, Alpha Vantage) | Símbolo → OHLC diario |
| Obtener Indicadores Macro ↔ IMacro ↔ BCCh | (sin entrada) → dict con UF/dólar/TPM/IPC |
| (Registro, Sesión, Consulta, Perfil) ↔ IBD ↔ PostgreSQL | Escrituras y lecturas relacionales vía SQLAlchemy (psycopg 3, TCP 5432/TLS) |

## Trazabilidad componente → código Python

| Componente del diagrama | Archivo / módulo real |
|---|---|
| Enrutar Consulta y Regenerar Explicación | `src/web/routes.py:api_query`, `api_regenerate`, `_run_query`, `_log_and_validate` |
| Registro Cuenta Nueva | `src/auth/routes.py:api_register` + `src/auth/service.py:register_user` |
| Iniciar / Cerrar Sesión | `src/auth/routes.py:api_login`, `api_logout` + `authenticate_user` |
| Obtener Precios | `src/extractor/sources.py:fetch_price_history` |
| Calcular Indicadores | `src/extractor/indicators.py` (`compute_rsi`, `compute_moving_averages`, `compute_macd`, `compute_bollinger_bands`) |
| Obtener Indicadores Macro | `src/extractor/sources.py:fetch_macro_indicators` |
| Clasificar Sentimiento (FinBERT) | `src/nlp/explainer.py:_finbert_signal` |
| Generar Explicación | `src/nlp/explainer.py:generate_explanation`, `regenerate_explanation` |
| Validar Coherencia | `src/nlp/validator.py:validate_coherence` |
| Perfil Adaptativo | `src/profile/service.py:get_detail_level`, `build_learning_profile` |
| Cuentas de Usuario | `src/auth/models.py:User`, `RevokedToken` |
| Registro de Consultas | `src/profile/models.py:QueryLog`, `InstrumentVisit` |

## Reglas de dependencia (contrato de diseño)

Estas reglas explican por qué el diagrama tiene las líneas que tiene, y no otras. Cualquier conexión faltante en el diagrama es una prohibición explícita.

1. **El Presentador es el único orquestador**: `Enrutar Consulta y Regenerar Explicación` es el único componente que compone servicios de dominio dentro de una misma petición HTTP. Los componentes de lógica de negocio no se invocan entre sí en cadena (salvo la dependencia explícita entre `Generar Explicación` y `Clasificar Sentimiento`/`Validar Coherencia`, que forman el pipeline NLP).

2. **`Obtener Precios` no persiste**: los datos financieros son efímeros (RNF-08.1). Solo viven una caché en memoria durante 5 minutos. La base de datos no contiene ninguna fila de precios ni indicadores calculados.

3. **`Generar Explicación` no consulta la base de datos** ni llama a `Obtener Precios`. Recibe el dato del indicador como entrada y devuelve la explicación como salida. La persistencia del texto la hace `Enrutar Consulta y Regenerar Explicación`.

4. **Los servicios externos se consumen solo desde la lógica de negocio** (`Obtener Precios`, `Obtener Indicadores Macro`) a través de las interfaces `Precios Históricos` y `Indicadores Macro Chile`. Cambiar de proveedor no afecta a las demás capas.

5. **Datos personales mínimos**: los datos identificables viven solo en `users`; `query_logs` e `instrument_visits` referencian `user_id` y no copian correo ni nombre. Es la propiedad estructural que sostiene el RNF-05.

## Deuda arquitectónica identificada

Estas son inconsistencias entre las reglas de diseño y el código actual. **No afectan el funcionamiento** del sistema y no se reflejan en el diagrama (que muestra el diseño intencional), pero conviene documentarlas como mejoras futuras:

1. **Acceso al ORM difuso**. Nueve archivos de `src/` importan `db` de `src.extensions` y ocho llaman `db.session.*` directamente en distintas capas (services, routes, `__init__.py`). Un patrón *Repository* centralizado en `src/repositories/` reduciría la superficie de acceso a la persistencia a un único punto. Costo estimado: 1-2 días; ~15 archivos afectados. Los ejemplos de referencia de proyectos aprobados en la carrera tampoco cumplen esta regla, por lo que la deuda es aceptable en el marco del prototipo.

2. **Doble punto de orquestación**. `src/profile/routes.py` (líneas 10-14) importa `get_indicator` y `generate_explanation`, replicando la orquestación de `src/web/routes.py`. El diagrama de arriba muestra el diseño objetivo (un solo Presentador orquestando `Perfil Adaptativo`), pero en el código hay dos routes que orquestan. Refactor sugerido: extraer `src/services/query_service.py` con `run_query()` y `regenerate()`; ambos routes delegan allí. Costo estimado: medio día.

## Cómo renderizar este diagrama

- **VS Code**: extensión *PlantUML* (jebbs.plantuml), `Alt+D` sobre el bloque `plantuml`.
- **Online**: pegar el contenido entre `@startuml` y `@enduml` en [https://plantuml.com/plantuml/uml/](https://plantuml.com/plantuml/uml/).
- **En una imagen para la memoria**: exportar como PNG o SVG desde VS Code o desde el servidor de PlantUML.
