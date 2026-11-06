# -*- coding: utf-8 -*-
"""
Capa de fundamentales: FMP (endpoints /stable/), con cache por simbolo.

Solo se llama para los CANDIDATOS que pasaron el filtro de precio -> uso minimo de API.
Plan gratis: 250 req/dia, historia limitada a 5 anios. FMP jubilo /api/v3/ -> usar /stable/.
"""
import os
import json
import time
import datetime
import urllib.parse
import urllib.request
import urllib.error

import config as C

FUND_DIR = os.path.join(C.CACHE_DIR, "fundamentals")
os.makedirs(FUND_DIR, exist_ok=True)


# --------------------------------------------------------------------- HTTP
_last_call = [0.0]
_MIN_INTERVAL = 0.25   # throttle: minimo entre llamadas (anti rate-limit de rafaga)


def _get(path, **params):
    """GET a un endpoint /stable/ con throttle + reintentos. JSON o None si premium/falla."""
    if not C.FMP_KEY:
        raise RuntimeError("Falta FMP_KEY en config.local.py")
    params["apikey"] = C.FMP_KEY
    url = f"{C.FMP_BASE}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        dt = time.time() - _last_call[0]
        if dt < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - dt)
        _last_call[0] = time.time()
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            _ = e.read()
            if e.code in (401, 402, 403):
                return None                     # no autorizado / premium: no reintentar
            time.sleep(1.2 * (attempt + 1))     # 429 u otros: backoff y reintentar
            continue
        except Exception:
            time.sleep(0.6 * (attempt + 1))
            continue
        try:
            data = json.loads(body)
        except Exception:
            return None
        if isinstance(data, dict) and "Error Message" in data:
            return None
        return data
    return None


def _one(data):
    """Primer registro de una lista, o el dict tal cual."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


# --------------------------------------------------------------------- normalizacion de estados
def _n(x):
    try:
        f = float(x)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


# esquema comun -> campo FMP
_FMP_MAP = {
    "revenue": "revenue", "gross_profit": "grossProfit", "ebit": "ebit", "ebitda": "ebitda",
    "net_income": "netIncome", "interest_expense": "interestExpense", "cogs": "costOfRevenue",
    "sga": "sellingGeneralAndAdministrativeExpenses", "depreciation": "depreciationAndAmortization",
    "shares": "weightedAverageShsOut",
    "total_assets": "totalAssets", "current_assets": "totalCurrentAssets",
    "current_liabilities": "totalCurrentLiabilities", "total_liabilities": "totalLiabilities",
    "long_term_debt": "longTermDebt", "total_debt": "totalDebt", "cash": "cashAndCashEquivalents",
    "retained_earnings": "retainedEarnings", "equity": "totalStockholdersEquity",
    "receivables": "netReceivables", "ppe_net": "propertyPlantEquipmentNet",
    "operating_cash_flow": "operatingCashFlow", "free_cash_flow": "freeCashFlow",
    "capex": "capitalExpenditure", "dividends_paid": "netDividendsPaid",
}


def _fmp_statements(income, balance, cash):
    """Normaliza los estados de FMP a un esquema comun (anual, mas reciente primero)."""
    income = income or []
    out = []
    for i in range(len(income)):
        merged = dict(income[i] or {})
        if i < len(balance or []):
            merged.update(balance[i] or {})
        if i < len(cash or []):
            merged.update(cash[i] or {})
        rec = {k: _n(merged.get(src)) for k, src in _FMP_MAP.items()}
        rec["year"] = str(income[i].get("fiscalYear") or income[i].get("date") or "")[:4]
        out.append(rec)
    return out


def _yf_statements(tk, price_series):
    """Normaliza estados de yfinance al mismo esquema + serie EV/EBITDA-EV/Sales (km) por anio."""
    try:
        inc, bal, cf = tk.income_stmt, tk.balance_sheet, tk.cashflow
    except Exception:
        return [], []
    if inc is None or inc.empty or bal is None or bal.empty:
        return [], []

    def g(df, name, col):
        try:
            if df is None or name not in df.index or col not in df.columns:
                return None
            v = float(df.loc[name, col])
            return v if v == v else None
        except Exception:
            return None

    stmts, km = [], []
    for col in inc.columns:
        rev = g(inc, "Total Revenue", col)
        ebitda = g(inc, "EBITDA", col)
        rec = {
            "year": str(col)[:4],
            "revenue": rev, "gross_profit": g(inc, "Gross Profit", col),
            "ebit": g(inc, "EBIT", col), "ebitda": ebitda, "net_income": g(inc, "Net Income", col),
            "interest_expense": g(inc, "Interest Expense", col), "cogs": g(inc, "Cost Of Revenue", col),
            "sga": g(inc, "Selling General And Administration", col),
            "depreciation": g(inc, "Reconciled Depreciation", col),
            "shares": g(inc, "Diluted Average Shares", col) or g(inc, "Basic Average Shares", col),
            "total_assets": g(bal, "Total Assets", col), "current_assets": g(bal, "Current Assets", col),
            "current_liabilities": g(bal, "Current Liabilities", col),
            "total_liabilities": g(bal, "Total Liabilities Net Minority Interest", col),
            "long_term_debt": g(bal, "Long Term Debt", col), "total_debt": g(bal, "Total Debt", col),
            "cash": g(bal, "Cash And Cash Equivalents", col),
            "retained_earnings": g(bal, "Retained Earnings", col),
            "equity": g(bal, "Stockholders Equity", col) or g(bal, "Common Stock Equity", col),
            "receivables": g(bal, "Receivables", col) or g(bal, "Accounts Receivable", col),
            "ppe_net": g(bal, "Net PPE", col),
            "operating_cash_flow": g(cf, "Operating Cash Flow", col),
            "free_cash_flow": g(cf, "Free Cash Flow", col),
            "capex": g(cf, "Capital Expenditure", col),
            "dividends_paid": g(cf, "Cash Dividends Paid", col),
        }
        stmts.append(rec)
        shares = g(bal, "Ordinary Shares Number", col) or rec["shares"]
        debt = rec["total_debt"] or 0.0
        csh = rec["cash"] or 0.0
        price = None
        if price_series is not None and shares:
            try:
                price = float(price_series.asof(col))
            except Exception:
                price = None
        ev = (shares * price + debt - csh) if (shares and price) else None
        km.append({"evToEBITDA": (ev / ebitda) if (ev and ebitda and ebitda > 0) else None,
                   "evToSales": (ev / rev) if (ev and rev and rev > 0) else None})
    return stmts, km


def _yf_pseudo_bundle(symbol, profile, market_cap=None, price_series=None):
    """Respaldo universal desde yfinance: multiplos actuales (.info) + historia (estados + precios)
    para que 'vs Historia' funcione tambien en los simbolos que FMP no cubre gratis."""
    import yfinance as yf
    tk = yf.Ticker(symbol)
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    def g(k):
        v = info.get(k)
        return v if isinstance(v, (int, float)) else None

    ev, fcf, pe = g("enterpriseValue"), g("freeCashflow"), g("trailingPE")
    ebitda, td, tc = g("ebitda"), g("totalDebt"), g("totalCash")
    mc = g("marketCap") or market_cap
    km_ttm = {
        "evToEBITDATTM": g("enterpriseToEbitda"),
        "evToSalesTTM": g("enterpriseToRevenue"),
        "freeCashFlowYieldTTM": (fcf / ev) if (fcf and ev) else None,
        "earningsYieldTTM": (1.0 / pe) if (pe and pe > 0) else None,
        "returnOnInvestedCapitalTTM": None,
        "netDebtToEBITDATTM": ((td - tc) / ebitda) if (td is not None and tc is not None and ebitda) else None,
        "enterpriseValueTTM": ev,
        "marketCap": mc,
    }
    prof = profile if profile else {"industry": info.get("industry"), "sector": info.get("sector")}
    stmts, km_hist = _yf_statements(tk, price_series)
    return {"symbol": symbol, "source": "yfinance", "profile": prof, "km_ttm": km_ttm,
            "ratios_ttm": {"priceToEarningsRatioTTM": pe},
            "income": [], "balance": [], "cash": [], "ratios": [], "km": km_hist,
            "statements": stmts, "_fetched": time.strftime("%Y-%m-%d")}


def get_fundamentals(symbol, market_cap=None, price_series=None, max_age_days=30, verbose=False):
    """Paquete de fundamentales de un simbolo. FMP primario; yfinance de respaldo si FMP no lo
    cubre en el plan gratis. Cachea el resultado."""
    cache = os.path.join(FUND_DIR, f"{symbol}.json")
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) / 86400.0 < max_age_days:
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    if verbose:
        print(f"    [fund] {symbol} ...")

    profile = _one(_get("profile", symbol=symbol))
    km_ttm = _one(_get("key-metrics-ttm", symbol=symbol))

    if km_ttm:                              # FMP cubre este simbolo
        L = C.FMP_HISTORY_LIMIT
        bundle = {
            "symbol": symbol, "source": "fmp", "profile": profile, "km_ttm": km_ttm,
            "ratios_ttm": _one(_get("ratios-ttm", symbol=symbol)),
            "income":  _get("income-statement", symbol=symbol, period="annual", limit=L) or [],
            "balance": _get("balance-sheet-statement", symbol=symbol, period="annual", limit=L) or [],
            "cash":    _get("cash-flow-statement", symbol=symbol, period="annual", limit=L) or [],
            "ratios":  _get("ratios", symbol=symbol, period="annual", limit=L) or [],
            "km":      _get("key-metrics", symbol=symbol, period="annual", limit=L) or [],
            "_fetched": time.strftime("%Y-%m-%d"),
        }
        bundle["statements"] = _fmp_statements(bundle["income"], bundle["balance"], bundle["cash"])
        complete = bool(bundle["income"])
    else:                                   # respaldo yfinance (FMP premium para este simbolo)
        bundle = _yf_pseudo_bundle(symbol, profile, market_cap, price_series)
        complete = any(bundle["km_ttm"].get(k) is not None
                       for k in ("evToEBITDATTM", "evToSalesTTM", "enterpriseValueTTM"))
        if verbose:
            print(f"    [fund] {symbol}: FMP premium -> yfinance ({'ok' if complete else 'sin datos'})")

    if complete:
        try:
            json.dump(bundle, open(cache, "w", encoding="utf-8"))
        except Exception:
            pass
    return bundle


# --------------------------------------------------------------------- medianas de industria / sector
def _recent_weekdays(n=6):
    """Fechas ISO de los ultimos n dias habiles (hoy hacia atras)."""
    out, d = [], datetime.date.today()
    while len(out) < n:
        if d.weekday() < 5:          # 0-4 = lun-vie
            out.append(d.isoformat())
        d -= datetime.timedelta(days=1)
    return out


def _median(vals):
    vals = sorted(v for v in vals if isinstance(v, (int, float)) and v and v > 0)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0


def _snapshot_pe(kind):
    """kind = 'industry' o 'sector'. Devuelve dict nombre->P/E mediana (agregada por bolsa)."""
    cache = os.path.join(C.CACHE_DIR, f"{kind}_pe.json")
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) / 86400.0 < 1:
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    rows = None
    for iso in _recent_weekdays():
        rows = _get(f"{kind}-pe-snapshot", date=iso)
        if rows:
            break
    groups = {}
    for r in (rows or []):
        name = r.get(kind)
        pe = r.get("pe")
        if name and isinstance(pe, (int, float)) and pe > 0:
            groups.setdefault(name, []).append(pe)
    out = {k: _median(v) for k, v in groups.items()}
    try:
        json.dump(out, open(cache, "w", encoding="utf-8"))
    except Exception:
        pass
    return out


def get_industry_pe():
    return _snapshot_pe("industry")


def get_sector_pe():
    return _snapshot_pe("sector")


if __name__ == "__main__":
    b = get_fundamentals("AAPL", verbose=True)
    print("profile industry:", b["profile"].get("industry"), "| sector:", b["profile"].get("sector"))
    print("EV/EBITDA TTM:", b["km_ttm"].get("evToEBITDATTM"), "| FCF yield:", b["km_ttm"].get("freeCashFlowYieldTTM"))
    ind = get_industry_pe()
    print("industrias con P/E:", len(ind), "| ej Semiconductors:", ind.get("Semiconductors"))
