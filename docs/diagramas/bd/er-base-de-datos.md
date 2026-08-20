# Modelo entidad-relación — `appfint.db`

**Motor**: SQLite (archivo `appfint.db`, recreado desde cero con `db.create_all()` al arrancar la app; no hay migraciones).
**Fuente de verdad**: modelos SQLAlchemy en `src/auth/models.py` y `src/evaluation/models.py`.

Este diagrama refleja las 7 tablas reales. Las flechas apuntan del "muchos" al "uno" (FK → PK).

```mermaid
erDiagram
    users ||--o{ query_logs : "id → user_id (opcional)"
    users ||--o{ instrument_visits : "id → user_id"
    evaluation_sessions ||--o{ survey_responses : "session_id"
    evaluation_sessions ||--o{ query_logs : "session_id"

    users {
        int id PK
        string(80) username
        string(255) email UK "unique, indexed"
        string(255) password_hash "bcrypt"
        datetime created_at
    }

    revoked_tokens {
        string(64) jti PK "JWT ID revocado"
        datetime revoked_at
    }

    evaluation_sessions {
        string(36) session_id PK "UUID de Flask"
        datetime created_at
        float interaction_seconds "RF-14.1"
    }

    survey_responses {
        int id PK
        string(36) session_id FK
        string(4) phase "pre | post"
        string(16) question_id
        int answer_index
        boolean correct
        datetime created_at
    }

    query_logs {
        int id PK
        string(36) session_id FK
        string(20) instrument
        string(20) indicator
        string(30) source "yahoo | alpha_vantage"
        int processing_time_ms "RNF-01.2"
        int user_id FK "nullable (anónimos)"
        boolean is_regeneration
        text explanation_text
        int variant "0..N (RF-04)"
        datetime created_at
    }

    instrument_visits {
        int id PK
        int user_id FK
        string(20) instrument
        datetime created_at
    }

    coherence_checks {
        int id PK
        string(36) session_id "sin FK formal"
        string(20) instrument
        string(20) indicator
        float value
        string(10) risk_level
        text explanation_text
        boolean coherent
        text reason
        string(20) status "pendiente | revisado"
        datetime created_at
    }
```

## Notas de diseño

- **`revoked_tokens` es independiente** (sin FK a `users`): un JWT sigue siendo revocable aunque el usuario se borre. La lista se consulta en el callback `token_in_blocklist` de Flask-JWT-Extended.
- **`coherence_checks.session_id` no tiene FK formal** (sí es UUID de sesión igual que en `evaluation_sessions`, pero la columna se declara suelta). Si algún día se activa integridad referencial completa, tocaría agregarla.
- **`query_logs.user_id` es opcional**: consultas anónimas (sin login) dejan la columna en NULL y siguen funcionando. Cuando hay JWT válido, se asocia para el perfil adaptativo (RF-18.1).
- **`instrument_visits` vs `query_logs`**: una selección de instrumento en el dashboard produce **1** `InstrumentVisit` (para el perfil de aprendizaje) y **4** `QueryLog` (uno por indicador consultado en paralelo). Ver comentario en `src/evaluation/models.py:57`.
- **Sin tabla de precios**: todos los datos históricos son efímeros y viven en `TTLCache` (memoria, TTL 5 min). La BD es solo estado de la aplicación, no espejo del mercado.

## Ver los datos reales

Instalar en VS Code la extensión **SQLite Viewer** (`qwtel.sqlite-viewer`) y hacer doble-clic en `appfint.db` para navegar las 7 tablas como en cualquier IDE (DBeaver, DataGrip). Cada columna es filtrable y ordenable; no reemplaza SQL, pero para inspección visual alcanza.
