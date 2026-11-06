# -*- coding: utf-8 -*-
"""
Etapa 4 del embudo: NOTICIAS (el porqué de la caída).

Titulares recientes por candidato para entender el MOTIVO. Universal y sin key: yfinance
(gratis). Si hay FINNHUB_KEY en config.local.py, se usa Finnhub (mas curado). La maquina
trae el contexto; el veredicto temporal-vs-estructural lo da el usuario.
"""
import os
import json
import time
import datetime
import urllib.parse
import urllib.request
import urllib.error

import config as C

NEWS_DIR = os.path.join(C.CACHE_DIR, "news")
os.makedirs(NEWS_DIR, exist_ok=True)


def _finnhub_news(symbol, n):
    if not C.FINNHUB_KEY:
        return []
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=60)
    params = {"symbol": symbol, "from": frm.isoformat(), "to": to.isoformat(),
              "token": C.FINNHUB_KEY}
    url = "https://finnhub.io/api/v1/company-news?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []
    out = []
    for d in (data or [])[:n]:
        dt = d.get("datetime")
        date = datetime.date.fromtimestamp(dt).isoformat() if dt else ""
        out.append({"title": d.get("headline"), "url": d.get("url"),
                    "source": d.get("source"), "date": date, "type": "STORY"})
    return [o for o in out if o["title"] and o["url"]]


def _yf_news(symbol, n):
    import yfinance as yf
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception:
        return []
    out = []
    for it in raw:
        c = it.get("content") or {}
        url = ((c.get("clickThroughUrl") or {}) or {}).get("url") or \
              ((c.get("canonicalUrl") or {}) or {}).get("url")
        title = c.get("title")
        if not (title and url):
            continue
        out.append({"title": title, "url": url,
                    "source": (c.get("provider") or {}).get("displayName") or "",
                    "date": (c.get("pubDate") or "")[:10],
                    "type": c.get("contentType") or "STORY"})
        if len(out) >= n:
            break
    return out


def get_news(symbol, n=4, max_age_days=1):
    """Titulares recientes de un simbolo (Finnhub si hay key, si no yfinance). Cacheado 1 dia."""
    cache = os.path.join(NEWS_DIR, f"{symbol}.json")
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) / 86400.0 < max_age_days:
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    items = _finnhub_news(symbol, n) or _yf_news(symbol, n)
    if items:
        try:
            json.dump(items, open(cache, "w", encoding="utf-8"))
        except Exception:
            pass
    return items


def get_news_map(symbols, n=4, verbose=False):
    out = {}
    for s in symbols:
        out[s] = get_news(s, n=n)
        if verbose:
            print(f"    [news] {s}: {len(out[s])} titulares")
    return out


if __name__ == "__main__":
    m = get_news_map(["INTC", "NFLX"], verbose=True)
    for s, items in m.items():
        print(f"\n{s}:")
        for it in items:
            print(f"  [{it['date']}] ({it['source']}) {it['title']}")
