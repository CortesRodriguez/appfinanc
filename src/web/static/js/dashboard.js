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
  let bollingerUpperSeries = null;
  let bollingerMiddleSeries = null;
  let bollingerLowerSeries = null;

  // Subgraficos (RSI, MACD): se crean la primera vez que el usuario los
  // habilita. Antes de eso, sus <div> estan ocultos.
  let rsiChart = null;
  let rsiSeries = null;
  let macdChart = null;
  let macdLineSeries = null;
  let macdSignalSeries = null;
  let macdHistSeries = null;

  // Ultimo payload de /api/chart, guardado para poder re-aplicar visibilidad
  // sin volver a pedir datos.
  let lastChartSeries = null;

  // Estado de visibilidad de cada indicador. El default coincide con los
  // checkboxes iniciales del template (solo MACD marcado).
  const indicatorVisibility = {
    sma_short: false,
    sma_long: false,
    bollinger: false,
    rsi: false,
    macd: true,
  };

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
  let selectedInterval = "1d";
  const cardState = {}; // indicator key -> {variant, days}
  // Estado de la sidebar: solo orden. Chips de ganadoras/perdedoras se
  // sacaron por decision de diseno — la usuaria queria maxima densidad y
  // ver de una todas las acciones.
  let sidebarSort = "nombre"; // 'nombre' | 'cambio_desc' | 'cambio_asc' | 'precio_desc' | 'precio_asc'

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
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "meta empty-list";
      li.textContent = "Sin coincidencias en este filtro.";
      listEl.appendChild(li);
      return;
    }
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

  // Busqueda de texto + orden. Actualiza contador visible arriba del list.
  function applySidebarPipeline() {
    const q = (searchInput.value || "").trim().toLowerCase();
    const search = (inst) =>
      !q ||
      inst.symbol.toLowerCase().includes(q) ||
      inst.name.toLowerCase().includes(q) ||
      (inst.sector || "").toLowerCase().includes(q);

    const changeOf = (inst) => (typeof inst.daily_change_pct === "number" ? inst.daily_change_pct : null);
    const priceOf = (inst) => (typeof inst.price === "number" ? inst.price : null);

    const filtered = catalog.filter(search);
    const countEl = document.getElementById("sidebar-count-num");
    if (countEl) countEl.textContent = filtered.length;

    const collator = new Intl.Collator("es-CL", { sensitivity: "base" });
    const sorted = [...filtered].sort((a, b) => {
      switch (sidebarSort) {
        case "cambio_desc": return (changeOf(b) ?? -Infinity) - (changeOf(a) ?? -Infinity);
        case "cambio_asc": return (changeOf(a) ?? Infinity) - (changeOf(b) ?? Infinity);
        case "precio_desc": return (priceOf(b) ?? -Infinity) - (priceOf(a) ?? -Infinity);
        case "precio_asc": return (priceOf(a) ?? Infinity) - (priceOf(b) ?? Infinity);
        default: return collator.compare(a.name, b.name);
      }
    });

    renderList(sorted);
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
      applySidebarPipeline();
    } catch (err) {
      listEl.innerHTML = "<li class='meta'>No fue posible cargar la lista de instrumentos.</li>";
    }
  }

  searchInput.addEventListener("input", () => {
    lookupHint.classList.add("hidden");
    applySidebarPipeline();

    const q = searchInput.value.trim();
    if (q && listEl.querySelectorAll(".instrument-item").length === 0) {
      lookupHint.classList.remove("hidden");
      lookupHint.innerHTML = `No está en la lista. <button type="button" id="lookup-btn">Buscar "${q.toUpperCase()}" directamente</button>`;
      document.getElementById("lookup-btn").addEventListener("click", () => lookupSymbol(q));
    }
  });

  // Select de ordenamiento (nombre / cambio / precio).
  const sortSelect = document.getElementById("sort-select");
  if (sortSelect) {
    sortSelect.addEventListener("change", (e) => {
      sidebarSort = e.target.value;
      applySidebarPipeline();
    });
  }

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
        fontFamily: "Inter, -apple-system, sans-serif",
        attributionLogo: false, // apaga la marca TradingView del canvas
      },
      grid: {
        vertLines: { color: "rgba(139, 152, 165, 0.08)" },
        horzLines: { color: "rgba(139, 152, 165, 0.08)" },
      },
      // minimumWidth mantiene el eje de precio con ancho constante -> los
      // tres charts stackeados quedan con la misma columna de precios y las
      // series alineadas verticalmente pixel a pixel.
      rightPriceScale: { borderColor: "#232c38", minimumWidth: PRICE_SCALE_MIN_WIDTH },
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

    // MA "corta" (por defecto 50): linea fina y punteada, sub-dominante —
    // el ruido de la MA corta debe estorbar poco. TradingView usa el mismo
    // patron (dashed / thinner) para las MAs auxiliares.
    smaShortSeries = chartInstance.addLineSeries({
      color: "#38bdf8",
      lineWidth: 1,
      lineStyle: 2, // dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // MA "larga" (por defecto 200): linea solida, mas gruesa, en naranja —
    // color estandar en TradingView para MA200 (F7931E). Es la referencia
    // dominante de tendencia de largo plazo, por eso pesa mas visualmente.
    smaLongSeries = chartInstance.addLineSeries({
      color: "#F7931E",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Bandas de Bollinger al estilo TradingView:
    //   - Banda superior e inferior: linea azul #2962FF, fina y solida.
    //   - Banda media (SMA20): misma azul mas transparente + punteada
    //     (indica que es la media de referencia, no una banda de precio).
    //   Sin fill entre bandas porque lightweight-charts v4 no soporta band
    //   series nativos; las lineas finas ya dan el look estandar.
    bollingerUpperSeries = chartInstance.addLineSeries({
      color: "#2962FF",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    bollingerMiddleSeries = chartInstance.addLineSeries({
      color: "rgba(41, 98, 255, 0.55)",
      lineWidth: 1,
      lineStyle: 2, // dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    bollingerLowerSeries = chartInstance.addLineSeries({
      color: "#2962FF",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Registrar el chart principal en el sync de crosshair; el subscribe
    // dispara el tooltip flotante y sincroniza RSI/MACD.
    registerCrosshair(chartInstance, "main");
    registerTimeSync(chartInstance);
  }

  // Config comun de subgraficos: mismos margenes, mismo look. Ancho minimo
  // del eje de precio alineado con el chart principal para que las tres
  // "panes" queden con el borde derecho perfectamente en columna, como TV.
  const PRICE_SCALE_MIN_WIDTH = 68;
  const SUB_CHART_OPTIONS = {
    autoSize: true,
    layout: { background: { type: "solid", color: "#131a24" }, textColor: "#e6edf3", fontSize: 11, fontFamily: "Inter, -apple-system, sans-serif", attributionLogo: false },
    grid: {
      vertLines: { color: "rgba(139, 152, 165, 0.06)" },
      horzLines: { color: "rgba(139, 152, 165, 0.06)" },
    },
    rightPriceScale: { borderColor: "#232c38", scaleMargins: { top: 0.1, bottom: 0.1 }, minimumWidth: PRICE_SCALE_MIN_WIDTH },
    // El eje de tiempo se muestra SOLO en el pane mas bajo visible (lo maneja
    // updateBottomTimeAxis). Aqui arrancan ocultos.
    timeScale: { borderColor: "#232c38", timeVisible: false, secondsVisible: false, visible: false },
    crosshair: { mode: 1 },
    localization: { locale: "es-CL" },
  };

  // Subgrafico RSI al estilo TradingView:
  //   - Linea unica en violeta (#7E57C2), el color de RSI por default de TV.
  //   - Escala FIJA 0-100 (no autoscale) — asi las lineas 70/30/50 estan
  //     siempre en la misma posicion visual, se pueda leer sobrecompra/
  //     sobreventa de un vistazo.
  //   - Guias horizontales en 70 (rojo), 50 (gris punteada) y 30 (verde).
  //   - Bandas de fondo tenues sobre 70 y bajo 30 para reforzar las zonas.
  function ensureRsiChart() {
    if (rsiChart) return;
    const el = document.getElementById("rsi-chart");
    if (!el) return;
    rsiChart = LightweightCharts.createChart(el, SUB_CHART_OPTIONS);
    rsiSeries = rsiChart.addLineSeries({
      color: "#7E57C2",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
      crosshairMarkerBorderColor: "#7E57C2",
      crosshairMarkerBackgroundColor: "#7E57C2",
      // Escala visual fija 0-100: el rango del oscilador es cerrado por
      // definicion, no dejar que el autoscale lo estire ni comprima.
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    rsiSeries.createPriceLine({ price: 70, color: "rgba(239, 83, 80, 0.55)", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "70" });
    rsiSeries.createPriceLine({ price: 50, color: "rgba(139, 152, 165, 0.35)", lineWidth: 1, lineStyle: 3, axisLabelVisible: false });
    rsiSeries.createPriceLine({ price: 30, color: "rgba(38, 166, 154, 0.55)", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "30" });
    registerCrosshair(rsiChart, "rsi");
    registerTimeSync(rsiChart);
  }

  // Subgrafico MACD al estilo TradingView:
  //   - Linea MACD azul (#2962FF), linea de senal naranja (#FF6D00) — colores
  //     por default de TV.
  //   - Histograma con 4 colores segun signo y direccion:
  //       verde brillante  -> histograma >= 0 y creciendo
  //       verde apagado    -> histograma >= 0 y decreciendo
  //       rojo apagado     -> histograma <  0 y creciendo (menos negativo)
  //       rojo brillante   -> histograma <  0 y decreciendo (mas negativo)
  //     Este esquema es el que TV usa por default y muestra "impulso" del
  //     histograma, no solo su signo.
  //   - Linea horizontal en 0 (referencia).
  function ensureMacdChart() {
    if (macdChart) return;
    const el = document.getElementById("macd-chart");
    if (!el) return;
    macdChart = LightweightCharts.createChart(el, SUB_CHART_OPTIONS);
    macdHistSeries = macdChart.addHistogramSeries({
      priceLineVisible: false,
      lastValueVisible: false,
      base: 0,
    });
    macdLineSeries = macdChart.addLineSeries({
      color: "#2962FF",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerRadius: 3,
    });
    macdSignalSeries = macdChart.addLineSeries({
      color: "#FF6D00",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerRadius: 3,
    });
    // Cero horizontal como referencia.
    macdLineSeries.createPriceLine({ price: 0, color: "rgba(139, 152, 165, 0.4)", lineWidth: 1, lineStyle: 3, axisLabelVisible: false });
    registerCrosshair(macdChart, "macd");
    registerTimeSync(macdChart);
  }

  // Colores TradingView del histograma MACD (verde/rojo, claro/oscuro).
  const MACD_HIST_COLORS = {
    posUp: "#26A69A",       // >=0 y creciendo
    posDown: "#B2DFDB",     // >=0 pero decreciendo
    negUp: "#FFCDD2",       // <0 pero creciendo (menos negativo)
    negDown: "#EF5350",     // <0 y decreciendo
  };

  function macdHistColor(curr, prev) {
    if (curr >= 0) return prev !== null && curr < prev ? MACD_HIST_COLORS.posDown : MACD_HIST_COLORS.posUp;
    return prev !== null && curr > prev ? MACD_HIST_COLORS.negUp : MACD_HIST_COLORS.negDown;
  }

  function applyIndicatorVisibility() {
    if (smaShortSeries) smaShortSeries.applyOptions({ visible: indicatorVisibility.sma_short });
    if (smaLongSeries) smaLongSeries.applyOptions({ visible: indicatorVisibility.sma_long });
    if (bollingerUpperSeries) bollingerUpperSeries.applyOptions({ visible: indicatorVisibility.bollinger });
    if (bollingerMiddleSeries) bollingerMiddleSeries.applyOptions({ visible: indicatorVisibility.bollinger });
    if (bollingerLowerSeries) bollingerLowerSeries.applyOptions({ visible: indicatorVisibility.bollinger });

    const rsiPanel = document.getElementById("rsi-panel");
    const macdPanel = document.getElementById("macd-panel");
    if (rsiPanel) rsiPanel.classList.toggle("hidden", !indicatorVisibility.rsi);
    if (macdPanel) macdPanel.classList.toggle("hidden", !indicatorVisibility.macd);

    if (indicatorVisibility.rsi) {
      ensureRsiChart();
      if (lastChartSeries) applyRsiData(lastChartSeries);
    }
    if (indicatorVisibility.macd) {
      ensureMacdChart();
      if (lastChartSeries) applyMacdData(lastChartSeries);
    }

    // El eje de tiempo (fechas) vive solo en el pane mas bajo visible; y
    // los subs recien creados heredan el rango temporal del principal.
    updateBottomTimeAxis();
    syncTimeRangeFromMain();
    // Alinea escalas despues de que los subs se hayan pintado con datos.
    requestAnimationFrame(alignPriceScales);
  }

  function applyRsiData(series) {
    if (!rsiSeries) return;
    const points = (series.dates || [])
      .map((d, i) => (series.rsi && series.rsi[i] != null ? { time: d, value: series.rsi[i] } : null))
      .filter(Boolean);
    rsiSeries.setData(points);
    // No fitContent aqui: el rango temporal lo controla el chart principal
    // (via syncTimeRangeFromMain). Si hacemos fit, el RSI se estiraria hacia
    // atras hasta el inicio del buffer de 10 anos aunque el usuario haya
    // pedido "1 ano".
  }

  function applyMacdData(series) {
    if (!macdLineSeries || !macdSignalSeries || !macdHistSeries) return;
    const dates = series.dates || [];
    const line = dates
      .map((d, i) => (series.macd_line && series.macd_line[i] != null ? { time: d, value: series.macd_line[i] } : null))
      .filter(Boolean);
    const signalPts = dates
      .map((d, i) => (series.macd_signal && series.macd_signal[i] != null ? { time: d, value: series.macd_signal[i] } : null))
      .filter(Boolean);
    // Histograma: color depende de signo Y direccion (estilo TradingView).
    // Se recorre en orden temporal manteniendo el valor previo no-nulo.
    let prev = null;
    const hist = [];
    for (let i = 0; i < dates.length; i++) {
      const v = series.macd_histogram && series.macd_histogram[i];
      if (v == null) continue;
      hist.push({ time: dates[i], value: v, color: macdHistColor(v, prev) });
      prev = v;
    }
    macdLineSeries.setData(line);
    macdSignalSeries.setData(signalPts);
    macdHistSeries.setData(hist);
    // Rango temporal lo controla el chart principal (ver applyRsiData).
  }

  // ------------------------------------------------------------------
  // Crosshair sincronizado + tooltip flotante estilo TradingView.
  // Cuando el usuario mueve el cursor sobre cualquier chart, todos los
  // demas mueven su crosshair al mismo instante temporal, y las cajas
  // flotantes (overlays) muestran los valores exactos del punto bajo el
  // cursor. Cuando el cursor sale del area del chart, mostramos los
  // valores mas recientes (comportamiento por defecto de TV).
  // ------------------------------------------------------------------
  const crosshairRegistry = []; // [{ chart, id }]

  function registerCrosshair(chart, id) {
    crosshairRegistry.push({ chart, id });
    chart.subscribeCrosshairMove((param) => onCrosshairMove(param, id));
  }

  // Encuentra el indice en `series.dates` del punto correspondiente a `time`.
  // lightweight-charts entrega el tiempo del punto en el que esta el crosshair;
  // buscamos el indice para leer todas las series alineadas del payload.
  function indexOfTime(time) {
    if (!lastChartSeries || !lastChartSeries.dates) return -1;
    if (!time) return lastChartSeries.dates.length - 1; // fuera del chart -> ultimo
    return lastChartSeries.dates.indexOf(time);
  }

  function fmtNumber(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
  }

  function updateMainLegend(idx) {
    const s = lastChartSeries;
    if (!s) return;
    const el = document.getElementById("price-legend");
    if (!el) return;
    if (idx < 0 || idx >= s.dates.length) {
      el.classList.add("hidden");
      return;
    }
    el.classList.remove("hidden");
    const setText = (id, txt) => { const n = document.getElementById(id); if (n) n.textContent = txt; };

    setText("ov-symbol", current ? current.symbol : "");
    setText("ov-date", fmtDate(s.dates[idx]));
    setText("ov-o", fmtNumber(s.open ? s.open[idx] : null, 2));
    setText("ov-h", fmtNumber(s.high ? s.high[idx] : null, 2));
    setText("ov-l", fmtNumber(s.low ? s.low[idx] : null, 2));
    setText("ov-c", fmtNumber(s.close ? s.close[idx] : null, 2));

    // Variacion vs cierre previo, con signo y color.
    const chgEl = document.getElementById("ov-chg");
    if (chgEl) {
      const c = s.close ? s.close[idx] : null;
      const prev = idx > 0 && s.close ? s.close[idx - 1] : null;
      if (c != null && prev != null && prev !== 0) {
        const chg = ((c - prev) / prev) * 100;
        const sign = chg > 0 ? "+" : "";
        chgEl.textContent = `${sign}${chg.toFixed(2)}%`;
        chgEl.className = "ov-chg " + (chg > 0 ? "up" : chg < 0 ? "down" : "flat");
      } else {
        chgEl.textContent = "—";
        chgEl.className = "ov-chg flat";
      }
    }

    // Segunda linea: solo se muestra si alguna serie overlay esta visible.
    const showShort = indicatorVisibility.sma_short && s.sma_short && s.sma_short[idx] != null;
    const showLong = indicatorVisibility.sma_long && s.sma_long && s.sma_long[idx] != null;
    const showBB = indicatorVisibility.bollinger && s.bollinger_upper && s.bollinger_upper[idx] != null;

    const maLine = document.getElementById("ov-ma-line");
    if (maLine) maLine.classList.toggle("hidden", !(showShort || showLong || showBB));

    const toggle = (id, on) => { const n = document.getElementById(id); if (n) n.classList.toggle("hidden", !on); };
    toggle("ov-ma-short-wrap", showShort);
    toggle("ov-ma-long-wrap", showLong);
    toggle("ov-bb-wrap", showBB);

    if (showShort) {
      setText("ov-ma-short-w", s.short_window || "");
      setText("ov-ma-short", fmtNumber(s.sma_short[idx], 2));
    }
    if (showLong) {
      setText("ov-ma-long-w", s.long_window || "");
      setText("ov-ma-long", fmtNumber(s.sma_long[idx], 2));
    }
    if (showBB) {
      setText("ov-bb-upper", fmtNumber(s.bollinger_upper[idx], 2));
      setText("ov-bb-middle", fmtNumber(s.bollinger_middle[idx], 2));
      setText("ov-bb-lower", fmtNumber(s.bollinger_lower[idx], 2));
    }
  }

  function updateRsiLegend(idx) {
    const s = lastChartSeries;
    const el = document.getElementById("rsi-legend");
    if (!el || !s) return;
    if (idx < 0 || idx >= (s.rsi || []).length) { el.classList.add("hidden"); return; }
    el.classList.remove("hidden");
    const v = s.rsi[idx];
    document.getElementById("ov-rsi").textContent = fmtNumber(v, 2);
    const tag = document.getElementById("ov-rsi-tag");
    if (v == null) { tag.textContent = ""; tag.className = "ov-tag"; }
    else if (v > 70) { tag.textContent = "sobrecompra"; tag.className = "ov-tag over"; }
    else if (v < 30) { tag.textContent = "sobreventa"; tag.className = "ov-tag under"; }
    else { tag.textContent = "neutral"; tag.className = "ov-tag mid"; }
  }

  function updateMacdLegend(idx) {
    const s = lastChartSeries;
    const el = document.getElementById("macd-legend");
    if (!el || !s) return;
    if (idx < 0 || idx >= (s.macd_line || []).length) { el.classList.add("hidden"); return; }
    el.classList.remove("hidden");
    document.getElementById("ov-macd").textContent = fmtNumber(s.macd_line[idx], 4);
    document.getElementById("ov-macd-sig").textContent = fmtNumber(s.macd_signal[idx], 4);
    const histEl = document.getElementById("ov-macd-hist");
    const h = s.macd_histogram ? s.macd_histogram[idx] : null;
    histEl.textContent = fmtNumber(h, 4);
    histEl.className = h == null ? "" : h >= 0 ? "up" : "down";
  }

  function updateAllLegends(idx) {
    updateMainLegend(idx);
    updateRsiLegend(idx);
    updateMacdLegend(idx);
  }

  function onCrosshairMove(param, sourceId) {
    // Sincroniza el crosshair con los otros charts al mismo instante.
    const t = param.time || null;
    crosshairRegistry.forEach(({ chart, id }) => {
      if (id === sourceId) return;
      // setCrosshairPosition espera (price, time, series). Solo lo movemos si
      // hay tiempo valido; si el mouse salio de todos los charts, no forzamos.
      if (t) chart.setCrosshairPosition(NaN, t, chart === rsiChart ? rsiSeries : macdLineSeries);
      else chart.clearCrosshairPosition();
    });

    const idx = indexOfTime(t);
    updateAllLegends(idx);
  }

  // ------------------------------------------------------------------
  // Sync del rango de tiempo entre el chart principal y los subgraficos.
  // Cuando el usuario abre un instrumento con "1 ano" el chart principal
  // muestra el ultimo ano; los subgraficos deben mostrar exactamente ese
  // mismo rango (no todos los 10 anos que se traen como buffer). Cualquier
  // pan/zoom en cualquier chart debe propagarse al resto.
  // Un flag re-entrant evita el loop infinito de subscribers cruzados.
  // ------------------------------------------------------------------
  let syncingTimeRange = false;

  function propagateVisibleRange(sourceChart, logicalRange) {
    if (syncingTimeRange || !logicalRange) return;
    syncingTimeRange = true;
    try {
      const targets = [chartInstance, rsiChart, macdChart].filter((c) => c && c !== sourceChart);
      targets.forEach((c) => c.timeScale().setVisibleLogicalRange(logicalRange));
    } finally {
      syncingTimeRange = false;
    }
  }

  function registerTimeSync(chart) {
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => propagateVisibleRange(chart, range));
  }

  function syncTimeRangeFromMain() {
    // Se llama cuando reciennace un subgrafico (RSI/MACD toggle-on) para
    // que empiece alineado con la vista del principal.
    if (!chartInstance) return;
    const range = chartInstance.timeScale().getVisibleLogicalRange();
    propagateVisibleRange(chartInstance, range);
  }

  // Alinea el ancho de la escala de precio (columna derecha) de los tres
  // charts al maximo real que necesita el mayor de ellos. Sin esto, el chart
  // principal (precios ~65 000) tiene una escala de ~70 px, RSI (0-100) de
  // ~35 px y MACD (~100) de ~40 px, lo que hace que las areas de ploteo
  // queden desalineadas y el crosshair caiga en columnas de fecha distintas.
  // TradingView aplica el mismo truco: iguala el ancho de la escala a la
  // mayor de todas para que las series de todos los panes queden pixel-a-pixel
  // sobre la misma columna temporal.
  let aligningScales = false;
  function alignPriceScales() {
    if (aligningScales) return; // evita reentrada por el re-layout que dispara applyOptions
    const charts = [chartInstance, rsiChart, macdChart].filter(Boolean);
    if (charts.length < 2) return;
    aligningScales = true;
    try {
      const widths = charts.map((c) => c.priceScale("right").width());
      const target = Math.max(...widths, PRICE_SCALE_MIN_WIDTH);
      charts.forEach((c) => c.priceScale("right").applyOptions({ minimumWidth: target }));
    } finally {
      // Se libera en el siguiente tick para permitir que el layout se asiente
      // antes del proximo ciclo (por si un chart repinta y dispara otra vez).
      setTimeout(() => { aligningScales = false; }, 0);
    }
  }

  // El eje de tiempo (fechas en la banda inferior) se muestra SOLO en el
  // pane mas bajo actualmente visible: MACD > RSI > principal. Asi el
  // stack se lee como un unico chart con eje compartido.
  function updateBottomTimeAxis() {
    const showOn = indicatorVisibility.macd
      ? "macd"
      : indicatorVisibility.rsi
      ? "rsi"
      : "main";
    if (chartInstance) chartInstance.timeScale().applyOptions({ visible: showOn === "main" });
    if (rsiChart) rsiChart.timeScale().applyOptions({ visible: showOn === "rsi" });
    if (macdChart) macdChart.timeScale().applyOptions({ visible: showOn === "macd" });
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

    const mapBand = (arr) => dates
      .map((d, i) => (arr && arr[i] != null ? { time: d, value: arr[i] } : null))
      .filter(Boolean);
    bollingerUpperSeries.setData(mapBand(series.bollinger_upper));
    bollingerMiddleSeries.setData(mapBand(series.bollinger_middle));
    bollingerLowerSeries.setData(mapBand(series.bollinger_lower));

    const legendShort = document.getElementById("legend-ma-short");
    const legendLong = document.getElementById("legend-ma-long");
    if (legendShort && series.short_window) legendShort.textContent = `MA${series.short_window}`;
    if (legendLong && series.long_window) legendLong.textContent = `MA${series.long_window}`;

    lastChartSeries = series;
    applyIndicatorVisibility();
    // Muestra por defecto los valores del ultimo punto en el tooltip (como TV).
    updateAllLegends(dates.length - 1);

    const visibleDays = series.visible_days || dates.length;
    if (dates.length > visibleDays && visibleDays > 0) {
      // Buffer estatico: se trajeron mas velas que las del boton para permitir
      // pan/zoom-out al pasado. La vista inicial se ancla al rango pedido.
      const fromDate = dates[Math.max(0, dates.length - visibleDays)];
      const toDate = dates[dates.length - 1];
      chartInstance.timeScale().setVisibleRange({ from: fromDate, to: toDate });
    } else {
      chartInstance.timeScale().fitContent();
    }
    // Propaga el rango ya establecido a RSI/MACD (si estan abiertos).
    syncTimeRangeFromMain();
    // Iguala el ancho de la escala de precio en los tres charts para que
    // las columnas temporales queden pixel-a-pixel alineadas.
    requestAnimationFrame(alignPriceScales);
  }

  async function loadChart(symbol, days) {
    chartError.classList.add("hidden");
    chartLoading.classList.remove("hidden");

    try {
      const response = await fetch(`${window.APP_ENDPOINTS.chart}?symbol=${encodeURIComponent(symbol)}&days=${days}&interval=${selectedInterval}`);
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

  // Badge principal: la senal oficial de RF-04.2 por indicador.
  //   RSI  y Bollinger  -> sobrecomprado / sobrevendido / neutral
  //   MACD y Medias mov -> alcista / bajista
  // Backend ya calcula `signal` (RSI, Bollinger) y `trend` (MACD, MAs).
  function signalBadge(indicatorKey, data) {
    if (indicatorKey === "medias_moviles" || indicatorKey === "macd") {
      const trend = data.trend === "bajista" ? "bajista" : "alcista";
      const arrow = trend === "bajista" ? "▼" : "▲";
      return { cls: trend, text: `${arrow} ${trend}` };
    }
    if (indicatorKey === "rsi") {
      const sig = data.signal || "neutral"; // sobrecomprado | sobrevendido | neutral
      const arrow = sig === "sobrecomprado" ? "▲" : sig === "sobrevendido" ? "▼" : "●";
      return { cls: sig, text: `${arrow} ${sig}` };
    }
    if (indicatorKey === "bandas_bollinger") {
      // Backend puede devolver: sobrecomprado / sobrevendido / cercano_al_extremo / normal
      const sig = data.signal || "normal";
      const label = sig === "cercano_al_extremo" ? "cerca del extremo" : sig;
      const arrow = sig === "sobrecomprado" ? "▲" : sig === "sobrevendido" ? "▼" : "●";
      return { cls: sig, text: `${arrow} ${label}` };
    }
    return { cls: "neutral", text: data.signal || "" };
  }

  // Badge secundario: nivel de riesgo relativo (RF-06.1), aplica a los 4 indicadores.
  function riskBadge(data) {
    const lvl = data.risk_level;
    if (!lvl) return null;
    return { cls: lvl, text: `riesgo ${lvl}` };
  }

  function formatIndicatorValue(indicatorKey, data) {
    if (indicatorKey === "medias_moviles") return data.trend === "bajista" ? "Bajista" : "Alcista";
    if (indicatorKey === "rsi") return `${data.value}`;
    if (indicatorKey === "macd") return `${data.value}`;
    if (indicatorKey === "bandas_bollinger") return `%B ${data.value}`;
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

    const signal = signalBadge(meta.key, data);
    const risk = riskBadge(data);

    // Dos modos de renderizado:
    //   - explained=false: valor + badge + boton "Ver explicacion en simple".
    //     Es el estado inicial tras loadIndicators (fetch barato, sin log).
    //   - explained=true: se agrega el parrafo de explicacion + boton de
    //     regeneracion. La trazabilidad de RF-02.2 (fuente, fecha, indicador
    //     literal) vive en /history, no en la card — evita ruido visual.
    const explained = Boolean(data.explanation);

    card.innerHTML = `
      <div class="indicator-card-header">
        <span class="indicator-title">${meta.title}</span>
        <div class="badge-stack">
          <span class="badge ${signal.cls}">${signal.text}</span>
          ${risk ? `<span class="badge badge-small ${risk.cls}">${risk.text}</span>` : ""}
        </div>
      </div>
      <div class="indicator-value">${formatIndicatorValue(meta.key, data)}</div>
      <div class="indicator-sub">${meta.sub}</div>
      ${explained ? `<p class="indicator-text">${data.explanation}</p>` : ""}
      ${explained && data.coherent === false ? '<div class="warn">Marcado para revisión de coherencia.</div>' : ""}
      ${explained
        ? `<button type="button" class="link-btn regen-btn">No entendí esto</button>`
        : `<button type="button" class="explain-cta">Ver explicación en simple</button>`}
    `;

    if (explained) {
      card.querySelector(".regen-btn").addEventListener("click", () => regenerateCard(meta));
    } else {
      card.querySelector(".explain-cta").addEventListener("click", () => explainCard(meta));
    }
  }


  // Fetch ligero: solo valor + badge + trazabilidad, sin explicacion ni log.
  // Se usa en el fetch inicial al hacer click en una accion (RF-02.2/CU-03:
  // cada QueryLog representa una consulta deliberada del usuario, no un batch).
  async function fetchValue(symbol, indicatorKey, days) {
    const url = `${window.APP_ENDPOINTS.indicatorValue}?symbol=${encodeURIComponent(symbol)}&indicator=${encodeURIComponent(indicatorKey)}&days=${days}`;
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No fue posible obtener el indicador.");
    return data;
  }

  // Fetch completo: golpea /api/query (o /api/regenerate si variant>0),
  // corre FinBERT, valida coherencia y persiste `QueryLog` + `CoherenceCheck`.
  // Cada llamada a esta funcion = una fila de traza en RF-02.2.
  async function fetchExplanation(symbol, indicatorKey, days, variant) {
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

    // Instrumento 1: el backend nos avisa cuando esta cuenta ya cumple umbral
    // y todavía no decidió participar. El banner se muestra una sola vez por
    // sesión de dashboard (el propio banner se auto-oculta al decidir).
    if (data.invitacion_estudio === "mostrar" && typeof window.showStudyBanner === "function") {
      window.showStudyBanner();
    }
    return data;
  }

  // Handler del boton "Ver explicacion en simple": muestra un spinner en la
  // card, pide la explicacion via /api/query (unica llamada que escribe log),
  // y re-renderiza la card con explicacion + panel de trazabilidad.
  async function explainCard(meta) {
    if (!current) return;
    const state = cardState[meta.key];
    const card = document.querySelector(`.indicator-card[data-indicator="${meta.key}"]`);
    if (card) card.classList.add("card-loading");

    try {
      const data = await fetchExplanation(current.symbol, meta.key, state.days, 0);
      // Preservamos campos ricos del /api/query (explanation, coherent) y
      // aseguramos que renderCard entre en modo explained=true.
      lastIndicatorData[meta.key] = data;
      renderCard(meta, data);
      composeSummary();
    } catch (err) {
      indicatorsError.textContent = err.message;
      indicatorsError.classList.remove("hidden");
    } finally {
      if (card) card.classList.remove("card-loading");
    }
  }

  async function regenerateCard(meta) {
    if (!current) return;
    const state = cardState[meta.key];
    state.variant += 1;

    try {
      const data = await fetchExplanation(current.symbol, meta.key, state.days, state.variant);
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
    const rsi = lastIndicatorData.rsi;
    const macd = lastIndicatorData.macd;
    const bb = lastIndicatorData.bandas_bollinger;

    if (!trend || !rsi || !macd || !bb || !current) return;

    const trendWord = trend.trend === "bajista" ? "bajista" : "alcista";
    const macdWord = macd.trend === "bajista" ? "bajista" : "alcista";
    const bbSignal = bb.signal === "sobrecomprado"
      ? "por sobre el rango habitual del precio"
      : bb.signal === "sobrevendido"
      ? "por debajo del rango habitual del precio"
      : "dentro del rango habitual del precio";
    const parts = [
      `${current.symbol} muestra una tendencia ${trendWord} según sus medias móviles y una lectura ${macdWord} en el MACD.`,
      `El RSI está en ${rsi.value} puntos, lo que indica riesgo ${rsi.risk_level} de sobrecompra o sobreventa.`,
      `Las Bandas de Bollinger sitúan al precio ${bbSignal} (%B ${bb.value}, riesgo ${bb.risk_level}).`,
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
      // Fetch inicial ligero: valores + trazabilidad, sin explicaciones ni
      // escritura en `query_logs`. La explicacion (y su fila de log) se
      // genera cuando la usuaria pulsa "Ver explicacion en simple" en cada
      // card. Este split le da semantica real a RF-02.2 / CU-03: cada log
      // corresponde a una consulta deliberada, no a un batch.
      const results = await Promise.all(
        window.APP_INDICATORS.map((meta) => fetchValue(symbol, meta.key, days))
      );
      window.APP_INDICATORS.forEach((meta, idx) => {
        const data = results[idx];
        lastIndicatorData[meta.key] = data;
        renderCard(meta, data); // sin `explanation` => modo valor-only
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

  // Selector de intervalo de vela (Diario/Semanal/Mensual/Trimestral): solo
  // afecta la granularidad del grafico. Los indicadores del panel siguen
  // atados al rango del boton, no al intervalo.
  const intervalSelect = document.getElementById("interval-select");
  if (intervalSelect) {
    intervalSelect.addEventListener("change", (e) => {
      selectedInterval = e.target.value;
      if (current) {
        loadChart(current.symbol, selectedDays);
      }
    });
  }

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

  // Al redimensionar la ventana, autoSize recalcula el ancho del canvas
  // pero las escalas de precio pueden divergir otra vez segun los labels.
  // Alineamos con debounce corto para no reflowear en cada pixel de resize.
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(alignPriceScales, 100);
  });

  // Checkboxes del header del chart: cada uno controla la visibilidad de
  // un indicador. Overlays (MA corta/larga/Bollinger) usan applyOptions
  // sobre la serie; subgraficos (RSI/MACD) muestran/ocultan su panel y
  // se crean de forma perezosa cuando se activan por primera vez.
  document.querySelectorAll("[data-indicator-toggle]").forEach((cb) => {
    const key = cb.dataset.indicatorToggle;
    if (key in indicatorVisibility) {
      cb.checked = indicatorVisibility[key];
    }
    cb.addEventListener("change", () => {
      indicatorVisibility[key] = cb.checked;
      applyIndicatorVisibility();
    });
  });

  loadQuotes();
})();

// Instrumento 1: banner recordatorio para responder la autoevaluación.
// El consentimiento se otorga al momento del registro (checkbox opcional en
// register.html / modal de auth). Este banner solo aparece cuando la cuenta
// tiene `acepta_evaluacion=True` y ya cumplió `SURVEY_THRESHOLD` visitas.
// "Responder ahora" navega a /encuesta; "Más tarde" oculta el banner por esta
// sesión (no cambia la decisión persistida).
(function initStudyBanner() {
  const banner = document.getElementById("study-banner");
  if (!banner) return;

  const postponeBtn = document.getElementById("study-postpone");
  let alreadyShown = false;

  window.showStudyBanner = function () {
    if (alreadyShown) return;
    alreadyShown = true;
    banner.classList.remove("hidden");
  };

  if (postponeBtn) {
    postponeBtn.addEventListener("click", () => banner.classList.add("hidden"));
  }
})();
