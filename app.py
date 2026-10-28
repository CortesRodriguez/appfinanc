"""Punto de entrada de la aplicacion (Vista de Desarrollo / Capa de Presentacion)."""

import logging
import os
import warnings

from src.web import create_app

# Ruido de dependencias de terceros: yfinance 1.7 usa `inplace=` de pandas 3.x,
# que emite Pandas4Warning en cada consulta. No afecta resultados.
warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*inplace keyword.*")

app = create_app()

if __name__ == "__main__":
    # Oculta el log de peticiones "GET ... 200" (werkzeug). Los errores siguen visibles.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5001)
