// Cinta de precios estilo bolsa de valores: IPSA, UF, dólar, TPM, IPC y las
// acciones del catálogo, desplazándose en loop continuo (RF-01, CU-01).

(function initTickerTape() {
  const track = document.getElementById("ticker-track");
  if (!track) return;

  const REFRESH_MS = 5 * 60 * 1000; // igual al cache del backend (RNF-02.2)

  function fmtValue(item) {
    if (item.value === null || item.value === undefined) return "—";
    const formatted = item.value.toLocaleString("es-CL", { maximumFractionDigits: 2 });
    return item.unit === "$" ? `$${formatted}` : item.unit === "%" ? `${formatted}%` : formatted;
  }

  function fmtChange(pct) {
    if (pct === null || pct === undefined) return "";
    const arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "";
    const cls = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
    return `<span class="ticker-change ${cls}">${arrow} ${Math.abs(pct).toFixed(2)}%</span>`;
  }

  function renderItem(item) {
    return `
      <span class="ticker-item ${item.kind}">
        <strong>${item.label}</strong>
        <span class="ticker-value">${fmtValue(item)}</span>
        ${fmtChange(item.daily_change_pct)}
      </span>
    `;
  }

  async function loadTicker() {
    try {
      const response = await fetch(window.APP_TICKER_ENDPOINT);
      const items = await response.json();
      if (!Array.isArray(items) || items.length === 0) return;

      // Se duplica el contenido para que el loop de -50% quede perfectamente
      // continuo (el navegador nunca ve un salto/corte en la cinta).
      const html = items.map(renderItem).join("");
      track.innerHTML = html + html;

      const timestamp = new Date().toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
      track.title = `Actualizado a las ${timestamp}`;
    } catch (err) {
      track.innerHTML = '<span class="ticker-item">No fue posible cargar la cinta de precios.</span>';
    }
  }

  loadTicker();
  setInterval(loadTicker, REFRESH_MS);
})();
