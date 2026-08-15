"""CLI de prueba del Modulo Extractor (Sprint 5).

Uso:
    python main.py --listar-tickers
    python main.py --ticker CHILE.SN --rango "3 meses"
    python main.py --macro

Como el Modulo Procesador NLP (Sprint 6) y el Presentador (Sprint 7)
aun no existen segun el cronograma, este runner ejerce el Extractor
end-to-end contra Yahoo Finance y mindicador.cl y muestra el bundle
`IndicadorNormalizado` por consola en formato JSON. Ese bundle es el
contrato que consumira el proximo sprint.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import is_dataclass

from extractor import (
    BancoCentralExtractor,
    IPSA_TICKERS,
    RANGOS_TEMPORALES,
    YahooExtractor,
)
from extractor.alpha_vantage_extractor import (
    AlphaVantageExtractor,
    AlphaVantageNoConfiguradoError,
)


def _serializar(obj):
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if is_dataclass(obj):
        from dataclasses import asdict

        return asdict(obj)
    raise TypeError(f"No se puede serializar {type(obj).__name__}")


def _configurar_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )


def _listar_tickers() -> None:
    print("Empresas del IPSA disponibles (RF-01.1):")
    for ticker, nombre in IPSA_TICKERS.items():
        print(f"  {ticker:<18} {nombre}")
    print("\nRangos temporales (RF-01.1):", ", ".join(RANGOS_TEMPORALES))


def _extraer_instrumento(ticker: str, rango: str, usar_alpha: bool) -> None:
    if usar_alpha:
        try:
            extractor = AlphaVantageExtractor()
            resultado = extractor.extraer(ticker, rango)
        except AlphaVantageNoConfiguradoError as exc:
            print(f"[!] {exc}", file=sys.stderr)
            print("[i] Cayendo a Yahoo Finance como fuente primaria.")
            resultado = YahooExtractor().extraer(ticker, rango)
    else:
        resultado = YahooExtractor().extraer(ticker, rango)

    print(json.dumps(resultado, default=_serializar, indent=2, ensure_ascii=False))


def _extraer_macro() -> None:
    bundle = BancoCentralExtractor().extraer()
    print(json.dumps(bundle, default=_serializar, indent=2, ensure_ascii=False))


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 5 - Modulo Extractor. Prototipo CLI para ejercitar la "
            "extraccion, validacion y normalizacion de indicadores."
        ),
    )
    parser.add_argument("--listar-tickers", action="store_true", help="Muestra las 30 empresas del IPSA disponibles.")
    parser.add_argument("--ticker", help="Ticker Yahoo Finance de la empresa a consultar.")
    parser.add_argument(
        "--rango",
        choices=list(RANGOS_TEMPORALES),
        default="3 meses",
        help="Rango temporal de la consulta (default: 3 meses).",
    )
    parser.add_argument(
        "--alpha-vantage",
        action="store_true",
        help="Usa Alpha Vantage como fuente primaria (requiere ALPHA_VANTAGE_API_KEY).",
    )
    parser.add_argument("--macro", action="store_true", help="Consulta los indicadores del Banco Central.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logging en modo debug.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _construir_parser()
    args = parser.parse_args(argv)
    _configurar_logging(args.verbose)

    if args.listar_tickers:
        _listar_tickers()
        return 0

    hizo_algo = False
    if args.ticker:
        _extraer_instrumento(args.ticker, args.rango, args.alpha_vantage)
        hizo_algo = True

    if args.macro:
        _extraer_macro()
        hizo_algo = True

    if not hizo_algo:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
