# Revisión Sumativa 1 (ACIF1121): checklist de correcciones

Fecha de revisión: 2026-10-23
Fuentes revisadas: pauta (`f1_s4_evaluación_instrucciones_sumativa 1.pdf`, criterios C1–C28), informe `f1_s11xcortes.docx`, PPT `Presentación_XCORTES.pptx`, `registro_verificacion_appfint.xlsx` y el estado del repo.

Limitaciones de la revisión: no vi las imágenes del docx ni los renders del PPT. No hay evidencia de una herramienta de planificación (Jira, Trello, etc.) en ninguno de los archivos.

Leyenda: `[ ]` pendiente, `[x]` hecho.

---

## 1. Lo que está bien (no tocar)

| Criterio | Estado |
|---|---|
| C1–C3 Problemática y pertinencia | Sólido. Datos EFH 2024 y CMF 2024, tabla de indicadores nacionales, causas técnicas y cognitivas (Kahneman), comparación con Fintual y otras. |
| C4 Objetivo general | Verbo en infinitivo, ligado a problema y solución. |
| C7 Marco teórico | 6 fuentes académicas de 2023–2025 (Baghavathi, Huang, Kosireddy, Lazarev, Li, Martins). Cumple el mínimo de 5. |
| C8 Metodología | Scrum frente a Cascada con tabla comparativa y justificación (falta una segunda alternativa, ver sección 2). |
| C9 (base) | 32 CU con RF-xx.x, prioridad, HH estimadas, sprints con fechas y tabla de seguimiento. |
| C10–C11 Arquitectura | Modelo 4+1, diagramas de componentes, secuencia, despliegue y BD. |
| C15 Funcionalidades | El código cubre los 32 CU. 108 tests pasando. |
| C23 PPT | Sigue la estructura de 7 bloques de la pauta. |

---

## 2. Cambios en el documento oficial (`f1_s11xcortes.docx`)

El informe está congelado al 01/09 y ya no coincide con el proyecto.

### 2.1 Avance y requerimientos (C9, el de más riesgo)
- [ ] La tabla de seguimiento dice 20/32 CU (62,5%), bajo el 70% exigido. El global por HH es 64%.
- [ ] Sprint 4 aparece en 0% y RF-05.1 y RF-05.2 en "Sin comenzar", pero ya están implementados.
- [ ] Actualizar estados, HH reales, Burndown y Burn-up.
- [ ] Listar el 30% pendiente con actividad y fecha/hito. Si todo está hecho, declarar lo que queda: validación con usuarios, pruebas de carga, despliegue.

### 2.2 Contradicciones con el sistema actual
- [ ] **SQLite → PostgreSQL**. El doc dice SQLite en Vista física, Diagrama de despliegue y Conclusiones. El código ya exige PostgreSQL (`config.py`, ADR 0004); falta corregir el docx y verificar las migraciones contra un PostgreSQL real.
- [ ] **FinBERT → LLM**. El doc dice "NLP con FinBERT". El motor real es el LLM `qwen/qwen3.8-27b` vía Groq, con plantillas como respaldo. FinBERT es opcional y solo da la etiqueta de sentimiento. Afecta Alcance, Marco teórico (no hay sección sobre Qwen), Vista lógica, Conclusiones y Tabla 3.4.
- [ ] **Módulo de Evaluación y encuestas**. El doc lo describe (Vista lógica, alcance, resultados esperados, "cuestionario antes y después"), pero se eliminó del código (`surveys.py`, `eligibility.py`, `reports.py` y plantillas). Decidir:
  - (a) quitar las encuestas de alcance, resultados y diagramas (recomendado), o
  - (b) reinstaurarlas como parte del 30% pendiente.

### 2.3 Inconsistencias internas
- [ ] El objetivo 4 habla de "datos en tiempo real" y las limitaciones dicen "no en tiempo real".
- [ ] Las Conclusiones dicen "tres objetivos específicos" y hay cuatro.
- [ ] Los nombres de CU-03, CU-06 y CU-08 cambian entre el doc (Tabla 4.x) y el xlsx.
- [ ] Tablas y figuras sin numerar ("Tabla .", "Figure .") y títulos en inglés ("Figure").

### 2.4 Apartados que faltan
- [ ] **C12 Atributos de calidad y gestión de datos**: escalabilidad, seguridad, disponibilidad, recuperación; estrategia de datos con consistencia y trazabilidad. Reutilizar `docs/diseno/09_stack_tecnologico.md`.
- [ ] **C13 Plan operativo, cumplimiento y riesgos**: normativa (Ley 19.628 / 21.719, CMF), riesgos con mitigación, responsables y seguimiento.
- [ ] **C14 Planificación con herramienta de gestión**: enlace o capturas, dependencias, responsables, estados, evidencias.
- [ ] **C22 Anexos**: numerados ("Anexo 1…"), titulados, con fuente y citados en el texto.
- [ ] **C17 Conclusiones**: reescribir contra los 4 objetivos específicos, con alcances, limitaciones y proyección.

### 2.5 Metodología (C8)
- [ ] Agregar una segunda alternativa (Kanban o XP). La pauta pide al menos dos.
- [ ] Describir etapas, actividades y productos de Scrum aplicados al proyecto.

### 2.6 Bibliografía (C21)
- [ ] Unificar "y" y "&" entre autores (APA 7 usa "&" o "y" de forma consistente).
- [ ] Agregar DOI/URL a Li et al., Huang et al., Baghavathi, Banco Central y CMF.
- [ ] Aplicar sangría francesa de 0,5 cm.
- [ ] Verificar que cada cita del texto tenga referencia y viceversa.

### 2.7 Formato y entrega (C18–C20)
- [ ] Entregar en **PDF**, tamaño carta, Arial o Times 12, márgenes 2,5 cm, interlineado 1,5.
- [ ] Nombre de archivo: `acif1121_s04_informe_xcortes` (el actual es `f1_s11xcortes.docx`).
- [ ] Portada: agregar asignatura y código del curso. Cambiar "Septiembre 2026" por la fecha real de entrega.
- [ ] Revisar que el índice refleje todo, incluidos los anexos.
- [ ] Revisar ortografía y gramática.

---

## 3. Cambios en el proyecto

### 3.1 Verificación (C16, 9 pts)
- [ ] `registro_verificacion_appfint.xlsx`: la hoja de Autenticación y Perfil está 100% "Pendiente". En NLP hay 2 casos pendientes y 1 "con observaciones" ("Mejorar las explicaciones").
- [ ] Hoja Errores vacía (solo el ejemplo E-01). Registrar errores reales con severidad y prioridad, y la corrección aplicada.
- [ ] Re-probar "explicación comprensible" (ahora sin analogías).
- [ ] Documentar la verificación de los **RNF**: tiempo de respuesta, legibilidad (Fernández-Huerta), seguridad (bloqueo de login, CSRF), tolerancia a fallos. Ya hay tests para varios; falta registrarlos.

### 3.2 Evidencia
- [ ] Capturas nuevas del panel de explicación y del perfil. Verificarlos primero en el navegador (reiniciar servidor, Cmd+Shift+R).
- [ ] Montar el backlog de los 32 CU en una herramienta (Jira, Trello, Notion…) con responsables, estados e hitos. Capturas anexadas al informe.

### 3.3 Limpieza técnica
- [x] Borrar `src/web/templates/history.html` (huérfano).
- [ ] Borrar las 3 cuentas `@test.cl` de la BD de desarrollo `appfint`.
- [x] Revisar `CLAUDE.md` / `docs/`: ya no mencionan encuestas (ver ADR 0007).

---

## 4. PPT y defensa (C23–C28)

- [ ] Subir el PPT a ≥70% con datos actualizados. Las diapositivas 10–13 solo muestran CU-02 y CU-10.
- [ ] Corregir "Qwen3" por la versión real (`qwen3.8-27b`).
- [ ] Reflejar PostgreSQL y las eliminaciones (encuestas).
- [ ] Máximo 10 minutos: 1 + 1 + 1 + 1 + 2 + 2 + 2.
- [ ] Preparar preguntas: por qué se quitaron las encuestas, cómo se garantiza que el LLM no contradiga el dato (`validate_coherence`), por qué Groq/Qwen y no FinBERT, cómo funcionan los niveles adaptativos. Base: `docs/defensa_preguntas_respuestas.md`.

---

## 5. Orden sugerido

1. Actualizar tablas de avance y CU.
2. Resolver la decisión sobre las encuestas.
3. Escribir los apartados nuevos: calidad, riesgos, planificación, anexos.
4. Ejecutar y registrar las pruebas.
5. Corregir inconsistencias, bibliografía y formato.
6. Actualizar el PPT.
