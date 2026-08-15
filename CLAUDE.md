# CLAUDE.md - Guia rapida del proyecto

Repositorio: `anteproyecto_app` (GitHub: `CortesRodriguez/appfinanc`).
Documento fuente: `f1_s04xcortes.docx` (fuera del repo).

## Que es esto

Prototipo academico del anteproyecto **"Sistema basado en IA para apoyar
la comprension de informacion financiera tecnica en inversionistas
principiantes del contexto digital chileno"** (Ximena Cortes, 2026).
El sistema transforma indicadores financieros (RSI, volatilidad, medias
moviles, rentabilidad) en explicaciones comprensibles.

## Estructura

```
extractor/         Sprint 5. Obtiene datos desde Yahoo Finance y mindicador.cl.
nlp_processor/     Sprint 6. FinBERT + generador de explicaciones + riesgo + glosario.
app/               Sprints 7-9. Flask app (auth JWT, consulta, perfil, cinta).
  templates/
  static/
main.py            CLI para ejercitar el Extractor.
run.py             Entry point de la app Flask.
instance/          SQLite generada en runtime (ignored).
logs/              Trazabilidad de extracciones (ignored).
```

## Convenciones importantes

- **Fechas del cronograma manda.** Solo se implementan requerimientos
  del sprint activo o previos, segun Tabla 2.57 del anteproyecto. Al
  avanzar en el tiempo se agregan nuevos sprints. No adelantar trabajo.
- **Contrato Extractor -> NLP:** `IndicadorNormalizado`
  (`extractor/normalizer.py`). Ese dataclass es el unico input que
  espera el Procesador NLP. Si se agrega un indicador nuevo, extender
  aca primero.
- **FinBERT es opcional.** El wrapper `nlp_processor/finbert.py` carga
  `transformers` de forma perezosa. Si el paquete no esta instalado,
  cae a una heuristica y lo indica en el campo `fuente`. No es un bug.
- **Anonimizacion de encuestas (RNF-05).** `RespuestaEncuesta` NO tiene
  FK a `Usuario`. Solo se guarda si aceptaron participar; nunca se
  vincula.
- **Cache 5 min (RNF-02.2).** Definido en `extractor/config.py`
  (`CACHE_TTL_SEG`). Cualquier consulta al mismo ticker + rango dentro
  de la ventana reutiliza el `IndicadorNormalizado`.
- **Reintentos 3x (RNF-09.2).** Manejo centralizado en
  `extractor/cache.py::con_reintentos`. Los extractores lo envuelven.
- **RF-04.2 (coherencia).** Antes de mostrar una explicacion, se
  verifica que las categorias cualitativas coincidan con los umbrales
  reales del indicador (RSI). Ver `nlp_processor/validator.py`.
- **Contrasenas:** Flask-Bcrypt, min 8 caracteres (RNF-06.1). JWT en
  cookie HttpOnly, expira en 24 h (RNF-06.2).

## Cosas que NO cambiar sin cuidado

- Umbrales del RSI (`extractor/config.py::UMBRALES_RSI`): son
  referenciados por el generador y la validacion de coherencia. Si se
  cambian, hay que revisar `nlp_processor/validator.py`.
- `Perfil.desde_actividad()`: la formula que decide "basico" ->
  "intermedio" -> "avanzado" segun consultas / regeneraciones. Es
  parte de RF-13.2.
- Nombres de indicadores permitidos: `rsi`, `volatilidad`,
  `media_movil`, `rentabilidad`. Estan hardcodeados en la UI, el
  generador y la BD.

## Cosas que si es OK cambiar solo

- Copy visible en templates HTML (mensajes, botones, headings).
- Estilos en `app/static/css/styles.css`.
- Textos del glosario (`nlp_processor/glosario.py`).

## Como correr

```bash
python3 -m pip install -r requirements.txt

# CLI para probar el Extractor
python3 main.py --ticker CHILE.SN --rango "3 meses"

# App web completa
python3 run.py
# abrir http://127.0.0.1:5000
```

Primer arranque crea automaticamente `instance/appfinanc.sqlite`.

## Fuentes de datos

- Yahoo Finance (`yfinance`, sin API key).
- Alpha Vantage (fallback opcional, requiere `ALPHA_VANTAGE_API_KEY`).
- Banco Central via `https://mindicador.cl/api/<indicador>` (sin key).

## Estado por sprint (al 18/10/2026)

| Sprint | Alcance | Estado |
|--------|---------|--------|
| 1-4    | Analisis, diseño y seleccion NLP | Completado (documental) |
| 5      | Extractor (RF-01, RF-02, RF-03) | Implementado |
| 6      | Procesador NLP (RF-04, RF-05, RF-06) | Implementado |
| 7      | Presentador Flask (RF-07, RF-08, RF-09, RF-10) | Implementado |
| 8      | Auth y perfil (RF-11, RF-12, RF-13, RF-14) | Implementado |
| 9      | Integracion | Implementado |
| 10-13  | Pruebas, evaluacion, cierre docs | Pendiente segun cronograma |

## Cosas pendientes (fuera de fecha)

- Sprint 10: pruebas funcionales sistematicas y ajuste de RNF.
- Sprint 11: aplicacion y analisis de la encuesta pre/post.
- Sprint 12: validacion semantica de explicaciones vs indicadores.
- Sprint 13: documentacion final y diagramas.
