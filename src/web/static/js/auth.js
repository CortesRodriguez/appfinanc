// Registro, inicio y cierre de sesion (RF-16, RF-17, CU-11, CU-12).

(function initLogout() {
  const link = document.getElementById("logout-link");
  if (!link) return;

  link.addEventListener("click", async (event) => {
    event.preventDefault();
    await fetch("/api/auth/logout", { method: "POST", headers: csrfHeaders() });
    window.location.href = "/";
  });
})();

(function initRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) return;

  const errorBox = document.getElementById("auth-error");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.classList.add("hidden");

    const payload = {
      username: form.username.value,
      email: form.email.value,
      password: form.password.value,
      acepta_evaluacion: form.acepta_evaluacion ? form.acepta_evaluacion.checked : false,
    };

    try {
      const response = await fetch("/api/auth/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        errorBox.textContent = data.error || "No fue posible completar el registro.";
        errorBox.classList.remove("hidden");
        return;
      }

      window.location.href = "/perfil";
    } catch (err) {
      errorBox.textContent = "No fue posible conectar con el servidor.";
      errorBox.classList.remove("hidden");
    }
  });
})();

(function initLoginForm() {
  const form = document.getElementById("login-form");
  if (!form) return;

  const errorBox = document.getElementById("auth-error");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.classList.add("hidden");

    const payload = { email: form.email.value, password: form.password.value };

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        errorBox.textContent = data.error || "No fue posible iniciar sesión.";
        errorBox.classList.remove("hidden");
        return;
      }

      const params = new URLSearchParams(window.location.search);
      window.location.href = params.get("next") === "perfil" ? "/perfil" : "/";
    } catch (err) {
      errorBox.textContent = "No fue posible conectar con el servidor.";
      errorBox.classList.remove("hidden");
    }
  });
})();

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

  const loginForm = modal.querySelector('[data-form="login"]');
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();
    const submitBtn = loginForm.querySelector(".auth-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginForm.email.value,
          password: loginForm.password.value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || "No fue posible iniciar sesión.");
        return;
      }
      window.location.reload();
    } catch (err) {
      showError("No fue posible conectar con el servidor.");
    } finally {
      submitBtn.disabled = false;
    }
  });

  const registerForm = modal.querySelector('[data-form="register"]');
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const password = registerForm.password.value;
    const passwordConfirm = registerForm.password_confirm.value;
    if (password !== passwordConfirm) {
      showError("Las contraseñas no coinciden.");
      return;
    }

    const submitBtn = registerForm.querySelector(".auth-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: registerForm.email.value,
          password: password,
          password_confirm: passwordConfirm,
          acepta_evaluacion: registerForm.acepta_evaluacion
            ? registerForm.acepta_evaluacion.checked
            : false,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || "No fue posible completar el registro.");
        return;
      }
      window.location.reload();
    } catch (err) {
      showError("No fue posible conectar con el servidor.");
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
