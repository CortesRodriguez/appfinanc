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
  const explainPanel = document.getElementById("explain-panel");
  const LEVEL_NAMES = { basico: "Básico", intermedio: "Intermedio", avanzado: "Avanzado" };
  let activeKey = null; // indicador cuya explicacion esta abierta en el panel

  const periodButtons = document.querySelectorAll(".period-btn");
  const periodLabelEl = document.getElementById("chart-period-label");
  const PERIOD_LABELS = { 30: "1 mes", 90: "3 meses", 180: "6 meses", 365: "1 año" };
  const INTERVAL_LABELS = { "1d": "1D", "1w": "1S", "1mo": "1M", "3mo": "3M" };
  const TYPE_LABELS = { candlestick: "Velas", line: "Línea", area: "Montaña" };

  let catalog = [];
  let current = null; // {symbol, name, sector, type, price, daily_change_pct}
  let selectedDays = 180;
  let selectedInterval = "1d";
  let selectedChartType = "candlestick";
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
      renderLanding();
    } catch (err) {
      listEl.innerHTML = "<li class='meta'>No fue posible cargar la lista de instrumentos.</li>";
      renderLanding("No fue posible cargar las cotizaciones.");
    }
  }

  // ---------- Portada (sin acción seleccionada) ----------
  // Todo se arma con createElement/textContent: los titulares vienen de
  // medios externos y nunca se insertan como HTML.
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fillMessage(listEl, msg) {
    listEl.innerHTML = "";
    listEl.appendChild(el("li", "meta", msg));
  }

  function timeAgo(iso) {
    const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (!Number.isFinite(minutes)) return "";
    if (minutes < 60) return `hace ${Math.max(1, minutes)} min`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `hace ${hours} h`;
    const days = Math.round(hours / 24);
    return days === 1 ? "hace 1 día" : `hace ${days} días`;
  }

  function topMovers() {
    const sorted = catalog
      .filter((i) => typeof i.daily_change_pct === "number")
      .sort((a, b) => b.daily_change_pct - a.daily_change_pct);
    return {
      up: sorted.filter((i) => i.daily_change_pct > 0).slice(0, 3),
      down: sorted.filter((i) => i.daily_change_pct < 0).reverse().slice(0, 3),
    };
  }

  function sparklineSvg(closes, cls) {
    const w = 84, h = 26;
    const min = Math.min(...closes), max = Math.max(...closes);
    const span = max - min || 1;
    const points = closes
      .map((v, i) => `${((i / (closes.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`)
      .join(" ");
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("class", `sparkline ${cls}`);
    svg.setAttribute("aria-hidden", "true");
    const line = document.createElementNS(ns, "polyline");
    line.setAttribute("points", points);
    svg.appendChild(line);
    return svg;
  }

  async function loadSparkline(symbol, slot) {
    try {
      const response = await fetch(`${window.APP_ENDPOINTS.sparkline}?symbol=${encodeURIComponent(symbol)}`);
      if (!response.ok) return;
      const { closes } = await response.json();
      if (!closes || closes.length < 2) return;
      const trend = closes[closes.length - 1] >= closes[0] ? "up" : "down";
      slot.replaceChildren(sparklineSvg(closes, trend));
      slot.title = "Últimos 30 días";
    } catch (err) {
      // Sin mini-gráfico: la fila sigue funcionando.
    }
  }

  function renderMoverList(listEl, rows) {
    if (!rows.length) {
      fillMessage(listEl, "Sin datos de variación hoy.");
      return;
    }
    listEl.innerHTML = "";
    rows.forEach((inst) => {
      const btn = el("button", "mover-row");
      btn.type = "button";
      btn.dataset.symbol = inst.symbol;
      const name = el("span", "mover-name");
      name.append(el("strong", "", inst.name), el("small", "tickr", inst.symbol.replace(".SN", "")));
      const spark = el("span", "mover-spark");
      btn.append(
        name,
        spark,
        el("span", "mover-price", fmtPrice(inst.price)),
        el("span", `change ${changeClass(inst.daily_change_pct)}`, fmtChange(inst.daily_change_pct)),
      );
      const li = el("li");
      li.appendChild(btn);
      listEl.appendChild(li);
      loadSparkline(inst.symbol, spark);
    });
  }

  function newsItem(article) {
    const li = el("li", "news-item");
    const link = el("a", "news-title", article.title);
    link.href = article.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    li.append(link, el("span", "news-meta", [article.source, timeAgo(article.published)].filter(Boolean).join(" · ")));
    return li;
  }

  async function fetchNews(symbol) {
    const url = symbol
      ? `${window.APP_ENDPOINTS.news}?symbol=${encodeURIComponent(symbol)}`
      : window.APP_ENDPOINTS.news;
    const response = await fetch(url);
    if (!response.ok) throw new Error("news");
    return (await response.json()).items || [];
  }

  async function renderMarketNews() {
    const listEl = document.getElementById("news-market");
    if (!listEl) return;
    try {
      const items = (await fetchNews()).slice(0, 4);
      if (!items.length) return fillMessage(listEl, "Sin noticias recientes del mercado.");
      listEl.innerHTML = "";
      items.forEach((a) => listEl.appendChild(newsItem(a)));
    } catch (err) {
      fillMessage(listEl, "No fue posible cargar las noticias.");
    }
  }

  async function renderMoverNews(movers) {
    const listEl = document.getElementById("news-movers");
    if (!listEl) return;
    const insts = [...movers.up, ...movers.down];
    if (!insts.length) return fillMessage(listEl, "Sin movimientos para mostrar hoy.");

    const results = await Promise.all(insts.map((inst) => fetchNews(inst.symbol).catch(() => null)));
    if (results.every((r) => r === null)) return fillMessage(listEl, "No fue posible cargar las noticias.");

    listEl.innerHTML = "";
    insts.forEach((inst, idx) => {
      const li = el("li", "news-item mover-news");
      const head = el("button", "mover-news-head");
      head.type = "button";
      head.dataset.symbol = inst.symbol;
      const arrow = inst.daily_change_pct > 0 ? "▲" : "▼";
      head.append(
        el("strong", "", inst.name),
        el("span", `change ${changeClass(inst.daily_change_pct)}`, `${arrow} ${fmtChange(inst.daily_change_pct)}`),
      );
      li.appendChild(head);
      const article = (results[idx] || [])[0];
      if (article) {
        const inner = newsItem(article);
        li.append(...inner.childNodes);
      } else {
        li.appendChild(el("span", "news-meta", "Sin noticias recientes."));
      }
      listEl.appendChild(li);
    });
  }

  function renderLanding(errorMsg) {
    const upEl = document.getElementById("movers-up");
    const downEl = document.getElementById("movers-down");
    if (!upEl || !downEl) return;
    if (errorMsg) {
      fillMessage(upEl, errorMsg);
      fillMessage(downEl, errorMsg);
      renderMoverNews({ up: [], down: [] });
      return;
    }
    const movers = topMovers();
    renderMoverList(upEl, movers.up);
    renderMoverList(downEl, movers.down);
    renderMoverNews(movers);
  }

  const landingDate = document.getElementById("landing-date");
  if (landingDate) {
    const today = new Date().toLocaleDateString("es-CL", { weekday: "long", day: "numeric", month: "long" });
    landingDate.textContent = today.charAt(0).toUpperCase() + today.slice(1);
  }
  renderMarketNews();

  // Clic en una fila de alzas/bajas o en un chip de "Sigue donde quedaste".
  emptyState.addEventListener("click", (event) => {
    const target = event.target.closest("[data-symbol]");
    if (!target) return;
    const symbol = target.dataset.symbol;
    const inst = catalog.find((i) => i.symbol === symbol);
    if (inst) selectInstrument(inst);
    else lookupSymbol(symbol);
  });

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
        fontFamily: "IBM Plex Sans, -apple-system, sans-serif",
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
      crosshair: { mode: 1, horzLine: { labelBackgroundColor: "#374151" } },
      localization: { locale: "es-CL" },
    });

    createPriceSeries(selectedChartType);

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

  const CHART_TYPE_ICONS = {
    candlestick: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><line x1="3.5" y1="1.5" x2="3.5" y2="13.5"/><rect x="1.5" y="4.5" width="4" height="5"/><line x1="7.5" y1="2.5" x2="7.5" y2="12.5"/><rect x="5.5" y="6" width="4" height="4.5"/><line x1="11.5" y1="3" x2="11.5" y2="12"/><rect x="9.5" y="5" width="4" height="3.5"/></svg>',
    line: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1,12 4.5,6.5 8,9.5 11.5,4 14,6"/></svg>',
    area: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1,11 4.5,6 8,8.5 11.5,3.5 14,5.5"/><path d="M1,11 L4.5,6 L8,8.5 L11.5,3.5 L14,5.5 L14,14 L1,14 Z" fill="currentColor" opacity="0.2" stroke="none"/></svg>',
  };

  function createPriceSeries(type) {
    if (candleSeries) chartInstance.removeSeries(candleSeries);

    const iconBtn = document.getElementById("ctrl-charttype-btn");
    if (iconBtn) iconBtn.innerHTML = `${TYPE_LABELS[type] || "Velas"} <span class="ctrl-chevron">▾</span>`;

    if (type === "line") {
      candleSeries = chartInstance.addLineSeries({
        color: "#26a69a",
        lineWidth: 2,
        priceLineVisible: true,
        priceLineStyle: 2,
        priceLineColor: "#26a69a",
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: "#26a69a",
        crosshairMarkerBackgroundColor: "#26a69a",
      });
    } else if (type === "area") {
      candleSeries = chartInstance.addAreaSeries({
        lineColor: "#26a69a",
        topColor: "rgba(38,166,154,0.28)",
        bottomColor: "rgba(38,166,154,0.02)",
        lineWidth: 2,
        priceLineVisible: true,
        priceLineStyle: 2,
        priceLineColor: "#26a69a",
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: "#26a69a",
        crosshairMarkerBackgroundColor: "#26a69a",
      });
    } else {
      candleSeries = chartInstance.addCandlestickSeries({
        upColor: "#26a69a",
        downColor: "#ef5350",
        borderVisible: false,
        wickUpColor: "#26a69a",
        wickDownColor: "#ef5350",
        priceLineVisible: true,
        priceLineStyle: 2,
        priceLineColor: "#26a69a",
        lastValueVisible: true,
      });
    }
  }

  // Config comun de subgraficos: mismos margenes, mismo look. Ancho minimo
  // del eje de precio alineado con el chart principal para que las tres
  // "panes" queden con el borde derecho perfectamente en columna, como TV.
  const PRICE_SCALE_MIN_WIDTH = 68;
  const SUB_CHART_OPTIONS = {
    autoSize: true,
    layout: { background: { type: "solid", color: "#131a24" }, textColor: "#e6edf3", fontSize: 11, fontFamily: "IBM Plex Sans, -apple-system, sans-serif", attributionLogo: false },
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
  let _activePriceLineColor = "#26a69a"; // color actual de la línea estática de precio (evita applyOptions redundantes)
  let _crosshairLabelBg = "#374151";     // color actual de la etiqueta del crosshair en el eje Y

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

    // Actualiza colores según la vela bajo el cursor (solo desde el chart principal).
    if (sourceId === "main" && candleSeries && chartInstance && lastChartSeries) {
      let candleColor;   // color de la vela bajo el cursor (o gris si no hay vela)
      let restoreColor;  // color de la última vela (para restaurar al salir)

      const n = lastChartSeries.dates.length - 1;
      const lastO = lastChartSeries.open?.[n];
      const lastC = lastChartSeries.close?.[n];
      restoreColor = (lastO != null && lastC != null) ? (lastC >= lastO ? "#26a69a" : "#ef5350") : "#26a69a";

      if (!t) {
        // Cursor fuera del chart: vuelve al color de la última vela.
        candleColor = restoreColor;
      } else {
        const barIdx = lastChartSeries.dates.indexOf(t);
        if (barIdx >= 0) {
          const o = lastChartSeries.open?.[barIdx];
          const c = lastChartSeries.close?.[barIdx];
          candleColor = (o != null && c != null) ? (c >= o ? "#26a69a" : "#ef5350") : "#64748b";
        } else {
          candleColor = "#64748b"; // entre velas: gris
        }
      }

      // 1) Línea estática de último precio: refleja la vela bajo el cursor.
      if (candleColor !== _activePriceLineColor) {
        _activePriceLineColor = candleColor;
        candleSeries.applyOptions({ priceLineColor: candleColor });
      }

      // 2) Etiqueta del crosshair en el eje Y: gris en espacio vacío,
      //    color de vela cuando el cursor cruza una barra concreta.
      const labelBg = (t && lastChartSeries.dates.indexOf(t) >= 0) ? candleColor : "#374151";
      if (labelBg !== _crosshairLabelBg) {
        _crosshairLabelBg = labelBg;
        chartInstance.applyOptions({ crosshair: { horzLine: { labelBackgroundColor: labelBg } } });
      }
    }
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

    if (selectedChartType === "line" || selectedChartType === "area") {
      const closeLine = dates
        .map((d, i) => (series.close[i] != null ? { time: d, value: series.close[i] } : null))
        .filter(Boolean);
      candleSeries.setData(closeLine);
    } else {
      candleSeries.setData(candles);
    }

    // Línea de precio actual: color según dirección de la última vela (cierre vs apertura).
    const _lastCandle = candles[candles.length - 1];
    const _priceLineColor = _lastCandle
      ? (_lastCandle.close >= _lastCandle.open ? "#26a69a" : "#ef5350")
      : "#26a69a";
    _activePriceLineColor = _priceLineColor;
    candleSeries.applyOptions({ priceLineColor: _priceLineColor, priceLineStyle: 2 });

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

  // Badge de sentimiento FinBERT (RF-04.1): aparece bajo la explicación
  // cuando el modelo está activo y devuelve una señal. Si finbert_signal es
  // null (modelo no disponible o USE_FINBERT=false), no se renderiza nada.
  function renderFinbertBadge(signal) {
    if (!signal) return "";
    const map = {
      positive: ["Positivo", "#22c55e"],
      negative: ["Negativo", "#ef4444"],
      neutral:  ["Neutral",  "#94a3b8"],
    };
    const [label, color] = map[signal.label] || ["Desconocido", "#94a3b8"];
    const pct = Math.round(signal.score * 100);
    const tooltip = "FinBERT clasifica si la señal del indicador tiene connotación positiva, negativa o neutral según análisis de texto financiero especializado (RF-04.1).";
    return `<span class="finbert-badge" title="${tooltip}" style="background:${color}20;color:${color};border:1px solid ${color}40;border-radius:4px;padding:2px 8px;font-size:0.72rem;margin-top:5px;display:inline-block;letter-spacing:0.02em;cursor:help;">Análisis NLP: ${label} (${pct}%)</span>`;
  }

  // Badge principal: la senal oficial de RF-04.2 por indicador.
  //   RSI  y Bollinger  -> sobrecomprado / sobrevendido / neutral
  //   MACD y Medias mov -> alcista / bajista
  // Backend ya calcula `signal` (RSI, Bollinger) y `trend` (MACD, MAs).
  function signalBadge(indicatorKey, data) {
    if (indicatorKey === "medias_moviles" || indicatorKey === "macd") {
      const trend = data.trend === "bajista" ? "bajista" : "alcista";
      const arrow = trend === "bajista" ? "▼" : "▲";
      const label = trend === "bajista" ? "en baja" : "en alza";
      return { cls: trend, text: `${arrow} ${label}` };
    }
    if (indicatorKey === "rsi") {
      const sig = data.signal || "neutral"; // sobrecomprado | sobrevendido | neutral
      const arrow = sig === "sobrecomprado" ? "▲" : sig === "sobrevendido" ? "▼" : "●";
      return { cls: sig, text: `${arrow} ${sig}` };
    }
    if (indicatorKey === "bandas_bollinger") {
      // Backend puede devolver: sobrecomprado / sobrevendido / cercano_al_extremo / normal
      const sig = data.signal || "normal";
      const label = sig === "cercano_al_extremo" ? "cerca extremo" : sig;
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
    if (indicatorKey === "medias_moviles") return data.trend === "bajista" ? "En baja" : "En alza";
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

    // La card solo muestra valor + badges + boton; la explicacion se muestra
    // en el panel de debajo (ver renderPanel). La trazabilidad de RF-02.2
    // (fuente, fecha, indicador literal) vive en el Historial del perfil.
    card.innerHTML = `
      <div class="indicator-card-header">
        <span class="indicator-title">${meta.title}</span>
        <div class="badge-row">
          <span class="badge ${signal.cls}">${signal.text}</span>
          ${risk ? `<span class="badge badge-risk ${risk.cls}">${risk.text}</span>` : ""}
        </div>
      </div>
      <div class="indicator-value">${formatIndicatorValue(meta.key, data)}</div>
      <div class="indicator-sub">${meta.sub}</div>
      <button type="button" class="explain-cta" aria-controls="explain-panel" aria-expanded="false"></button>
    `;

    card.querySelector(".explain-cta").addEventListener("click", () => selectIndicator(meta));
    updateCardButtons();
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
  // corre FinBERT, valida coherencia y persiste un `QueryLog`.
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
    return data;
  }

  // ---- Panel de explicacion (debajo de las cards) ----
  // Las cards solo muestran valor + badges + boton. La explicacion, la escala
  // visual y las acciones viven en un unico panel ancho que cambia segun el
  // indicador activo (`activeKey`). Pedir la explicacion de un indicador ya
  // visto reabre el panel sin escribir otra fila en `query_logs`.
  function ctaLabel(key) {
    if (activeKey === key) return "Viendo explicación";
    const known = lastIndicatorData[key];
    return known && known.explanation ? "Ver explicación" : "Ver explicación en simple";
  }

  function updateCardButtons() {
    document.querySelectorAll(".indicator-card").forEach((card) => {
      const key = card.dataset.indicator;
      const on = key === activeKey;
      card.classList.toggle("is-active", on);
      const btn = card.querySelector(".explain-cta");
      if (!btn) return;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-expanded", on ? "true" : "false");
      btn.textContent = ctaLabel(key);
    });
  }

  // Escala visual del valor (solo RSI y %B, que tienen un rango con zonas).
  // En el nivel basico no se muestran numeros de umbral ni jerga.
  function scaleSpec(key, data, level) {
    const v = Number(data.value);
    if (!Number.isFinite(v)) return null;
    const plain = level === "basico";
    const plainZones = ["Zona baja", "Zona normal", "Zona alta"];
    if (key === "rsi") {
      return {
        label: "RSI", v, min: 0, max: 100, lo: 30, hi: 70,
        ticks: plain ? [] : [0, 30, 70, 100],
        zones: plain ? plainZones : ["Sobreventa", "Neutral", "Sobrecompra"],
      };
    }
    if (key === "bandas_bollinger") {
      return {
        label: "%B", v, min: -0.25, max: 1.25, lo: 0, hi: 1,
        ticks: plain ? [] : [0, 1],
        zones: plain ? plainZones : ["Bajo la banda", "Dentro de las bandas", "Sobre la banda"],
      };
    }
    return null;
  }

  function renderScale(key, data, level) {
    const spec = scaleSpec(key, data, level);
    if (!spec) return "";
    const span = spec.max - spec.min;
    const pct = (x) => Math.min(100, Math.max(0, ((x - spec.min) / span) * 100));
    const loP = pct(spec.lo);
    const hiP = pct(spec.hi);
    const zone = spec.v < spec.lo ? 0 : spec.v > spec.hi ? 2 : 1;
    const ticks = spec.ticks
      .map((t) => `<span style="left:${pct(t).toFixed(2)}%">${t}</span>`)
      .join("");
    const legend = spec.zones
      .map((z, i) => `<span class="z z${i}${i === zone ? " current" : ""}">${z}</span>`)
      .join("");
    return `
      <div class="scale" role="img" aria-label="${spec.label} en ${spec.v}: ${spec.zones[zone]}">
        <div class="scale-track">
          <span class="scale-zone low" style="width:${loP.toFixed(2)}%"></span>
          <span class="scale-zone mid" style="width:${(hiP - loP).toFixed(2)}%"></span>
          <span class="scale-zone high" style="width:${(100 - hiP).toFixed(2)}%"></span>
          <span class="scale-marker" style="left:${pct(spec.v).toFixed(2)}%" title="${spec.label} ${spec.v}"></span>
        </div>
        ${ticks ? `<div class="scale-ticks">${ticks}</div>` : ""}
        <div class="scale-legend">${legend}</div>
      </div>`;
  }

  function revealPanel() {
    explainPanel.classList.remove("hidden");
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() => {
      explainPanel.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
    });
  }

  function panelTitle(meta) {
    const name = (current && (current.name || current.symbol.replace(".SN", ""))) || "";
    return `${meta.title} · ${name}`;
  }

  function showPanelLoading(meta) {
    explainPanel.classList.remove("is-loading");
    explainPanel.innerHTML = `
      <div class="explain-panel-head">
        <div class="explain-panel-title">
          <span class="badge-label">EXPLICACIÓN EN SIMPLE</span>
          <h3 class="explain-panel-name"></h3>
        </div>
      </div>
      <div class="loading"><span class="spinner"></span> Generando explicación…</div>`;
    explainPanel.querySelector(".explain-panel-name").textContent = panelTitle(meta);
  }

  function renderPanel(meta, data) {
    const level = data.detail_level || "intermedio";
    const signal = signalBadge(meta.key, data);
    const risk = riskBadge(data);
    const levelName = LEVEL_NAMES[level] || level;
    explainPanel.classList.remove("is-loading");
    explainPanel.innerHTML = `
      <div class="explain-panel-head">
        <div class="explain-panel-title">
          <span class="badge-label">EXPLICACIÓN EN SIMPLE</span>
          <h3 class="explain-panel-name"></h3>
        </div>
        <div class="badge-row">
          <span class="badge ${signal.cls}">${signal.text}</span>
          ${risk ? `<span class="badge badge-risk ${risk.cls}">${risk.text}</span>` : ""}
        </div>
        <a class="detail-tag ${level}" href="${window.APP_ENDPOINTS.profile}" title="Cambiar mi nivel en Mi perfil">Nivel ${levelName}</a>
        <button type="button" class="panel-close" aria-label="Cerrar explicación">×</button>
      </div>
      <p class="explain-text"></p>
      ${renderScale(meta.key, data, level)}
      <div class="explain-meta">
        ${renderFinbertBadge(data.finbert_signal)}
        ${data.coherent === false ? '<span class="warn">Marcado para revisión de coherencia.</span>' : ""}
      </div>
      <div class="explain-actions">
        <button type="button" class="link-btn regen-btn">No entendí esto</button>
        <button type="button" class="link-btn done-btn">Entendido</button>
      </div>`;
    explainPanel.querySelector(".explain-panel-name").textContent = panelTitle(meta);
    explainPanel.querySelector(".explain-text").textContent = data.explanation;
    explainPanel.querySelector(".regen-btn").addEventListener("click", () => regenerateCard(meta));
    explainPanel.querySelector(".done-btn").addEventListener("click", closePanel);
    explainPanel.querySelector(".panel-close").addEventListener("click", closePanel);
  }

  function closePanel() {
    const key = activeKey;
    activeKey = null;
    explainPanel.classList.add("hidden");
    explainPanel.classList.remove("is-loading");
    explainPanel.innerHTML = "";
    updateCardButtons();
    const btn = key && document.querySelector(`.indicator-card[data-indicator="${key}"] .explain-cta`);
    if (btn) btn.focus({ preventScroll: true });
  }

  // Handler del boton de la card: abre el panel de ese indicador (o lo cierra
  // si ya era el activo). Solo la primera vez pide /api/query, que es la unica
  // llamada que escribe log; despues reutiliza la explicacion ya cargada.
  async function selectIndicator(meta) {
    if (!current) return;
    if (activeKey === meta.key) {
      closePanel();
      return;
    }
    indicatorsError.classList.add("hidden");
    activeKey = meta.key;
    updateCardButtons();

    const known = lastIndicatorData[meta.key];
    if (known && known.explanation) {
      renderPanel(meta, known);
      revealPanel();
      return;
    }

    const state = cardState[meta.key];
    const card = document.querySelector(`.indicator-card[data-indicator="${meta.key}"]`);
    showPanelLoading(meta);
    revealPanel();
    if (card) card.classList.add("card-loading");

    try {
      const data = await fetchExplanation(current.symbol, meta.key, state.days, 0);
      if (cardState[meta.key] !== state) return; // se cargo otro instrumento/periodo
      // El servidor puede partir en la redaccion preferida del usuario (RF-13.2):
      // el contador local debe seguirla para que "No entendí esto" rote desde ahi.
      state.variant = data.variant || 0;
      lastIndicatorData[meta.key] = data;
      composeSummary();
      if (activeKey === meta.key) renderPanel(meta, data);
      updateCardButtons();
    } catch (err) {
      if (cardState[meta.key] === state) {
        if (activeKey === meta.key) closePanel();
        indicatorsError.textContent = err.message;
        indicatorsError.classList.remove("hidden");
      }
    } finally {
      if (card) card.classList.remove("card-loading");
    }
  }

  async function regenerateCard(meta) {
    if (!current) return;
    const state = cardState[meta.key];
    state.variant += 1;
    explainPanel.classList.add("is-loading");

    try {
      const data = await fetchExplanation(current.symbol, meta.key, state.days, state.variant);
      if (cardState[meta.key] !== state) return;
      lastIndicatorData[meta.key] = data;
      composeSummary();
      if (activeKey === meta.key) {
        renderPanel(meta, data);
        const regen = explainPanel.querySelector(".regen-btn");
        if (regen) regen.focus({ preventScroll: true });
      }
    } catch (err) {
      state.variant -= 1;
      indicatorsError.textContent = err.message;
      indicatorsError.classList.remove("hidden");
    } finally {
      explainPanel.classList.remove("is-loading");
    }
  }

  const lastIndicatorData = {};

  function composeSummary() {
    const trend = lastIndicatorData.medias_moviles;
    const rsi = lastIndicatorData.rsi;
    const macd = lastIndicatorData.macd;
    const bb = lastIndicatorData.bandas_bollinger;

    if (!trend || !rsi || !macd || !bb || !current) return;

    const name = current.name || current.symbol.replace(".SN", "");
    const kind = (current.type || "Acción").toLowerCase();
    const sector = current.sector && current.sector !== "Ticker personalizado"
      ? ` del sector ${current.sector}`
      : "";

    // Cuantas senales apuntan al alza: medias moviles y MACD por tendencia;
    // RSI y Bollinger por su zona (sobrevendido = posible rebote, sobrecomprado = posible freno).
    const alza = [trend.trend, macd.trend].filter((t) => t !== "bajista").length;
    const extremos = [rsi.signal, bb.signal].filter(
      (s) => s === "sobrecomprado" || s === "sobrevendido"
    );
    let lectura;
    if (alza === 2) lectura = "Hoy sus señales de tendencia apuntan al alza";
    else if (alza === 0) lectura = "Hoy sus señales de tendencia apuntan a la baja";
    else lectura = "Hoy sus señales de tendencia están divididas";
    if (extremos.length === 0) {
      lectura += " y el precio se mueve en una zona normal.";
    } else {
      const zona = extremos.includes("sobrecomprado") && extremos.includes("sobrevendido")
        ? "con señales de extremo en direcciones opuestas"
        : extremos[0] === "sobrecomprado"
        ? "y el precio está en una zona alta, donde suele haber más riesgo de retroceso"
        : "y el precio está en una zona baja, donde a veces aparece un rebote";
      lectura += lectura.endsWith("divididas") ? `, ${zona}.` : ` ${zona}.`;
    }
    const parts = [
      `${name} es una ${kind}${sector} que se transa en la Bolsa de Santiago.`,
      lectura,
      "Abre cada indicador para ver qué significa en simple.",
    ];
    summaryText.textContent = parts.join(" ");
  }

  async function loadIndicators(symbol, days) {
    indicatorsError.classList.add("hidden");
    indicatorsLoading.classList.remove("hidden");
    summaryLoading.classList.remove("hidden");
    indicatorGrid.innerHTML = "";
    summaryText.textContent = "";
    activeKey = null;
    explainPanel.classList.add("hidden");
    explainPanel.innerHTML = "";
    Object.keys(lastIndicatorData).forEach((k) => delete lastIndicatorData[k]);

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
    viewSector.textContent = `${inst.symbol.replace(".SN", "")} · ${inst.sector || inst.type}`;
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
  // Sistema de dropdowns: abre al hacer click en .ctrl-btn, cierra al hacer
  // click fuera o al seleccionar una opcion.
  document.querySelectorAll(".ctrl-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const wrap = btn.closest(".ctrl-wrap");
      const isOpen = wrap.classList.contains("open");
      document.querySelectorAll(".ctrl-wrap").forEach((w) => {
        w.classList.remove("open");
        w.querySelector(".ctrl-btn")?.setAttribute("aria-expanded", "false");
      });
      if (!isOpen) {
        wrap.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });
  document.addEventListener("click", () => {
    document.querySelectorAll(".ctrl-wrap").forEach((w) => {
      w.classList.remove("open");
      w.querySelector(".ctrl-btn")?.setAttribute("aria-expanded", "false");
    });
  });

  // Intervalo de vela desde el dropdown
  document.querySelectorAll("[data-interval]").forEach((item) => {
    item.addEventListener("click", () => {
      const interval = item.dataset.interval;
      if (interval === selectedInterval) {
        document.getElementById("ctrl-interval")?.classList.remove("open");
        return;
      }
      selectedInterval = interval;
      document.querySelectorAll("[data-interval]").forEach((i) => i.classList.toggle("active", i === item));
      const ibtn = document.getElementById("ctrl-interval-btn");
      if (ibtn) ibtn.innerHTML = `${INTERVAL_LABELS[interval] || interval} <span class="ctrl-chevron">▾</span>`;
      document.getElementById("ctrl-interval")?.classList.remove("open");
      if (current) loadChart(current.symbol, selectedDays);
    });
  });

  // Tipo de gráfico desde el dropdown
  document.querySelectorAll("[data-chart-type]").forEach((item) => {
    item.addEventListener("click", () => {
      const type = item.dataset.chartType;
      if (type === selectedChartType) {
        document.getElementById("ctrl-charttype")?.classList.remove("open");
        return;
      }
      selectedChartType = type;
      document.querySelectorAll("[data-chart-type]").forEach((i) => i.classList.toggle("active", i === item));
      document.getElementById("ctrl-charttype")?.classList.remove("open");
      if (chartInstance && lastChartSeries) {
        createPriceSeries(type);
        renderChart(lastChartSeries);
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

