# Fase 11 — Plan operativo, cumplimiento y riesgos (C13)

## Cumplimiento

**Esta sección no es asesoría legal.** Las normas están nombradas de memoria: confirma el artículo y el estado vigente de cada una antes de citarlas en el informe.

| Marco | Qué implica para el sistema | Estado |
|---|---|---|
| Ley 19.628 (protección de la vida privada) y Ley 21.719 (nueva ley de datos personales) (verificar vigencia y fechas) | Solo se guardan nombre de usuario, correo y hash de contraseña; no hay datos de pago ni financieros del usuario | **Pendiente**: política de privacidad visible, vía para eliminar la cuenta y base legal del tratamiento |
| CMF / regulación de asesoría de inversión (verificar) | El sistema explica indicadores y no recomienda comprar ni vender; el alcance lo excluye expresamente | **Pendiente**: aviso visible en la interfaz ("contenido educativo, no es asesoría de inversión") |
| Términos de uso de proveedores (Yahoo Finance, Alpha Vantage, Google News, Groq) | Uso acotado a un prototipo académico | **Pendiente**: revisar los términos de cada proveedor |
| Credenciales | Claves en variables de entorno (`.env` fuera del repositorio) | Cumplido (`.gitignore`) |

## Matriz de riesgos

Probabilidad e impacto: A (alta), M (media), B (baja). Responsable: el autor del proyecto.

| # | Riesgo | Prob. | Impacto | Mitigación | Seguimiento |
|---|---|---|---|---|---|
| R1 | `yfinance` (no oficial) deja de funcionar o bloquea | M | A | Respaldo en Alpha Vantage, caché de 5 min, mensaje de error comprensible | `scripts/validate_tickers.py` antes de cada demo |
| R2 | Alpha Vantage excede su cuota gratuita | M | M | Caché; la cuota solo se usa si Yahoo falla | Revisar la cuota vigente del proveedor |
| R3 | Google News RSS (no oficial) cambia o falla | M | B | Se degrada a lista vacía; no afecta los indicadores | `tests/test_news.py` |
| R4 | Groq no responde o cambia el modelo | M | M | Respaldo automático a plantillas (ADR 0002) | Registrar cuántas salidas caen al respaldo (**pendiente**) |
| R5 | El LLM redacta un texto que contradice el dato | M | A | Verificación mínima + `validate_coherence` que avisa; falta bloquearlo (ADR 0002) | Implementar la validación previa a la aceptación |
| R6 | Fuga o pérdida de datos de cuentas | B | A | bcrypt, JWT httpOnly, CSRF, bloqueo por intentos, PostgreSQL con TLS y respaldos (ADR 0004, 0006) | Probar una restauración de respaldo |
| R7 | Las migraciones fallan en PostgreSQL (se escribieron pensando en SQLite) | B | A | Verificado el 2026-10-28: la base `appfint` quedó en la revisión `0005` con las 5 tablas esperadas y los 108 tests pasan contra PostgreSQL 16. Falta repetir `flask db upgrade` sobre una base totalmente vacía | Repetir la prueba en una base vacía antes de entregar |
| R8 | Sin validación con usuarios, no hay evidencia de que mejore la comprensión | A | M | Declararlo como limitación; validación técnica con tests (ADR 0007) | Reevaluar si hay tiempo para una prueba con usuarios |
| R9 | El informe y el PPT quedan desactualizados respecto del código | A | A | Aplicar los cambios de `docs/revision_sumativa1.md` | Revisión antes de la entrega |
| R10 | Retraso del 30 % pendiente | M | A | Priorizar C9, C12–C14 y C22 | Seguimiento semanal en la herramienta de gestión (**pendiente**) |

## Plan operativo

1. Despliegue: PostgreSQL gestionado (nodo aparte), `flask --app app db upgrade`, gunicorn con 2 o más workers detrás de HTTPS, con `JWT_COOKIE_SECURE=true`.
2. Antes de cada demo: `python scripts/validate_tickers.py`, comprobar la conexión a la base y a los proveedores, y ejecutar `pytest`.
3. Monitoreo mínimo: `query_logs.processing_time_ms` y los registros de gunicorn.
