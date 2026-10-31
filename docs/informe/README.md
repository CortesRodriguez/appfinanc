# Apartados del informe en borrador (rúbrica ACIF1123)

| Archivo | Criterio | Puntos |
|---|---|---|
| [c07_comparacion_tecnicas_ia.md](c07_comparacion_tecnicas_ia.md) | C7 Comparación de técnicas de IA | 9 |
| [c08_seleccion_tecnica.md](c08_seleccion_tecnica.md) | C8 Selección y justificación de la técnica | 12 |
| [c11_datos_y_etica.md](c11_datos_y_etica.md) | C11 Requerimientos de datos y consideraciones éticas | 9 |
| [c12_metricas_mvp.md](c12_metricas_mvp.md) | C12 Criterios y métricas de evaluación del MVP | 9 |

## Advertencia sobre el uso de IA

Estos textos son **borradores** redactados con ayuda de una herramienta de IA a partir del código y la documentación del repositorio. La rúbrica y las normas de la asignatura advierten que el contenido generado sin declaración ni revisión crítica puede constituir una falta a la integridad académica, y la entrega se revisa con una herramienta antiplagio. Antes de llevarlos al informe: léelos, reescríbelos con tus palabras, comprueba cada cifra y declara el uso de la herramienta.

## Qué debes cerrar antes de entregar

1. **Confirmar la rúbrica.** La que pegaste es la de ACIF1123 (207 puntos); el PDF del repositorio es de ACIF1121 (150 puntos). Pregunta en el foro cuál rige.
2. **Verificar el identificador del modelo** `qwen/qwen3.8-27b` en la consola de Groq y usar el nombre exacto en todo el informe.
3. **Confirmar la meta de legibilidad (≥ 60)** de C12: es una propuesta, no un requerimiento.
4. **Medir el tiempo de respuesta real** (con red y con el LLM activado). La cifra actual (media de 3,6 ms en 12 consultas de una sola sesión) no demuestra el cumplimiento de los 5 s.
5. **Probar el LLM real** al menos una vez con `USE_LLM=true`; ninguna prueba lo ejecutó contra la API.
6. **Verificar** las leyes 19.628 y 21.719, la licencia e idioma de `ProsusAI/finbert` (su ficha devolvió error 403 al consultarla) y la cuota vigente de Groq.
7. **Agregar DOI o URL** a Li et al. (2023) y a las referencias del Banco Central, la CMF y el Centro de Políticas Públicas UC.
8. **Decidir si hace falta una prueba con usuarios** para C6/C12 (ver el último apartado de C12).

## Lo que estos apartados no resuelven

La rúbrica también evalúa aspectos que siguen pendientes y no se cubren aquí: la bitácora técnica (C16), la tabla de avance actualizada y la verificación de hitos del 70 % (C14, C15), la evidencia de acceso al MVP (C13), y las contradicciones del informe con el sistema actual (encuestas, SQLite, "20/32 casos de uso").
