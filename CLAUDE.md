# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (dev server on http://127.0.0.1:5000/)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_indicators.py

# Run a single test by name
pytest tests/test_indicators.py::test_compute_volatility

# Validate all IPSA tickers against Yahoo Finance (live network call)
python scripts/validate_tickers.py

# First-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

If `appfint.db` schema is stale (e.g. new tables were added), delete the file — `db.create_all()` at startup recreates it from scratch. There are no migrations.

## Architecture

The app is a Flask monolith with four independent backend modules, a thin Flask presenter layer, and a vanilla-JS frontend. All modules live under `src/`.

```
extractor/   — fetches and caches price data; computes financial indicators
nlp/         — generates Spanish natural-language explanations from indicator dicts
evaluation/  — pre/post survey persistence, query logging, coherence checking
auth/        — JWT-in-cookie login (Flask-JWT-Extended + Flask-Bcrypt)
profile/     — adaptive detail-level based on per-user regeneration history
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

### Key design constraints to be aware of

- **`VALID_PERIODS = (30, 90, 180, 365)`** in `extractor/__init__.py` is enforced by `_validate_inputs()`. Passing any other value raises `ExtractionError` → HTTP 502. Both `/api/chart` and `/api/query` enforce this.
- **`days` counts trading rows, not calendar days.** `tail(N)` returns the N most recent trading-day rows. 30 rows ≈ 6 calendar weeks; 180 rows ≈ 8.5 calendar months. Labels (1M/3M/6M/1A) are approximate.
- **MA windows auto-scale** in `compute_ma_series()`: `short_window = min(50, max(2, len(close)//2))`. For a 30-row window the series has MA~15/MA~30, not MA50/MA200. The HTML legend is hardcoded and does not reflect this.
- **Cache is per (symbol, days).** Switching timeframes always triggers a fresh fetch; switching instruments also triggers a fresh fetch.
- **No price data in the DB.** `appfint.db` only stores users, JWT revocations, sessions, query logs, coherence checks, survey responses, and instrument visits. All price data is ephemeral (in-memory cache).
- **Session race condition** (already fixed): `before_app_request` establishes the session cookie on page load so concurrent AJAX calls don't race to create it. `ensure_evaluation_session()` in `evaluation/__init__.py` tolerates `IntegrityError` from parallel `/api/query` calls.
- **CSRF pattern**: JWT is stored in an httpOnly cookie. A second CSRF token is in a JS-readable cookie (`csrf_access_token`); all mutating fetch calls must set `X-CSRF-TOKEN` header from it (see `static/js/csrf.js`).
- **FinBERT is opt-in**: `USE_FINBERT=true` in `.env` adds a sentiment signal to explanations. The app runs normally without `transformers`/`torch` installed.
- **Adaptive detail level** (`profile/service.py:get_detail_level`): if a logged-in user has regenerated an indicator's explanation ≥ 2 times, subsequent explanations for that indicator use a more detailed template variant.

### Catalog and instruments

`data/instruments.json` lists the 30 IPSA constituents with `.SN` suffix for Yahoo Finance. IPSA itself (`^IPSA`) is shown in the ticker tape only — it is not in the catalog and cannot be queried individually. Any other ticker can be queried ad-hoc via `/api/lookup` (uses `get_price_series` with 90 days as a probe) without being added to the catalog.
