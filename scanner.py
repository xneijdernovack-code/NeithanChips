# -*- coding: utf-8 -*-
"""
Scanner "Value en Crisis" -- orquestador.

Uso:
    python scanner.py --stage price   # Fase 1: caidas desde el pico (sin API)
    python scanner.py --stage value   # Fase 1 + Fase 2: valuacion (necesita FMP_KEY)
    python scanner.py --top 50        # limitar el universo (mas rapido)

Fases 3-4 (calidad / noticias) se agregan encima.
"""
import os
import sys
import shutil
import argparse
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

import config as C
import universe as U
import data_prices as DP
import drawdown as DD
import data_fundamentals as DF
import valuation as VAL
import scoring as SCOR
import data_news as NEWS
import report as R


def _pipeline(top_n):
    uni = U.get_universe(top_n)
    print(f"\n  Universo: {len(uni)} empresas (top por market cap)")
    prices = DP.get_prices(uni["symbol"].tolist(), years=C.PRICE_YEARS)
    warns = DP.validate(prices)
    cand = DD.find_candidates(prices)
    return uni, prices, cand, warns


def _add_valuation(cand, uni, prices):
    if not len(cand):
        return cand, {}
    print("\n  [Fase 2] valuacion: bajando fundamentales de los candidatos (FMP + respaldo yfinance)...")
    ind, sec = DF.get_industry_pe(), DF.get_sector_pe()
    capmap = uni.set_index("symbol")["market_cap"]
    funds = {}
    for sym in cand["symbol"]:
        ps = prices[sym] if sym in prices.columns else None
        funds[sym] = DF.get_fundamentals(sym, market_cap=capmap.get(sym), price_series=ps, verbose=True)
    return VAL.enrich(cand, funds, ind, sec), funds


def _print_candidates(cand, uni):
    if not len(cand):
        print("  (sin candidatos hoy)")
        return
    meta = uni.set_index("symbol")
    has_val = "val_verdict" in cand.columns
    has_qual = "quality_verdict" in cand.columns
    if has_qual:
        show = cand.sort_values("final_score", ascending=False)
    elif has_val:
        show = cand.sort_values("value_z", ascending=False)
    else:
        show = cand
    print("\n  " + "-" * 84)
    if has_qual:
        print(f"  {'#':>2} {'Ticker':<7}{'Caida':>8}{'vsInd':>7}{'F':>3}  {'Valuacion':<14}Calidad")
    elif has_val:
        print(f"  {'#':>2} {'Ticker':<7}{'Caida':>8}{'Sev':>4}{'vsInd':>7}{'vsHist':>7}  Veredicto")
    else:
        print(f"  {'#':>2} {'Ticker':<7}{'Caida':>8}{'Sev':>4}  Sector")
    print("  " + "-" * 84)
    for i, (_, r) in enumerate(show.iterrows()):
        line = f"  {i+1:>2} {r['symbol']:<7}{r['drop_pct']:>7.1f}%"
        if has_qual:
            d = r.get("disc_vs_peer")
            ds = f"{d*100:>+6.0f}%" if pd.notna(d) else f"{'--':>7}"
            P = r.get("piotroski")
            ps = f"{int(P):>3}" if pd.notna(P) else f"{'--':>3}"
            line += f"{ds}{ps}  {str(r.get('val_verdict', ''))[:14]:<14}{r.get('quality_verdict', '')}"
        elif has_val:
            d, h = r.get("disc_vs_peer"), r.get("ownhist_pctl")
            ds = f"{d*100:>+6.0f}%" if pd.notna(d) else f"{'--':>7}"
            hs = f"p{h:>4.0f}" if pd.notna(h) else f"{'--':>7}"
            line += f"{r['severity_pctl']:>4.0f}{ds}{hs}  {r.get('val_verdict', '')}"
        else:
            sec = str(meta.loc[r['symbol'], 'sector'])[:22] if r['symbol'] in meta.index else ""
            line += f"{r['severity_pctl']:>4.0f}  {sec}"
        print(line)


def run(top_n, do_value, do_quality=False, do_news=False):
    if do_news:
        stage = "Fase 1-4: caida + valuacion + calidad + noticias"
    elif do_quality:
        stage = "Fase 1+2+3: caida + valuacion + calidad"
    elif do_value:
        stage = "Fase 1+2: caida + valuacion"
    else:
        stage = "Fase 1: caidas desde el pico"
    print("=" * 76)
    print(f" SCANNER VALUE EN CRISIS  ---  {stage}")
    print("=" * 76)

    uni, prices, cand, warns = _pipeline(top_n)
    print(f"\n  Candidatos (caida {int(C.DROP_MIN*100)}-{int(C.DROP_MAX*100)}%, "
          f"pico <= {C.RECENT_DAYS}d): {len(cand)}")

    funds = {}
    if do_value:
        cand, funds = _add_valuation(cand, uni, prices)
    if do_quality and len(cand):
        print("\n  [Fase 3] calidad: Piotroski, Altman, margenes, apalancamiento, momentum + flags...")
        cand = SCOR.enrich(cand, funds, prices)

    news_map = None
    if do_news and len(cand):
        src = "yfinance + Finnhub" if C.FINNHUB_KEY else "yfinance"
        print(f"\n  [Fase 4] noticias: titulares recientes por candidato ({src})...")
        news_map = NEWS.get_news_map(cand["symbol"].tolist())

    _print_candidates(cand, uni)

    path = R.build_report(cand, prices, uni, warns=warns, news=news_map)
    print(f"\n  Reporte HTML: {path}")
    # copia estable "index.html" (siempre la ultima) para publicar en web
    latest = os.path.join(C.OUT_DIR, "index.html")
    try:
        shutil.copyfile(path, latest)
        print(f"  Copia estable (para web): {latest}")
    except Exception as e:
        print(f"  (no se pudo copiar a index.html: {e})")

    print("\n  " + "=" * 66)
    print("  AVISOS HONESTOS")
    print("  " + "=" * 66)
    print("  - Esto es una LISTA DE INVESTIGACION, no una senal de compra.")
    print("  - El edge documentado es de CANASTA (grupo diversificado, 3-5 anos),")
    print("    no una proyeccion fiable de una sola accion.")
    if do_value:
        print("  - 'vs Ind.' = P/E vs mediana de industria; 'vs Hist.' = EV/EBITDA y EV/Sales vs 5 anios.")
        if do_quality:
            print("  - CALIDAD (Fase 3): sana / aceptable / fragil / posible trampa, desde Piotroski F,")
            print("    Altman Z, margenes, apalancamiento y momentum + flags de deterioro. La CANASTA")
            print("    se rankea por score final y descarta las 'posible trampa'. Barato + sano.")
        else:
            print("  - Falta Fase 3 (calidad/anti-trampa): sin ella, barato != sano. Corre --stage quality.")
        yf = int((cand.get("source") == "yfinance").sum()) if "source" in cand.columns else 0
        if yf:
            print(f"  - {yf} candidatos con datos de yfinance (FMP no los cubre gratis, marcados ~).")
        if do_news:
            print("  - Fase 4: titulares recientes por candidato para leer el 'porque'; juzgar si el")
            print("    motivo es temporal (oportunidad) o estructural (trampa) es TU trabajo.")
    else:
        print("  - Falta el cruce clave (valuacion/calidad). Corre --stage value o --stage quality.")
    print("  - Universo = S&P 500 de hoy => sesgo de supervivencia.")
    if warns:
        print(f"  - {len(warns)} tickers con avisos de datos (ver reporte).")
    print()
    return path


def main():
    ap = argparse.ArgumentParser(description="Scanner Value en Crisis")
    ap.add_argument("--stage", default="price",
                    choices=["price", "value", "quality", "news", "all"])
    ap.add_argument("--top", type=int, default=C.UNIVERSE_TOP_N)
    args = ap.parse_args()

    run(args.top,
        do_value=(args.stage in ("value", "quality", "news", "all")),
        do_quality=(args.stage in ("quality", "news", "all")),
        do_news=(args.stage in ("news", "all")))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"  (tiempo total: {time.time()-t0:.0f}s)")
