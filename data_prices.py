# -*- coding: utf-8 -*-
"""
Capa de precios: historico AJUSTADO (splits+dividendos) via yfinance, con cache y validacion.

Regla de oro de la investigacion: usar SIEMPRE precios ajustados, o un split parece un
crash del 50% que nunca ocurrio. auto_adjust=True lo garantiza.
"""
import os
import json
import time

import numpy as np
import pandas as pd

import config as C


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def get_prices(symbols, years=None, force=False):
    """
    Devuelve un DataFrame ancho de cierres AJUSTADOS (index=fecha, columnas=symbols).
    Cachea por dia: si ya se bajo hoy y cubre los symbols pedidos, reusa el cache.
    """
    years = years or C.PRICE_YEARS
    symbols = list(dict.fromkeys(symbols))  # unicos, en orden
    cache = os.path.join(C.CACHE_DIR, "prices.parquet")
    meta = os.path.join(C.CACHE_DIR, "prices_meta.json")

    if not force and os.path.exists(cache) and os.path.exists(meta):
        try:
            m = json.load(open(meta))
            same_day = m.get("date") == time.strftime("%Y-%m-%d")
            covers = set(symbols).issubset(set(m.get("symbols", [])))
            if same_day and covers:
                df = pd.read_parquet(cache)
                print(f"  [precios] cache de hoy ({df.shape[1]} tickers)")
                return df[symbols]
        except Exception:
            pass

    import yfinance as yf
    print(f"  [precios] descargando {len(symbols)} tickers, {years}a, ajustado...")
    closes = {}
    t0 = time.time()
    for batch in _chunks(symbols, 60):
        data = yf.download(batch, period=f"{years}y", interval="1d",
                           auto_adjust=True, group_by="ticker",
                           threads=True, progress=False)
        for s in batch:
            try:
                if len(batch) == 1:
                    col = data["Close"]
                else:
                    col = data[s]["Close"]
                col = col.dropna()
                if len(col):
                    closes[s] = col
            except Exception:
                pass
        time.sleep(0.5)  # respiro entre lotes (anti rate-limit)

    df = pd.DataFrame(closes).sort_index()
    print(f"  [precios] {df.shape[1]}/{len(symbols)} tickers OK en {time.time()-t0:.0f}s")

    try:
        df.to_parquet(cache)
        json.dump({"date": time.strftime("%Y-%m-%d"), "symbols": list(df.columns)},
                  open(meta, "w"))
    except Exception:
        pass
    return df


def validate(prices):
    """
    Chequeos de sanidad. Devuelve dict symbol -> lista de avisos.
    Detecta movimientos diarios sospechosos (posible tick malo o split no ajustado).
    """
    warns = {}
    rets = prices.pct_change()
    for s in prices.columns:
        w = []
        col = prices[s].dropna()
        if len(col) < C.MIN_HISTORY_DAYS:
            w.append(f"historico corto ({len(col)}d)")
        mx = rets[s].abs().max()
        if pd.notna(mx) and mx > C.SUSPICIOUS_BAR_MOVE:
            w.append(f"barra sospechosa {mx*100:.0f}%")
        if w:
            warns[s] = w
    return warns


if __name__ == "__main__":
    p = get_prices(["AAPL", "MSFT", "NKE", "PFE", "BA"], years=3)
    print(p.tail(3))
    print("avisos:", validate(p))
