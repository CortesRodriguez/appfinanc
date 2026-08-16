// Helper para leer el token CSRF de la cookie que expone flask-jwt-extended
// (JWT_COOKIE_CSRF_PROTECT) y adjuntarlo en las peticiones que cambian estado.

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

function csrfHeaders(extra) {
  const token = getCookie("csrf_access_token");
  const headers = Object.assign({ "Content-Type": "application/json" }, extra || {});
  if (token) headers["X-CSRF-TOKEN"] = token;
  return headers;
}
