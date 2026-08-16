"""Pruebas de las condiciones de carrera encontradas al usar el dashboard real
(varias solicitudes en paralelo por cada instrumento seleccionado)."""

import threading


def test_ensure_evaluation_session_survives_concurrent_creation(app):
    """El dashboard dispara 4 consultas en paralelo la primera vez que un
    usuario interactua en una sesion nueva; todas intentan crear la misma
    fila de EvaluationSession al mismo tiempo. Antes de la correccion, la
    segunda en llegar chocaba con IntegrityError (UNIQUE constraint) y la
    solicitud completa fallaba con un 500."""
    from src.evaluation import ensure_evaluation_session
    from src.evaluation.models import EvaluationSession

    session_id = "concurrent-session-test"
    errors = []

    def _worker():
        try:
            with app.app_context():
                ensure_evaluation_session(session_id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []

    with app.app_context():
        assert EvaluationSession.query.filter_by(session_id=session_id).count() == 1
