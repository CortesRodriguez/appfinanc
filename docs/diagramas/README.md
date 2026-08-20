# Diagramas de diseño — appfint

Todos los diagramas están en Mermaid, embebidos en archivos `.md` versionados junto al código. La convención de colores es común a todos los tipos:

| Prefijo | Rol | Color (estructurales) | Ejemplos en los diagramas de secuencia |
|---|---|---|---|
| `V_` | Vista (lo que ve el usuario) | Verde `#D5E8D4` | `V_Login`, `V_Registro`, `V_Dashboard` |
| `C_` | Controlador — endpoint Flask **o** servicio de dominio **o** gestor de BD | Azul `#DAE8FC` | `C_APIQuery`, `C_Autenticación`, `C_Extractor`, `C_NLP`, `C_Coherencia`, `C_SQLite` |
| `ext_` | Fuente externa | Rosado `#F8CECC` | `ext_YahooFinance`, `ext_AlphaVantage`, `ext_MindicadorCL` |
| `T_` | Tabla específica de la base de datos | Beige `#FFE6CC` | `T_users`, `T_query_logs`, `T_coherence_checks`, `T_evaluation_sessions` |

**Sobre `C_SQLite`**: representa el gestor de BD (la capa que abre la conexión y ejecuta el SQL). En el código real es SQLAlchemy sobre el archivo `appfint.db`. Aparece como participante propio en los diagramas de secuencia siguiendo la convención UML pedida (el profesor lo llama "controlador MySQL" por plantilla — el patrón es el mismo, solo cambia el motor de BD).

## Cómo verlos

### En VS Code (recomendado)

Instalar dos extensiones (una vez):

1. **Markdown Preview Mermaid Support** (`bierner.markdown-mermaid`) → renderiza los bloques ```` ```mermaid ```` al abrir cualquier `.md` con `Cmd+Shift+V`.
2. **SQLite Viewer** (`qwtel.sqlite-viewer`) → doble-clic sobre `appfint.db` muestra las 7 tablas como en DBeaver / DataGrip, con filtros y ordenamiento por columna. Complemento visual del [ER](bd/er-base-de-datos.md).

Con esas dos extensiones tienes **todo conectado en la misma ventana**: los diagramas se renderizan al abrirlos y la BD se explora como tabla sin salir del editor.

### En la web

Pegar el contenido de cada bloque ```` ```mermaid ```` en <https://mermaid.live>.

### Exportar a PNG/SVG para el informe

En mermaid.live → botón **Actions** → **PNG** o **SVG** → pegar en el `.docx` del anteproyecto.

## Estructura por carpeta

```
docs/diagramas/
├── bd/            — modelo entidad-relación (SQLAlchemy → SQLite)
├── componentes/   — vista estática de módulos y dependencias internas
├── despliegue/    — nodos físicos, procesos y conexiones de red
└── secuencia/     — un diagrama por caso de uso (CU-01, CU-11, CU-12, ...)
```

## Índice

### Estructural

| Diagrama | Archivo | Descripción |
|---|---|---|
| Entidad-relación de `appfint.db` | [bd/er-base-de-datos.md](bd/er-base-de-datos.md) | Las 7 tablas reales y sus FKs. |
| Componentes | [componentes/componentes.md](componentes/componentes.md) | Paquetes Python bajo `src/` y sus dependencias. |
| Despliegue | [despliegue/despliegue.md](despliegue/despliegue.md) | Proceso Flask local + fuentes externas HTTPS. |

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
3. **CU-06 / CU-07** — Responder encuesta pre / post (RF-11, RF-12).
4. **CU-08** — Revisar coherencia semántica en `/admin/coherencia` (RF-13).
5. **CU-09 / CU-10** — Ver reporte / exportar CSV (RF-15).
6. **CU-13** — Ver perfil adaptativo (RF-18, RF-19).
