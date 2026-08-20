def _register(client, email="user@test.cl", password="12345678", username="Usuario"):
    return client.post("/api/auth/registro", json={"username": username, "email": email, "password": password})


def test_register_rejects_short_password(client):
    response = _register(client, password="1234567")
    assert response.status_code == 409
    assert "8" in response.get_json()["error"]


def test_register_sets_session_cookies(client):
    response = _register(client)
    assert response.status_code == 201
    assert client.get_cookie("access_token_cookie") is not None
    assert client.get_cookie("csrf_access_token") is not None


def test_register_rejects_duplicate_email(client):
    _register(client, email="dup@test.cl")
    response = _register(client, email="dup@test.cl", username="Otro")
    assert response.status_code == 409


def test_login_rejects_wrong_password(client):
    _register(client, email="login@test.cl", password="12345678")
    response = client.post("/api/auth/login", json={"email": "login@test.cl", "password": "incorrecta"})
    assert response.status_code == 401


def test_login_succeeds_with_correct_credentials(client):
    _register(client, email="login2@test.cl", password="12345678")
    response = client.post("/api/auth/login", json={"email": "login2@test.cl", "password": "12345678"})
    assert response.status_code == 200


def test_logout_revokes_token(client):
    _register(client, email="logout@test.cl")
    csrf = client.get_cookie("csrf_access_token").value

    ok_before = client.get("/api/perfil", headers={"X-CSRF-TOKEN": csrf})
    assert ok_before.status_code == 200

    client.post("/api/auth/logout", headers={"X-CSRF-TOKEN": csrf})

    blocked_after = client.get("/api/perfil", headers={"X-CSRF-TOKEN": csrf})
    assert blocked_after.status_code == 401


def test_profile_page_redirects_anonymous_to_login(client):
    response = client.get("/perfil")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Bloque 3: consentimiento contextual movido al registro -------------------

def test_register_without_consent_leaves_flag_null(client, app):
    from src.auth.models import User

    _register(client, email="sin@consent.cl", password="12345678")
    with app.app_context():
        user = User.query.filter_by(email="sin@consent.cl").first()
        assert user is not None
        assert user.acepta_evaluacion is None


def test_register_with_explicit_consent_true(client, app):
    from src.auth.models import User

    response = client.post(
        "/api/auth/registro",
        json={
            "username": "Voluntaria",
            "email": "voluntaria@test.cl",
            "password": "12345678",
            "acepta_evaluacion": True,
        },
    )
    assert response.status_code == 201
    with app.app_context():
        user = User.query.filter_by(email="voluntaria@test.cl").first()
        assert user is not None
        assert user.acepta_evaluacion is True


def test_register_with_explicit_consent_false(client, app):
    from src.auth.models import User

    response = client.post(
        "/api/auth/registro",
        json={
            "email": "declina@test.cl",
            "password": "12345678",
            "acepta_evaluacion": False,
        },
    )
    assert response.status_code == 201
    with app.app_context():
        user = User.query.filter_by(email="declina@test.cl").first()
        assert user is not None
        assert user.acepta_evaluacion is False
