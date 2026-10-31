"""Noticias del mercado y de las empresas del catalogo (extension del Extractor).

Fuente: Google News RSS (sin API key). `yfinance` no entrega noticias para
las acciones .SN, y los RSS directos de los medios chilenos no son estables.
No es una API oficial: ante cualquier falla se devuelve lista vacia y el
dashboard muestra el estado vacio, sin romper la portada (RNF-08).

El texto de busqueda sale siempre del catalogo (`aliases` en
data/instruments.json), nunca de lo que escribe el usuario.
"""

import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import requests

from .cache import TTLCache

NEWS_URL = "https://news.google.com/rss/search?q={query}&hl=es-419&gl=CL&ceid=CL:es-419"
MARKET_QUERY = 'IPSA OR "bolsa de Santiago" when:2d'
REQUEST_TIMEOUT = 8
MAX_FEED_BYTES = 2 * 1024 * 1024
# La busqueda por empresa exige contexto financiero: sin esto "Concha y Toro"
# trae noticias de la avenida y "Copec" las del rally.
BUSINESS_TERMS = (
    "acciones OR bolsa OR utilidades OR resultados OR ganancias OR inversión OR "
    "millones OR deuda OR bonos OR ventas OR dividendo OR compra OR adquisición OR empresa"
)
# Fichas automaticas de cotizacion ("... – GETTEX:B7E", "ADR – FWB:355"): no son noticias.
_QUOTE_PAGE = re.compile(r"[–-]\s*[A-Z]{2,}:[A-Z0-9.]+\s*$")
# Portales de cotizaciones/fichas: generan paginas automaticas, no noticias.
BLOCKED_SOURCES = {"tradingview", "yahoo", "traders union", "marketscreener", "investing.com"}
# Se piden mas titulares de los que se muestran porque el filtro de relevancia
# por empresa descarta los que no la nombran.
FETCH_LIMIT = 20

news_cache = TTLCache(ttl_seconds=20 * 60)


class NewsSourceError(Exception):
    """La fuente de noticias no respondio o devolvio algo ilegible."""


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _source_name(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith(("http://", "https://")):
        return urlparse(raw).netloc.removeprefix("www.")
    return raw


def fetch_news(query: str, limit: int = FETCH_LIMIT):
    """Titulares de Google News para `query`: [{title, source, url, published}], mas recientes primero.

    Lanza NewsSourceError si la fuente falla; solo se aceptan enlaces http(s).
    """
    try:
        response = requests.get(
            NEWS_URL.format(query=quote(query)),
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        if len(response.content) > MAX_FEED_BYTES:
            raise NewsSourceError("Respuesta de noticias demasiado grande.")
        root = ET.fromstring(response.content)
    except NewsSourceError:
        raise
    except (requests.RequestException, ET.ParseError) as exc:
        raise NewsSourceError(str(exc)) from exc

    items, seen = [], set()
    for node in root.findall(".//item"):
        link = (node.findtext("link") or "").strip()
        title = (node.findtext("title") or "").strip()
        if not title or urlparse(link).scheme not in ("http", "https"):
            continue
        source = _source_name(node.findtext("source"))
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()
        if _QUOTE_PAGE.search(title) or _normalize(source) in BLOCKED_SOURCES:
            continue
        key = _normalize(title)
        if key in seen:
            continue
        seen.add(key)
        try:
            published = parsedate_to_datetime(node.findtext("pubDate")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        items.append(
            {"title": title, "source": source, "url": link, "published": published.isoformat()}
        )

    items.sort(key=lambda i: i["published"], reverse=True)
    return items[:limit]


def mentions(title: str, terms) -> bool:
    """True si el titular nombra alguno de los terminos como palabra completa.

    Ignora tildes y mayusculas, salvo en siglas (CAP, CCU, SMU): esas deben
    aparecer en mayusculas, para no confundir CAP con "Blue Cap".
    """
    for term in terms:
        if term.isupper():
            if re.search(rf"\b{re.escape(term)}\b", title):
                return True
        elif re.search(rf"\b{re.escape(_normalize(term))}\b", _normalize(title)):
            return True
    return False


def _excluded(title: str, inst: dict) -> bool:
    """Titulares con palabras que delatan otro significado del nombre (p. ej. la avenida Concha y Toro)."""
    return mentions(title, inst.get("news_exclude", []))


def _search_terms(inst: dict):
    return inst.get("aliases") or [inst["name"]]


def _cached(key, loader, ttl_seconds):
    try:
        return news_cache.get_or_load(key, loader, ttl_seconds)
    except NewsSourceError:
        return []  # no se cachea: la proxima carga reintenta


def get_market_news(max_items: int = 5, cache_ttl_seconds: int = 20 * 60):
    """Titulares generales del mercado chileno (IPSA / Bolsa de Santiago)."""
    return _cached(("market",), lambda: fetch_news(MARKET_QUERY), cache_ttl_seconds)[:max_items]


def get_company_news(inst: dict, max_items: int = 5, cache_ttl_seconds: int = 20 * 60):
    """Titulares recientes que nombran a la empresa `inst` (entrada del catalogo)."""
    terms = _search_terms(inst)
    query = "(" + " OR ".join(f'"{t}"' for t in terms) + f") ({BUSINESS_TERMS}) when:14d"

    def load():
        return [
            i for i in fetch_news(query) if mentions(i["title"], terms) and not _excluded(i["title"], inst)
        ]

    return _cached(("company", inst["symbol"]), load, cache_ttl_seconds)[:max_items]
