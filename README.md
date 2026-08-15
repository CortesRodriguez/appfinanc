# Anteproyecto - Sistema IA para comprension financiera

Sprint activo: **Sprint 5 (10/08/2026 - 23/08/2026) - Modulo Extractor**.

## Alcance implementado a la fecha (15/08/2026)

Se implementa unicamente lo que corresponde al cronograma vigente
(Tabla 2.57 del anteproyecto). Los modulos futuros (NLP, Presentador,
Autenticacion, etc.) no se construyen aun.

| Requerimiento | Descripcion | Estado |
|---------------|-------------|--------|
| RF-01.1 | Seleccion de instrumento (30 empresas IPSA) y rango temporal | Implementado en `extractor/config.py` y validado en los extractores |
| RF-02.1 | Extraccion de volatilidad, RSI, medias moviles y rentabilidad desde Yahoo Finance / Alpha Vantage | `extractor/yahoo_extractor.py`, `extractor/alpha_vantage_extractor.py`, `extractor/indicators.py` |
| RF-02.2 | Trazabilidad (fecha, hora, fuente) por cada extraccion | `extractor/traceability.py` (JSONL en `logs/trazabilidad.jsonl`) |
| RF-02.3 | UF, dolar observado, TPM e IPC desde `mindicador.cl` | `extractor/banco_central_extractor.py` |
| RF-03.1 | Rate limit + cache 5 min (RNF-02.2) + reintentos (RNF-09.2) | `extractor/cache.py` |
| RF-03.2 | Validacion de formato y rango numerico | `extractor/validator.py` |
| RF-03.3 | Normalizacion a estructura interna comun `IndicadorNormalizado` | `extractor/normalizer.py` |

Casos de uso cubiertos: CU-01 (parcial, sin UI), CU-02, CU-03, CU-04,
CU-05, CU-06, CU-07.

## Fuera de alcance en esta entrega

- Modulo Procesador NLP con FinBERT (Sprint 6).
- Interfaz web Flask, cinta de precios y presentacion visual (Sprint 7).
- Registro, autenticacion y perfil de aprendizaje (Sprint 8).
- Integracion, pruebas de usuario y evaluacion (Sprints 9-13).

## Instalacion

```bash
python3 -m pip install -r requirements.txt
```

## Uso

```bash
# Listar los 30 tickers del IPSA que soporta el sistema
python3 main.py --listar-tickers

# Extraer indicadores de una accion en un rango de 3 meses
python3 main.py --ticker CHILE.SN --rango "3 meses"

# Consultar los indicadores macro del Banco Central
python3 main.py --macro

# Forzar Alpha Vantage (requiere export ALPHA_VANTAGE_API_KEY=...)
python3 main.py --ticker CHILE.SN --rango "1 mes" --alpha-vantage
```

Cada extraccion queda registrada en `logs/trazabilidad.jsonl` con la
fecha, hora, fuente y valor obtenido, cumpliendo RF-02.2.
