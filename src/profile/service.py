"""Perfil adaptativo de aprendizaje (RF-13, RF-14).

`QueryLog` registra una fila por cada explicacion que el usuario pide
("Ver explicacion en simple", RF-14.3) y por cada regeneracion explicita
("No entendi esto"). El valor inicial de cada tarjeta se obtiene por un
endpoint ligero que no escribe log, asi que `QueryLog` solo contiene
acciones deliberadas. `InstrumentVisit` registra una fila por instrumento
seleccionado y alimenta "instrumentos mas consultados" (RF-14.2).
"""

from sqlalchemy import func

from src.auth.models import User
from src.evaluation.models import InstrumentVisit, QueryLog
from src.extensions import db
from src.nlp.explainer import STYLE_LABELS
from src.nlp.levels import DEFAULT_LEVEL, EXPERIENCE_TO_LEVEL, LEVEL_ORDER

# RF-13.2: a partir de esta cantidad de regeneraciones para un indicador,
# se considera que al usuario le cuesta comprenderlo y se le baja un nivel de
# explicacion (mas basico) para ese indicador; cada nueva tanda baja otro escalon.
DETAIL_THRESHOLD = 2


INDICATORS = ("rsi", "medias_moviles", "macd", "bandas_bollinger")


# Ventana de filas recientes por indicador que se revisa para inferir el estilo preferido.
STYLE_WINDOW = 20


def _starting_level(experience: str | None) -> str:
    return EXPERIENCE_TO_LEVEL.get(experience, DEFAULT_LEVEL)


def _level_for(experience: str | None, regenerations: int) -> str:
    """Regla unica del nivel de explicacion (RF-13.2).

    La experiencia declarada fija el punto de partida (nunca -> basico, poco -> intermedio,
    experiencia -> avanzado; sin respuesta -> intermedio). Cada DETAIL_THRESHOLD
    regeneraciones ("No entendi esto") en un indicador bajan un escalon, con piso en basico.
    """
    index = LEVEL_ORDER.index(_starting_level(experience))
    index = max(0, index - regenerations // DETAIL_THRESHOLD)
    return LEVEL_ORDER[index]


def get_detail_level(user_id: int, indicator: str) -> str:
    if not user_id:
        return DEFAULT_LEVEL

    user = db.session.get(User, user_id)
    query = QueryLog.query.filter_by(user_id=user_id, indicator=indicator, is_regeneration=True)
    if user and user.level_reset_at:
        query = query.filter(QueryLog.created_at >= user.level_reset_at)
    return _level_for(user.experience_level if user else None, query.count())


def preferred_variant(user_id: int, indicator: str) -> int | None:
    """Redaccion (variant) en la que el usuario suele quedarse para un indicador.

    Un "punto de parada" es una explicacion que el usuario recibio y no regenero
    despues: cada cadena (consulta + sus "No entendi esto") se cierra en la ultima
    fila. Se devuelve la variante del punto de parada mas reciente dentro de las
    ultimas STYLE_WINDOW filas, o None si no hay historial (se usa 0).
    """
    if not user_id:
        return None

    rows = (
        QueryLog.query.filter_by(user_id=user_id, indicator=indicator)
        .order_by(QueryLog.id.desc())
        .limit(STYLE_WINDOW)
        .all()
    )
    rows.reverse()  # cronologico

    stops = []
    open_chain = {}  # (sesion, instrumento) -> ultima fila de la cadena abierta
    for row in rows:
        key = (row.session_id, row.instrument)
        if not row.is_regeneration and key in open_chain:
            stops.append(open_chain[key])  # una consulta nueva cierra la cadena anterior
        open_chain[key] = row
    stops.extend(open_chain.values())

    if not stops:
        return None
    return max(stops, key=lambda r: r.id).variant or 0


def recent_queries(user_id: int, limit: int = 50):
    """Ultimas consultas del usuario, mas recientes primero (historial, RF-10)."""
    return (
        QueryLog.query.filter_by(user_id=user_id)
        .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
        .limit(limit)
        .all()
    )


def recent_visits(user_id: int, limit: int = 20):
    """Instrumentos visitados, uno por instrumento con su ultima visita y total."""
    rows = (
        db.session.query(
            InstrumentVisit.instrument,
            func.max(InstrumentVisit.created_at).label("last_visit"),
            func.count(InstrumentVisit.id).label("total"),
        )
        .filter(InstrumentVisit.user_id == user_id)
        .group_by(InstrumentVisit.instrument)
        .order_by(func.max(InstrumentVisit.created_at).desc())
        .limit(limit)
        .all()
    )
    return [{"instrument": r.instrument, "last_visit": r.last_visit, "count": r.total} for r in rows]


def build_learning_profile(user_id: int):
    """Resumen del perfil de aprendizaje (RF-13.1, RF-14.1 a RF-14.5)."""
    # RF-14.3: total de consultas = explicaciones pedidas + regeneraciones.
    total_queries = QueryLog.query.filter_by(user_id=user_id).count()

    # RF-14.2: instrumentos mas consultados (top 5) y cuantos distintos hay.
    top_instruments_rows = (
        db.session.query(InstrumentVisit.instrument, func.count(InstrumentVisit.id).label("total"))
        .filter(InstrumentVisit.user_id == user_id)
        .group_by(InstrumentVisit.instrument)
        .order_by(func.count(InstrumentVisit.id).desc(), InstrumentVisit.instrument)
        .limit(5)
        .all()
    )
    top_instruments = [{"instrument": row.instrument, "count": row.total} for row in top_instruments_rows]
    distinct_instruments = (
        db.session.query(func.count(func.distinct(InstrumentVisit.instrument)))
        .filter(InstrumentVisit.user_id == user_id)
        .scalar()
    ) or 0

    # RF-14.1 y nivel de detalle (RF-13.2): regeneraciones por indicador.
    regeneration_rows = (
        db.session.query(QueryLog.indicator, func.count(QueryLog.id).label("total"))
        .filter(QueryLog.user_id == user_id, QueryLog.is_regeneration.is_(True))
        .group_by(QueryLog.indicator)
        .order_by(func.count(QueryLog.id).desc(), QueryLog.indicator)
        .all()
    )
    user = db.session.get(User, user_id)
    experience = user.experience_level if user else None
    # El nivel solo cuenta las regeneraciones posteriores al ultimo cambio de experiencia.
    level_query = db.session.query(QueryLog.indicator, func.count(QueryLog.id).label("total")).filter(
        QueryLog.user_id == user_id, QueryLog.is_regeneration.is_(True)
    )
    if user and user.level_reset_at:
        level_query = level_query.filter(QueryLog.created_at >= user.level_reset_at)
    regenerations = {row.indicator: row.total for row in level_query.group_by(QueryLog.indicator).all()}
    detail_levels = {
        indicator: _level_for(experience, regenerations.get(indicator, 0)) for indicator in INDICATORS
    }
    # Por que se aplica cada nivel (transparencia de CU-27): historial > experiencia declarada.
    start_level = _starting_level(experience)
    detail_sources = {
        indicator: (
            "historial"
            if detail_levels[indicator] != start_level
            else "experiencia" if experience in EXPERIENCE_TO_LEVEL else None
        )
        for indicator in INDICATORS
    }
    preferred_styles = {}
    for indicator in INDICATORS:
        variant = preferred_variant(user_id, indicator)
        preferred_styles[indicator] = None if variant is None else STYLE_LABELS.get(variant, str(variant))

    top_indicator = None
    top_indicator_count = 0
    last_query_for_indicator = None

    if regeneration_rows:
        top_indicator, top_indicator_count = regeneration_rows[0].indicator, regeneration_rows[0].total
        # RF-14.4 / RF-14.5: se reutiliza la ultima explicacion guardada.
        last_query_for_indicator = (
            QueryLog.query.filter_by(user_id=user_id, indicator=top_indicator)
            .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
            .first()
        )

    return {
        "total_queries": total_queries,
        "distinct_instruments": distinct_instruments,
        "top_instruments": top_instruments,
        "detail_levels": detail_levels,
        "detail_sources": detail_sources,
        "preferred_styles": preferred_styles,
        "experience_level": experience,
        "detail_threshold": DETAIL_THRESHOLD,
        "top_indicator": top_indicator,
        "top_indicator_regenerations": top_indicator_count,
        "top_indicator_instrument": last_query_for_indicator.instrument if last_query_for_indicator else None,
        "top_indicator_explanation": last_query_for_indicator.explanation_text if last_query_for_indicator else None,
        "top_indicator_variant": last_query_for_indicator.variant if last_query_for_indicator else 0,
    }
