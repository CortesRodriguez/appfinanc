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
