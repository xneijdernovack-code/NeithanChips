# -*- coding: utf-8 -*-
"""
Universo: constituyentes del S&P 500 -> top N por capitalizacion de mercado.

Fuentes (en orden): Wikipedia (con User-Agent), datahub CSV, y respaldo local cacheado.
Market caps via yfinance fast_info (paralelo + cache 30 dias).
"""
import os
import io
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config as C


# ----------------------------------------------------------------------- utilidades
def _http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": C.BROWSER_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def yahooize(symbol):
    """Wikipedia usa BRK.B / BF.B; Yahoo usa BRK-B / BF-B."""
    return symbol.strip().upper().replace(".", "-")


def _cache_age_days(path):
    if not os.path.exists(path):
        return 1e9
    return (time.time() - os.path.getmtime(path)) / 86400.0


# ----------------------------------------------------------------------- constituyentes
def get_constituents():
    """DataFrame[symbol, name, sector, sub_industry]. symbol ya normalizado para Yahoo."""
    cache = os.path.join(C.CACHE_DIR, "constituents.parquet")

    if _cache_age_days(cache) < C.UNIVERSE_CACHE_DAYS:
        try:
            return pd.read_parquet(cache)
        except Exception:
            pass

    df = None
    # 1) Wikipedia
    try:
        html = _http_get(C.WIKI_SP500_URL)
        tables = pd.read_html(io.StringIO(html))
        t = tables[0]
        df = pd.DataFrame({
            "symbol": t["Symbol"].astype(str),
            "name": t["Security"].astype(str),
            "sector": t["GICS Sector"].astype(str),
            "sub_industry": t["GICS Sub-Industry"].astype(str),
        })
        print(f"  [universo] Wikipedia OK ({len(df)} empresas)")
    except Exception as e:
        print(f"  [universo] Wikipedia fallo ({e}); intentando datahub...")

    # 2) datahub CSV
    if df is None:
        try:
            txt = _http_get(C.DATAHUB_SP500_URL)
            t = pd.read_csv(io.StringIO(txt))
            df = pd.DataFrame({
                "symbol": t["Symbol"].astype(str),
                "name": t["Security"].astype(str),
                "sector": t["GICS Sector"].astype(str),
                "sub_industry": t.get("GICS Sub-Industry", pd.Series([""] * len(t))).astype(str),
            })
            print(f"  [universo] datahub OK ({len(df)} empresas)")
        except Exception as e:
            print(f"  [universo] datahub fallo ({e}); usando respaldo local...")

    # 3) respaldo local
    if df is None:
        backup = os.path.join(C.DATA_DIR, "sp500_fallback.csv")
        if os.path.exists(backup):
            df = pd.read_csv(backup)
            print(f"  [universo] respaldo local ({len(df)} empresas)")
        else:
            raise RuntimeError("No se pudo obtener el universo del S&P 500 por ninguna fuente.")

    df["symbol"] = df["symbol"].map(yahooize)
    df = df.drop_duplicates("symbol").reset_index(drop=True)

    try:
        df.to_parquet(cache, index=False)
        # respaldo permanente por si las fuentes caen luego
        df.to_csv(os.path.join(C.DATA_DIR, "sp500_fallback.csv"), index=False)
    except Exception:
        pass
    return df


# ----------------------------------------------------------------------- market caps
def _one_cap(symbol):
    import yfinance as yf
    try:
        fi = yf.Ticker(symbol).fast_info
        mc = fi["market_cap"]           # acceso por corchete (fast_info.get() esta roto)
        return symbol, float(mc) if mc else None
    except Exception:
        return symbol, None


def get_market_caps(symbols):
    """Serie symbol -> market_cap (USD). Paralelo + cache 30 dias."""
    cache = os.path.join(C.CACHE_DIR, "marketcaps.parquet")
    if _cache_age_days(cache) < C.UNIVERSE_CACHE_DAYS:
        try:
            s = pd.read_parquet(cache)["market_cap"]
            if s.notna().sum() >= 0.8 * len(symbols):
                return s
        except Exception:
            pass

    print(f"  [universo] bajando market caps de {len(symbols)} empresas (una vez, cacheado)...")
    caps = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=C.MARKETCAP_WORKERS) as ex:
        futs = [ex.submit(_one_cap, s) for s in symbols]
        done = 0
        for f in as_completed(futs):
            sym, mc = f.result()
            caps[sym] = mc
            done += 1
            if done % 100 == 0:
                print(f"    ... {done}/{len(symbols)}")
    ok = sum(1 for v in caps.values() if v)
    print(f"  [universo] market caps: {ok}/{len(symbols)} OK en {time.time()-t0:.0f}s")

    s = pd.Series(caps, name="market_cap")
    try:
        s.to_frame().to_parquet(cache)
    except Exception:
        pass
    return s


# ----------------------------------------------------------------------- universo final
def get_universe(top_n=None):
    """DataFrame[symbol, name, sector, sub_industry, market_cap] con las top_n por cap."""
    top_n = top_n or C.UNIVERSE_TOP_N
    cons = get_constituents()
    caps = get_market_caps(cons["symbol"].tolist())
    cons["market_cap"] = cons["symbol"].map(caps)
    cons = cons.dropna(subset=["market_cap"]).sort_values("market_cap", ascending=False)
    # rank por tamaño dentro del S&P 500 (1 = la mas grande del indice). Se recalcula cada corrida.
    cons["sp500_rank"] = range(1, len(cons) + 1)
    uni = cons.head(top_n).reset_index(drop=True)
    return uni


if __name__ == "__main__":
    u = get_universe()
    print(f"\nTop {len(u)} por market cap:")
    print(u.head(15)[["symbol", "name", "sector", "market_cap"]].to_string(index=False))
