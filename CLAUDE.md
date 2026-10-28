# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (dev server on http://127.0.0.1:5001/)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_indicators.py

# Run a single test by name
pytest tests/test_indicators.py::test_compute_volatility

# Apply DB migrations (required before first run and after pulling schema changes)
flask --app app db upgrade

# Generate a migration after changing a model (review the file before applying)
flask --app app db migrate -m "descripcion"

# Validate all IPSA tickers against Yahoo Finance (live network call)
python scripts/validate_tickers.py

# First-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
createdb appfint && createdb appfint_test
cp .env.example .env   # set DATABASE_URL and TEST_DATABASE_URL
flask --app app db upgrade
```

The database is PostgreSQL (psycopg 3), the only supported engine, chosen so several users and gunicorn workers can write concurrently and data survives redeploys. `DATABASE_URL` is required: `config.py` refuses to start if it is missing or not PostgreSQL, and normalizes `postgres://`/`postgresql://` to `postgresql+psycopg://`. Schema changes go through Flask-Migrate/Alembic (`migrations/`) — the app never calls `db.create_all()`. Tests need a dedicated PostgreSQL database in `TEST_DATABASE_URL` whose name ends in `_test`; `tests/conftest.py` runs `create_all`/`drop_all` per test and refuses any other name, so never point it at a real database. Install dev dependencies with `pip install -r requirements-dev.txt`. The price cache (`TTLCache`) is per process, so with several workers each one fetches an instrument once per TTL.

## Architecture

The app is a Flask monolith with four independent backend modules, a thin Flask presenter layer, and a vanilla-JS frontend. All modules live under `src/`.

```
extractor/   — fetches and caches price data; computes financial indicators
nlp/         — generates Spanish natural-language explanations from indicator dicts
auth/        — JWT-in-cookie login (Flask-JWT-Extended + Flask-Bcrypt)
profile/     — adaptive detail-level based on per-user regeneration history; owns the QueryLog and InstrumentVisit models
web/         — Flask Blueprint (routes.py), Jinja2 templates, CSS, JS
```

`app.py` is a three-line entry point; `src/web/__init__.py` creates the Flask app and registers all blueprints; `config.py` holds all runtime configuration.

### Data flow for the price chart

1. User clicks a period button (1M/3M/6M/1A) → JS sends `GET /api/chart?symbol=…&days=N` where N ∈ {30, 90, 180, 365}.
2. `src/web/routes.py:api_chart()` calls `get_price_series(symbol, days)`.
3. `src/extractor/__init__.py:_get_history()` checks an in-memory `TTLCache` keyed by `(symbol, days)` (5-minute TTL). On miss, calls `src/extractor/sources.py:fetch_price_history()`.
4. `fetch_price_history()` tries Yahoo Finance (`yfinance`) first, Alpha Vantage as fallback. Yahoo is called with a string period from `PERIOD_TO_DAYS = {30: "3mo", 90: "6mo", 180: "1y", 365: "1y"}`, then the result is clipped to `hist.tail(days)`. Alpha Vantage clips with `sorted(dates)[-days:]`. Both paths return daily OHLC dicts `{date, open, high, low, close}`.
5. `src/extractor/indicators.py:compute_ma_series()` builds the JSON payload: parallel lists `dates`, `close`, `open`, `high`, `low`, `sma_short`, `sma_long`.
6. JS `renderChart()` in `dashboard.js` feeds this to TradingView Lightweight Charts v4.2.0 as a candlestick series + two line series.

The `days` parameter is also forwarded to `/api/query` (POST) for each of the four indicator cards — same history slice drives both the chart and the indicator calculations.

The indicator cards only show value + badges + a "Ver explicación en simple" button (uniform height). The explanation itself renders in a single full-width panel (`#explain-panel`, below `#indicator-grid`) driven by `activeKey` in `dashboard.js`: `selectIndicator()` opens it for the clicked card (calling `/api/query` only the first time; re-opening reuses `lastIndicatorData` so no extra `query_logs` row), `renderPanel()` draws text, level tag (links to `/perfil`), RSI/%B scale (`renderScale()`, no threshold numbers at level básico), FinBERT badge, "No entendí esto" (`regenerateCard()`) and "Entendido" (closes).

The dashboard landing (`#empty-state` in `index.html`, shown until an instrument is selected) reuses the `catalog` that `loadQuotes()` already fetched to render "Mayores alzas/bajas del día" with 30-day sparklines (`renderLanding()` in `dashboard.js`), plus the two news panels below, and, for logged-in users, `recent_visits()` (server-side in `index()`) for "Sigue donde quedaste". Visual language (IBM Plex Sans/Mono, 4 px radii, flat bordered cards) lives in the `:root` tokens of `style.css`, so it applies app-wide.

The news block (`extractor/news.py`) pulls headlines from the unofficial Google News RSS (`news.google.com/rss/search`, `hl=es-419&gl=CL`), cached 20 min in `news_cache`. Market news uses `IPSA OR "bolsa de Santiago" when:2d`; per-company news uses the `aliases` list in `data/instruments.json` (e.g. BCI → "BCI", SQM-B → "SQM") plus business terms, and keeps only headlines that actually mention the company (`news_exclude` drops false positives such as Concha y Toro's street addresses). `GET /api/news` and `GET /api/news?symbol=…` accept only catalog symbols (404 otherwise) and degrade to `{"items": []}` on upstream failure. `GET /api/sparkline?symbol=…` returns the last 30 closes for the mini-charts in the movers table.

### Key design constraints to be aware of

- **`VALID_PERIODS = (30, 90, 180, 365)`** in `extractor/__init__.py` is enforced by `_validate_inputs()`. Passing any other value raises `ExtractionError` → HTTP 502. Both `/api/chart` and `/api/query` enforce this.
- **`days` counts trading rows, not calendar days.** `tail(N)` returns the N most recent trading-day rows. 30 rows ≈ 6 calendar weeks; 180 rows ≈ 8.5 calendar months. Labels (1M/3M/6M/1A) are approximate.
- **MA windows auto-scale** in `compute_ma_series()`: `short_window = min(50, max(2, len(close)//2))`. For a 30-row window the series has MA~15/MA~30, not MA50/MA200. The HTML legend is hardcoded and does not reflect this.
- **Cache is per (symbol, days).** Switching timeframes always triggers a fresh fetch; switching instruments also triggers a fresh fetch.
- **No price data in the DB.** The database only stores users, JWT revocations, query logs, and instrument visits. All price data is ephemeral (in-memory cache).
- **History lives in the account, not the session.** `query_logs` (value, unit, risk_level, period_days since migration `0004`) and `instrument_visits` feed the "Historial" tab of `/perfil` (`#historial`); `/history` just redirects there. Anonymous visitors get no history. The top bar (`base.html`) is brand + Acciones/Glosario on the left and a user dropdown (Mi perfil / Historial / Cerrar sesión) on the right; menu JS is at the top of `app.js`.
- **PostgreSQL enforces VARCHAR lengths.** `instrument` is `String(20)`, so `MAX_SYMBOL_LENGTH` in `extractor/__init__.py` rejects longer tickers before they reach the DB (otherwise → 500). Validate new user-supplied strings against their column length the same way.
- **Session race condition** (already fixed): `before_app_request` establishes the session cookie on page load so concurrent AJAX calls don't race to create it.
- **Login lockout**: `authenticate_user` counts failed attempts per user (`users.failed_login_attempts`, `users.locked_until`, migration `0002`); after `LOGIN_MAX_ATTEMPTS` (5) failures the account is locked `LOGIN_LOCK_MINUTES` (15) and the API returns 429. Credential errors stay generic (401). `AuthError.status` carries the HTTP code (400 validation, 409 duplicate). Passwords: 8–64 chars and ≤ 72 UTF-8 bytes (bcrypt limit). `?next=` on login only accepts keys from `NEXT_DESTINATIONS` in `auth.js`.
- **CSRF pattern**: JWT is stored in an httpOnly cookie. A second CSRF token is in a JS-readable cookie (`csrf_access_token`); all mutating fetch calls must set `X-CSRF-TOKEN` header from it (see `static/js/csrf.js`).
- **FinBERT is opt-in** (default `false`): `USE_FINBERT=true` in `.env` adds a sentiment label to explanations; it does not write the text. The text comes from the LLM (`USE_LLM=true` + `GROQ_API_KEY`, Groq `qwen/qwen3.8-27b`) or, as fallback, the templates. The app runs normally without `transformers`/`torch`/`groq`.
- **Adaptive explanations** (`profile/service.py`, RF-13.2): three explanation levels — `basico` / `intermedio` / `avanzado` — whose "ficha" (audience, vocabulary, forbidden terms, thresholds, IPSA context, max words) lives in `src/nlp/levels.py`. The ficha feeds both the LLM (`llm_explainer.build_system_prompt(level)`) and the fallback templates (`src/nlp/templates.py`, `TEMPLATES[level][indicator][risk]`). (1) Declared experience (`users.experience_level`, optional at registration, editable at `PATCH /api/perfil/experiencia`, migration `0003`) sets the starting level via `EXPERIENCE_TO_LEVEL` (nunca→basico, poco→intermedio, experiencia→avanzado; none/anonymous → `DEFAULT_LEVEL` intermedio). (2) Behavior: every `DETAIL_THRESHOLD` (2) regenerations of an indicator lower that indicator one level, floor `basico` (`_level_for()`); only regenerations after `users.level_reset_at` count (set whenever the declared experience changes, migration `0005`), so re-declaring experience restarts every indicator from the new starting level. In `basico`, LLM output containing a forbidden term is discarded in favor of the templates. Templates use `{zona}` (technical reading with threshold), `{llano}` (plain reading) and `{dir}` placeholders computed from `signal`/`trend` so "alto" templates never claim overbought on an oversold reading. (3) Preferred style: each pool is ordered by style (0 directa, 1 conversacional, 2 con contexto; `STYLE_LABELS`), and `preferred_variant()` returns the variant where the user last stopped regenerating, which `/api/query` uses as the starting variant (also passed to the LLM prompt). Keep that style ordering consistent when editing templates; `tests/test_profile.py` validates every level × style against the coherence validator and the level ficha.

### Catalog and instruments

`data/instruments.json` lists the 30 IPSA constituents with `.SN` suffix for Yahoo Finance. IPSA itself (`^IPSA`) is shown in the ticker tape only — it is not in the catalog and cannot be queried individually. Any other ticker can be queried ad-hoc via `/api/lookup` (uses `get_price_series` with 90 days as a probe) without being added to the catalog.
