# Diagrama de componentes — appfint
## 🎤 Cómo Explicar Mañana

### Versión Corta (30 segundos):
> "El diagrama muestra 4 capas: Cliente Web (lo que ve el usuario), 
> Servidor Backend (5 módulos que calculan), Base de Datos (para guardar), 
> y APIs Externas (para obtener precios). Todo conectado con HTTP/REST 
> y SQL."

### Versión Media (1 minuto):
> "La arquitectura es en capas. El usuario interactúa con el Frontend 
> (HTML/JS). El Frontend hace requests HTTP al Backend, que es un servidor 
> Flask con 5 módulos: Routes (orquestación), Extractor (calcula indicadores), 
> NLP (genera explicaciones), Auth (valida usuario), Profile (personaliza 
> nivel). El Backend consulta APIs externas para precios (Yahoo Finance), 
> usa caché para reutilizar, y guarda auditoría en PostgreSQL. Todo normalizado 
> en capas."

### Versión Larga (2 minutos):
> "Este diagrama de componentes muestra la Vista de Desarrollo: cómo está 
> implementada la aplicación.
>
> Tenemos 4 capas. La primera es el Cliente Web: HTML, CSS, JavaScript. 
> El usuario ve un dashboard con dropdown de acciones. Hace clic, el 
> Frontend manda HTTP requests al Backend.
>
> El Backend es el corazón: Flask + Python. Tiene 5 módulos internos. 
> Routes es el director: recibe peticiones, orquesta los otros 4. 
> Extractor calcula indicadores (RSI, MACD, etc.) usando matemática. 
> NLP genera explicaciones en español usando plantillas y opcional FinBERT. 
> Auth verifica que el usuario sea válido con JWT. Profile decide si mostrar 
> explicación simple o avanzada según cuántas veces el usuario regeneró.
>
> El Backend también maneja caché en memoria: si alguien consultó APPLE 
> hace 2 minutos, reutiliza los precios (caché, <100ms). Si no está en 
> caché, consulta Yahoo Finance (4-5 segundos), almacena en caché, y 
> sigue adelante.
>
> La tercera capa es Base de Datos: PostgreSQL con 4 tablas, en un servidor 
> separado. Guarda usuarios, historial de consultas, y datos para el perfil 
> adaptativo. Como vive aparte, los datos sobreviven a cada redespliegue.
>
> La cuarta capa son APIs externas: Yahoo Finance para precios. Si Yahoo 
> falla, Alpha Vantage es fallback.
>
> Todo conectado: Usuario → Frontend → Backend → Datos → APIs → 
> Indicadores → Explicaciones → Frontend → Usuario."

---

## 📋 Componentes Internos del Backend

```
┌────────────────────────────────────────────────────────────┐
│          SERVIDOR BACKEND (Flask/Python)                   │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Web/Routes (Orquestación)                            │  │
│  │ └─ Recibe peticiones HTTP                            │  │
│  │ └─ Coordina los 5 módulos                            │  │
│  │ └─ Retorna JSON                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │  Extractor   │  │     NLP      │  │      Auth         │ │
│  ├──────────────┤  ├──────────────┤  ├───────────────────┤ │
│  │ Calcula:     │  │ Genera en    │  │ Valida JWT        │ │
│  │ • RSI        │  │ español:     │  │ Verifica revoked_ │ │
│  │ • MA         │  │ • Simple     │  │ tokens            │ │
│  │ • MACD       │  │ • Avanzada   │  │                   │ │
│  │ • Bollinger  │  │ • Sentimiento│  │                   │ │
│  │              │  │ (FinBERT)    │  │                   │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
│                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │  Profile     │  │  Caché TTL (En memoria)              │ │
│  ├──────────────┤  ├──────────────────────────────────────┤ │
│  │ Decide:      │  │ TTL = 5 minutos                      │ │
│  │ • Nivel      │  │ Reutiliza precios                    │ │
│  │   simple vs  │  │ <100ms vs 4-5 segundos               │ │
│  │   avanzada   │  │                                      │ │
│  │ • Basado en  │  │                                      │ │
│  │   historial  │  │                                      │ │
│  │   de usuario │  │                                      │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

---

## ✅ Relaciones Entre Capas

| Relación | Protocolo | Tiempo | Contenido |
|----------|-----------|--------|-----------|
| Usuario → Frontend | HTTP (navegador) | ~10ms | Clicks, selecciones |
| Frontend → Backend | HTTP/REST (AJAX) | ~50-100ms | JSON requests |
| Backend → BD | SQL sobre TCP 5432 (TLS) | ~2-10ms | Inserts, queries |
| Backend → APIs | HTTPS | 4-5s primero, <100ms caché | Precios históricos |

---

## 📁 Archivos en el Diagrama

| Componente | Archivo(s) |
|------------|-----------|
| **Frontend** | `src/web/templates/dashboard.html` |
| | `src/web/static/js/dashboard.js` |
| | `src/web/static/css/styles.css` |
| **Routes** | `src/web/routes.py` |
| **Extractor** | `src/extractor/__init__.py` |
| | `src/extractor/indicators.py` |
| | `src/extractor/sources.py` |
| **NLP** | `src/nlp/__init__.py` |
| | `src/nlp/templates.py` |
| **Auth** | `src/auth/models.py` |
| | `src/auth/__init__.py` |
| **Profile** | `src/profile/service.py` |
| **BD** | PostgreSQL, base `appfint` (modelos en `src/auth/models.py`, `src/evaluation/models.py`; esquema en `migrations/versions/0001_esquema_inicial.py`) |

---

## 🎯 Preguntas que Podrían Hacer

### P: "¿Por qué 5 módulos en el backend?"
R: "Separación de responsabilidades (SOLID). Cada módulo hace una cosa: 
Extractor calcula, NLP explica, Auth asegura, Profile personaliza, 
Routes orquesta. Fácil de mantener y testear."

### P: "¿Por qué caché en memoria?"
R: "Porque consultar Yahoo Finance tarda 4-5 segundos. Si dos usuarios 
consultan APPLE al mismo tiempo, uno espera. Con caché, el segundo obtiene 
datos en <100ms. TTL 5 minutos es compromiso: datos frescos pero reutilizado."

### P: "¿Y si el caché se llena?"
R: "TTLCache tiene límite (1000 entradas). Si se llena, elimina las más 
antiguas. O si expira el TTL (5 min), se elimina automáticamente."

### P: "¿Qué pasa si Yahoo Finance no responde?"
R: "El backend reintenta 3 veces. Si sigue fallando, usa Alpha Vantage 
como fallback. Si ambas fallan, retorna error 502."

### P: "¿Por qué PostgreSQL?"
R: "Porque guardamos datos personales (correos, hashes bcrypt) que tienen 
que sobrevivir a los redespliegues: PostgreSQL corre en un nodo aparte del 
contenedor de Flask. Además soporta escrituras concurrentes reales (MVCC) 
de varios workers de gunicorn, tiene respaldos gestionados, TLS y valida 
tipos y largos estrictamente. El esquema se versiona con Alembic 
(`flask db upgrade`). Se evaluaron SQLite (archivo local, un solo escritor) 
y MySQL, pero PostgreSQL era la opción más robusta con SQLAlchemy."

### P: "¿Cómo se personaliza la explicación?"
R: "El módulo Profile verifica: 'Este usuario regeneró RSI 2+ veces'. 
Si sí, usa template 'advanced' (explicación más detallada). Si no, 
usa 'simple'."

---