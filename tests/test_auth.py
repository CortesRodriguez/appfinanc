def _register(client, email="user@test.cl", password="Clave123!", username="Usuario", confirm=None):
    return client.post(
        "/api/auth/registro",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password if confirm is None else confirm,
        },
    )


def test_register_rejects_short_password(client):
    response = _register(client, password="Ab1!")
    assert response.status_code == 400
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
    _register(client, email="login@test.cl", password="Clave123!")
    response = client.post("/api/auth/login", json={"email": "login@test.cl", "password": "incorrecta"})
    assert response.status_code == 401


def test_login_succeeds_with_correct_credentials(client):
    _register(client, email="login2@test.cl", password="Clave123!")
    response = client.post("/api/auth/login", json={"email": "login2@test.cl", "password": "Clave123!"})
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


def test_register_rejects_missing_username(client):
    response = _register(client, username="")
    assert response.status_code == 400


def test_register_rejects_duplicate_username(client):
    _register(client, email="user1@test.cl", username="Duplicado")
    response = _register(client, email="user2@test.cl", username="Duplicado")
    assert response.status_code == 409


def test_register_rejects_email_without_at(client):
    response = _register(client, email="correo-sin-arroba.cl")
    assert response.status_code == 400


def test_register_rejects_malformed_email_domain(client):
    response = _register(client, email="user@dominio")
    assert response.status_code == 400


def test_register_rejects_password_too_long(client):
    response = _register(client, password="Ab1!" * 17)
    assert response.status_code == 400


def test_register_rejects_password_without_digit(client):
    response = _register(client, password="SoloLetras!")
    assert response.status_code == 400


def test_register_rejects_password_without_special_char(client):
    response = _register(client, password="SoloLetras123")
    assert response.status_code == 400


def test_register_rejects_password_without_letter(client):
    response = _register(client, password="12345678!")
    assert response.status_code == 400


def test_register_accepts_valid_complex_password(client):
    response = _register(client, password="Clave123!")
    assert response.status_code == 201


def test_register_accepts_password_at_max_length(client):
    password = "Clave123!" + "a" * 55
    assert len(password) == 64
    response = _register(client, email="max64@test.cl", password=password)
    assert response.status_code == 201


def test_register_rejects_password_over_max_length(client):
    password = "Clave123!" + "a" * 56
    assert len(password) == 65
    response = _register(client, email="over64@test.cl", password=password)
    assert response.status_code == 400


def test_register_rejects_multibyte_password_over_bcrypt_limit(client):
    """60 caracteres (< 64) pero > 72 bytes en UTF-8: bcrypt lanzaria ValueError
    (500) si el servicio no lo cortara antes con un 400 legible."""
    password = "Clave1!" + "ñ" * 53
    assert len(password) < 64 and len(password.encode("utf-8")) > 72
    response = _register(client, email="bytes@test.cl", password=password)
    assert response.status_code == 400
    assert "bytes" in response.get_json()["error"]


def test_register_rejects_username_over_column_length(client):
    response = _register(client, username="u" * 81)
    assert response.status_code == 400


def test_register_rejects_mismatched_confirmation(client):
    response = _register(client, confirm="Otra1234!")
    assert response.status_code == 400
    assert "no coinciden" in response.get_json()["error"]


def test_register_requires_confirmation_field(client):
    response = client.post(
        "/api/auth/registro",
        json={"username": "Sin", "email": "sin@test.cl", "password": "Clave123!"},
    )
    assert response.status_code == 400


def _fail_login(client, email, times):
    last = None
    for _ in range(times):
        last = client.post("/api/auth/login", json={"email": email, "password": "mala"})
    return last


def test_login_locks_account_after_five_failed_attempts(client):
    _register(client, email="lock@test.cl")
    client.post("/api/auth/logout")

    assert _fail_login(client, "lock@test.cl", 4).status_code == 401
    assert _fail_login(client, "lock@test.cl", 1).status_code == 401  # quinto fallo: bloquea

    # Bloqueada: ni siquiera la clave correcta entra.
    locked = client.post("/api/auth/login", json={"email": "lock@test.cl", "password": "Clave123!"})
    assert locked.status_code == 429
    assert "minuto" in locked.get_json()["error"]


def test_successful_login_resets_failed_attempts(client):
    _register(client, email="reset@test.cl")
    _fail_login(client, "reset@test.cl", 4)

    ok = client.post("/api/auth/login", json={"email": "reset@test.cl", "password": "Clave123!"})
    assert ok.status_code == 200

    # El contador volvio a cero: 4 fallos mas no bloquean.
    assert _fail_login(client, "reset@test.cl", 4).status_code == 401


def test_login_works_again_after_lock_expires(client, app):
    import datetime as dt

    from src.auth.models import User
    from src.extensions import db

    _register(client, email="expira@test.cl")
    _fail_login(client, "expira@test.cl", 5)
    assert client.post("/api/auth/login", json={"email": "expira@test.cl", "password": "Clave123!"}).status_code == 429

    with app.app_context():
        user = User.query.filter_by(email="expira@test.cl").first()
        user.locked_until = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        db.session.commit()

    assert client.post("/api/auth/login", json={"email": "expira@test.cl", "password": "Clave123!"}).status_code == 200


def test_unknown_email_gets_same_generic_error_as_wrong_password(client):
    _register(client, email="real@test.cl")
    wrong = client.post("/api/auth/login", json={"email": "real@test.cl", "password": "mala"})
    unknown = client.post("/api/auth/login", json={"email": "noexiste@test.cl", "password": "mala"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()["error"] == unknown.get_json()["error"]


def test_google_login_creates_new_user(app):
    from src.auth.service import login_or_register_google_user

    with app.app_context():
        user = login_or_register_google_user(google_id="g-1", email="nuevo@test.cl", name="Nuevo")
        assert user.email == "nuevo@test.cl"
        assert user.google_id == "g-1"
        assert user.password_hash is None


def test_google_login_reuses_existing_google_account(app):
    from src.auth.service import login_or_register_google_user

    with app.app_context():
        first = login_or_register_google_user(google_id="g-2", email="repetido@test.cl", name="Repetido")
        second = login_or_register_google_user(google_id="g-2", email="repetido@test.cl", name="Repetido")
        assert first.id == second.id


def test_google_login_rejects_email_with_existing_password_account(client, app):
    from src.auth.service import AuthError, login_or_register_google_user

    _register(client, email="conpass@test.cl", username="ConPass")

    with app.app_context():
        try:
            login_or_register_google_user(google_id="g-3", email="conpass@test.cl", name="Con Pass")
            assert False, "debía lanzar AuthError"
        except AuthError:
            pass

