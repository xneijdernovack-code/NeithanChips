# -*- coding: utf-8 -*-
"""
Etapa 1 del embudo: deteccion de caidas desde el pico.

Para cada accion:
  - pico movil (rolling max de PEAK_WINDOW_DAYS) y pico historico (cummax)
  - caida actual = precio_hoy / pico - 1
  - dias desde el pico (velocidad de la caida)
  - severidad = percentil de la caida actual vs su propia historia de drawdowns
Candidato si la caida esta en la banda [DROP_MIN, DROP_MAX] y el pico es RECIENTE.

OJO (de la investigacion): la caida es solo un GENERADOR DE CANDIDATOS, no una senal de
compra. ~1 de cada 5 blue chips que caen <50% nunca recupera su pico.
"""
import numpy as np
import pandas as pd

import config as C


def _one(symbol, series, peak_window, recent_days):
    series = series.dropna()
    if len(series) < C.MIN_HISTORY_DAYS:
        return None

    last_price = float(series.iloc[-1])
    last_date = series.index[-1]

    # pico movil dentro de la ventana
    window = series.iloc[-peak_window:] if len(series) > peak_window else series
    peak_val = float(window.max())
    peak_date = window.idxmax()
    dd = last_price / peak_val - 1.0
    days_since_peak = int((last_date - peak_date).days)

    # pico historico (referencia)
    ath = float(series.max())
    dd_ath = last_price / ath - 1.0

    # severidad: donde cae la caida actual dentro de su propia distribucion historica
    roll_peak = series.cummax()
    hist_dd = (series / roll_peak - 1.0)
    severity_pctl = float((hist_dd <= dd).mean() * 100.0)  # 0 = lo peor que ha estado

    return {
        "symbol": symbol,
        "price": last_price,
        "peak": peak_val,
        "peak_date": peak_date.date().isoformat(),
        "drop_pct": dd * 100.0,            # negativo
        "days_since_peak": days_since_peak,
        "drop_from_ath_pct": dd_ath * 100.0,
        "severity_pctl": severity_pctl,    # menor = mas raro/severo vs su historia
    }


def find_candidates(prices, peak_window=None, recent_days=None,
                    drop_min=None, drop_max=None):
    peak_window = peak_window or C.PEAK_WINDOW_DAYS
    recent_days = recent_days or C.RECENT_DAYS
    drop_min = C.DROP_MIN if drop_min is None else drop_min
    drop_max = C.DROP_MAX if drop_max is None else drop_max

    rows = []
    for s in prices.columns:
        r = _one(s, prices[s], peak_window, recent_days)
        if r is None:
            continue
        drop = -r["drop_pct"] / 100.0                      # magnitud positiva
        in_band = drop_min <= drop <= drop_max
        recent = r["days_since_peak"] <= recent_days
        if in_band and recent:
            rows.append(r)

    df = pd.DataFrame(rows)
    if len(df):
        # ranking preliminar (Fase 1): mas severo primero. En fases siguientes el ranking
        # final sera por score compuesto de valor filtrado por calidad.
        df = df.sort_values(["severity_pctl", "drop_pct"]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    import data_prices
    p = data_prices.get_prices(["AAPL", "PFE", "BA", "INTC", "NKE", "MRNA"], years=5)
    print(find_candidates(p).to_string(index=False))
