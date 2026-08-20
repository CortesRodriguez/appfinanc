"""Reporte comparativo del Instrumento 1 (RF-15, CU-09, CU-10).

Con el diseño retrospectivo cada `SurveyResponse` ya contiene por
construcción las dos escalas (`scale_before` y `scale_now`), agrupadas
por `response_token`. El reporte agregado se construye promediando esas
escalas por concepto y calculando el delta subjetivo.

Las respuestas son anónimas: no aparece `user_id` ni `session_id` en
ninguna parte del reporte, y el `response_token` se ofusca en la vista
para que ni siquiera la investigadora pueda reidentificar respuestas.
"""

import csv
import io

from .models import SurveyResponse
from .surveys import SURVEY_CONCEPTS

_CONCEPT_LABEL = {c["id"]: c["label"] for c in SURVEY_CONCEPTS}


def _rows_by_response():
    """Devuelve {response_token: [SurveyResponse, ...]} solo con respuestas completas."""
    total_concepts = len(SURVEY_CONCEPTS)
    grouped: dict[str, list] = {}
    for row in SurveyResponse.query.all():
        grouped.setdefault(row.response_token, []).append(row)
    return {t: rows for t, rows in grouped.items() if len(rows) == total_concepts}


def build_comparative_report():
    """Consolida las respuestas retrospectivas (RF-15.1).

    Estructura de salida:
      - `rows`: lista de respuestas anonimizadas (una por `response_token`)
        con `avg_before`, `avg_now`, `avg_delta`.
      - `by_concept`: promedio por concepto sobre todas las respuestas.
      - `summary`: agregados globales.
    """
    by_response = _rows_by_response()

    rows = []
    for token, entries in by_response.items():
        avg_before = sum(e.scale_before for e in entries) / len(entries)
        avg_now = sum(e.scale_now for e in entries) / len(entries)
        rows.append(
            {
                "response_token": token,
                "avg_before": round(avg_before, 2),
                "avg_now": round(avg_now, 2),
                "avg_delta": round(avg_now - avg_before, 2),
            }
        )

    if not rows:
        return {"rows": [], "by_concept": [], "summary": None}

    by_concept: dict[str, dict] = {}
    for entries in by_response.values():
        for row in entries:
            slot = by_concept.setdefault(
                row.concept_id,
                {"concept_id": row.concept_id, "label": _CONCEPT_LABEL.get(row.concept_id, row.concept_id),
                 "sum_before": 0, "sum_now": 0, "n": 0},
            )
            slot["sum_before"] += row.scale_before
            slot["sum_now"] += row.scale_now
            slot["n"] += 1

    concept_rows = []
    for slot in by_concept.values():
        n = slot["n"]
        avg_b = slot["sum_before"] / n
        avg_n = slot["sum_now"] / n
        concept_rows.append(
            {
                "concept_id": slot["concept_id"],
                "label": slot["label"],
                "avg_before": round(avg_b, 2),
                "avg_now": round(avg_n, 2),
                "avg_delta": round(avg_n - avg_b, 2),
                "n": n,
            }
        )

    total = len(rows)
    summary = {
        "participants": total,
        "avg_before": round(sum(r["avg_before"] for r in rows) / total, 2),
        "avg_now": round(sum(r["avg_now"] for r in rows) / total, 2),
        "avg_delta": round(sum(r["avg_delta"] for r in rows) / total, 2),
        "concepts_evaluated": len(SURVEY_CONCEPTS),
    }
    return {"rows": rows, "by_concept": concept_rows, "summary": summary}


def export_report_csv() -> str:
    """CSV con una fila por respuesta anónima (RF-15.2, CU-10)."""
    report = build_comparative_report()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["response_token", "avg_before", "avg_now", "avg_delta"])
    for row in report["rows"]:
        writer.writerow([row["response_token"], row["avg_before"], row["avg_now"], row["avg_delta"]])
    return buffer.getvalue()
