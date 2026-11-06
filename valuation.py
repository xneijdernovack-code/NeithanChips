# -*- coding: utf-8 -*-
"""
Etapa 2 del embudo: VALUACION.

Para cada candidato responde las dos preguntas del usuario:
  (a) barata vs su INDUSTRIA?  -> P/E de la empresa vs la mediana de su industria (FMP).
  (b) barata vs SU PROPIA HISTORIA? -> percentil del multiplo (EV/EBITDA, EV/Sales) vs sus 5 anios.
Ademas: score compuesto de valor = promedio de z-scores de yields (earnings/FCF/shareholder),
segun evidencia (AQR: el compuesto supera a cualquier multiplo solo). Multiplos EV-based y EV/Sales
para esquivar la trampa de ganancias deprimidas (P/E se distorsiona en crisis).
"""
import numpy as np
import pandas as pd

import config as C


def _num(x):
    try:
        f = float(x)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _pct_rank(cur, hist):
    """Percentil de 'cur' dentro de su propia historia (0 = lo mas barato que ha estado)."""
    vals = [v for v in (_num(h) for h in hist) if v is not None and v > 0]
    c = _num(cur)
    if c is None or c <= 0 or not vals:
        return None
    allv = vals + [c]
    return 100.0 * sum(1 for v in allv if v <= c) / len(allv)


def _zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std(ddof=0)
    if not sd or np.isnan(sd):
        return pd.Series([np.nan] * len(s), index=s.index)
    return (s - s.mean()) / sd


def metrics_for(b, industry_pe, sector_pe):
    prof = b.get("profile", {}) or {}
    kmt = b.get("km_ttm", {}) or {}
    rtt = b.get("ratios_ttm", {}) or {}
    income = b.get("income", []) or []
    cash = b.get("cash", []) or []
    kmh = b.get("km", []) or []
    m = {}

    m["source"] = b.get("source", "fmp")
    m["industry"] = prof.get("industry")
    m["sector_fmp"] = prof.get("sector")

    # --- multiplos actuales (TTM) ---
    m["pe"] = _num(rtt.get("priceToEarningsRatioTTM"))
    m["ev_ebitda"] = _num(kmt.get("evToEBITDATTM"))
    m["ev_sales"] = _num(kmt.get("evToSalesTTM"))
    m["fcf_yield"] = _num(kmt.get("freeCashFlowYieldTTM"))
    m["earnings_yield"] = _num(kmt.get("earningsYieldTTM"))
    m["roic"] = _num(kmt.get("returnOnInvestedCapitalTTM"))
    m["net_debt_ebitda"] = _num(kmt.get("netDebtToEBITDATTM"))
    ev = _num(kmt.get("enterpriseValueTTM"))
    ebit = _num(income[0].get("ebit")) if income else None
    m["ev_ebit"] = (ev / ebit) if (ev and ebit and ebit > 0) else None

    # --- (a) barata vs industria (P/E vs mediana de industria; fallback sector) ---
    ind = m["industry"]
    peer_pe = industry_pe.get(ind) if ind else None
    basis = "industria"
    if not peer_pe:
        peer_pe = sector_pe.get(m["sector_fmp"]) if m["sector_fmp"] else None
        basis = "sector" if peer_pe else None
    m["peer_pe"] = peer_pe
    m["peer_basis"] = basis
    m["disc_vs_peer"] = (m["pe"] / peer_pe - 1.0) if (m["pe"] and m["pe"] > 0 and peer_pe) else None

    # --- (b) barata vs su propia historia (EV/EBITDA y EV/Sales, 5 anios; robusto a trough) ---
    p1 = _pct_rank(m["ev_ebitda"], [r.get("evToEBITDA") for r in kmh])
    p2 = _pct_rank(m["ev_sales"], [r.get("evToSales") for r in kmh])
    ps = [p for p in (p1, p2) if p is not None]
    m["ownhist_pctl"] = (sum(ps) / len(ps)) if ps else None

    # --- shareholder yield (dividendos + recompras + pago de deuda) / market cap ---
    mc = _num(kmt.get("marketCap"))
    if cash and mc and mc > 0:
        c0 = cash[0]
        div = -(_num(c0.get("netDividendsPaid")) or 0.0)
        buyback = -(_num(c0.get("commonStockRepurchased")) or 0.0)
        debt_paydown = -(_num(c0.get("netDebtIssuance")) or 0.0)
        m["shareholder_yield"] = (div + buyback + debt_paydown) / mc
    else:
        m["shareholder_yield"] = None
    return m


def enrich(cand, funds, industry_pe, sector_pe):
    """Agrega columnas de valuacion al DataFrame de candidatos + score compuesto (z-scores)."""
    rows = [metrics_for(funds.get(r["symbol"], {}), industry_pe, sector_pe)
            for _, r in cand.iterrows()]
    md = pd.DataFrame(rows, index=cand.index)
    out = pd.concat([cand, md], axis=1)

    # score compuesto de valor: promedio de z-scores de yields (mas alto = mas barato)
    for col in ("earnings_yield", "fcf_yield", "shareholder_yield"):
        out[col + "_z"] = _zscore(out[col])
    out["value_z"] = out[["earnings_yield_z", "fcf_yield_z", "shareholder_yield_z"]].mean(axis=1)

    # veredicto de valuacion (barata de verdad = descuento vs pares Y vs su historia)
    def verdict(r):
        d, h = r.get("disc_vs_peer"), r.get("ownhist_pctl")
        if d is None and h is None:
            return "sin datos"
        cheap_peer = d is not None and d <= C.PEER_DISCOUNT_MAX
        cheap_hist = h is not None and h <= C.OWNHIST_PCTL_MAX
        if cheap_peer and cheap_hist:
            return "barata de verdad"
        if (d is not None and d > 0.10) and not cheap_hist:
            return "cara (cayo pero cara)"
        if cheap_peer or cheap_hist:
            return "algo barata"
        return "en precio"
    out["val_verdict"] = out.apply(verdict, axis=1)
    return out


if __name__ == "__main__":
    import data_fundamentals as DF
    ind, sec = DF.get_industry_pe(), DF.get_sector_pe()
    for sym in ("MCD", "IBM", "NFLX"):
        b = DF.get_fundamentals(sym, verbose=True)
        m = metrics_for(b, ind, sec)
        print(f"\n{sym}  [{m['industry']}]")
        print(f"  P/E {m['pe']:.1f} vs {m['peer_basis']} {m['peer_pe']:.1f}  -> "
              f"desc {m['disc_vs_peer']*100:+.0f}%" if m['pe'] and m['peer_pe'] else "  P/E n/d")
        print(f"  EV/EBITDA {m['ev_ebitda']}, EV/Sales {m['ev_sales']}, "
              f"ownhist pctl {m['ownhist_pctl']}")
        print(f"  FCF yield {m['fcf_yield']}, earnings yield {m['earnings_yield']}, "
              f"shareholder yield {m['shareholder_yield']}")
