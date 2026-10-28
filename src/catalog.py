"""Catalogo de instrumentos (los constituyentes del IPSA, `data/instruments.json`)."""

import json
import os

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "instruments.json"
)

try:
    with open(_DATA_PATH, encoding="utf-8") as f:
        INSTRUMENTS = json.load(f)
except FileNotFoundError:
    INSTRUMENTS = []


def resolve_display_name(symbol: str) -> str:
    """Nombre de empresa para el ticker dado, o el ticker limpio como fallback."""
    return next(
        (inst["name"] for inst in INSTRUMENTS if inst["symbol"] == symbol),
        symbol.replace(".SN", ""),
    )
