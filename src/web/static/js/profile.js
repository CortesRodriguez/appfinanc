// Pestanas Resumen / Historial. `#historial` en la URL abre el historial
// (es el destino del menu de usuario).
(function initProfileTabs() {
  const tabs = document.querySelectorAll(".profile-tab");
  if (!tabs.length) return;

  function select(name) {
    tabs.forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      document.getElementById(tab.getAttribute("aria-controls")).classList.toggle("hidden", !active);
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      select(tab.dataset.tab);
      history.replaceState(null, "", tab.dataset.tab === "historial" ? "#historial" : window.location.pathname);
    });
  });

  const fromHash = () => select(window.location.hash === "#historial" ? "historial" : "resumen");
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();

// Perfil de aprendizaje: regenerar la explicacion del indicador mas dificil (CU-32).
(function initProfileRegenerate() {
  const btn = document.getElementById("profile-regenerate-btn");
  if (!btn) return;

  const loading = document.getElementById("profile-loading");
  const errorBox = document.getElementById("profile-error");

  btn.addEventListener("click", async () => {
    errorBox.classList.add("hidden");
    loading.classList.remove("hidden");
    btn.disabled = true;

    try {
      const response = await fetch(window.APP_ENDPOINTS.profileRegenerate, {
        method: "POST",
        headers: csrfHeaders(),
      });
      const data = await response.json();

      if (!response.ok) {
        errorBox.textContent = data.error || "No fue posible regenerar la explicación.";
        errorBox.classList.remove("hidden");
        return;
      }

      document.getElementById("profile-explanation").textContent = data.explanation;
      document.getElementById("profile-total").textContent = data.total_queries;
      document.getElementById("profile-regenerations").textContent = data.regenerations;
    } catch (err) {
      errorBox.textContent = "No fue posible conectar con el servidor.";
      errorBox.classList.remove("hidden");
    } finally {
      loading.classList.add("hidden");
      btn.disabled = false;
    }
  });
})();

// Experiencia declarada (RF-13.2): se guarda al elegir una opcion y se
// actualizan las etiquetas de nivel sin recargar.
(function initProfileExperience() {
  const radios = document.querySelectorAll('input[name="experience"]');
  if (!radios.length) return;

  const message = document.getElementById("profile-experience-msg");
  const LEVEL_TEXT = { basico: "Básico", intermedio: "Intermedio", avanzado: "Avanzado" };
  const SOURCE_TEXT = { historial: "Por lo que has pedido", experiencia: "Por tu experiencia" };

  radios.forEach((radio) => {
    radio.addEventListener("change", async () => {
      message.textContent = "Guardando…";
      radios.forEach((r) => (r.disabled = true));

      try {
        const response = await fetch(window.APP_ENDPOINTS.profileExperience, {
          method: "PATCH",
          headers: csrfHeaders(),
          body: JSON.stringify({ experience_level: radio.value }),
        });
        const data = await response.json();

        if (!response.ok) {
          message.textContent = data.error || "No fue posible guardar tu experiencia.";
          return;
        }

        document.querySelectorAll("#detail-levels .level-card").forEach((card) => {
          const key = card.dataset.indicator;
          const level = data.detail_levels[key];
          const tag = card.querySelector(".detail-tag");
          tag.className = `detail-tag ${level}`;
          tag.textContent = LEVEL_TEXT[level] || level;
          card.querySelector(".detail-source").textContent = SOURCE_TEXT[data.detail_sources[key]] || "Nivel inicial";
        });
        message.textContent = "Guardado. Tus próximas explicaciones usarán este nivel.";
      } catch (err) {
        message.textContent = "No fue posible conectar con el servidor.";
      } finally {
        radios.forEach((r) => (r.disabled = false));
      }
    });
  });
})();
