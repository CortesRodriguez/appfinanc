"""Verifica en Yahoo Finance cuales tickers del catalogo (data/instruments.json)
realmente devuelven datos. Correr localmente (con internet real):

    python scripts/validate_tickers.py

Imprime un resumen de tickers OK y tickers que fallan, para poder depurar
el catalogo manualmente si alguno quedo mal escrito o fue deslistado.
"""

import json
import os
import sys

import yfinance as yf

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "instruments.json")


def main():
    with open(_DATA_PATH, encoding="utf-8") as f:
        instruments = json.load(f)

    ok, failed = [], []
    for inst in instruments:
        symbol = inst["symbol"]
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist is None or hist.empty:
                failed.append(symbol)
            else:
                ok.append(symbol)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{symbol} ({exc})")

    print(f"OK ({len(ok)}): {', '.join(ok)}")
    print(f"FALLAN ({len(failed)}): {', '.join(failed) if failed else 'ninguno'}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
