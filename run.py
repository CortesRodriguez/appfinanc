"""Entry point de la app Flask (Sprint 7-9).

Uso:
    python run.py                # arranca en http://127.0.0.1:5000
    FLASK_DEBUG=1 python run.py  # con auto-reload
"""

from __future__ import annotations

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=debug)
