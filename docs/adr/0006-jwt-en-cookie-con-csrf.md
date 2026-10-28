# ADR 0006: sesión con JWT en cookie httpOnly y CSRF de doble envío

- Estado: aceptada
- Requerimientos relacionados: RF-11, RF-12, RNF-06

## Contexto y problema

Hay que autenticar usuarios con contraseña (y opcionalmente con Google), poder cerrar sesión de verdad y resistir XSS y CSRF.

## Opciones consideradas

### A. Sesión nativa de Flask
- Contra: sin expiración configurable ni revocación individual de tokens.

### B. JWT en `localStorage`
- Contra: accesible desde JavaScript; un XSS lo roba.

### C. JWT en cookie httpOnly con token CSRF de doble envío (elegida)
- Pro: el token no es legible desde JS; CSRF mitigado.
- Contra: toda petición mutante debe enviar el header `X-CSRF-TOKEN`.

## Decisión

Flask-JWT-Extended con el token en cookie httpOnly, expiración de 24 horas y revocación por `jti` en la tabla `revoked_tokens`. Una segunda cookie `csrf_access_token`, legible por JS, se reenvía en `X-CSRF-TOKEN` (ver `static/js/csrf.js`). Contraseñas con Flask-Bcrypt (8 a 64 caracteres y máximo 72 bytes UTF-8). Bloqueo de la cuenta durante 15 minutos tras 5 intentos fallidos. Login con Google mediante Authlib, sin vincular cuentas por correo.

## Consecuencias

- Positivas: logout efectivo, bloqueo anti fuerza bruta, mitigación de XSS y CSRF.
- Negativas: `JWT_COOKIE_SECURE` debe estar en `true` bajo HTTPS; la revocación exige una consulta a la base en cada petición autenticada.

## Verificación

`tests/test_auth.py`.

## Referencias

- OWASP, *Cross-Site Request Forgery Prevention Cheat Sheet* (verificar URL y año).
