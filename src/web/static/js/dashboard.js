// Dashboard principal: sidebar de instrumentos + panel de tendencia, resumen e indicadores.
// CU-01, CU-02, CU-04, RF-07, RF-08.

(function initDashboard() {
  const listEl = document.getElementById("instrument-list");
  if (!listEl) return;

  const searchInput = document.getElementById("instrument-search");
  const lookupHint = document.getElementById("lookup-hint");
  const emptyState = document.getElementById("empty-state");
  const view = document.getElementById("instrument-view");

  const viewSymbol = document.getElementById("view-symbol");
  const viewSector = document.getElementById("view-sector");
  const viewPrice = document.getElementById("view-price");
  const viewChange = document.getElementById("view-change");

  const chartLoading = document.getElementById("chart-loading");
  const chartError = document.getElementById("chart-error");
  const chartEl = document.getElementById("price-chart");

  // Instancia y series de lightweight-charts: se crean en el primer render
  // y se reutilizan en cargas posteriores (setData en vez de recrear).
  let chartInstance = null;
  let candleSeries = null;
  let smaShortSeries = null;
  let smaLongSeries = null;

  const summaryLoading = document.getElementById("summary-loading");
  const summaryText = document.getElementById("summary-text");

  const indicatorsLoading = document.getElementById("indicators-loading");
  const indicatorsError = document.getElementById("indicators-error");
  const indicatorGrid = document.getElementById("indicator-grid");

  const periodButtons = document.querySelectorAll(".period-btn");
  const periodLabelEl = document.getElementById("chart-period-label");
  const PERIOD_LABELS = { 30: "1 mes", 90: "3 meses", 180: "6 meses", 365: "1 año" };

  let catalog = [];
  let current = null; // {symbol, name, sector, type, price, daily_change_pct}
  let selectedDays = 180;
  const cardState = {}; // indicator key -> {variant, days}

  function fmtPrice(value) {
    if (value === null || value === undefined) return "—";
    return `$${value.toLocaleString("es-CL", { maximumFractionDigits: 2 })}`;
  }

  function fmtChange(value) {
    if (value === null || value === undefined) return "—";
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  }

  function changeClass(value) {
    if (value === null || value === undefined) return "flat";
    if (value > 0) return "up";
    if (value < 0) return "down";
    return "flat";
  }

  function renderList(items) {
    listEl.innerHTML = "";
    items.forEach((inst) => {
      const li = document.createElement("li");
      li.className = "instrument-item" + (current && current.symbol === inst.symbol ? " selected" : "");
      li.dataset.symbol = inst.symbol;
      li.innerHTML = `
        <div>
          <div class="name">${inst.name}</div>
          <div class="sector">${inst.sector || inst.type}</div>
        </div>
        <div class="quote">
          <div class="price">${fmtPrice(inst.price)}</div>
          <div class="change ${changeClass(inst.daily_change_pct)}">${fmtChange(inst.daily_change_pct)}</div>
        </div>
      `;
      li.addEventListener("click", () => selectInstrument(inst));
      listEl.appendChild(li);
    });
  }

  function highlightSelected() {
    document.querySelectorAll(".instrument-item").forEach((el) => {
      el.classList.toggle("selected", current && el.dataset.symbol === current.symbol);
    });
  }

  async function loadQuotes() {
    try {
      const response = await fetch(window.APP_ENDPOINTS.quotes);
      catalog = await response.json();
      renderList(catalog);
    } catch (err) {
      listEl.innerHTML = "<li class='meta'>No fue posible cargar la lista de instrumentos.</li>";
    }
  }

  searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim().toLowerCase();
    lookupHint.classList.add("hidden");

    if (!q) {
      renderList(catalog);
      return;
    }

    const filtered = catalog.filter(
      (inst) => inst.symbol.toLowerCase().includes(q) || inst.name.toLowerCase().includes(q) || (inst.sector || "").toLowerCase().includes(q)
    );
    renderList(filtered);

    if (filtered.length === 0) {
      lookupHint.classList.remove("hidden");
      lookupHint.innerHTML = `No está en la lista. <button type="button" id="lookup-btn">Buscar "${searchInput.value.trim().toUpperCase()}" directamente</button>`;
      document.getElementById("lookup-btn").addEventListener("click", () => lookupSymbol(searchInput.value.trim()));
    }
  });

  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const q = searchInput.value.trim().toLowerCase();
      const exact = catalog.find((inst) => inst.symbol.toLowerCase() === q);
      if (exact) {
        selectInstrument(exact);
      } else if (q) {
        lookupSymbol(searchInput.value.trim());
      }
    }
  });

  async function lookupSymbol(rawSymbol) {
    const symbol = rawSymbol.trim().toUpperCase();
    if (!symbol) return;

    lookupHint.classList.remove("hidden");
    lookupHint.textContent = `Buscando "${symbol}"…`;

    try {
      const response = await fetch(`${window.APP_ENDPOINTS.lookup}?symbol=${encodeURIComponent(symbol)}`);
      const data = await response.json();

      if (!response.ok) {
        lookupHint.textContent = data.error || "No se encontró ese ticker.";
        return;
      }

      lookupHint.classList.add("hidden");
      selectInstrument({ symbol: data.symbol, name: data.name, sector: "Ticker personalizado", type: data.type, price: null, daily_change_pct: null });
    } catch (err) {
      lookupHint.textContent = "No fue posible buscar ese ticker.";
    }
  }

  function ensureChart() {
    if (chartInstance) return;

    chartInstance = LightweightCharts.createChart(chartEl, {
      autoSize: true,
      layout: {
        background: { type: "solid", color: "#131a24" },
        textColor: "#e6edf3",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "rgba(139, 152, 165, 0.08)" },
        horzLines: { color: "rgba(139, 152, 165, 0.08)" },
      },
      rightPriceScale: { borderColor: "#232c38" },
      timeScale: { borderColor: "#232c38", timeVisible: false, secondsVisible: false },
      crosshair: { mode: 1 },
      localization: { locale: "es-CL" },
    });

    candleSeries = chartInstance.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    smaShortSeries = chartInstance.addLineSeries({
      color: "#38bdf8",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    smaLongSeries = chartInstance.addLineSeries({
      color: "#8b98a5",
      lineWidth: 2,
      lineStyle: 2, // dashed (replica el stroke-dasharray previo)
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
  }

  function renderChart(series) {
    ensureChart();

    const dates = series.dates || [];
    const hasOhlc = Array.isArray(series.open) && Array.isArray(series.high) && Array.isArray(series.low);

    const candles = dates
      .map((d, i) => {
        const c = series.close[i];
        if (c === null || c === undefined) return null;
        if (hasOhlc) {
          const o = series.open[i];
          const h = series.high[i];
          const l = series.low[i];
          if (o === null || o === undefined || h === null || h === undefined || l === null || l === undefined) return null;
          return { time: d, open: o, high: h, low: l, close: c };
        }
        // Fallback (cache antiguo sin OHLC): vela doji plana, sigue rindiendo algo visible.
        return { time: d, open: c, high: c, low: c, close: c };
      })
      .filter(Boolean);

    const smaShort = dates
      .map((d, i) => (series.sma_short[i] == null ? null : { time: d, value: series.sma_short[i] }))
      .filter(Boolean);

    const smaLong = dates
      .map((d, i) => (series.sma_long[i] == null ? null : { time: d, value: series.sma_long[i] }))
      .filter(Boolean);

    candleSeries.setData(candles);
    smaShortSeries.setData(smaShort);
    smaLongSeries.setData(smaLong);

    const legendShort = document.getElementById("legend-ma-short");
    const legendLong = document.getElementById("legend-ma-long");
    if (legendShort && series.short_window) legendShort.textContent = `MA${series.short_window}`;
    if (legendLong && series.long_window) legendLong.textContent = `MA${series.long_window}`;

    chartInstance.timeScale().fitContent();
  }

  async function loadChart(symbol, days) {
    chartError.classList.add("hidden");
    chartLoading.classList.remove("hidden");

    try {
      const response = await fetch(`${window.APP_ENDPOINTS.chart}?symbol=${encodeURIComponent(symbol)}&days=${days}`);
      const data = await response.json();

      if (!response.ok) {
        chartError.textContent = data.error || "No fue posible obtener el gráfico de tendencia.";
        chartError.classList.remove("hidden");
        return;
      }

      renderChart(data);
    } catch (err) {
      chartError.textContent = "No fue posible conectar con el servidor.";
      chartError.classList.remove("hidden");
    } finally {
      chartLoading.classList.add("hidden");
    }
  }

  function riskBadgeClass(indicatorKey, data) {
    if (indicatorKey === "medias_moviles") return data.trend || "alcista";
    return data.risk_level;
  }

  function riskBadgeText(indicatorKey, data) {
    if (indicatorKey === "medias_moviles") return data.trend === "bajista" ? "▼ bajando" : "▲ subiendo";
    return { bajo: "riesgo bajo", medio: "riesgo medio", alto: "riesgo alto" }[data.risk_level] || data.risk_level;
  }

  function formatIndicatorValue(indicatorKey, data) {
    if (indicatorKey === "medias_moviles") return data.trend === "bajista" ? "Bajista" : "Alcista";
    if (indicatorKey === "rsi") return `${data.value}`;
    return `${data.value}%`;
  }

  function renderCard(meta, data) {
    let card = document.querySelector(`.indicator-card[data-indicator="${meta.key}"]`);
    if (!card) {
      card = document.createElement("article");
      card.className = "indicator-card card";
      card.dataset.indicator = meta.key;
      indicatorGrid.appendChild(card);
    }

    card.innerHTML = `
      <div class="indicator-card-header">
        <span class="indicator-title">${meta.title}</span>
        <span class="badge ${riskBadgeClass(meta.key, data)}">${riskBadgeText(meta.key, data)}</span>
      </div>
      <div class="indicator-value">${formatIndicatorValue(meta.key, data)}</div>
      <div class="indicator-sub">${meta.sub}</div>
      <p class="indicator-text">${data.explanation}</p>
      ${data.coherent === false ? '<div class="warn">Marcado para revisión de coherencia.</div>' : ""}
      <button type="button" class="link-btn regen-btn">No entendí esto</button>
    `;

    card.querySelector(".regen-btn").addEventListener("click", () => regenerateCard(meta));
  }

  async function fetchIndicator(symbol, indicatorKey, days, variant) {
    const endpoint = variant > 0 ? window.APP_ENDPOINTS.regenerate : window.APP_ENDPOINTS.query;
    const body = variant > 0
      ? { symbol, indicator: indicatorKey, days, previous_variant: variant - 1 }
      : { symbol, indicator: indicatorKey, days };

    const response = await fetch(endpoint, {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No fue posible obtener el indicador.");
    return data;
  }

  async function regenerateCard(meta) {
    if (!current) return;
    const state = cardState[meta.key];
    state.variant += 1;

    try {
      const data = await fetchIndicator(current.symbol, meta.key, state.days, state.variant);
      lastIndicatorData[meta.key] = data;
      renderCard(meta, data);
      composeSummary();
    } catch (err) {
      indicatorsError.textContent = err.message;
      indicatorsError.classList.remove("hidden");
    }
  }

  const lastIndicatorData = {};

  function composeSummary() {
    const trend = lastIndicatorData.medias_moviles;
    const ret = lastIndicatorData.rentabilidad;
    const rsi = lastIndicatorData.rsi;
    const vol = lastIndicatorData.volatilidad;

    if (!trend || !ret || !rsi || !vol || !current) return;

    const trendWord = trend.trend === "bajista" ? "bajista" : "alcista";
    const parts = [
      `${current.symbol} muestra una tendencia ${trendWord} en el período consultado.`,
      `En ese lapso tuvo una rentabilidad de ${ret.value}% (riesgo ${ret.risk_level}) y una volatilidad de ${vol.value}% (riesgo ${vol.risk_level}).`,
      `El RSI está en ${rsi.value} puntos, lo que indica riesgo ${rsi.risk_level} de sobrecompra o sobreventa.`,
    ];
    summaryText.textContent = parts.join(" ");
  }

  async function loadIndicators(symbol, days) {
    indicatorsError.classList.add("hidden");
    indicatorsLoading.classList.remove("hidden");
    summaryLoading.classList.remove("hidden");
    indicatorGrid.innerHTML = "";
    summaryText.textContent = "";

    window.APP_INDICATORS.forEach((meta) => {
      cardState[meta.key] = { variant: 0, days };
    });

    try {
      const results = await Promise.all(
        window.APP_INDICATORS.map((meta) => fetchIndicator(symbol, meta.key, days, 0))
      );
      window.APP_INDICATORS.forEach((meta, idx) => {
        const data = results[idx];
        lastIndicatorData[meta.key] = data;
        renderCard(meta, data);
      });
      composeSummary();
    } catch (err) {
      indicatorsError.textContent = err.message;
      indicatorsError.classList.remove("hidden");
    } finally {
      indicatorsLoading.classList.add("hidden");
      summaryLoading.classList.add("hidden");
    }
  }

  function selectInstrument(inst) {
    current = inst;
    emptyState.classList.add("hidden");
    view.classList.remove("hidden");
    highlightSelected();

    viewSymbol.textContent = inst.name;
    viewSector.textContent = `${inst.symbol} · ${inst.sector || inst.type}`;
    viewPrice.textContent = fmtPrice(inst.price);
    viewChange.textContent = fmtChange(inst.daily_change_pct);
    viewChange.className = `change-badge change ${changeClass(inst.daily_change_pct)}`;

    loadChart(inst.symbol, selectedDays);
    loadIndicators(inst.symbol, selectedDays);
    logVisit(inst.symbol);
  }

  // Selector de rango temporal (1M/3M/6M/1A): cambia el periodo de la
  // consulta para el instrumento ya seleccionado, sin registrar una
  // visita nueva (RF-19.2/RF-19.3 solo cuentan seleccionar un instrumento,
  // no ajustar el rango de fechas sobre el mismo).
  periodButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const days = Number(btn.dataset.days);
      if (days === selectedDays) return;

      selectedDays = days;
      periodButtons.forEach((b) => b.classList.toggle("active", b === btn));
      periodLabelEl.textContent = PERIOD_LABELS[days] || `${days} días`;

      if (current) {
        loadChart(current.symbol, selectedDays);
        loadIndicators(current.symbol, selectedDays);
      }
    });
  });

  // RF-10: una sola llamada por instrumento seleccionado, independiente de
  // las consultas paralelas por indicador (ver comentario en el backend
  // sobre por que esto ya no se registra dentro de /api/query).
  function logVisit(symbol) {
    fetch(window.APP_ENDPOINTS.logVisit, {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify({ symbol }),
    }).catch(() => {
      /* no bloquea la UI si falla; el historial es informativo, no critico */
    });
  }

  loadQuotes();
})();
