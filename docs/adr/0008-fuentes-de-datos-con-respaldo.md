# 0008. Yahoo Finance con Alpha Vantage de respaldo

## Status

Aceptada (registrada a posteriori).

## Context

Se necesitan precios históricos de las acciones del IPSA, indicadores macro chilenos y noticias, sin costo y sin una API oficial gratuita completa.

Requerimientos relacionados: RF-02.1, RF-02.3, RNF-08, RNF-09.

Alternativas consideradas:

- **Solo `yfinance`.** Sin clave y con cobertura del IPSA (sufijo `.SN`). Costo: no es una API oficial; puede cambiar o bloquear sin aviso.
- **`yfinance` con Alpha Vantage de respaldo.** Agrega una red de seguridad con una API oficial de clave gratuita. Costo: límites bajos de uso (verificar la cuota vigente).

## Decision

`src/extractor/sources.py` intenta Yahoo Finance y, si falla, Alpha Vantage, con hasta 3 reintentos (RNF-09.2). UF, dólar, TPM e IPC vienen de mindicador.cl. Las noticias usan el RSS no oficial de Google News y se degradan a una lista vacía si falla.

## Consequences

Se vuelve más fácil:

- Seguir mostrando datos cuando una fuente cae.

Se vuelve más difícil:

- Garantizar la disponibilidad: depende de proveedores que el proyecto no controla.
- Gestionar los riesgos asociados, que deben registrarse en el plan de riesgos (`docs/diseno/11_riesgos_cumplimiento.md`): fuentes no oficiales (`yfinance`, Google News RSS) y un tercero para el LLM (Groq).
