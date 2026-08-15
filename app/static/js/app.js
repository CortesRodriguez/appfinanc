// Cinta de precios (RF-07.3, RF-07.4) + spinner (RF-08.3)

(function () {
    const track = document.getElementById("cinta-track");
    const spinner = document.getElementById("spinner");
    const form = document.getElementById("form-consulta");

    function actualizarCinta() {
        fetch("/cinta")
            .then((r) => r.json())
            .then((data) => {
                if (!track) return;
                if (data.error) {
                    track.textContent = data.mensaje;
                    return;
                }
                const macro = data.macro || {};
                const items = [];
                const orden = ["ipsa", "uf", "dolar", "tpm", "ipc"];
                orden.forEach((k) => {
                    if (k === "ipsa") {
                        items.push(`<span class="cinta__item">IPSA (proximamente)</span>`);
                    } else if (macro[k] !== undefined) {
                        items.push(`<span class="cinta__item">${k.toUpperCase()}: ${macro[k]}</span>`);
                    }
                });
                items.push(`<span class="cinta__item">— actualizado ${data.fecha}</span>`);
                track.innerHTML = items.join(" · ");
            })
            .catch(() => {
                if (track) track.textContent = "Cinta no disponible temporalmente.";
            });
    }

    if (form && spinner) {
        form.addEventListener("submit", () => {
            spinner.hidden = false;
        });
    }

    actualizarCinta();
    setInterval(actualizarCinta, 60 * 1000);
})();
