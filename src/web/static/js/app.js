// Barra superior: menu de usuario (escritorio) y panel plegable (celular).
(function initTopbarMenus() {
  const toggle = document.getElementById("nav-toggle");
  const nav = document.getElementById("main-nav");
  const userBtn = document.getElementById("user-menu-btn");
  const userList = document.getElementById("user-menu-list");

  function setUserMenu(open) {
    if (!userBtn) return;
    userBtn.setAttribute("aria-expanded", open ? "true" : "false");
    userList.classList.toggle("hidden", !open);
  }

  function setNav(open) {
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
    nav.classList.toggle("open", open);
  }

  if (userBtn) {
    userBtn.addEventListener("click", () => setUserMenu(userBtn.getAttribute("aria-expanded") !== "true"));
    // Ir a "Historial" estando ya en el perfil solo cambia el hash: cerrar el menu.
    userList.addEventListener("click", () => setUserMenu(false));
  }
  if (toggle) toggle.addEventListener("click", () => setNav(toggle.getAttribute("aria-expanded") !== "true"));

  document.addEventListener("click", (event) => {
    if (userBtn && !userBtn.parentElement.contains(event.target)) setUserMenu(false);
    if (toggle && !nav.contains(event.target) && !toggle.contains(event.target)) setNav(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    setUserMenu(false);
    setNav(false);
  });
})();

// Presentador: logica de interaccion del lado del cliente (RF-07, RF-08, CU-01 a CU-05).

(function initQueryForm() {
  const form = document.getElementById("query-form");
  if (!form) return;

  const instrumentSelect = document.getElementById("instrument");
  const periodSelect = document.getElementById("period");
  const indicatorSelect = document.getElementById("indicator");
  const submitBtn = document.getElementById("submit-btn");
  const loading = document.getElementById("loading");
  const errorBox = document.getElementById("error-box");
  const result = document.getElementById("result");
  const regenerateBtn = document.getElementById("regenerate-btn");

  let lastQuery = null;
  let lastVariant = 0;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  function hideError() {
    errorBox.classList.add("hidden");
  }

  function riskBadgeText(level) {
    return { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" }[level] || level;
  }

  function renderResult(data) {
    document.getElementById("result-title").textContent = `${data.symbol} — ${data.indicator_label}`;
    const badge = document.getElementById("risk-badge");
    badge.textContent = riskBadgeText(data.risk_level);
    badge.className = `badge ${data.risk_level}`;
    document.getElementById("result-value").textContent = `${data.value} ${data.unit}`;
    document.getElementById("result-explanation").textContent = data.explanation;
    document.getElementById("result-source").textContent = data.source;
    document.getElementById("result-time").textContent = new Date(data.extracted_at).toLocaleString("es-CL");

    const coherenceNote = document.getElementById("coherence-note");
    coherenceNote.classList.toggle("hidden", data.coherent !== false);

    lastVariant = data.variant;
    result.classList.remove("hidden");
  }

  // CU-01: al elegir instrumento se habilita la seleccion de indicador y periodo (RF-07.2)
  instrumentSelect.addEventListener("change", () => {
    const hasInstrument = Boolean(instrumentSelect.value);
    periodSelect.disabled = !hasInstrument;
    indicatorSelect.disabled = !hasInstrument;
    submitBtn.disabled = !(hasInstrument && indicatorSelect.value);
  });

  indicatorSelect.addEventListener("change", () => {
    submitBtn.disabled = !(instrumentSelect.value && indicatorSelect.value);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();
    result.classList.add("hidden");
    loading.classList.remove("hidden"); // RF-08.3: indicador de carga
    submitBtn.disabled = true;

    lastQuery = {
      symbol: instrumentSelect.value,
      indicator: indicatorSelect.value,
      days: Number(periodSelect.value),
    };

    try {
      const response = await fetch(window.APP_ENDPOINTS.query, {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify(lastQuery),
      });
      const data = await response.json();

      if (!response.ok) {
        showError(data.error || "Ocurrió un error al obtener la explicación.");
      } else {
        renderResult(data);
      }
    } catch (err) {
      showError("No fue posible conectar con el servidor. Intenta nuevamente.");
    } finally {
      loading.classList.add("hidden");
      submitBtn.disabled = false;
    }
  });

  // CU-04: solicitar una redaccion alternativa
  regenerateBtn.addEventListener("click", async () => {
    if (!lastQuery) return;
    hideError();
    loading.classList.remove("hidden");
    regenerateBtn.disabled = true;

    try {
      const response = await fetch(window.APP_ENDPOINTS.regenerate, {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({ ...lastQuery, previous_variant: lastVariant }),
      });
      const data = await response.json();

      if (!response.ok) {
        showError(data.error || "No fue posible generar una redacción alternativa.");
      } else {
        document.getElementById("result-explanation").textContent = data.explanation;
        document.getElementById("coherence-note").classList.toggle("hidden", data.coherent !== false);
        lastVariant = data.variant;
        if (data.unchanged) {
          showError("No se encontró una redacción alternativa distinta para este caso; se mantiene la explicación inicial.");
        }
      }
    } catch (err) {
      showError("No fue posible conectar con el servidor. Intenta nuevamente.");
    } finally {
      loading.classList.add("hidden");
      regenerateBtn.disabled = false;
    }
  });
})();

// CU-05: busqueda en el glosario
(function initGlossarySearch() {
  const searchInput = document.getElementById("glossary-search");
  if (!searchInput) return;

  const list = document.getElementById("glossary-list");
  const empty = document.getElementById("glossary-empty");

  let debounceTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const q = searchInput.value.trim();
      const response = await fetch(`${window.APP_ENDPOINTS.glossarySearch}?q=${encodeURIComponent(q)}`);
      const terms = await response.json();

      list.innerHTML = "";
      empty.classList.toggle("hidden", terms.length > 0);

      terms.forEach((term) => {
        const item = document.createElement("div");
        item.className = "glossary-item";
        item.innerHTML = `<dt>${term.term}</dt><dd>${term.definition}</dd>`;
        list.appendChild(item);
      });
    }, 200);
  });
})();
