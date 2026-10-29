# 0006. Sesión con JWT en cookie httpOnly y CSRF de doble envío

## Status

Aceptada (registrada a posteriori).

## Context

Hay que autenticar usuarios con contraseña (y opcionalmente con Google), poder cerrar sesión de verdad y resistir XSS y CSRF.

Requerimientos relacionados: RF-11, RF-12, RNF-06.

Alternativas consideradas:

- **Sesión nativa de Flask.** Descartada: sin expiración configurable ni revocación individual de tokens.
- **JWT en `localStorage`.** Descartada: es accesible desde JavaScript y un XSS lo roba.
- **JWT en cookie httpOnly con token CSRF de doble envío.** El token no es legible desde JS y el CSRF queda mitigado. Costo: toda petición mutante debe enviar el header `X-CSRF-TOKEN`.

Referencia (verificar URL y año antes de citar): OWASP, *Cross-Site Request Forgery Prevention Cheat Sheet*.

## Decision

Flask-JWT-Extended con el token en cookie httpOnly, expiración de 24 horas y revocación por `jti` en la tabla `revoked_tokens`. Una segunda cookie `csrf_access_token`, legible por JS, se reenvía en `X-CSRF-TOKEN` (ver `static/js/csrf.js`). Contraseñas con Flask-Bcrypt (8 a 64 caracteres y máximo 72 bytes UTF-8). Bloqueo de la cuenta durante 15 minutos tras 5 intentos fallidos. Login con Google mediante Authlib, sin vincular cuentas por correo.

## Consequences

Se vuelve más fácil:

- Cerrar sesión de forma efectiva.
- Frenar la fuerza bruta con el bloqueo por intentos.
- Mitigar XSS y CSRF.

Se vuelve más difícil:

- Desplegar sin HTTPS: `JWT_COOKIE_SECURE` debe estar en `true` bajo HTTPS.
- Reducir la carga en la base: la revocación exige una consulta en cada petición autenticada.

Verificación: `tests/test_auth.py`.
