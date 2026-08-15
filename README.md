# Anteproyecto - Sistema IA para comprension financiera

Sprint activo: **Sprint 9 (05/10/2026 - 18/10/2026) - Integracion**.

## Alcance implementado a la fecha (18/10/2026)

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
| RF-04.1 | Procesamiento con FinBERT (opcional, con heuristica fallback) | `nlp_processor/finbert.py` |
| RF-04.2 | Reglas de coherencia entre explicacion y valor real (RSI) | `nlp_processor/validator.py` |
| RF-05.1 | Explicacion sin jerga sin definir | `nlp_processor/generator.py` |
| RF-05.2 | Nivel de detalle adaptado al perfil | `nlp_processor/generator.py` (`PerfilAprendizaje`) |
| RF-06.1 | Clasificacion de riesgo bajo/medio/alto | `nlp_processor/risk.py` |
| RF-06.2 | Regeneracion de explicacion a pedido | `main.regenerar` |
| RF-07 | Interfaz web Flask + cinta de precios | `app/main.py`, `app/templates/*`, `app/static/*` |
| RF-08 | Valor original, etiqueta de riesgo, spinner | `app/templates/consulta.html` |
| RF-09 | Mensajes de error sin jerga + glosario | `app/templates/errors/*`, `app/templates/glosario.html` |
| RF-10 | Historial de las 5 ultimas consultas de la sesion | `app/main.py` + Flask session |
| RF-11 | Registro con Flask-Bcrypt | `app/auth.py::registro` |
| RF-12 | Login/logout con Flask-JWT-Extended en cookie | `app/auth.py::login` |
| RF-13 | Perfil de aprendizaje persistido y adaptativo | `app/services.py`, `nlp_processor/generator.py` |
| RF-14 | Resumen personalizado + reuso de la ultima explicacion | `app/perfil.py`, `ExplicacionCache` |

## Fuera de alcance en esta entrega

- Sprint 10: pruebas funcionales y ajustes RNF (a partir del 19/10).
- Sprint 11: aplicacion y analisis de la encuesta pre/post (02/11).
- Sprint 12: validacion semantica sistematica (16/11).
- Sprint 13: cierre de documentacion tecnica (30/11).

## Instalacion

```bash
python3 -m pip install -r requirements.txt
```

## Uso

### CLI del Extractor (util para debug)

```bash
python3 main.py --listar-tickers
python3 main.py --ticker CHILE.SN --rango "3 meses"
python3 main.py --macro
```

### App Flask

```bash
python3 run.py
# abrir http://127.0.0.1:5000
```

Flujo tipico:
1. Crear cuenta en `/auth/registro` (opcional: marcar consentimiento).
2. Iniciar sesion en `/auth/login`.
3. Elegir instrumento + rango + indicador en la pagina principal.
4. Revisar explicacion, valor, etiqueta de riesgo. Si no queda claro,
   pedir regeneracion.
5. Al llegar a 5 consultas se ofrece la encuesta (si dio consentimiento).
6. Revisar el resumen en `/perfil/`.

Cada extraccion queda registrada en `logs/trazabilidad.jsonl`
(RF-02.2). La base de datos SQLite se crea automaticamente en
`instance/appfinanc.sqlite`.
