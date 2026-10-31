"""Las rutas /api/* responden JSON aunque algo falle; las paginas conservan su HTML."""

import pytest


@pytest.fixture
def boom_app(app):
    """App con una ruta /api que revienta y otra pagina que revienta."""

    @app.route("/api/_boom")
    def _api_boom():
        raise RuntimeError("secreto interno: postgresql://usuario:clave@host/db")

    @app.route("/_pagina_boom")
    def _page_boom():
        raise RuntimeError("fallo en pagina")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["TESTING"] = False
    return app


def test_un_error_inesperado_en_api_devuelve_json_sin_filtrar_detalles(boom_app):
    response = boom_app.test_client().get("/api/_boom")
    assert response.status_code == 500
    assert response.is_json
    body = response.get_json()
    assert "error" in body
    assert "postgresql" not in response.get_data(as_text=True)
    assert "RuntimeError" not in response.get_data(as_text=True)


def test_una_ruta_api_inexistente_devuelve_json_404(client):
    response = client.get("/api/no-existe")
    assert response.status_code == 404
    assert response.is_json and "error" in response.get_json()


def test_un_metodo_no_permitido_en_api_devuelve_json_405(client):
    response = client.get("/api/query")
    assert response.status_code == 405
    assert response.is_json


def test_una_pagina_que_falla_sigue_respondiendo_html(boom_app):
    response = boom_app.test_client().get("/_pagina_boom")
    assert response.status_code == 500
    assert not response.is_json


def test_una_pagina_inexistente_sigue_respondiendo_html(client):
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert not response.is_json
