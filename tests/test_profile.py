import datetime as dt


def _fake_history(symbol, days, alpha_vantage_key=""):
    start = dt.date(2025, 1, 1)
    records = [{"date": (start + dt.timedelta(days=i)).isoformat(), "close": 100 + i * 0.3} for i in range(days)]
    return {"symbol": symbol, "source": "Yahoo Finance", "fetched_at": "2026-01-01T00:00:00+00:00", "records": records}


def _register_and_login(client, email="perfil@test.cl", experience=None, username="Perfil"):
    payload = {"username": username, "email": email, "password": "Clave123!", "password_confirm": "Clave123!"}
    if experience is not None:
        payload["experience_level"] = experience
    client.post("/api/auth/registro", json=payload)
    return client.get_cookie("csrf_access_token").value


def test_authenticated_visit_is_attributed_to_user_profile(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client)
    headers = {"X-CSRF-TOKEN": csrf}

    # Seleccionar un instrumento = una visita. Cada "Ver explicacion en simple"
    # (/api/query) es una consulta deliberada y queda atribuida a la cuenta.
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    client.post("/api/historial/visita", json={"symbol": "FALABELLA.SN"}, headers=headers)
    client.post("/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers)

    data = client.get("/api/perfil", headers=headers).get_json()
    assert data["total_queries"] == 1  # RF-14.3: visitas no cuentan, la explicacion pedida si
    assert data["distinct_instruments"] == 2
    assert data["top_instruments"][0]["instrument"] == "SQM-B.SN"
    assert data["top_instruments"][0]["count"] == 2
    # El perfil muestra el nombre de la empresa, no el ticker
    assert data["top_instruments"][0]["name"] != "SQM-B.SN"
    assert "SQM" in data["top_instruments"][0]["name"]

    page = client.get("/perfil").data.decode()
    assert "Explicaciones pedidas" in page
    assert data["top_instruments"][0]["name"] in page


def test_total_queries_counts_explanations_plus_regenerations(client, monkeypatch):
    """RF-14.3: 4 explicaciones pedidas + 1 'No entendi esto' = 5 consultas;
    seleccionar el instrumento (visita) no suma."""
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="totales@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    results = {}
    for indicator in ("bandas_bollinger", "rsi", "medias_moviles", "macd"):
        results[indicator] = client.post(
            "/api/query", json={"symbol": "SQM-B.SN", "indicator": indicator, "days": 180}, headers=headers
        ).get_json()

    client.post(
        "/api/regenerate",
        json={
            "symbol": "SQM-B.SN",
            "indicator": "rsi",
            "days": 180,
            "previous_variant": results["rsi"]["variant"],
        },
        headers=headers,
    )

    profile = client.get("/api/perfil", headers=headers).get_json()
    assert profile["total_queries"] == 5


def test_regeneration_count_identifies_hardest_indicator(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="hard@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )
    client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "macd", "days": 180}, headers=headers
    )

    profile = client.get("/api/perfil", headers=headers).get_json()
    assert profile["top_indicator"] == "rsi"
    assert profile["top_indicator_regenerations"] == 1
    assert profile["top_indicator_explanation"]


def test_queries_without_login_are_not_attributed_to_any_profile(client, monkeypatch, app):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()

    client.post("/api/query", json={"symbol": "SPY", "indicator": "rsi", "days": 180})

    from src.profile.models import QueryLog

    with app.app_context():
        log = QueryLog.query.order_by(QueryLog.id.desc()).first()
        assert log.user_id is None


def test_profile_regenerate_requires_previous_activity(client):
    csrf = _register_and_login(client, email="empty@test.cl")
    response = client.post("/api/perfil/regenerar", headers={"X-CSRF-TOKEN": csrf})
    assert response.status_code == 404


def test_profile_regenerate_produces_new_explanation(client, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="regen@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    # El perfil solo identifica un "indicador mas dificil" una vez que el
    # usuario ha pedido regenerar al menos una explicacion (RF-19.1).
    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )

    response = client.post("/api/perfil/regenerar", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["indicator"] == "rsi"
    assert data["explanation"]


def test_profile_empty_state_has_no_hard_indicator(client):
    csrf = _register_and_login(client, email="vacio@test.cl")
    data = client.get("/api/perfil", headers={"X-CSRF-TOKEN": csrf}).get_json()
    assert data["total_queries"] == 0
    assert data["top_instruments"] == []
    assert data["top_indicator"] is None
    assert set(data["detail_levels"].values()) == {"intermedio"}

    page = client.get("/perfil").data.decode()
    assert "Aún no hay datos suficientes" in page


def test_two_regenerations_lower_the_level_one_step(client, monkeypatch):
    """RF-13.2 / CU-27: con 2 regeneraciones de un indicador su nivel baja un escalon
    (intermedio -> basico, solo ese indicador) y el perfil lo muestra."""
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="nivel@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    variant = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()["variant"]

    for _ in range(2):
        variant = client.post(
            "/api/regenerate",
            json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": variant},
            headers=headers,
        ).get_json()["variant"]

    levels = client.get("/api/perfil", headers=headers).get_json()["detail_levels"]
    assert levels["rsi"] == "basico"
    assert levels["macd"] == "intermedio"
    assert "Básico" in client.get("/perfil").data.decode()


def test_profile_regenerate_uses_real_detail_level_and_timing(client, monkeypatch, app):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.profile.models import QueryLog
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="tiempo@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    )

    # 1 sola regeneracion -> sigue en el nivel inicial: el perfil no fuerza un cambio.
    data = client.post("/api/perfil/regenerar", headers=headers).get_json()
    assert data["detail_level"] == "intermedio"
    assert data["total_queries"] == 3  # query + regenerate + esta
    assert data["regenerations"] == 2

    with app.app_context():
        log = QueryLog.query.order_by(QueryLog.id.desc()).first()
        assert log.is_regeneration is True
        assert log.processing_time_ms is not None


def test_profile_reuses_last_explanation_without_regenerating(client, monkeypatch, app):
    """RF-14.5: visitar /perfil no genera ni registra nada; muestra la guardada."""
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.profile.models import QueryLog
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="reuso@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    first = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()
    regenerated = client.post(
        "/api/regenerate",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180, "previous_variant": first["variant"]},
        headers=headers,
    ).get_json()

    with app.app_context():
        before = QueryLog.query.count()

    for _ in range(2):
        page = client.get("/perfil").data.decode()
    assert regenerated["explanation"] in page

    with app.app_context():
        assert QueryLog.query.count() == before


# --- Adaptacion al usuario: experiencia declarada + estilo preferido (RF-13.2 / CU-27) ---

INDICATORS = ("rsi", "medias_moviles", "macd", "bandas_bollinger")


def _setup(client, monkeypatch, **kwargs):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    return {"X-CSRF-TOKEN": _register_and_login(client, **kwargs)}


def _query(client, headers, indicator="rsi", symbol="SQM-B.SN"):
    return client.post(
        "/api/query", json={"symbol": symbol, "indicator": indicator, "days": 180}, headers=headers
    ).get_json()


def _regenerate(client, headers, previous_variant, indicator="rsi", symbol="SQM-B.SN"):
    return client.post(
        "/api/regenerate",
        json={"symbol": symbol, "indicator": indicator, "days": 180, "previous_variant": previous_variant},
        headers=headers,
    ).get_json()


def test_register_rejects_invalid_experience(client):
    response = client.post(
        "/api/auth/registro",
        json={
            "username": "X", "email": "x@test.cl", "password": "Clave123!",
            "password_confirm": "Clave123!", "experience_level": "gurú",
        },
    )
    assert response.status_code == 400
    assert "experiencia" in response.get_json()["error"]


def test_experience_nunca_starts_every_indicator_basico(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="nunca@test.cl", experience="nunca")
    data = client.get("/api/perfil", headers=headers).get_json()
    assert data["experience_level"] == "nunca"
    assert set(data["detail_levels"].values()) == {"basico"}
    assert set(data["detail_sources"].values()) == {"experiencia"}
    # ya desde la primera consulta, sin historial: explicacion basica con IPSA
    result = _query(client, headers)
    assert result["detail_level"] == "basico"
    assert "IPSA" in result["explanation"]


def test_experience_experiencia_starts_avanzado_and_missing_intermedio(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="exp@test.cl", experience="experiencia")
    assert set(client.get("/api/perfil", headers=headers).get_json()["detail_levels"].values()) == {"avanzado"}
    result = _query(client, headers)
    assert result["detail_level"] == "avanzado"
    assert "IPSA" not in result["explanation"]

    other = client.application.test_client()
    other_headers = {"X-CSRF-TOKEN": _register_and_login(other, email="sin@test.cl", username="Sin")}
    data = other.get("/api/perfil", headers=other_headers).get_json()
    assert data["experience_level"] is None
    assert set(data["detail_levels"].values()) == {"intermedio"}
    assert set(data["detail_sources"].values()) == {None}


def test_behavior_lowers_level_step_by_step_with_floor(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="baja@test.cl", experience="experiencia")
    variant = _query(client, headers)["variant"]
    expected = {2: "intermedio", 4: "basico", 6: "basico"}
    for count in range(1, 7):
        variant = _regenerate(client, headers, variant)["variant"]
        if count in expected:
            data = client.get("/api/perfil", headers=headers).get_json()
            assert data["detail_levels"]["rsi"] == expected[count], count
            assert data["detail_sources"]["rsi"] == "historial"
    assert data["detail_levels"]["macd"] == "avanzado"
    assert data["detail_sources"]["macd"] == "experiencia"


def test_patch_experience_updates_levels_and_validates(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="patch@test.cl")

    ok = client.patch("/api/perfil/experiencia", json={"experience_level": "nunca"}, headers=headers)
    assert ok.status_code == 200
    assert set(ok.get_json()["detail_levels"].values()) == {"basico"}

    bad = client.patch("/api/perfil/experiencia", json={"experience_level": "xyz"}, headers=headers)
    assert bad.status_code == 400

    cleared = client.patch("/api/perfil/experiencia", json={"experience_level": ""}, headers=headers)
    assert cleared.get_json()["experience_level"] is None
    assert set(cleared.get_json()["detail_levels"].values()) == {"intermedio"}


def test_patch_experience_requires_session_and_csrf(client, monkeypatch):
    anonymous = client.patch("/api/perfil/experiencia", json={"experience_level": "nunca"})
    assert anonymous.status_code == 401

    _setup(client, monkeypatch, email="csrf@test.cl")
    no_csrf = client.patch("/api/perfil/experiencia", json={"experience_level": "nunca"})
    assert no_csrf.status_code in (401, 403)


def test_preferred_variant_is_where_the_user_stopped(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="estilo@test.cl")

    # Sin historial: arranca en la redaccion 0 y no hay estilo preferido.
    first = _query(client, headers)
    assert first["variant"] == 0
    assert client.get("/api/perfil", headers=headers).get_json()["preferred_styles"]["rsi"] == "directa"

    # Regenera hasta la redaccion 2 y se detiene ahi.
    v1 = _regenerate(client, headers, first["variant"])["variant"]
    v2 = _regenerate(client, headers, v1)["variant"]
    assert v2 == 2

    data = client.get("/api/perfil", headers=headers).get_json()
    assert data["preferred_styles"]["rsi"] == "con contexto"
    assert data["preferred_styles"]["macd"] is None  # sin datos en otros indicadores

    # La proxima consulta (otro instrumento) parte en ese estilo.
    assert _query(client, headers, symbol="FALABELLA.SN")["variant"] == 2


def test_preferred_variant_ignores_chain_that_was_regenerated_further(client, monkeypatch, app):
    """Una consulta (v0) seguida de regeneraciones no es punto de parada: lo es la ultima."""
    headers = _setup(client, monkeypatch, email="cadena@test.cl")
    v0 = _query(client, headers)["variant"]
    v1 = _regenerate(client, headers, v0)["variant"]

    from src.auth.models import User
    from src.profile.service import preferred_variant

    with app.app_context():
        user = User.query.filter_by(email="cadena@test.cl").first()
        assert preferred_variant(user.id, "rsi") == v1 == 1
        assert preferred_variant(user.id, "macd") is None
        assert preferred_variant(None, "rsi") is None


def test_style_preference_is_per_user(client, monkeypatch):
    headers_a = _setup(client, monkeypatch, email="a@test.cl", username="A")
    v = _query(client, headers_a)["variant"]
    _regenerate(client, headers_a, _regenerate(client, headers_a, v)["variant"])

    other = client.application.test_client()
    headers_b = {"X-CSRF-TOKEN": _register_and_login(other, email="b@test.cl", username="B")}
    data = other.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers_b
    ).get_json()
    assert data["variant"] == 0


_TEMPLATE_SAMPLES = {
    "rsi": [(50, "bajo", "neutral", None), (55, "medio", "neutral", None),
            (75, "alto", "sobrecomprado", None), (22, "alto", "sobrevendido", None)],
    "medias_moviles": [(4.2, "bajo", None, "alcista"), (-1.4, "medio", None, "bajista"),
                       (12.1, "alto", None, "alcista"), (-11.0, "alto", None, "bajista")],
    "macd": [(0.1, "bajo", None, "alcista"), (-0.5, "medio", None, "bajista"), (2.5, "alto", None, "alcista")],
    "bandas_bollinger": [(0.5, "bajo", "normal", None), (0.9, "medio", "cercano_al_extremo", None),
                         (0.1, "medio", "cercano_al_extremo", None), (1.2, "alto", "sobrecomprado", None),
                         (-0.2, "alto", "sobrevendido", None)],
}


def _template_cases():
    for indicator, rows in _TEMPLATE_SAMPLES.items():
        for value, risk, signal, trend in rows:
            data = {"indicator": indicator, "risk_level": risk, "value": value, "symbol": "SQM-B.SN",
                    "signal": signal, "trend": trend}
            if indicator == "medias_moviles":
                data.update(sma_short=10, sma_long=9 if trend == "alcista" else 11)
            yield data


def test_every_template_style_stays_coherent_with_the_validator():
    """Ningun nivel ni estilo de plantilla puede romper la coherencia (RF-04.2)."""
    from src.nlp.explainer import STYLE_LABELS, TEMPLATES, generate_explanation
    from src.nlp.levels import LEVEL_ORDER
    from src.nlp.validator import validate_coherence

    assert set(TEMPLATES) == set(LEVEL_ORDER)
    for level in LEVEL_ORDER:
        for data in _template_cases():
            assert len(TEMPLATES[level][data["indicator"]][data["risk_level"]]) == len(STYLE_LABELS)
            for variant in STYLE_LABELS:
                text = generate_explanation(data, variant=variant, use_finbert=False, detail_level=level)["text"]
                assert validate_coherence(data, text) == (True, None), (level, data["indicator"], variant, text)


def test_templates_follow_each_level_ficha():
    """Las plantillas de respaldo cumplen la ficha del nivel: largo maximo, sin jerga en
    basico, contexto IPSA solo en basico e intermedio, y el placeholder se resuelve."""
    from src.nlp.explainer import STYLE_LABELS, generate_explanation
    from src.nlp.levels import LEVEL_ORDER, LEVELS, contains_forbidden_term

    for level in LEVEL_ORDER:
        ficha = LEVELS[level]
        for data in _template_cases():
            for variant in STYLE_LABELS:
                result = generate_explanation(data, variant=variant, use_finbert=False, detail_level=level)
                text = result["text"]
                assert result["detail_level"] == level
                assert len(text.split()) <= ficha["max_words"], (level, text)
                assert contains_forbidden_term(level, text) is None, (level, text)
                assert ("IPSA" in text) == ficha["ipsa"], (level, text)
                assert "{" not in text and ", ." not in text and ": ." not in text, (level, text)


def test_no_template_uses_metaphors():
    """Las explicaciones son literales: ninguna plantilla de ningun nivel usa analogias."""
    import re

    from src.nlp.explainer import TEMPLATES

    metaphors = re.compile(r"term[óo]metro|corredor|\bpedal\b|pasillo|carretera|\bpulso\b|\bauto\b|\btren\b|paredes", re.I)
    for level, indicators in TEMPLATES.items():
        for indicator, risks in indicators.items():
            for risk, pool in risks.items():
                for text in pool:
                    assert not metaphors.search(text), (level, indicator, risk, text)


def test_llm_prompts_forbid_analogies():
    from src.nlp.llm_explainer import _STYLE_HINTS, _build_llm_prompt, build_system_prompt

    assert "analogía" not in _STYLE_HINTS[2].replace("sin analogías", "")
    assert "No uses analogías" in build_system_prompt("intermedio")
    assert "No uses analogías" in build_system_prompt("basico")
    data = {"indicator": "macd", "value": 1.2, "risk_level": "medio", "trend": "alcista"}
    assert "Incluye una analogía" not in _build_llm_prompt(data, "Banco BCI", "basico", variant=2)


def test_llm_output_with_metaphor_falls_back_to_basico_templates(monkeypatch):
    from src.nlp.explainer import generate_explanation

    data = {"indicator": "rsi", "value": 55.0, "risk_level": "medio", "signal": "neutral", "symbol": "BCI.SN"}
    monkeypatch.setattr(
        "src.nlp.llm_explainer.generate_explanation_llm",
        lambda *a, **k: "El RSI es como un termómetro: marca 55.0 y es riesgo medio.",
    )
    result = generate_explanation(data, use_finbert=False, detail_level="basico", use_llm=True, llm_api_key="x")
    assert "termómetro" not in result["text"].lower()


def test_basico_level_mentions_no_threshold_numbers():
    from src.nlp.explainer import STYLE_LABELS, generate_explanation

    for data in _template_cases():
        if data["indicator"] != "rsi":
            continue
        for variant in STYLE_LABELS:
            text = generate_explanation(data, variant=variant, use_finbert=False, detail_level="basico")["text"]
            assert "70" not in text and "30" not in text, text


def test_unknown_level_falls_back_to_default():
    from src.nlp.explainer import generate_explanation

    data = next(_template_cases())
    assert generate_explanation(data, use_finbert=False, detail_level="detallado")["detail_level"] == "intermedio"


def test_system_prompt_carries_each_level_ficha():
    from src.nlp.levels import LEVEL_ORDER, LEVELS
    from src.nlp.llm_explainer import _build_llm_prompt, build_system_prompt

    prompts = {level: build_system_prompt(level) for level in LEVEL_ORDER}
    assert len(set(prompts.values())) == len(LEVEL_ORDER)
    for level, prompt in prompts.items():
        ficha = LEVELS[level]
        assert ficha["audience"] in prompt
        assert ficha["vocabulary"] in prompt
        assert f"Máximo {ficha['max_words']} palabras" in prompt
    assert "No agregues contexto del IPSA" in prompts["avanzado"]

    data = {"indicator": "rsi", "value": 78.5, "risk_level": "alto", "signal": "sobrecomprado"}
    basic_user = _build_llm_prompt(data, "Banco BCI", "basico", variant=2)
    assert '"78.5"' in basic_user and '"riesgo alto"' in basic_user
    assert "sobrecompra" not in basic_user  # el dato se describe sin jerga
    assert "analogía" not in _build_llm_prompt(data, "Banco BCI", "avanzado", variant=2)


def test_llm_output_with_jargon_falls_back_to_basico_templates(monkeypatch):
    from src.nlp.explainer import generate_explanation

    data = {"indicator": "rsi", "value": 78.5, "risk_level": "alto", "signal": "sobrecomprado", "symbol": "BCI.SN"}
    jargon = "El RSI de BCI está en 78.5 (riesgo alto): sobrecompra con momentum extremo."
    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", lambda *a, **k: jargon)

    basic = generate_explanation(data, use_finbert=False, detail_level="basico", use_llm=True, llm_api_key="x")
    assert basic["text"] != jargon
    advanced = generate_explanation(data, use_finbert=False, detail_level="avanzado", use_llm=True, llm_api_key="x")
    assert advanced["text"] == jargon


def _history_page(client):
    return client.get("/perfil").data.decode()


def test_history_lists_queries_and_visits_in_profile(client, monkeypatch):
    """RF-10 / CU-30: las consultas y visitas de la cuenta se ven en /perfil (pestana
    Historial) con nombre de empresa, valor y riesgo; cada visita aparece una sola vez."""
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="hist@test.cl")
    headers = {"X-CSRF-TOKEN": csrf}

    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)
    client.post("/api/historial/visita", json={"symbol": "FALABELLA.SN"}, headers=headers)
    query = client.post(
        "/api/query", json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180}, headers=headers
    ).get_json()

    page = _history_page(client)
    assert 'id="panel-historial"' in page
    assert "Explicaciones que pediste" in page
    assert "Acciones que revisaste" in page
    assert "RSI" in page
    assert "SQM-B" in page and "Falabella" in page
    assert f'{query["value"]}' in page
    assert "Aún no has pedido explicaciones" not in page


def test_history_empty_state_for_new_account(client):
    _register_and_login(client, email="vacio2@test.cl")
    assert "Aún no has pedido explicaciones" in _history_page(client)


def test_query_log_stores_detail_for_history(client, app, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.profile.models import QueryLog
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="detalle@test.cl")
    data = client.post(
        "/api/query",
        json={"symbol": "SQM-B.SN", "indicator": "rsi", "days": 180},
        headers={"X-CSRF-TOKEN": csrf},
    ).get_json()

    with app.app_context():
        row = QueryLog.query.one()
        assert row.value == data["value"]
        assert row.risk_level == data["risk_level"]
        assert row.unit == data["unit"]
        assert row.period_days == 180


def test_history_is_private_per_user(client, app, monkeypatch):
    monkeypatch.setattr("src.extractor.fetch_price_history", _fake_history)
    from src.extractor.cache import price_history_cache

    price_history_cache.clear()
    csrf = _register_and_login(client, email="a@test.cl", username="UsuarioA")
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers={"X-CSRF-TOKEN": csrf})

    other = app.test_client()
    _register_and_login(other, email="b@test.cl", username="UsuarioB")
    page = other.get("/perfil").data.decode()
    assert "Acciones que revisaste" not in page
    assert "SQM-B" not in page


def test_old_history_url_redirects_to_profile_tab(client):
    response = client.get("/history")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/perfil#historial")


def test_navbar_for_logged_out_visitor(client):
    page = client.get("/glosario").data.decode()
    assert ">Acciones<" in page and ">Glosario<" in page
    assert "Iniciar sesión" in page and "Crear cuenta" in page
    assert "Consultar" not in page
    assert 'id="user-menu-btn"' not in page


def test_navbar_for_logged_in_user_has_account_menu(client):
    _register_and_login(client, email="nav@test.cl", username="Navegante")
    page = client.get("/glosario").data.decode()
    assert 'id="user-menu-btn"' in page
    assert "Mi perfil" in page and "Historial" in page and "Cerrar sesión" in page
    assert 'id="logout-link"' in page
    assert "Crear cuenta" not in page


def test_landing_for_visitor_has_welcome_and_movers(client):
    page = client.get("/").data.decode()
    assert "Bienvenido a Norte" in page
    assert "Mayores alzas del día" in page and "Mayores bajas del día" in page
    assert "Sigue donde quedaste" not in page


def test_landing_for_new_account_greets_without_recent_section(client):
    _register_and_login(client, email="portada0@test.cl", username="Portada")
    page = client.get("/").data.decode()
    assert "Hola, Portada" in page
    assert "Bienvenido a Norte" not in page
    assert "Sigue donde quedaste" not in page


def test_landing_lists_recent_visits_of_the_account_only(client):
    csrf = _register_and_login(client, email="portada1@test.cl", username="Uno")
    headers = {"X-CSRF-TOKEN": csrf}
    client.post("/api/historial/visita", json={"symbol": "FALABELLA.SN"}, headers=headers)
    client.post("/api/historial/visita", json={"symbol": "SQM-B.SN"}, headers=headers)

    page = client.get("/").data.decode()
    assert "Sigue donde quedaste" in page
    assert 'data-symbol="FALABELLA.SN"' in page and 'data-symbol="SQM-B.SN"' in page
    assert page.index('data-symbol="SQM-B.SN"') < page.index('data-symbol="FALABELLA.SN"')

    # Otra cuenta no ve las visitas de la primera.
    client.post("/api/auth/logout", headers=headers)
    _register_and_login(client, email="portada2@test.cl", username="Dos")
    other = client.get("/").data.decode()
    assert "Sigue donde quedaste" not in other
    assert 'data-symbol="FALABELLA.SN"' not in other


def test_landing_has_movers_and_news_blocks_only(client):
    page = client.get("/").data.decode()
    for text in ("Mayores alzas del día", "Mayores bajas del día", "Noticias del mercado", "Por qué se mueven hoy"):
        assert text in page
    assert 'id="news-market"' in page and 'id="news-movers"' in page
    assert "/api/news" in page and "/api/sparkline" in page
    # Bloques retirados del rediseño.
    assert 'id="market-strip"' not in page and 'id="sector-grid"' not in page


def test_trim_prefers_sentence_boundary():
    from src.nlp.explainer import _trim_to_max_words

    text = "Una frase completa con varias palabras aquí. Otra frase que se corta y no termina bien por el límite."
    assert _trim_to_max_words(text, 10) == "Una frase completa con varias palabras aquí."
    assert _trim_to_max_words("uno dos tres cuatro cinco seis", 4) == "uno dos tres cuatro."


def test_llm_text_that_loses_risk_label_when_trimmed_falls_back_to_templates(monkeypatch):
    from src.nlp.explainer import generate_explanation

    data = {"indicator": "rsi", "value": 28.11, "risk_level": "alto", "signal": "sobrevendido", "symbol": "BCI.SN"}
    long_text = (
        "El RSI de BCI está en 28.11, una cifra que mide la fuerza reciente del precio con mucho detalle. "
        + "Relleno " * 60
        + "Todo esto implica riesgo alto."
    )
    monkeypatch.setattr("src.nlp.llm_explainer.generate_explanation_llm", lambda *a, **k: long_text)
    result = generate_explanation(data, use_finbert=False, detail_level="intermedio", use_llm=True, llm_api_key="x")
    assert "Relleno" not in result["text"]
    assert "riesgo alto" in result["text"].lower() and "28.11" in result["text"]


def test_changing_experience_resets_the_regeneration_count(client, monkeypatch):
    """Tras cambiar la experiencia declarada, las regeneraciones anteriores ya no bajan
    el nivel: todos los indicadores parten del nivel de la nueva experiencia."""
    headers = _setup(client, monkeypatch, email="reset@test.cl", experience="poco")
    variant = _query(client, headers, indicator="macd")["variant"]
    for _ in range(5):
        variant = _regenerate(client, headers, variant, indicator="macd")["variant"]
    levels = client.get("/api/perfil", headers=headers).get_json()["detail_levels"]
    assert levels["macd"] == "basico"

    changed = client.patch("/api/perfil/experiencia", json={"experience_level": "experiencia"}, headers=headers)
    assert set(changed.get_json()["detail_levels"].values()) == {"avanzado"}
    assert changed.get_json()["detail_sources"]["macd"] == "experiencia"
    assert _query(client, headers, indicator="macd")["detail_level"] == "avanzado"

    # Las regeneraciones nuevas sí cuentan desde el cambio.
    variant = _query(client, headers, indicator="macd")["variant"]
    for _ in range(2):
        variant = _regenerate(client, headers, variant, indicator="macd")["variant"]
    data = client.get("/api/perfil", headers=headers).get_json()
    assert data["detail_levels"]["macd"] == "intermedio"
    assert data["detail_levels"]["rsi"] == "avanzado"


def test_saving_the_same_experience_does_not_reset_the_count(client, monkeypatch):
    headers = _setup(client, monkeypatch, email="igual@test.cl", experience="poco")
    variant = _query(client, headers)["variant"]
    for _ in range(2):
        variant = _regenerate(client, headers, variant)["variant"]
    client.patch("/api/perfil/experiencia", json={"experience_level": "poco"}, headers=headers)
    levels = client.get("/api/perfil", headers=headers).get_json()["detail_levels"]
    assert levels["rsi"] == "basico"
