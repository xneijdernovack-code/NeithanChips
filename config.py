# -*- coding: utf-8 -*-
"""
Configuracion del Scanner "Value en Crisis".
Parametros versionados (este archivo SI se comparte). Las API keys van en config.local.py.
"""
import os

# ---------------------------------------------------------------- rutas
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")     # datasets bundled (medianas de industria, respaldos)
CACHE_DIR = os.path.join(BASE, "cache")   # parquet: precios, market caps, fundamentales
OUT_DIR = os.path.join(BASE, "salida")    # reportes HTML + csv

for _d in (DATA_DIR, CACHE_DIR, OUT_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------- universo
UNIVERSE_TOP_N = 100      # top N del S&P 500 por capitalizacion
PRICE_YEARS = 5           # anios de historico de precios a descargar

# ---------------------------------------------------------------- FASE 1: filtro de precio (caida)
PEAK_WINDOW_DAYS = 252    # ventana movil ~52 semanas para el "pico"
DROP_MIN = 0.20           # caida minima desde el pico (20%)
DROP_MAX = 0.50           # caida maxima (50%) -- mas alla huele a quiebra
RECENT_DAYS = 365         # el pico debe haber ocurrido dentro de este rango (caida "reciente")
MIN_HISTORY_DAYS = 300    # descartar tickers con muy poco historico
SUSPICIOUS_BAR_MOVE = 0.40  # |retorno diario| mayor a esto = posible tick malo / split no ajustado

# ---------------------------------------------------------------- FASE 2: valuacion (placeholder)
PEER_DISCOUNT_MAX = -0.15   # descuento minimo vs mediana de industria (-15%)
OWNHIST_PCTL_MAX = 25       # percentil maximo del multiplo vs su propia historia

# ---------------------------------------------------------------- FASE 3: calidad (placeholder)
PIOTROSKI_MIN = 5

# ---------------------------------------------------------------- canasta
BASKET_TOP_N = 15         # cuantos nombres mostrar en la vista "canasta"

# ---------------------------------------------------------------- cache / red
UNIVERSE_CACHE_DAYS = 30   # refrescar universo + market caps cada 30 dias
MARKETCAP_WORKERS = 8      # hilos para bajar market caps (fast_info)
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# fuentes del universo (en orden de preferencia)
WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DATAHUB_SP500_URL = ("https://raw.githubusercontent.com/datasets/"
                     "s-and-p-500-companies/main/data/constituents.csv")

# ---------------------------------------------------------------- FMP (Fase 2-3)
# FMP jubilo /api/v3/ (Ago 2025); usar SIEMPRE /stable/. Plan gratis: 250 req/dia, 5 anios de historia.
FMP_BASE = "https://financialmodelingprep.com/stable"
FMP_HISTORY_LIMIT = 5       # el plan gratis limita 'limit' a 5

# ---------------------------------------------------------------- API keys (de config.local.py)
FMP_KEY = ""
FINNHUB_KEY = ""
_local = os.path.join(BASE, "config.local.py")
if os.path.exists(_local):
    import importlib.util as _ilu
    try:
        _spec = _ilu.spec_from_file_location("config_local", _local)
        _cl = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_cl)
        FMP_KEY = (getattr(_cl, "FMP_KEY", "") or "").strip()
        FINNHUB_KEY = (getattr(_cl, "FINNHUB_KEY", "") or "").strip()
    except Exception as _e:
        print(f"  [config] no se pudo leer config.local.py: {_e}")

# En la nube (GitHub Actions) las llaves llegan por variables de entorno (Secrets) y ganan prioridad.
FMP_KEY = (os.environ.get("FMP_KEY") or FMP_KEY).strip()
FINNHUB_KEY = (os.environ.get("FINNHUB_KEY") or FINNHUB_KEY).strip()
