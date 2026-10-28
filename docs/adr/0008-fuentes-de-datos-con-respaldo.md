# ADR 0008: Yahoo Finance con Alpha Vantage de respaldo

- Estado: aceptada
- Requerimientos relacionados: RF-02.1, RF-02.3, RNF-08, RNF-09

## Contexto y problema

Se necesitan precios históricos de las acciones del IPSA, indicadores macro chilenos y noticias, sin costo y sin una API oficial gratuita completa.

## Opciones consideradas

### A. Solo `yfinance`
- Pro: sin clave y con cobertura del IPSA (sufijo `.SN`).
- Contra: no es una API oficial; puede cambiar o bloquear sin aviso.

### B. `yfinance` con Alpha Vantage de respaldo (elegida)
- Pro: red de seguridad con una API oficial de clave gratuita.
- Contra: límites bajos de uso (verificar la cuota vigente).

## Decisión

`src/extractor/sources.py` intenta Yahoo Finance y, si falla, Alpha Vantage, con hasta 3 reintentos (RNF-09.2). UF, dólar, TPM e IPC vienen de mindicador.cl. Las noticias usan el RSS no oficial de Google News y se degradan a una lista vacía si falla.

## Consecuencias

- Riesgos a registrar en el plan de riesgos (`docs/diseno/11_riesgos_cumplimiento.md`): dependencia de fuentes no oficiales (`yfinance`, Google News RSS) y de un tercero para el LLM (Groq).
- La disponibilidad de los datos depende de proveedores que el proyecto no controla.
