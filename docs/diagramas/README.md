# Diagramas de diseño — appfint

Todos los diagramas están en Mermaid, embebidos en archivos `.md` versionados junto al código. La convención de colores es común a todos los tipos:

| Prefijo | Rol | Color (estructurales) | Ejemplos en los diagramas de secuencia |
|---|---|---|---|
| `V_` | Vista (lo que ve el usuario) | Verde `#D5E8D4` | `V_Login`, `V_Registro`, `V_Dashboard` |
| `C_` | Controlador — endpoint Flask **o** servicio de dominio **o** gestor de BD | Azul `#DAE8FC` | `C_APIQuery`, `C_Autenticación`, `C_Extractor`, `C_NLP`, `C_Coherencia`, `C_PostgreSQL` |
| `ext_` | Fuente externa | Rosado `#F8CECC` | `ext_YahooFinance`, `ext_AlphaVantage`, `ext_MindicadorCL` |
| `T_` | Tabla específica de la base de datos | Beige `#FFE6CC` | `T_users`, `T_query_logs`, `T_instrument_visits`, `T_revoked_tokens` |

**Sobre `C_PostgreSQL`**: representa el gestor de BD (la capa que abre la conexión y ejecuta el SQL). En el código real es SQLAlchemy (driver psycopg 3) conectado por TCP al servidor PostgreSQL, base `appfint`. Aparece como participante propio en los diagramas de secuencia siguiendo la convención UML pedida (el profesor lo llama "controlador MySQL" por plantilla — el patrón es el mismo, solo cambia el motor de BD).

## Cómo verlos

### En VS Code (recomendado)

Instalar dos extensiones (una vez):

1. **Markdown Preview Mermaid Support** (`bierner.markdown-mermaid`) → renderiza los bloques ```` ```mermaid ```` al abrir cualquier `.md` con `Cmd+Shift+V`.
2. **Un cliente de PostgreSQL** para explorar la base `appfint`: en terminal, `psql -d appfint` y luego `\dt` (lista las 4 tablas) o `\d users` (columnas, índices y FKs); en interfaz gráfica, pgAdmin, DBeaver o TablePlus, o la extensión **PostgreSQL** de VS Code (`ms-ossdata.vscode-pgsql`), que muestra las tablas con filtros y ordenamiento por columna. Complemento visual del [modelo de la BD](bd/ED%20BBDD.md) y del [DDL](bd/DDL_APPFINT_DATABASE.sql).

Con esas dos extensiones tienes **todo conectado en la misma ventana**: los diagramas se renderizan al abrirlos y la BD se explora como tabla sin salir del editor.

### En la web

Pegar el contenido de cada bloque ```` ```mermaid ```` en <https://mermaid.live>.

### Exportar a PNG/SVG para el informe

En mermaid.live → botón **Actions** → **PNG** o **SVG** → pegar en el `.docx` del anteproyecto.

## Estructura por carpeta

```
docs/diagramas/
├── bd/            — modelo entidad-relación y DDL (SQLAlchemy → PostgreSQL)
├── componentes/   — vista estática de módulos y dependencias internas
├── despliegue/    — nodos físicos, procesos y conexiones de red
└── secuencia/     — un diagrama por caso de uso (CU-01, CU-11, CU-12, ...)
```

## Índice

### Estructural

| Diagrama | Archivo | Descripción |
|---|---|---|
| Entidad-relación de la base `appfint` | [bd/ED BBDD.md](bd/ED%20BBDD.md) | Las 4 tablas reales y sus FKs. |
| DDL PostgreSQL | [bd/DDL_APPFINT_DATABASE.sql](bd/DDL_APPFINT_DATABASE.sql) | `CREATE TABLE` equivalente a la migración `0001_esquema_inicial`. |
| Componentes | [componentes/componentes.md](componentes/componentes.md) | Paquetes Python bajo `src/` y sus dependencias. |
| Despliegue | [despliegue/despliegue.md](despliegue/despliegue.md) | Proxy HTTPS + gunicorn/Flask + nodo PostgreSQL separado + fuentes externas HTTPS. |

### Secuencia (casos de uso)

| CU | Descripción | Archivo |
|---|---|---|
| CU-01 | Consultar indicador financiero | [secuencia/cu-01-consultar-indicador.md](secuencia/cu-01-consultar-indicador.md) |
| CU-11 | Registro de usuario (modal) | [secuencia/cu-11-registro.md](secuencia/cu-11-registro.md) |
| CU-12 | Inicio de sesión (modal) | [secuencia/cu-12-login.md](secuencia/cu-12-login.md) |

## Casos de uso pendientes por diagramar

Faltan por dibujar (mismo estilo y misma carpeta `secuencia/`). Sugerencia de orden de prioridad para el informe:

1. **CU-02** — Cambiar rango temporal / intervalo de vela del gráfico (usa el buffer estático de 10 años).
2. **CU-04** — Regenerar explicación ("No entendí"), con lógica de detalle adaptativo (RF-18.3).
3. **CU-13** — Ver perfil adaptativo (RF-18, RF-19).
