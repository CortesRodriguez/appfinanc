"""Perfil adaptativo de aprendizaje (RF-18, RF-19).

`QueryLog` registra cada indicador consultado (incluye las cuatro
llamadas paralelas que dispara una sola seleccion de instrumento en el
dashboard) y cada regeneracion explicita ("No entendi esto"). Para las
metricas que ve el usuario (RF-19.2, RF-19.3) se usa en cambio
`InstrumentVisit`, que registra una fila por instrumento seleccionado:
así "consultas totales" cuenta acciones reales del usuario (ver un
instrumento, pedir una explicacion nueva) en vez de inflarse por los
cuatro indicadores que se calculan automaticamente detras de cada
seleccion.
"""

from sqlalchemy import func

from src.evaluation.models import InstrumentVisit, QueryLog
from src.extensions import db

# RF-18.3: a partir de esta cantidad de regeneraciones para un indicador,
# se considera que al usuario le cuesta comprenderlo y se le entregan
# explicaciones con mayor nivel de detalle para ese indicador.
DETAIL_THRESHOLD = 2


def get_detail_level(user_id: int, indicator: str) -> str:
    if not user_id:
        return "estandar"

    count = QueryLog.query.filter_by(user_id=user_id, indicator=indicator, is_regeneration=True).count()
    return "detallado" if count >= DETAIL_THRESHOLD else "estandar"


def build_learning_profile(user_id: int):
    """Retorna el resumen de perfil descrito en RF-19.1 a RF-19.4.

    "Consultas totales" (RF-19.3) = instrumentos vistos + regeneraciones
    explicitas: cada una es una accion real del usuario, a diferencia de
    los cuatro `QueryLog` que se crean automaticamente por instrumento.
    """
    visit_count = InstrumentVisit.query.filter_by(user_id=user_id).count()
    regeneration_count = QueryLog.query.filter_by(user_id=user_id, is_regeneration=True).count()
    total_queries = visit_count + regeneration_count

    top_instruments_rows = (
        db.session.query(InstrumentVisit.instrument, func.count(InstrumentVisit.id).label("total"))
        .filter(InstrumentVisit.user_id == user_id)
        .group_by(InstrumentVisit.instrument)
        .order_by(func.count(InstrumentVisit.id).desc())
        .limit(5)
        .all()
    )
    top_instruments = [{"instrument": row.instrument, "count": row.total} for row in top_instruments_rows]

    regeneration_rows = (
        db.session.query(QueryLog.indicator, func.count(QueryLog.id).label("total"))
        .filter(QueryLog.user_id == user_id, QueryLog.is_regeneration.is_(True))
        .group_by(QueryLog.indicator)
        .order_by(func.count(QueryLog.id).desc())
        .all()
    )

    top_indicator = None
    top_indicator_count = 0
    last_query_for_indicator = None

    if regeneration_rows:
        top_indicator, top_indicator_count = regeneration_rows[0].indicator, regeneration_rows[0].total
        last_query_for_indicator = (
            QueryLog.query.filter_by(user_id=user_id, indicator=top_indicator)
            .order_by(QueryLog.created_at.desc())
            .first()
        )

    return {
        "total_queries": total_queries,
        "top_instruments": top_instruments,
        "top_indicator": top_indicator,
        "top_indicator_regenerations": top_indicator_count,
        "top_indicator_instrument": last_query_for_indicator.instrument if last_query_for_indicator else None,
        "top_indicator_explanation": last_query_for_indicator.explanation_text if last_query_for_indicator else None,
        "top_indicator_variant": last_query_for_indicator.variant if last_query_for_indicator else 0,
    }
