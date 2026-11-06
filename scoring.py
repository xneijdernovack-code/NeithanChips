# -*- coding: utf-8 -*-
"""
Etapa 3 del embudo: CALIDAD / ANTI-TRAMPA.

El filtro que separa "barata sana" de "barata pero moribunda". Calcula desde los estados
financieros normalizados (FMP o yfinance, cobertura universal):
  - Piotroski F (0-9): fortaleza financiera.
  - Altman Z'' (variante no-manufactura; se omite en financieras/REITs): riesgo de quiebra.
  - Gross profitability (Novy-Marx), ROIC, margenes y su tendencia, crecimiento de ventas,
    deuda neta/EBITDA, cobertura de intereses, cobertura del dividendo, momentum 6-12m.
  - FLAGS DE DETERIORO (abogado del diablo) -> veredicto de calidad y ranking final.
"""
import numpy as np
import pandas as pd


FIN_SECTORS = {"Financials", "Financial Services", "Real Estate", "Banks", "Insurance"}


def _num(x):
    try:
        f = float(x)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _ratio(a, b):
    a, b = _num(a), _num(b)
    return (a / b) if (a is not None and b not in (None, 0)) else None


def piotroski(st):
    """F-Score 0-9 usando el anio actual (st[0]) vs el anterior (st[1])."""
    if len(st) < 2 or not st[0].get("total_assets"):
        return None
    c, p = st[0], st[1]
    s = 0
    roa_c = _ratio(c.get("net_income"), c.get("total_assets"))
    roa_p = _ratio(p.get("net_income"), p.get("total_assets"))
    cfo = _num(c.get("operating_cash_flow"))
    ni = _num(c.get("net_income"))
    if roa_c is not None and roa_c > 0: s += 1                     # 1 rentable
    if cfo is not None and cfo > 0: s += 1                         # 2 genera caja
    if roa_c is not None and roa_p is not None and roa_c > roa_p: s += 1  # 3 ROA mejora
    if cfo is not None and ni is not None and cfo > ni: s += 1     # 4 caja > utilidad (accruals)
    lev_c = _ratio(c.get("long_term_debt"), c.get("total_assets"))
    lev_p = _ratio(p.get("long_term_debt"), p.get("total_assets"))
    if lev_c is not None and lev_p is not None and lev_c < lev_p: s += 1  # 5 se desapalanca
    cr_c = _ratio(c.get("current_assets"), c.get("current_liabilities"))
    cr_p = _ratio(p.get("current_assets"), p.get("current_liabilities"))
    if cr_c is not None and cr_p is not None and cr_c > cr_p: s += 1      # 6 liquidez mejora
    sh_c, sh_p = _num(c.get("shares")), _num(p.get("shares"))
    if sh_c is not None and sh_p is not None and sh_c <= sh_p * 1.01: s += 1  # 7 no diluye
    gm_c = _ratio(c.get("gross_profit"), c.get("revenue"))
    gm_p = _ratio(p.get("gross_profit"), p.get("revenue"))
    if gm_c is not None and gm_p is not None and gm_c > gm_p: s += 1      # 8 margen mejora
    at_c = _ratio(c.get("revenue"), c.get("total_assets"))
    at_p = _ratio(p.get("revenue"), p.get("total_assets"))
    if at_c is not None and at_p is not None and at_c > at_p: s += 1      # 9 rotacion mejora
    return s


def altman(st, sector):
    """Altman Z'' (no-manufactura). Zonas: >2.6 seguro, 1.1-2.6 gris, <1.1 peligro."""
    if not st:
        return {"z": None, "zone": None}
    if sector in FIN_SECTORS:
        return {"z": None, "zone": "n/a"}
    c = st[0]
    ta = _num(c.get("total_assets"))
    if not ta:
        return {"z": None, "zone": None}
    wc = (_num(c.get("current_assets")) or 0.0) - (_num(c.get("current_liabilities")) or 0.0)
    re, ebit = _num(c.get("retained_earnings")), _num(c.get("ebit"))
    tl, eq = _num(c.get("total_liabilities")), _num(c.get("equity"))
    if None in (re, ebit, tl, eq) or not tl:
        return {"z": None, "zone": None}
    z = 6.56 * (wc / ta) + 3.26 * (re / ta) + 6.72 * (ebit / ta) + 1.05 * (eq / tl)
    zone = "seguro" if z > 2.6 else ("gris" if z >= 1.1 else "peligro")
    return {"z": z, "zone": zone}


def _cagr(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2 or vals[0] <= 0 or vals[-1] <= 0:
        return None
    return (vals[0] / vals[-1]) ** (1.0 / (len(vals) - 1)) - 1.0   # [0]=reciente, [-1]=viejo


def momentum(price, lo=252, hi=21):
    """Retorno 12-1 (de hace ~12 meses a hace ~1 mes); negativo = sigue cayendo."""
    try:
        s = price.dropna()
        if len(s) < lo + 2:
            return None
        return float(s.iloc[-hi] / s.iloc[-lo] - 1.0)
    except Exception:
        return None


def score_one(bundle, price, sector):
    st = bundle.get("statements") or []
    kmt = bundle.get("km_ttm") or {}
    if not st:
        return {"piotroski": None, "altman_z": None, "altman_zone": None, "gp_assets": None,
                "gross_margin": None, "margin_trend": None, "rev_cagr": None, "roic": None,
                "net_debt_ebitda": _num(kmt.get("netDebtToEBITDATTM")), "interest_cov": None,
                "div_fcf_payout": None, "momentum": momentum(price) if price is not None else None,
                "flags": [], "nflags": 0, "quality_verdict": "sin datos", "quality_score": np.nan}
    c = st[0]
    r = {}
    r["piotroski"] = piotroski(st)
    az = altman(st, sector)
    r["altman_z"], r["altman_zone"] = az["z"], az["zone"]
    r["gp_assets"] = _ratio(c.get("gross_profit"), c.get("total_assets"))
    gm_now = _ratio(c.get("gross_profit"), c.get("revenue"))
    gm_old = _ratio(st[-1].get("gross_profit"), st[-1].get("revenue")) if len(st) >= 2 else None
    r["gross_margin"] = gm_now
    r["margin_trend"] = (gm_now - gm_old) if (gm_now is not None and gm_old is not None) else None
    r["rev_cagr"] = _cagr([s.get("revenue") for s in st])
    r["net_debt_ebitda"] = _num(kmt.get("netDebtToEBITDATTM"))
    r["interest_cov"] = _ratio(c.get("ebit"), c.get("interest_expense"))
    roic = _num(kmt.get("returnOnInvestedCapitalTTM"))
    if roic is None:
        ic = (_num(c.get("equity")) or 0.0) + (_num(c.get("total_debt")) or 0.0) - (_num(c.get("cash")) or 0.0)
        ebit = _num(c.get("ebit"))
        roic = (ebit * 0.79 / ic) if (ebit is not None and ic and ic > 0) else None
    r["roic"] = roic
    div, fcf = _num(c.get("dividends_paid")), _num(c.get("free_cash_flow"))
    if div is not None and div < 0:
        r["div_fcf_payout"] = (-div / fcf) if (fcf and fcf > 0) else 2.0
    else:
        r["div_fcf_payout"] = 0.0
    r["momentum"] = momentum(price) if price is not None else None

    # --- flags de deterioro ---
    fl = []
    if r["rev_cagr"] is not None and r["rev_cagr"] < -0.02: fl.append("ventas en declive")
    if r["margin_trend"] is not None and r["margin_trend"] < -0.03: fl.append("margen erosionando")
    if r["net_debt_ebitda"] is not None and r["net_debt_ebitda"] > 4: fl.append("apalancamiento alto")
    if r["interest_cov"] is not None and 0 < r["interest_cov"] < 2: fl.append("cobertura de intereses baja")
    if r["div_fcf_payout"] is not None and r["div_fcf_payout"] > 1: fl.append("dividendo > FCF")
    if r["altman_zone"] == "peligro": fl.append("riesgo de quiebra (Altman)")
    if r["piotroski"] is not None and r["piotroski"] <= 2: fl.append("Piotroski muy bajo")
    if r["momentum"] is not None and r["momentum"] < -0.25: fl.append("sigue cayendo (momentum)")
    r["flags"], r["nflags"] = fl, len(fl)

    # --- veredicto de calidad ---
    P, zone = r["piotroski"], r["altman_zone"]
    if (zone == "peligro") or (P is not None and P <= 2) or (len(fl) >= 3):
        v = "posible trampa"
    elif (P is not None and P >= 7) and zone != "peligro" and len(fl) <= 1:
        v = "sana"
    elif (P is not None and P <= 4) or len(fl) >= 2:
        v = "fragil"
    else:
        v = "aceptable"
    r["quality_verdict"] = v

    # --- score de calidad 0-100 (para ordenar) ---
    q = 50.0
    if P is not None: q += (P - 5) * 6
    if zone == "peligro": q -= 25
    elif zone == "seguro": q += 8
    q -= len(fl) * 8
    if r["gp_assets"] is not None: q += min(15.0, r["gp_assets"] * 30)
    r["quality_score"] = max(0.0, min(100.0, q))
    return r


def enrich(cand, funds, prices):
    """Agrega columnas de calidad + ranking final (value_z penalizado por calidad, trampas al fondo)."""
    rows = []
    for _, rw in cand.iterrows():
        sym = rw["symbol"]
        b = funds.get(sym, {})
        ps = prices[sym] if (prices is not None and sym in prices.columns) else None
        sector = rw.get("sector") or (b.get("profile", {}) or {}).get("sector")
        rows.append(score_one(b, ps, sector))
    md = pd.DataFrame(rows, index=cand.index)
    out = pd.concat([cand, md], axis=1)

    vz = pd.to_numeric(out.get("value_z"), errors="coerce").fillna(0.0)
    qual = (pd.to_numeric(out.get("quality_score"), errors="coerce").fillna(50.0) - 50.0) / 50.0
    trap = (out.get("quality_verdict") == "posible trampa").astype(float)
    out["final_score"] = vz + 0.6 * qual - 3.0 * trap
    return out
