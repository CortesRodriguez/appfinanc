# Diagrama ER - Explicación para Mañana

## 📊 El Diagrama

```
erDiagram
    users ||--o{ query_logs : "id → user_id"
    users ||--o{ instrument_visits : "id → user_id"

    users {
        int id PK
        string(80) username
        string(255) email UK 
        string(255) password_hash 
        datetime created_at
    }

    revoked_tokens {
        string(64) jti PK 
        datetime revoked_at
    }

    query_logs {
        int id PK
        string(36) session_id
        string(20) instrument
        string(20) indicator
        string(30) source 
        int processing_time_ms
        int user_id FK
        boolean is_regeneration
        text explanation_text
        int variant
        datetime created_at
    }

    instrument_visits {
        int id PK
        int user_id FK
        string(20) instrument
        datetime created_at
    }
```

---

## 🔤 Decodificar los Símbolos

### Símbolos de Relación: `||--o{`

| Símbolo | Significa |
|---------|-----------|
| `\|\|` | "Uno y solo uno" (lado izquierdo) |
| `--` | "Se relaciona con" |
| `o{` | "Cero o muchos" (lado derecho) |

**Ejemplo:** `users ||--o{ query_logs`
- `||` = Un usuario (1)
- `--` = Se relaciona con
- `o{` = Cero o muchas consultas

→ **"1 usuario puede tener 0 o muchas consultas"**

---

## 🏷️ Abreviaturas en Campos

| Abreviatura | Significa | Ejemplo |
|-------------|-----------|---------|
| **PK** | Primary Key (clave primaria) | `id PK` → id es único |
| **FK** | Foreign Key (clave foránea) | `user_id FK` → referencia a otra tabla |
| **UK** | Unique Key (clave única) | `email UK` → no hay dos iguales |
| **string(N)** | Texto de N caracteres | `string(80)` → máx 80 caracteres |
| **int** | Número entero | `int id`, `int processing_time_ms` |
| **boolean** | Verdadero/Falso | `boolean is_regeneration` |
| **text** | Texto largo | `text explanation_text` |
| **datetime** | Fecha y hora | `datetime created_at` |

---

## 📍 Las 4 Tablas Explicadas

### 1️⃣ TABLA: `users`

```
users {
    int id PK
    string(80) username UK
    string(255) email UK 
    string(255) password_hash   (NULL si la cuenta es de Google)
    string(255) google_id UK   (NULL si la cuenta usa contraseña)
    timestamptz created_at
}
```

**¿Qué es?** Tabla de usuarios registrados (con contraseña o con cuenta de Google)

**Campos:**
- `id PK` → Identificador único (1, 2, 3...)
  - Cada usuario tiene un id distinto
  - Se usa para buscar rápido
  
- `username` → Nombre de usuario
  - Ej: "juan", "maria"
  - Text de hasta 80 caracteres
  
- `email UK` → Email único
  - Ej: "juan@example.com"
  - `UK` = Unique Key = no pueden haber dos usuarios con el mismo email
  - Se usa para login
  
- `password_hash` → Contraseña encriptada
  - Ej: "$2b$16$....." (bcrypt)
  - NUNCA se guarda la contraseña en plano
  - ¿Por qué hash? Si alguien roba la BD, no puede leer contraseñas
  
- `created_at` → Timestamp de registro
  - Ej: "2026-08-21 10:30:00"
  - Cuándo se registró el usuario

**Ejemplo de 2 filas:**
```
| id | username | email            | password_hash           | created_at          |
|----|----------|------------------|------------------------|---------------------|
| 1  | juan     | juan@example.com | $2b$16$xYz...         | 2026-08-21 10:30:00 |
| 2  | maria    | maria@example.com| $2b$16$aBc...         | 2026-08-21 11:00:00 |
```

---

### 2️⃣ TABLA: `revoked_tokens`

```
revoked_tokens {
    string(64) jti PK 
    datetime revoked_at
}
```

**¿Qué es?** Lista negra de tokens revocados (logout)

**Campos:**
- `jti PK` → JWT ID (identificador del token)
  - Ej: "eyJ0eXAiOiJKV1..." (64 caracteres)
  - `PK` = clave primaria (único)
  - Se extrae del JWT cuando usuario hace logout
  
- `revoked_at` → Cuándo se revocó
  - Ej: "2026-08-21 12:00:00"

**¿Por qué existe?**
- Cuando usuario cierra sesión, su JWT se invalida
- Se agrega a esta lista negra
- Próximas consultas verifican: "¿Este token está revocado?"
- Si sí → "Acceso denegado" (401)

**Ejemplo:**
```
| jti                | revoked_at          |
|--------------------|---------------------|
| eyJ0eXAi... | 2026-08-21 12:00:00 |
| eyJ1bGVy... | 2026-08-21 13:15:00 |
```

---

### 3️⃣ TABLA: `query_logs`

```
query_logs {
    int id PK
    string(36) session_id
    string(20) instrument
    string(20) indicator
    string(30) source 
    int processing_time_ms
    int user_id FK
    boolean is_regeneration
    text explanation_text
    int variant
    datetime created_at
}
```

**¿Qué es?** Historial de TODAS las consultas de indicadores

**Campos:**
- `id PK` → Identificador único de consulta
  
- `session_id` → Agrupa consultas del mismo usuario
  - Ej: "uuid-123-456"
  
- `instrument` → Símbolo de acción
  - Ej: "AAPL.SN", "GOOGL.SN"
  
- `indicator` → Indicador consultado
  - Ej: "rsi", "macd", "medias_moviles"
  
- `source` → De dónde vinieron los datos
  - Ej: "yahoo_finance" (primera vez, lento)
  - Ej: "cache" (segunda vez, rápido)
  - Ej: "alpha_vantage" (fallback)
  
- `processing_time_ms` → Tiempo en milisegundos
  - Ej: 4500 (4.5 segundos)
  - ¿Por qué? Verificar RNF-01: respuesta < 5 segundos
  
- `user_id FK` → Quién hizo la consulta
  - Ej: 1 (usuario id=1)
  - `FK` = Foreign Key = referencia a users.id
  - **Importante:** Es NULL si fue usuario anónimo
  
- `is_regeneration` → ¿Fue regenerada?
  - `0` = no (consulta original)
  - `1` = sí (usuario hizo clic "No entendí, regenera")
  
- `explanation_text` → La explicación generada
  - Ej: "El RSI está en máximo, indicador de sobrecompra..."
  - Se almacena para auditoría
  
- `variant` → Número de variante
  - `0` = original
  - `1` = regenerada una vez
  - `2` = regenerada dos veces
  - Etc.
  
- `created_at` → Timestamp de la consulta

**Ejemplo:**
```
| id | instrument | indicator | source       | processing_time_ms | user_id | is_regeneration | variant |
|----|------------|-----------|--------------|-------------------|---------|-----------------|---------|
| 42 | AAPL.SN    | rsi       | yahoo_finance| 4500               | 1       | 0               | 0       |
| 43 | AAPL.SN    | rsi       | cache        | 50                 | 1       | 1               | 1       |
| 44 | GOOGL.SN   | macd      | yahoo_finance| 3800               | NULL    | 0               | 0       |
```

**¿Qué preguntas responde?**
- "¿Cuántas veces se consultó RSI?" → COUNT(*) WHERE indicator='rsi'
- "¿Cuál es el tiempo promedio?" → AVG(processing_time_ms)
- "¿Cuántos usuarios regeneraron?" → COUNT(DISTINCT user_id) WHERE is_regeneration=1
- "¿Qué usuario consultó qué?" → SELECT * WHERE user_id=1

---

### 4️⃣ TABLA: `instrument_visits`

```
instrument_visits {
    int id PK
    int user_id FK
    string(20) instrument
    datetime created_at
}
```

**¿Qué es?** Resumen: qué acciones vio cada usuario

**Campos:**
- `id PK` → Identificador único de visita
  
- `user_id FK` → Usuario que visitó
  - `FK` = Foreign Key = referencia a users.id
  - **Importante:** NOT NULL (solo usuarios registrados)
  
- `instrument` → Acción visitada
  - Ej: "AAPL.SN", "GOOGL.SN"
  
- `created_at` → Timestamp de la visita

**¿Por qué está separada de query_logs?**

Cuando usuario selecciona APPLE:
1. Se disparan 4 consultas en paralelo (RSI, MA, MACD, BB)
2. Cada una crea 1 fila en query_logs → **4 filas**
3. Pero el usuario VIERON "una acción"

Si contamos query_logs:
```
| id | instrument | indicator |
|---|---|---|
| 1 | AAPL.SN | rsi |
| 2 | AAPL.SN | macd |
| 3 | AAPL.SN | medias_moviles |
| 4 | AAPL.SN | bandas_bollinger |
```
→ Parecería que el usuario hizo 4 "cosas" (❌ confunde el perfil)

**Solución: instrument_visits**
```
| id | user_id | instrument |
|---|---|---|
| 1 | 1 | AAPL.SN |
```
→ 1 visita = 1 acción del usuario (✅ perfil correcto)

**Ejemplo:**
```
| id | user_id | instrument | created_at          |
|----|---------|------------|---------------------|
| 1  | 1       | AAPL.SN    | 2026-08-21 11:00:00 |
| 2  | 1       | GOOGL.SN   | 2026-08-21 11:05:00 |
| 3  | 1       | AAPL.SN    | 2026-08-21 11:10:00 |
```

**¿Qué pregunta responde?**
- "¿Cuántas veces este usuario vio APPLE?" → COUNT(*) WHERE user_id=1 AND instrument='AAPL.SN' → 2 veces

---

## 🔗 Las Relaciones

### Relación 1: `users ||--o{ query_logs`

```
┌──────────────┐         ┌──────────────────┐
│    USERS     │ ──1:N── │  QUERY_LOGS      │
└──────────────┘         └──────────────────┘
    (1 user)                (0 or many)
```

**Significado:**
- 1 usuario puede tener 0 o muchas consultas
- Muchas consultas pertenecen a 1 usuario
- **FK:** query_logs.user_id → users.id
- **Tipo:** NULLABLE (user_id puede ser NULL = anónimo)

**Ejemplo:**
```
Usuario id=1 (juan)
├─ Consulta id=42 (RSI)
├─ Consulta id=43 (MACD)
└─ Consulta id=44 (MA)

Usuario NULL (anónimo)
└─ Consulta id=99 (Bollinger)
```

---

### Relación 2: `users ||--o{ instrument_visits`

```
┌──────────────┐         ┌──────────────────────┐
│    USERS     │ ──1:N── │ INSTRUMENT_VISITS    │
└──────────────┘         └──────────────────────┘
    (1 user)             (0 or many)
```

**Significado:**
- 1 usuario puede visitar 0 o muchos instrumentos
- Muchas visitas pertenecen a 1 usuario
- **FK:** instrument_visits.user_id → users.id
- **Tipo:** NOT NULL (solo usuarios registrados)

**Ejemplo:**
```
Usuario id=1 (juan)
├─ Visitó AAPL.SN
├─ Visitó GOOGL.SN
└─ Visitó AAPL.SN (de nuevo)

Usuario id=2 (maria)
├─ Visitó NETFLIX.SN
└─ Visitó MICROSOFT.SN
```

---

### Relación 3: `revoked_tokens` (sin relación)

```
┌──────────────────┐
│ REVOKED_TOKENS   │  (SIN RELACIÓN con USERS)
└──────────────────┘
```

**¿Por qué NO tiene FK?**
- jti es anónimo (no sabemos a quién pertenecía el token)
- Diseño para eficiencia (búsqueda O(1) sin JOIN)
- Se invalida un token sin saber quién fue

**Pero...** implícitamente:
- Cuando usuario id=1 hace logout, su jti se agrega acá
- Es N:1 lógica, pero sin FK en la BD

---

## 🎤 Cómo Explicar Mañana

### Versión Corta (30 segundos):
> "El diagrama muestra 4 tablas: users para credenciales, 
> query_logs para historial de consultas, instrument_visits para 
> qué acciones vio cada usuario, y revoked_tokens para tokens 
> invalidados en logout. Las relaciones 1:N conectan users con 
> query_logs e instrument_visits."

### Versión Media (1 minuto):
> "Tenemos 4 tablas. Users guarda email y contraseña en hash. 
> Query_logs registra cada consulta: quién la hizo, qué indicador, 
> cuánto tardó, y si regeneró. Instrument_visits es diferente: 
> cuando un usuario selecciona APPLE, se hacen 4 consultas técnicas 
> (una por indicador) pero eso es 1 'visita'. Revoked_tokens es 
> una lista negra de tokens para el logout.
>
> Las relaciones son 1:N: 1 usuario puede tener muchas consultas 
> y muchas visitas. Todo conectado por el id del usuario."

### Versión Larga (2 minutos):
> "El diagrama ER muestra la estructura de datos desde el modelo. 
> Tenemos 4 entidades:
>
> La tabla USERS es el núcleo: almacena id (clave primaria), 
> username, email (único), password_hash en bcrypt, y created_at. 
> El email es unique: no hay dos usuarios con el mismo email.
>
> QUERY_LOGS es donde auditamos: cada consulta genera una fila 
> con id único, session_id, instrumento, indicador, tiempo en 
> milisegundos, user_id que la hizo (puede ser NULL si es anónimo), 
> y si fue regenerada. La relación 1:N significa que 1 usuario 
> genera muchas consultas.
>
> INSTRUMENT_VISITS es especial: seleccionar 1 acción dispara 
> 4 consultas en paralelo (4 indicadores), pero eso es 1 'acción' 
> del usuario. Si contamos las 4 consultas como 4 acciones, el 
> perfil adaptativo se confunde. Por eso está separada.
>
> REVOKED_TOKENS es la lista negra: cuando cierras sesión, tu 
> jti se invalida aquí. Sin relación FK porque jti es anónimo, 
> pero implícitamente es N:1 (muchos tokens de 1 usuario).
>
> Todas las relaciones convergen en users.id: todo se conecta 
> a través del usuario."

---

## ✅ Checklist: ¿Está todo Correcto?

- [ ] **users** tiene 5 campos → id, username, email, password_hash, created_at ✅
- [ ] **email tiene UK** → Unique key ✅
- [ ] **query_logs tiene 11 campos** → Todos listados ✅
- [ ] **user_id en query_logs es FK** → Apunta a users.id ✅
- [ ] **instrument_visits tiene 4 campos** → id, user_id, instrument, created_at ✅
- [ ] **user_id en instrument_visits es FK** → Apunta a users.id ✅
- [ ] **revoked_tokens tiene 2 campos** → jti, revoked_at ✅
- [ ] **revoked_tokens NO tiene FK** → Correcto (lista negra) ✅
- [ ] **Relación 1:N** → users ||--o{ query_logs ✅
- [ ] **Relación 1:N** → users ||--o{ instrument_visits ✅

**Total: 100% fidedigno** ✅

---

## 📋 Preguntas que Podrían Hacer Mañana

### P: "¿Por qué PK en id y UK en email?"
R: "id es la clave primaria: identifica cada fila. Email es clave única: 
no pueden haber dos usuarios con el mismo email. El id se usa internamente, 
el email lo usa el usuario para login."

### P: "¿Qué pasa si borro un usuario?"
R: "Con FK sin CASCADE, no puedo borrar si tiene consultas o visitas. 
Eso preserva la auditoría. En producción tendríamos soft delete (fecha 
de borrado)."

### P: "¿Por qué user_id en query_logs es nullable?"
R: "Porque un usuario anónimo (sin registrarse) puede consultar. 
Si NULL, fue anónimo. Si tiene valor, fue registrado."

### P: "¿Cuál es la tabla más importante?"
R: "query_logs. Registra cada acción para auditoría, 
calcula tiempos (RNF-01), y alimenta el perfil adaptativo."

### P: "¿Por qué 4 tablas y no 2?"
R: "Separar query_logs e instrument_visits fue decisión de diseño. 
Sin separación, contar acciones sería incorrecto (1 acción = 4 consultas 
técnicas). Con separación, el perfil es exacto."

