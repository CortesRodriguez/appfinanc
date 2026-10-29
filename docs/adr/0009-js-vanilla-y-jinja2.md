# 0009. Interfaz con Jinja2 en el servidor y JavaScript vanilla

## Status

Aceptada (registrada a posteriori).

## Context

La interfaz tiene pocas pantallas (siete plantillas en `src/web/templates/`) y ninguna maneja un estado de aplicación complejo. Lo desarrolla una sola persona, sin margen para aprender infraestructura de frontend durante el proyecto.

Requerimientos relacionados: RNF-03 (diseño de interfaz y responsividad), RNF-07 (mantenibilidad).

Alternativa considerada y descartada: un framework moderno (React, Vue o Svelte). Habría exigido aprender infraestructura de producción (Vite o Webpack, JSX, hooks) sin aportar valor a la propuesta del proyecto. Esta justificación proviene de `docs/diseno/09_stack_tecnologico.md`, sección Frontend (que habla de "~10 pantallas"; el recuento actual de plantillas es siete); no hay evidencia en el repositorio de que se hayan evaluado otras alternativas con prototipos o mediciones.

## Decision

Flask renderiza el HTML en el servidor con plantillas Jinja2 (`src/web/templates/`). El JavaScript sin framework (`src/web/static/js/`) solo agrega interactividad puntual. El estado vive en el DOM y en la sesión de Flask, sin un store.

## Consequences

Se vuelve más fácil:

- Desarrollar y desplegar: no hay paso de compilación ni dependencias de frontend que instalar.
- Explicar la separación en la vista de desarrollo del modelo 4+1: el servidor produce la página y el JS solo la anima.

Se vuelve más difícil:

- Crecer en interactividad: `src/web/static/js/dashboard.js` ya concentra la lógica del dashboard en un solo archivo grande, y un framework de componentes la repartiría mejor.
- Reutilizar componentes de interfaz entre pantallas.
- Probar el JavaScript: el repositorio no tiene pruebas automáticas del frontend, solo de las rutas.
