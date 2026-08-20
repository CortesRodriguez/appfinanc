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
        headers: { "Content-Type": "application/json" },
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
        headers: { "Content-Type": "application/json" },
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

// CU-06 / CU-07: autoevaluación retrospectiva con resumen previo a la confirmación (RF-11.3)
(function initSurveyForm() {
  const form = document.getElementById("survey-form");
  if (!form) return;

  const reviewBtn = document.getElementById("review-btn");
  const summarySection = document.getElementById("survey-summary");
  const summaryList = document.getElementById("summary-list");
  const confirmBtn = document.getElementById("confirm-submit-btn");
  const backBtn = document.getElementById("back-to-edit-btn");
  const resultBox = document.getElementById("survey-result");
  const errorBox = document.getElementById("survey-error");

  function collectAnswers() {
    const items = form.querySelectorAll(".survey-item");
    const answers = {};
    let allAnswered = true;

    items.forEach((item) => {
      const conceptId = item.dataset.concept;
      const beforeChecked = item.querySelector(`input[name="${conceptId}_before"]:checked`);
      const nowChecked = item.querySelector(`input[name="${conceptId}_now"]:checked`);
      if (!beforeChecked || !nowChecked) {
        allAnswered = false;
        return;
      }
      answers[conceptId] = { before: Number(beforeChecked.value), now: Number(nowChecked.value) };
    });

    return { answers, allAnswered };
  }

  reviewBtn.addEventListener("click", () => {
    errorBox.classList.add("hidden");
    const { answers, allAnswered } = collectAnswers();

    if (!allAnswered) {
      errorBox.textContent = "Debes marcar ambas escalas (antes y ahora) para cada concepto.";
      errorBox.classList.remove("hidden");
      return;
    }

    summaryList.innerHTML = "";
    form.querySelectorAll(".survey-item").forEach((item) => {
      const conceptId = item.dataset.concept;
      const label = item.querySelector("legend").textContent.trim();
      const pair = answers[conceptId];
      const delta = pair.now - pair.before;
      const li = document.createElement("li");
      const deltaTxt = delta > 0 ? `+${delta}` : `${delta}`;
      li.textContent = `${label} → antes ${pair.before}/5, ahora ${pair.now}/5 (Δ ${deltaTxt})`;
      summaryList.appendChild(li);
    });

    form.classList.add("hidden");
    summarySection.classList.remove("hidden");
    summarySection.dataset.answers = JSON.stringify(answers);
  });

  backBtn.addEventListener("click", () => {
    summarySection.classList.add("hidden");
    form.classList.remove("hidden");
  });

  confirmBtn.addEventListener("click", async () => {
    const answers = JSON.parse(summarySection.dataset.answers || "{}");
    confirmBtn.disabled = true;

    try {
      const response = await fetch(window.APP_ENDPOINTS.surveySubmit, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(answers),
      });
      const data = await response.json();

      if (!response.ok) {
        errorBox.textContent = data.error || "No fue posible enviar la encuesta.";
        errorBox.classList.remove("hidden");
        summarySection.classList.add("hidden");
        form.classList.remove("hidden");
        return;
      }

      summarySection.classList.add("hidden");
      const deltaSign = data.avg_delta > 0 ? "+" : "";
      resultBox.innerHTML =
        `<p><strong>¡Gracias por participar!</strong> Tu respuesta se guardó de forma anónima.</p>` +
        `<p>Tu comprensión percibida cambió, en promedio, de <strong>${data.avg_before}/5</strong> ` +
        `a <strong>${data.avg_now}/5</strong> (Δ ${deltaSign}${data.avg_delta}).</p>`;
      resultBox.classList.remove("hidden");
    } catch (err) {
      errorBox.textContent = "No fue posible conectar con el servidor. Intenta nuevamente.";
      errorBox.classList.remove("hidden");
    } finally {
      confirmBtn.disabled = false;
    }
  });
})();
