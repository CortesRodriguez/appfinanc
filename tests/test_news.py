import pytest
import requests

from src.extractor import news
from src.extractor.news import NewsSourceError, fetch_news, get_company_news, get_market_news, mentions

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Falabella marca récord en bolsa - Diario Financiero</title>
        <link>https://df.cl/a</link><pubDate>Fri, 16 Oct 2026 22:45:00 GMT</pubDate>
        <source url="https://df.cl">Diario Financiero</source></item>
  <item><title>Falabella marca récord en bolsa - Diario Financiero</title>
        <link>https://df.cl/a2</link><pubDate>Fri, 16 Oct 2026 22:40:00 GMT</pubDate>
        <source url="https://df.cl">Diario Financiero</source></item>
  <item><title>Falabella abre tienda en Osorno - La Tercera</title>
        <link>https://latercera.com/b</link><pubDate>Sat, 17 Oct 2026 10:00:00 GMT</pubDate>
        <source url="https://latercera.com">La Tercera</source></item>
  <item><title>Enlace peligroso - Medio</title>
        <link>javascript:alert(1)</link><pubDate>Sat, 17 Oct 2026 11:00:00 GMT</pubDate>
        <source url="https://x.cl">Medio</source></item>
  <item><title>Otra empresa sube - BioBioChile</title>
        <link>https://biobio.cl/c</link><pubDate>Sat, 17 Oct 2026 12:00:00 GMT</pubDate>
        <source url="https://biobio.cl">BioBioChile</source></item>
  <item><title>Datos de Falabella - TradingView</title>
        <link>https://tradingview.com/d</link><pubDate>Sat, 17 Oct 2026 13:00:00 GMT</pubDate>
        <source url="https://tradingview.com">TradingView</source></item>
  <item><title>Ficha automática de Enel – FWB:355</title>
        <link>https://x.cl/e</link><pubDate>Sat, 17 Oct 2026 14:00:00 GMT</pubDate>
        <source url="https://x.cl">X</source></item>
</channel></rss>"""


class _Resp:
    def __init__(self, content=RSS.encode("utf-8"), status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture(autouse=True)
def _clean_cache():
    news.news_cache.clear()
    yield
    news.news_cache.clear()


def _patch_get(monkeypatch, response=None, calls=None):
    def fake_get(url, **kwargs):
        if calls is not None:
            calls.append(url)
        if isinstance(response, Exception):
            raise response
        return response or _Resp()

    monkeypatch.setattr(news.requests, "get", fake_get)


def test_fetch_news_parses_cleans_and_filters(monkeypatch):
    _patch_get(monkeypatch)
    items = fetch_news("falabella")
    titles = [i["title"] for i in items]
    # Sufijo del medio fuera, sin duplicados, sin enlaces no http, sin fichas automaticas.
    assert titles == ["Otra empresa sube", "Falabella abre tienda en Osorno", "Falabella marca récord en bolsa"]
    assert items[0]["source"] == "BioBioChile" and items[0]["url"].startswith("https://")
    assert items[0]["published"].startswith("2026-10-17T12:00:00")


def test_fetch_news_raises_on_network_or_xml_errors(monkeypatch):
    _patch_get(monkeypatch, response=requests.ConnectionError("sin red"))
    with pytest.raises(NewsSourceError):
        fetch_news("x")
    _patch_get(monkeypatch, response=_Resp(b"<html>no es xml"))
    with pytest.raises(NewsSourceError):
        fetch_news("x")
    _patch_get(monkeypatch, response=_Resp(status=503))
    with pytest.raises(NewsSourceError):
        fetch_news("x")


def test_mentions_ignores_accents_but_keeps_sigla_case():
    assert mentions("Colbun anuncia dividendo", ["Colbún"])
    assert mentions("Grupo SQM sube", ["SQM"])
    assert not mentions("La Bolsa y el sqm del terreno", ["SQM"])
    assert not mentions("Blue Cap AG", ["CAP"])
    assert not mentions("Falabellano de oro", ["Falabella"])


def test_company_news_filters_unrelated_and_excluded(monkeypatch):
    _patch_get(monkeypatch)
    falabella = {"symbol": "FALABELLA.SN", "name": "Falabella", "aliases": ["Falabella"]}
    titles = [i["title"] for i in get_company_news(falabella)]
    assert titles == ["Falabella abre tienda en Osorno", "Falabella marca récord en bolsa"]

    ctt = {"symbol": "CONCHATORO.SN", "name": "Viña Concha y Toro", "aliases": ["Falabella"], "news_exclude": ["Osorno"]}
    assert [i["title"] for i in get_company_news(ctt)] == ["Falabella marca récord en bolsa"]


def test_news_are_cached_and_failures_are_not(monkeypatch):
    calls = []
    _patch_get(monkeypatch, calls=calls)
    get_market_news()
    get_market_news()
    assert len(calls) == 1

    news.news_cache.clear()
    calls.clear()
    _patch_get(monkeypatch, response=requests.ConnectionError("x"), calls=calls)
    assert get_market_news() == []
    get_market_news()
    assert len(calls) == 2  # el fallo no se cachea: se reintenta


def test_api_news_market_company_unknown_and_failure(client, monkeypatch):
    _patch_get(monkeypatch)
    market = client.get("/api/news")
    assert market.status_code == 200 and len(market.get_json()["items"]) == 3

    company = client.get("/api/news?symbol=FALABELLA.SN").get_json()["items"]
    assert [i["title"] for i in company] == ["Falabella abre tienda en Osorno", "Falabella marca récord en bolsa"]

    assert client.get("/api/news?symbol=NO-EXISTE.SN").status_code == 404
    assert client.get("/api/news?symbol=" + "A" * 300).status_code == 404

    news.news_cache.clear()
    _patch_get(monkeypatch, response=requests.ConnectionError("sin red"))
    failed = client.get("/api/news?symbol=FALABELLA.SN")
    assert failed.status_code == 200 and failed.get_json() == {"items": []}
