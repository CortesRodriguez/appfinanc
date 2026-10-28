// Registro, inicio y cierre de sesion (RF-16, RF-17, CU-11, CU-12).

// Login con Google redirige de vuelta con ?oauth_error=... cuando el correo
// ya tiene cuenta por contraseña (las cuentas no se vinculan automáticamente).
(function initOauthErrorBanner() {
  const params = new URLSearchParams(window.location.search);
  const message = params.get("oauth_error");
  if (!message) return;

  params.delete("oauth_error");
  const query = params.toString();
  const cleanUrl = window.location.pathname + (query ? `?${query}` : "") + window.location.hash;
  window.history.replaceState({}, "", cleanUrl);

  const pageError = document.getElementById("auth-error");
  if (pageError) {
    pageError.textContent = message;
    pageError.classList.remove("hidden");
    return;
  }

  const modal = document.getElementById("auth-modal");
  if (!modal) return;
  modal.querySelectorAll(".auth-tab").forEach((t) => {
    const active = t.dataset.tab === "login";
    t.classList.toggle("active", active);
    t.setAttribute("aria-selected", active ? "true" : "false");
  });
  modal.querySelectorAll(".auth-form").forEach((f) => f.classList.toggle("hidden", f.dataset.form !== "login"));
  modal.classList.remove("hidden");
  const modalError = document.getElementById("auth-modal-error");
  if (modalError) {
    modalError.textContent = message;
    modalError.classList.remove("hidden");
  }
})();

(function initLogout() {
  const link = document.getElementById("logout-link");
  if (!link) return;

  link.addEventListener("click", async (event) => {
    event.preventDefault();
    await fetch("/api/auth/logout", { method: "POST", headers: csrfHeaders() });
    window.location.href = "/";
  });
})();

// Envio comun de los formularios de registro y login (pagina y modal):
// mismo payload, mismo manejo de errores, boton deshabilitado mientras envia.
async function submitAuth(form, endpoint, showError, onSuccess) {
  const submitBtn = form.querySelector("button[type=submit]");
  const payload = {};
  new FormData(form).forEach((value, key) => { payload[key] = value; });

  if ("password_confirm" in payload && payload.password_confirm !== payload.password) {
    showError("Las contraseñas no coinciden.");
    return;
  }

  submitBtn.disabled = true;
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "No fue posible completar la operación.");
      return;
    }
    onSuccess();
  } catch (err) {
    showError("No fue posible conectar con el servidor.");
  } finally {
    submitBtn.disabled = false;
  }
}

// Botones "Mostrar" junto a los campos de contraseña.
document.querySelectorAll(".pw-toggle").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = btn.closest(".pw-wrap").querySelector("input");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Ocultar" : "Mostrar";
    btn.setAttribute("aria-pressed", show ? "true" : "false");
  });
});

// ?next= solo admite destinos internos conocidos (evita open redirect).
const NEXT_DESTINATIONS = { perfil: "/perfil" };

function pageAuthForm(formId, endpoint, onSuccess) {
  const form = document.getElementById(formId);
  if (!form) return;

  const errorBox = document.getElementById("auth-error");
  const showError = (msg) => {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    errorBox.classList.add("hidden");
    submitAuth(form, endpoint, showError, onSuccess);
  });
}

pageAuthForm("register-form", "/api/auth/registro", () => {
  window.location.href = "/perfil";
});

pageAuthForm("login-form", "/api/auth/login", () => {
  const next = new URLSearchParams(window.location.search).get("next");
  window.location.href = NEXT_DESTINATIONS[next] || "/";
});

// Modal de autenticacion invocado desde la nav (RF-16 / RF-17 mejorado):
// registro/login sin salir de la pagina actual. Al exito, se recarga la
// pagina para que el context_processor en src/web/__init__.py reevalue
// `current_user` y la nav muestre "Mi perfil" + "Cerrar sesion".
(function initAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (!modal) return;

  const errorBox = document.getElementById("auth-modal-error");
  const tabs = modal.querySelectorAll(".auth-tab");
  const forms = modal.querySelectorAll(".auth-form");
  const closeBtn = document.getElementById("auth-modal-close");
  const openBtns = document.querySelectorAll(".nav-auth-btn");

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
  }

  function selectTab(tabName) {
    tabs.forEach((t) => {
      const active = t.dataset.tab === tabName;
      t.classList.toggle("active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    forms.forEach((f) => f.classList.toggle("hidden", f.dataset.form !== tabName));
    clearError();
    const firstInput = modal.querySelector(`[data-form="${tabName}"] input`);
    if (firstInput) setTimeout(() => firstInput.focus(), 0);
  }

  function openModal(tabName) {
    selectTab(tabName || "login");
    modal.classList.remove("hidden");
  }

  function closeModal() {
    modal.classList.add("hidden");
    clearError();
    forms.forEach((f) => f.reset());
  }

  openBtns.forEach((btn) => {
    btn.addEventListener("click", () => openModal(btn.dataset.authTab));
  });

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => selectTab(tab.dataset.tab));
  });

  closeBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) closeModal();
  });

  ["login", "register"].forEach((name) => {
    const form = modal.querySelector(`[data-form="${name}"]`);
    const endpoint = name === "login" ? "/api/auth/login" : "/api/auth/registro";
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      clearError();
      submitAuth(form, endpoint, showError, () => window.location.reload());
    });
  });
})();
