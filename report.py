# -*- coding: utf-8 -*-
"""
Reporte HTML del scanner. Dos vistas (decision del usuario):
  - RADAR:   candidatos individuales para investigar uno por uno.
  - CANASTA: los top N como cartera diversificada (donde vive el edge estadistico).
Diseno premium: hero oscuro con degradado animado (sutil, GPU) + tabla clara legible,
tema conmutable (Auto/Claro/Hibrido/Oscuro), tabla responsive (columnas congeladas + modo
tarjeta <900px). Self-contained (sparklines base64, CSS/JS inline, sin librerias).
"""
import os
import io
import base64
import time
import html as _html

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C


# --------------------------------------------------------------- sparklines
def _sparkline(series, peak_date=None, days=365):
    s = series.dropna()
    if len(s) > days:
        s = s.iloc[-days:]
    fig, ax = plt.subplots(figsize=(2.6, 0.55), dpi=110)
    ax.plot(s.index, s.values, color="#38bdf8", lw=1.5)
    ax.fill_between(s.index, s.values, s.min(), color="#38bdf8", alpha=0.16)
    try:
        pk = s.idxmax()
        ax.scatter([pk], [s.max()], s=15, color="#f43f5e", zorder=5)
        ax.scatter([s.index[-1]], [s.values[-1]], s=15, color="#22d3ee", zorder=5)
    except Exception:
        pass
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _drop_color(drop_pct):
    # escala de calor con texto blanco AA (>=5:1) sobre cada tono
    d = abs(drop_pct)
    if d >= 45:
        return "#7f1d1d"
    if d >= 35:
        return "#991b1b"
    if d >= 27:
        return "#b91c1c"
    return "#c2410c"


# --------------------------------------------------------------- velas (SVG) + iconos KPI
def _candles_svg():
    """SVG de velas glow que forman una onda ascendente (determinista, sin aleatorio)."""
    import math
    W, H, n = 1200, 320, 26
    step = W / n

    def cy(i):
        return H * 0.5 - 30 * math.sin(i * 0.55) - 18 * math.sin(i * 0.23) - i * 1.0

    parts = []
    for i in range(n):
        x = step * i + step * 0.5
        c = cy(i)
        body = 24 + 15 * abs(math.sin(i * 1.3))
        wick = body + 20 + 12 * abs(math.sin(i * 0.9))
        bw = step * 0.4
        up = (i % 3 != 0)
        fill = "#22d3ee" if up else "none"
        op = 0.5 if up else 0.85
        parts.append(
            f'<line x1="{x:.1f}" y1="{c-wick/2:.1f}" x2="{x:.1f}" y2="{c+wick/2:.1f}" '
            f'stroke="#67e8f9" stroke-width="1.5" opacity="0.65"/>'
            f'<rect x="{x-bw/2:.1f}" y="{c-body/2:.1f}" width="{bw:.1f}" height="{body:.1f}" rx="2" '
            f'fill="{fill}" stroke="#22d3ee" stroke-width="1.6" opacity="{op}"/>'
        )
    pts = " ".join(f"{step*i+step*0.5:.1f},{cy(i):.1f}" for i in range(n))
    inner = f'<polyline points="{pts}" fill="none" stroke="#7dd3fc" stroke-width="1.4" opacity="0.45"/>' + "".join(parts)
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
            f'xmlns="http://www.w3.org/2000/svg">{inner}</svg>')


_IC_UNIVERSO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
                '<path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg>')
_IC_CAND = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.6"/>'
            '<circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/></svg>')
_IC_DROP = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v13"/>'
            '<path d="M6 12l6 6 6-6"/></svg>')
_IC_SECT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/>'
            '<rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/>'
            '<rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/>'
            '<rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></svg>')
_IC_IG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
          '<rect x="3" y="3" width="18" height="18" rx="5.5"/><circle cx="12" cy="12" r="4.2"/>'
          '<circle cx="17.4" cy="6.6" r="1.15" fill="currentColor" stroke="none"/></svg>')
_IC_IN = ('<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 '
          '2.5 0 0 0-.02-5zM3.2 9.2h3.6V21H3.2zM9.3 9.2h3.45v1.62h.05c.48-.9 1.66-1.86 3.42-1.86 '
          '3.66 0 4.33 2.4 4.33 5.53V21h-3.6v-4.9c0-1.17-.02-2.67-1.63-2.67-1.63 0-1.88 1.27-1.88 '
          '2.58V21H9.3z"/></svg>')


# --------------------------------------------------------------- HTML
CSS = """
/* ===================== MECANISMO DE TEMA ===================== */
/* base = HIBRIDO (recomendado): datos claros + hero oscuro animado */
:root{ color-scheme:light dark;
  --cel:#0ea5e9; --cel-d:#0369a1; --neon:#22d3ee; --violet:#7c3aed;
  --bg:#ffffff; --wash:#e8f7ff;
  --surface:#ffffff; --surface-2:#f2fafe;
  --panel:rgba(255,255,255,.86); --panel-solid:#ffffff;
  --row:#ffffff; --row-alt:#f2fafe; --row-hover:#eaf6ff;
  --head:#0f2231; --head-fg:#ffffff;
  --text:#0f2231; --muted:#51637a; --line:#e2eef5; --stroke:#e2eef5;
  --val-up:#047857; --val-dn:#be123c; --val-neutral:#475569;
  --vd-strong-bg:#dcfce7; --vd-strong-fg:#14532d;
  --vd-good-bg:#e0f2fe; --vd-good-fg:#075985;
  --vd-mid-bg:#eef2f7; --vd-mid-fg:#334155;
  --vd-bad-bg:#fee2e2; --vd-bad-fg:#991b1b;
  --vd-none-bg:#eef2f7; --vd-none-fg:#475569;
  --hero-bg:#050b18; --hero-fg:#eaf6ff; --hero-sub:#cfeaff;
  --hero-grad:linear-gradient(180deg,rgba(4,10,22,.55),rgba(4,10,22,0) 42%);
  --hero-seam:var(--bg);
  --hero-blob-a:rgba(14,165,233,.55); --hero-blob-b:rgba(124,58,237,.55); --hero-blob-c:rgba(34,211,238,.50);
  --hero-blob-op:.85;
  --sh-1:0 1px 2px rgba(15,34,49,.06),0 8px 24px rgba(15,34,49,.10);
  --sh-2:0 16px 38px rgba(14,165,233,.18);
  --r:14px; --r-lg:20px; --ease:cubic-bezier(.22,.61,.36,1);
  --frz1:44px;
}
@media (prefers-color-scheme:dark){ :root:not([data-theme]){
  --bg:#070d16; --wash:#0b1626; --surface:#0d1a2b; --surface-2:#0f2035;
  --panel:rgba(17,29,47,.62); --panel-solid:#0d1a2b;
  --row:#0d1a2b; --row-alt:#0f2035; --row-hover:#152b44;
  --head:#0a1626; --head-fg:#dbeafc;
  --text:#e8f1f8; --muted:#93a6b8; --line:rgba(120,170,210,.16); --stroke:rgba(120,170,210,.16);
  --val-up:#34d399; --val-dn:#fb7185; --val-neutral:#93a6b8;
  --vd-strong-bg:rgba(16,185,129,.16); --vd-strong-fg:#6ee7b7;
  --vd-good-bg:rgba(56,189,248,.16); --vd-good-fg:#7dd3fc;
  --vd-mid-bg:rgba(148,163,184,.14); --vd-mid-fg:#cbd5e1;
  --vd-bad-bg:rgba(244,63,94,.16); --vd-bad-fg:#fda4af;
  --vd-none-bg:rgba(148,163,184,.10); --vd-none-fg:#94a3b8;
  --sh-1:0 1px 2px rgba(0,0,0,.4),0 18px 44px -22px rgba(0,0,0,.8);
  --sh-2:0 24px 55px -22px rgba(0,0,0,.85);
}}
:root[data-theme="oscuro"]{ color-scheme:dark;
  --bg:#070d16; --wash:#0b1626; --surface:#0d1a2b; --surface-2:#0f2035;
  --panel:rgba(17,29,47,.62); --panel-solid:#0d1a2b;
  --row:#0d1a2b; --row-alt:#0f2035; --row-hover:#152b44;
  --head:#0a1626; --head-fg:#dbeafc;
  --text:#e8f1f8; --muted:#93a6b8; --line:rgba(120,170,210,.16); --stroke:rgba(120,170,210,.16);
  --val-up:#34d399; --val-dn:#fb7185; --val-neutral:#93a6b8;
  --vd-strong-bg:rgba(16,185,129,.16); --vd-strong-fg:#6ee7b7;
  --vd-good-bg:rgba(56,189,248,.16); --vd-good-fg:#7dd3fc;
  --vd-mid-bg:rgba(148,163,184,.14); --vd-mid-fg:#cbd5e1;
  --vd-bad-bg:rgba(244,63,94,.16); --vd-bad-fg:#fda4af;
  --vd-none-bg:rgba(148,163,184,.10); --vd-none-fg:#94a3b8;
  --sh-1:0 1px 2px rgba(0,0,0,.4),0 18px 44px -22px rgba(0,0,0,.8);
  --sh-2:0 24px 55px -22px rgba(0,0,0,.85);
}
:root[data-theme="claro"]{ color-scheme:light;
  --hero-bg:#0284c7; --hero-fg:#ffffff; --hero-sub:#eaf6ff;
  --hero-grad:linear-gradient(135deg,#0284c7 0%,#3b5bdb 45%,#7c3aed 75%,#22d3ee 100%);
  --hero-blob-a:rgba(255,255,255,.4); --hero-blob-b:rgba(124,58,237,.4); --hero-blob-c:rgba(34,211,238,.5);
  --hero-blob-op:.4;
}

/* ===================== BASE + FONDO ANIMADO ===================== */
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5}
body::after{content:"";position:fixed;inset:0;z-index:-2;pointer-events:none;
  background:radial-gradient(70% 45% at 50% 120%, var(--wash), transparent 60%), var(--bg)}
.aurora{position:fixed;inset:-20%;z-index:-1;pointer-events:none;overflow:hidden}
.aurora::before,.aurora::after{content:"";position:absolute;width:560px;height:560px;border-radius:50%;
  filter:blur(42px);opacity:var(--hero-blob-op);will-change:transform;backface-visibility:hidden}
.aurora::before{left:-8%;top:-14%;background:radial-gradient(circle at 35% 35%,var(--hero-blob-a),transparent 62%);
  animation:blobA 22s var(--ease) infinite alternate}
.aurora::after{right:-8%;bottom:-16%;background:radial-gradient(circle at 60% 40%,var(--hero-blob-b),transparent 60%);
  animation:blobB 30s var(--ease) infinite alternate}
@keyframes blobA{from{transform:translate3d(0,0,0) scale(1.05)} to{transform:translate3d(7vmax,5vmax,0) scale(1.16)}}
@keyframes blobB{from{transform:translate3d(0,0,0) scale(1.10)} to{transform:translate3d(-6vmax,-4vmax,0) scale(1.0)}}
@keyframes rise{from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){
  .aurora::before,.aurora::after,.cover::before{animation:none!important}
  *,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}
}

/* ===================== HERO ===================== */
.cover{position:relative;isolation:isolate;overflow:hidden;color:var(--hero-fg);
  padding:56px 30px 84px;border-radius:0 0 26px 26px;background:var(--hero-bg);
  box-shadow:0 18px 44px rgba(6,18,48,.28)}
.cover::before{content:"";position:absolute;inset:-35%;z-index:0;will-change:transform;
  background:radial-gradient(38% 52% at 22% 32%,var(--hero-blob-a),transparent 60%),
    radial-gradient(42% 58% at 78% 24%,var(--hero-blob-b),transparent 62%),
    radial-gradient(46% 60% at 58% 82%,var(--hero-blob-c),transparent 60%);
  filter:blur(34px) saturate(140%);opacity:var(--hero-blob-op);
  animation:blobA 20s var(--ease) infinite alternate}
.cover::after{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;
  background:var(--hero-grad),linear-gradient(180deg,transparent 68%,var(--hero-seam) 100%)}
.cover>*{position:relative;z-index:2;animation:rise .6s var(--ease) both}
.cover h1{margin:0 0 8px;font-size:clamp(24px,4.4vw,32px);letter-spacing:.2px;
  text-shadow:0 2px 30px rgba(34,211,238,.30);animation-delay:.10s}
.cover .sub{opacity:.95;font-size:clamp(13px,1.6vw,15px);max-width:760px;color:var(--hero-sub);animation-delay:.16s}
.pill{display:inline-block;margin-bottom:14px;padding:4px 13px;border-radius:999px;
  font-size:12px;font-weight:700;letter-spacing:.5px;
  background:rgba(255,255,255,.16);border:1px solid rgba(120,213,250,.5);color:var(--hero-fg);animation-delay:.05s}
.wrap{position:relative;z-index:3;max-width:1180px;margin:-56px auto 0;padding:0 22px 60px}

/* ===================== STATS / TITULOS / TEXTO ===================== */
.stats{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 8px}
.card{flex:1;min-width:150px;padding:15px 17px;border-radius:16px;background:var(--panel);
  border:1px solid var(--stroke);box-shadow:var(--sh-1);animation:rise .5s var(--ease) both;
  transition:transform .18s var(--ease),box-shadow .18s,border-color .18s}
.card:hover{transform:translateY(-3px);box-shadow:var(--sh-2);border-color:var(--neon)}
.stats .card:nth-child(2){animation-delay:.06s}.stats .card:nth-child(3){animation-delay:.12s}.stats .card:nth-child(4){animation-delay:.18s}
.card .n{font-size:27px;font-weight:800;color:var(--cel-d);letter-spacing:-.3px}
.card .l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
h2{margin:36px 0 6px;font-size:20px;color:var(--cel-d);border-left:5px solid var(--neon);padding-left:12px}
.note{color:var(--muted);font-size:13px;margin:0 0 14px}.note b{color:var(--text)}
.hint{color:var(--muted);font-size:12px;margin:8px 0 0}.hint b{color:var(--text)}
.soon{color:var(--muted);font-style:italic;font-size:12px}
.tk{font-weight:800;color:var(--cel-d)}.nm{color:var(--muted);font-size:12px}
.sec{font-size:12px;color:var(--muted)}.rank{font-weight:800;color:var(--cel-d);text-align:center}
.badge{display:inline-block;color:#fff;padding:2px 9px;border-radius:8px;font-weight:800;font-size:12.5px}
.v{font-weight:700}.v.val-up{color:var(--val-up)}.v.val-dn{color:var(--val-dn)}.v.val-mid{color:var(--val-neutral)}
.vd-strong{background:var(--vd-strong-bg);color:var(--vd-strong-fg)}
.vd-good{background:var(--vd-good-bg);color:var(--vd-good-fg)}
.vd-mid{background:var(--vd-mid-bg);color:var(--vd-mid-fg)}
.vd-bad{background:var(--vd-bad-bg);color:var(--vd-bad-fg)}
.vd-none{background:var(--vd-none-bg);color:var(--vd-none-fg)}

/* ===================== TOOLBAR / TEMA / ORDEN ===================== */
.toolbar{display:flex;align-items:center;gap:12px;margin:16px 0 2px;flex-wrap:wrap}
.toolbar .lbl{font-size:13px;color:var(--muted)}
.toolbar select{font:inherit;padding:6px 10px;border:1px solid var(--stroke);border-radius:10px;background:var(--panel-solid);color:var(--text);margin-left:6px}
.toolbar button{font:inherit;font-weight:800;padding:7px 16px;border:1px solid var(--cel);border-radius:10px;
  background:var(--cel);color:#04121c;cursor:pointer;transition:transform .12s var(--ease),background .18s,box-shadow .18s,color .18s}
.toolbar button:hover{background:var(--cel-d);border-color:var(--cel-d);box-shadow:var(--sh-2);transform:translateY(-1px);color:#eaf6ff}
.toolbar button:active{transform:translateY(0)}
.toolbar .counter{font-size:12.5px;color:var(--muted);margin-left:auto}
.themebar{display:inline-flex;gap:4px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:3px;margin-top:16px}
.themebar button{font:inherit;font-size:12px;font-weight:700;padding:4px 12px;border:0;border-radius:999px;background:transparent;color:var(--hero-fg);cursor:pointer;opacity:.7;transition:opacity .18s,background .18s}
.themebar button[aria-pressed="true"]{background:rgba(255,255,255,.22);opacity:1}
th.sortable{cursor:pointer;user-select:none;transition:background .18s,color .18s}
th.sortable:hover{background:#1b3a4a;color:#a5f3fc}
th.sortable.active{background:var(--cel-d);color:#eaf6ff}
th .caret{font-size:10px;margin-left:4px;color:var(--neon);opacity:0;transition:opacity .18s,transform .18s var(--ease);display:inline-block}
th.sortable.active .caret{opacity:1}

/* ===================== CALLOUTS / CHIPS / FOOT / A11Y ===================== */
.call{border:1px solid var(--stroke);border-left:5px solid var(--val-dn);border-radius:var(--r);padding:15px 18px;margin:26px 0;background:var(--panel);box-shadow:var(--sh-1)}
.call.blue{border-left-color:var(--cel)}
.call h3{margin:0 0 6px;font-size:15px;color:var(--val-dn)}.call.blue h3{color:var(--cel-d)}
.call ul{margin:6px 0 0 2px;padding-left:18px}.call li{margin:3px 0;font-size:13px}.call b{color:var(--text)}
.secbar{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 4px}
.chip{background:var(--panel);border:1px solid var(--stroke);border-radius:999px;padding:5px 13px;font-size:12px;color:var(--text);transition:transform .15s var(--ease),border-color .2s}
.chip:hover{transform:translateY(-2px);border-color:var(--neon)}
.foot{color:var(--muted);font-size:12px;margin-top:34px;border-top:1px solid var(--stroke);padding-top:14px}
:where(button,select,th.sortable,a):focus-visible{outline:2px solid var(--neon);outline-offset:2px;border-radius:8px}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  .card,.call,.chip,.toolbar select{background:var(--panel-solid)}
}

/* ===================== TABLA: scroller + header sticky + freeze ===================== */
.tablewrap{position:relative;margin-top:12px}
.tablescroll{overflow:auto;max-height:78vh;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;
  border:1px solid var(--stroke);border-radius:var(--r-lg);background:var(--row);
  scrollbar-width:thin;scrollbar-color:var(--cel) transparent}
.tablescroll::-webkit-scrollbar{height:10px;width:10px}
.tablescroll::-webkit-scrollbar-thumb{background:linear-gradient(90deg,var(--cel),var(--neon));border-radius:99px;border:2px solid transparent;background-clip:content-box}
.tablescroll::-webkit-scrollbar-track{background:transparent}
.tablewrap::after{content:"";position:absolute;top:0;right:0;bottom:0;width:44px;z-index:6;pointer-events:none;
  border-radius:0 var(--r-lg) var(--r-lg) 0;opacity:0;transition:opacity .2s;
  background:linear-gradient(to left,var(--bg),transparent)}
.tablewrap.can-right::after{opacity:1}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
#radar{min-width:1040px}
#radar th,#radar td{white-space:nowrap;box-shadow:inset 0 -1px 0 var(--stroke)}
#radar thead th{position:sticky;top:0;z-index:3;background:var(--head);color:var(--head-fg);
  text-align:left;padding:10px 11px;font-weight:600;font-size:11.6px}
#radar td{padding:8px 11px;vertical-align:middle;background:var(--row);color:var(--text)}
#radar tbody tr[data-sector]:nth-child(even) td{background:var(--row-alt)}
#radar tbody tr[data-sector]{transition:background .15s}
#radar tbody tr[data-sector]:hover td{background:var(--row-hover)}
#radar th:nth-child(1),#radar tbody tr[data-sector] td:nth-child(1){position:sticky;left:0;z-index:2;text-align:center;
  width:var(--frz1);min-width:var(--frz1);max-width:var(--frz1)}
#radar th:nth-child(2),#radar tbody tr[data-sector] td:nth-child(2){position:sticky;left:var(--frz1);z-index:2;min-width:172px;white-space:normal;
  box-shadow:6px 0 12px -8px rgba(15,34,49,.35),inset 0 -1px 0 var(--stroke)}
#radar thead th:nth-child(1),#radar thead th:nth-child(2){z-index:5;background:var(--head)}
#radar tbody tr[data-sector] td:nth-child(1),#radar tbody tr[data-sector] td:nth-child(2){background:var(--row)}
#radar tbody tr[data-sector]:nth-child(even) td:nth-child(1),
#radar tbody tr[data-sector]:nth-child(even) td:nth-child(2){background:var(--row-alt)}
#radar tbody tr[data-sector]:hover td:nth-child(1),
#radar tbody tr[data-sector]:hover td:nth-child(2){background:var(--row-hover)}
#radar tbody tr[data-sector]:hover td:nth-child(1){box-shadow:inset 3px 0 0 var(--neon),inset 0 -1px 0 var(--stroke)}

/* ===================== MODO TARJETA (<900px) ===================== */
@media (max-width:900px){
  .tablewrap::after{display:none}
  .tablescroll{overflow:visible;max-height:none;border:0;background:transparent}
  #radar{min-width:0;width:100%}
  #radar thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  #radar,#radar tbody{display:block}
  #radar tbody tr[data-sector]{display:block;position:relative;margin:0 0 14px;padding:12px 16px;
    background:var(--panel-solid);border:1px solid var(--stroke);border-left:4px solid var(--neon);
    border-radius:var(--r-lg);box-shadow:var(--sh-1)}
  #radar tbody tr[data-sector] td{display:flex;justify-content:space-between;align-items:center;gap:16px;
    width:auto;white-space:normal;text-align:right;padding:7px 0;position:static!important;
    background:transparent!important;box-shadow:inset 0 -1px 0 var(--stroke)!important}
  #radar tbody tr[data-sector] td::before{color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:.4px;text-align:left;margin-right:auto}
  #radar td:nth-child(1){display:none}
  #radar td:nth-child(2){display:block;text-align:left;font-size:15px;padding:0 0 9px;margin-bottom:6px;border-bottom:1px solid var(--stroke)}
  #radar td:nth-child(2)::before{content:""}
  #radar td:nth-child(3)::before{content:"Rank S&P"}
  #radar td:nth-child(4)::before{content:"Sector"}
  #radar td:nth-child(5)::before{content:"Precio"}
  #radar td:nth-child(6)::before{content:"Caida"}
  #radar td:nth-child(7)::before{content:"Dias desde pico"}
  #radar td:nth-child(8)::before{content:"Severidad"}
  #radar td:nth-child(9){display:block;text-align:left}
  #radar td:nth-child(9)::before{content:"Ultimo ano";display:block;margin-bottom:5px}
  #radar td:nth-child(10)::before{content:"vs Ind."}
  #radar td:nth-child(11)::before{content:"vs Hist."}
  #radar td:nth-child(12)::before{content:"Valor"}
  #radar td:nth-child(13)::before{content:"Veredicto"}
  #radar td:nth-child(14)::before{content:"Calidad"}
  #radar td:nth-child(9) img{width:100%;max-width:200px;margin-left:auto}
}

/* ===================== IMPRESION (A4 landscape) ===================== */
@media print{
  @page{size:A4 landscape;margin:12mm}
  .aurora,.themebar,.toolbar,.tablewrap::after,.hint{display:none!important}
  body::after{display:none}
  .cover{background:#0b3a55!important;color:#fff;box-shadow:none;padding:22px 18px;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .cover::before,.cover::after{display:none}
  .wrap{margin-top:16px;max-width:none}
  .card,.call,.chip{background:#fff!important;color:#0b1220;box-shadow:none;border:1px solid #ccd;break-inside:avoid}
  .tablescroll{overflow:visible;max-height:none;border:1px solid #cbd5e1}
  table,#radar{min-width:0}
  #radar{font-size:9.5px}
  #radar thead th{position:static;background:#0f2231!important;color:#fff!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  #radar th:nth-child(1),#radar th:nth-child(2),
  #radar tbody tr[data-sector] td:nth-child(1),#radar tbody tr[data-sector] td:nth-child(2){position:static;box-shadow:inset 0 -1px 0 #e2e8f0}
  #radar td{background:#fff!important;color:#0b1220!important;box-shadow:inset 0 -1px 0 #e2e8f0}
  .v.val-up{color:#047857!important}.v.val-dn{color:#be123c!important}.v.val-mid{color:#475569!important}
  .badge,.vd-strong,.vd-good,.vd-mid,.vd-bad,.vd-none{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  #radar tbody tr{break-inside:avoid}
}

/* ============ velas + destellos (hero) + KPI de vidrio + eco de pagina ============ */
.cover{padding:56px 30px 92px;
  background:radial-gradient(125% 95% at 24% -14%, rgba(21,110,190,.55), transparent 58%), var(--hero-bg)}
.cover-fx{position:absolute;inset:0;z-index:0;overflow:hidden;pointer-events:none;animation:none}
.candles{position:absolute;left:0;right:0;bottom:-4%;height:74%;opacity:.5;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);
  animation:bob 9s var(--ease) infinite alternate}
.candles-track{display:flex;width:200%;height:100%;
  filter:drop-shadow(0 0 6px rgba(34,211,238,.45));will-change:transform;animation:drift 44s linear infinite}
.candles-track svg{flex:0 0 50%;width:50%;height:100%;display:block}
.sparkles{position:absolute;inset:0}
.sparkles::before,.sparkles::after{content:"";position:absolute;inset:0;will-change:opacity}
.sparkles::before{background:
  radial-gradient(1.6px 1.6px at 12% 26%,#fff,transparent),
  radial-gradient(1.4px 1.4px at 28% 62%,#a5f3fc,transparent),
  radial-gradient(1.8px 1.8px at 46% 32%,#fff,transparent),
  radial-gradient(1.3px 1.3px at 63% 58%,#7dd3fc,transparent),
  radial-gradient(1.6px 1.6px at 79% 28%,#fff,transparent),
  radial-gradient(1.4px 1.4px at 90% 64%,#a5f3fc,transparent);
  animation:twinkle 3.4s ease-in-out infinite}
.sparkles::after{background:
  radial-gradient(1.3px 1.3px at 18% 48%,#7dd3fc,transparent),
  radial-gradient(1.5px 1.5px at 37% 20%,#fff,transparent),
  radial-gradient(1.4px 1.4px at 55% 72%,#a5f3fc,transparent),
  radial-gradient(1.6px 1.6px at 72% 42%,#fff,transparent),
  radial-gradient(1.3px 1.3px at 85% 22%,#7dd3fc,transparent);
  animation:twinkle 4.6s ease-in-out .8s infinite}
@keyframes drift{from{transform:translate3d(0,0,0)} to{transform:translate3d(-50%,0,0)}}
@keyframes bob{from{transform:translate3d(0,0,0)} to{transform:translate3d(0,-3%,0)}}
@keyframes twinkle{0%,100%{opacity:.3} 50%{opacity:1}}

.wrap{margin-top:22px}
.stats{display:flex;flex-wrap:wrap;gap:14px;margin:24px 0 0}
.kpi{flex:1;min-width:148px;padding:14px 16px;border-radius:16px;
  background:rgba(255,255,255,.07);border:1px solid rgba(140,200,240,.28);
  box-shadow:0 10px 26px rgba(3,14,32,.4),0 0 26px var(--acc-glow,rgba(34,211,238,.16));
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  animation:rise .5s var(--ease) both;transition:transform .18s var(--ease),box-shadow .18s,border-color .18s}
.kpi:hover{transform:translateY(-3px);border-color:var(--acc,#7dd3fc);
  box-shadow:0 14px 34px rgba(3,14,32,.5),0 0 34px var(--acc-glow,rgba(34,211,238,.3))}
.stats .kpi:nth-child(2){animation-delay:.06s}.stats .kpi:nth-child(3){animation-delay:.12s}.stats .kpi:nth-child(4){animation-delay:.18s}
.kpi .ic{width:30px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center;
  background:var(--acc-soft,rgba(34,211,238,.16));color:var(--acc,#7dd3fc);margin-bottom:9px}
.kpi .ic svg{width:17px;height:17px}
.kpi .n{font-size:26px;font-weight:800;letter-spacing:-.3px;line-height:1.1;color:var(--acc,#eaf6ff)}
.kpi .l{font-size:11.5px;color:var(--hero-sub);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
.kpi-cel{--acc:#38bdf8;--acc-soft:rgba(56,189,248,.18);--acc-glow:rgba(56,189,248,.22)}
.kpi-neon{--acc:#22d3ee;--acc-soft:rgba(34,211,238,.18);--acc-glow:rgba(34,211,238,.24)}
.kpi-amber{--acc:#fbbf24;--acc-soft:rgba(251,191,36,.2);--acc-glow:rgba(251,191,36,.2)}
.kpi-violet{--acc:#a78bfa;--acc-soft:rgba(167,139,250,.22);--acc-glow:rgba(167,139,250,.22)}

.page-fx{position:fixed;left:0;right:0;bottom:0;height:56vh;z-index:-1;pointer-events:none;opacity:.06;overflow:hidden;
  -webkit-mask-image:linear-gradient(180deg,transparent,#000 45%);mask-image:linear-gradient(180deg,transparent,#000 45%)}
.page-fx .candles-track{filter:none;animation-duration:120s}

@media print{ .cover-fx,.page-fx{display:none!important} }
@media (prefers-reduced-motion:reduce){ .candles,.candles-track,.sparkles::before,.sparkles::after{animation:none!important} }

/* ====== velas detras del contenido + tabla translucida + marca de agua ====== */
:root{--row:rgba(255,255,255,.66);--row-alt:rgba(240,249,255,.66);--row-hover:rgba(223,244,255,.88);--row-solid:#ffffff;--echo-op:.14}
@media (prefers-color-scheme:dark){:root:not([data-theme]){--row:rgba(13,26,43,.58);--row-alt:rgba(16,32,53,.58);--row-hover:rgba(22,43,68,.88);--row-solid:#0b1626;--echo-op:.24}}
:root[data-theme="oscuro"]{--row:rgba(13,26,43,.58);--row-alt:rgba(16,32,53,.58);--row-hover:rgba(22,43,68,.88);--row-solid:#0b1626;--echo-op:.24}

.page-fx{top:24vh;bottom:0;height:auto;opacity:var(--echo-op,.14);
  -webkit-mask-image:linear-gradient(180deg,transparent,#000 20%,#000 86%,transparent);
  mask-image:linear-gradient(180deg,transparent,#000 20%,#000 86%,transparent)}
.page-fx .candles-track{height:100%;filter:blur(1.4px);animation-duration:90s}
.tablescroll{background:transparent}
#radar thead th:nth-child(1),#radar thead th:nth-child(2){background:var(--head)}
#radar tbody tr[data-sector] td:nth-child(1),#radar tbody tr[data-sector] td:nth-child(2){background:var(--row-solid)}
#radar tbody tr[data-sector]:nth-child(even) td:nth-child(1),
#radar tbody tr[data-sector]:nth-child(even) td:nth-child(2){background:var(--row-solid)}
#radar tbody tr[data-sector]:hover td:nth-child(1),
#radar tbody tr[data-sector]:hover td:nth-child(2){background:var(--row-hover)}

/* marca del autor + watermark */
.byline{margin-top:12px;font-size:12.5px;color:var(--hero-sub);display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.byline b{color:var(--hero-fg)}
.byline .soc{display:inline-flex;align-items:center;gap:4px;text-decoration:none;color:var(--hero-sub)}
.byline .soc svg{width:15px;height:15px}
.byline .soc-in{color:#3b9be8}
.byline a.soc-ig{color:#f472a6}
.byline a.soc-ig:hover{text-decoration:underline}
.foot .credit{margin-top:9px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.foot .credit b{color:var(--text)}
.foot .credit .soc{display:inline-flex;align-items:center;gap:4px;text-decoration:none;color:var(--muted)}
.foot .credit .soc svg{width:15px;height:15px}
.foot .credit .soc-in{color:#0a66c2}
.foot .credit a.soc-ig{color:#c1358a}
.watermark{position:fixed;right:12px;bottom:11px;z-index:20;pointer-events:none;display:flex;align-items:center;gap:6px;
  font-size:11px;font-weight:700;letter-spacing:.2px;color:var(--muted);background:var(--panel);
  border:1px solid var(--stroke);border-radius:999px;padding:4px 11px;box-shadow:var(--sh-1);opacity:.74}
.watermark svg{width:13px;height:13px}
.watermark .wm-ig{color:#c1358a;display:inline-flex}
@media (max-width:900px){.watermark{display:none}}
@media print{.watermark{display:none!important}}

/* ====== tema OSCURO afinado a azul "ligeramente oscuro" (default) + textos legibles ====== */
@media (prefers-color-scheme:dark){:root:not([data-theme]){
  --bg:#0a1a2e;--wash:#0e2138;--surface:#102843;--surface-2:#14314f;
  --panel:rgba(18,42,68,.62);--panel-solid:#102843;
  --row:rgba(16,38,62,.56);--row-alt:rgba(20,46,74,.56);--row-hover:rgba(28,58,90,.85);--row-solid:#0e2038;
  --head:#0a1c32;--echo-op:.28}}
:root[data-theme="oscuro"]{
  --bg:#0a1a2e;--wash:#0e2138;--surface:#102843;--surface-2:#14314f;
  --panel:rgba(18,42,68,.62);--panel-solid:#102843;
  --row:rgba(16,38,62,.56);--row-alt:rgba(20,46,74,.56);--row-hover:rgba(28,58,90,.85);--row-solid:#0e2038;
  --head:#0a1c32;--echo-op:.28}
@media (prefers-color-scheme:dark){:root:not([data-theme]) :is(h2,.tk,.rank,.call.blue h3){color:#7dd3fc}}
:root[data-theme="oscuro"] :is(h2,.tk,.rank,.call.blue h3){color:#7dd3fc}

/* badge de calidad "fragil" (ambar, theme-aware) */
:root{--vd-warn-bg:#fef3c7;--vd-warn-fg:#92400e}
@media (prefers-color-scheme:dark){:root:not([data-theme]){--vd-warn-bg:rgba(251,191,36,.16);--vd-warn-fg:#fcd34d}}
:root[data-theme="oscuro"]{--vd-warn-bg:rgba(251,191,36,.16);--vd-warn-fg:#fcd34d}
.q-frag{background:var(--vd-warn-bg);color:var(--vd-warn-fg)}

/* Fase 4: noticias */
.newsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;margin-top:10px}
.newscard{background:var(--panel);border:1px solid var(--stroke);border-radius:14px;padding:13px 16px;box-shadow:var(--sh-1)}
.newshead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:9px;padding-bottom:8px;border-bottom:1px solid var(--stroke)}
.newslist{list-style:none;margin:0;padding:0}
.newslist li{margin:0 0 10px}
.newslist li:last-child{margin-bottom:0}
.newslist a{color:var(--text);text-decoration:none;font-weight:600;font-size:13px;line-height:1.35;display:block}
.newslist a:hover{color:var(--neon);text-decoration:underline}
.newsmeta{color:var(--muted);font-size:11px;margin-top:2px;display:block}
"""

# JS vanilla (sin librerias): ordenar por clic, filtrar por sector, reset, renumerar "#",
# sombra-indicador de scroll y switcher de tema (persistente).
SCRIPT = r"""<script>
(function(){
  var table=document.getElementById('radar'); if(!table||!table.tBodies.length) return;
  var tbody=table.tBodies[0];
  var original=Array.prototype.slice.call(tbody.rows);
  var total=original.filter(function(r){return r.querySelector('.rownum');}).length;
  var sel=document.getElementById('sectorFilter');
  var counter=document.getElementById('counter');
  var resetBtn=document.getElementById('resetBtn');
  var curKey=null,curDir=null;
  function renumber(){
    var n=0;
    Array.prototype.slice.call(tbody.rows).forEach(function(r){
      var c=r.querySelector('.rownum'); if(!c) return;
      if(r.style.display==='none') return;
      n++; c.textContent=n;
    });
    if(counter) counter.textContent='mostrando '+n+' de '+total;
  }
  function clearCarets(){
    table.querySelectorAll('th.sortable').forEach(function(t){
      t.classList.remove('active'); t.removeAttribute('aria-sort');
      var c=t.querySelector('.caret'); if(c) c.textContent='';
    });
  }
  function sortBy(th){
    var type=th.getAttribute('data-type'), def=th.getAttribute('data-dir')||'asc';
    var key=th.getAttribute('data-key');
    if(curKey===key){curDir=(curDir==='asc'?'desc':'asc');} else {curKey=key;curDir=def;}
    var idx=th.cellIndex;
    var rows=Array.prototype.slice.call(tbody.rows);
    rows.sort(function(a,b){
      var av=a.cells[idx]?a.cells[idx].getAttribute('data-sort'):null;
      var bv=b.cells[idx]?b.cells[idx].getAttribute('data-sort'):null;
      var r;
      if(type==='num'){
        var an=parseFloat(av),bn=parseFloat(bv),ax=isNaN(an),bx=isNaN(bn);
        r=(ax&&bx)?0:ax?1:bx?-1:an-bn;
      } else { r=(av||'').localeCompare(bv||''); }
      return curDir==='asc'?r:-r;
    });
    rows.forEach(function(r){tbody.appendChild(r);});
    clearCarets(); th.classList.add('active');
    th.setAttribute('aria-sort', curDir==='asc'?'ascending':'descending');
    var c=th.querySelector('.caret'); if(c) c.textContent=(curDir==='asc'?'▲':'▼');
    renumber();
  }
  table.querySelectorAll('th.sortable').forEach(function(th){
    th.tabIndex=0; th.setAttribute('role','button');
    th.addEventListener('click',function(){sortBy(th);});
    th.addEventListener('keydown',function(e){
      if(e.key==='Enter'||e.key===' '){e.preventDefault();sortBy(th);}
    });
  });
  if(sel) sel.addEventListener('change',function(){
    var v=sel.value;
    Array.prototype.slice.call(tbody.rows).forEach(function(r){
      if(!r.querySelector('.rownum')) return;
      var s=r.getAttribute('data-sector')||'';
      r.style.display=(v==='__all__'||s===v)?'':'none';
    });
    renumber();
  });
  if(resetBtn) resetBtn.addEventListener('click',function(){
    original.forEach(function(r){r.style.display='';tbody.appendChild(r);});
    if(sel) sel.value='__all__';
    curKey=null;curDir=null;clearCarets();renumber();
  });
  renumber();
})();
/* sombra derecha reactiva del scroller */
(function(){var sc=document.querySelector('.tablescroll');if(!sc)return;var f=sc.parentElement;
  function e(){f.classList.toggle('can-right',sc.scrollLeft < sc.scrollWidth-sc.clientWidth-1);}
  sc.addEventListener('scroll',e,{passive:true});window.addEventListener('resize',e);e();})();
/* switcher de tema (Auto = sigue al SO) con persistencia */
(function(){var root=document.documentElement,bar=document.querySelector('.themebar');if(!bar)return;
  function apply(v){ if(v==='auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme',v);
    bar.querySelectorAll('button').forEach(function(b){b.setAttribute('aria-pressed', b.dataset.set===v);}); }
  var saved=null; try{saved=localStorage.getItem('scanTheme2');}catch(e){}
  apply(saved||'oscuro');
  bar.addEventListener('click',function(ev){var b=ev.target.closest('button');if(!b)return;
    try{localStorage.setItem('scanTheme2',b.dataset.set);}catch(e){} apply(b.dataset.set);});})();
</script>"""


def _esc(x):
    return _html.escape(str(x))


def _num2(x):
    try:
        f = float(x)
        return f if f == f else None   # descarta NaN
    except (TypeError, ValueError):
        return None


def _valcolor(kind, v):
    """Devuelve una CLASE (no hex) para que el color viva en tokens y sea theme-aware."""
    up, dn, mid = "val-up", "val-dn", "val-mid"
    if kind == "disc":   # descuento vs pares (fraccion): verde = barato
        return up if v < -0.10 else (dn if v > 0.10 else mid)
    if kind == "hist":   # percentil 0-100: verde = barato vs su historia
        return up if v < 33 else (dn if v > 66 else mid)
    if kind == "valz":   # score compuesto: verde = mas barato
        return up if v > 0.3 else (dn if v < -0.3 else mid)
    return mid


_VERDICT_CLASS = {
    "barata de verdad":      "vd-strong",
    "algo barata":           "vd-good",
    "en precio":             "vd-mid",
    "cara (cayo pero cara)": "vd-bad",
    "sin datos":             "vd-none",
}

_QUAL_CLASS = {
    "sana": "vd-strong", "aceptable": "vd-good", "fragil": "q-frag",
    "posible trampa": "vd-bad", "sin datos": "vd-none",
}


def _qual_cell(r):
    """Celda de Calidad (Fase 3): veredicto + F-score, flags en tooltip. Fallback = 'Fase 3'."""
    v = r.get("quality_verdict")
    if not isinstance(v, str) or not v:
        return '<td class="soon" data-sort="">Fase 3</td>'
    cls = _QUAL_CLASS.get(v, "vd-mid")
    P = _num2(r.get("piotroski"))
    ptxt = f" &middot; F{int(P)}" if P is not None else ""
    qs = _num2(r.get("quality_score"))
    sort = f"{qs:.2f}" if qs is not None else ""
    flags = r.get("flags")
    title = "; ".join(flags) if isinstance(flags, list) and flags else v
    return (f'<td data-sort="{sort}" title="{_esc(title)}">'
            f'<span class="badge {cls}">{_esc(v)}{ptxt}</span></td>')


def _val_cells(r, has_val):
    """Devuelve las 4 celdas de valuacion + la de calidad."""
    if not has_val:
        soon = '<td class="soon" data-sort="">Fase 2</td>'
        return soon * 4 + '<td class="soon" data-sort="">Fase 3</td>'
    # vs Industria (descuento del P/E vs mediana de industria)
    d = _num2(r.get("disc_vs_peer"))
    if d is None:
        ind = '<td data-sort="" class="soon">&mdash;</td>'
    else:
        bs = " <span class='nm'>(sec)</span>" if r.get("peer_basis") == "sector" else ""
        ind = f'<td class="v {_valcolor("disc", d)}" data-sort="{d:.4f}">{d*100:+.0f}%{bs}</td>'
    # vs Historia (percentil del multiplo vs sus 5 anios)
    h = _num2(r.get("ownhist_pctl"))
    hist = ('<td data-sort="" class="soon">&mdash;</td>' if h is None else
            f'<td class="v {_valcolor("hist", h)}" data-sort="{h:.2f}">p{h:.0f}</td>')
    # score compuesto de valor
    vz = _num2(r.get("value_z"))
    val = ('<td data-sort="" class="soon">&mdash;</td>' if vz is None else
           f'<td class="v {_valcolor("valz", vz)}" data-sort="{vz:.4f}">{vz:+.2f}</td>')
    # veredicto (pill theme-aware por clase)
    verd = str(r.get("val_verdict") or "sin datos")
    cls = _VERDICT_CLASS.get(verd, "vd-mid")
    vcell = f'<td data-sort="{_esc(verd)}"><span class="badge {cls}">{_esc(verd)}</span></td>'
    return ind + hist + val + vcell + _qual_cell(r)


def _radar_rows(df, prices):
    has_val = "val_verdict" in df.columns
    out = []
    for i, r in df.iterrows():
        sym = r["symbol"]
        spark = ""
        if sym in prices.columns:
            spark = f'<img alt="" src="data:image/png;base64,{_sparkline(prices[sym])}">'
        color = _drop_color(r["drop_pct"])
        name = r.get("name", "")
        sector = r.get("sector", "")
        try:
            rk = int(r.get("sp500_rank"))
            rank_disp, rank_sort = f"#{rk}", rk
        except (TypeError, ValueError):
            rank_disp, rank_sort = "&mdash;", 99999
        mark = ('<sup title="datos yfinance" style="color:#f59e0b">&asymp;</sup>'
                if has_val and r.get("source") == "yfinance" else "")
        out.append(f"""<tr data-sector="{_esc(sector)}">
  <td class="rownum">{i+1}</td>
  <td data-sort="{_esc(sym)}"><span class="tk">{_esc(sym)}</span>{mark}<br><span class="nm">{_esc(name)}</span></td>
  <td class="rank" data-sort="{rank_sort}">{rank_disp}</td>
  <td class="sec" data-sort="{_esc(sector)}">{_esc(sector)}</td>
  <td data-sort="{r['price']:.4f}">${r['price']:,.2f}</td>
  <td data-sort="{r['drop_pct']:.4f}"><span class="badge" style="background:{color}">{r['drop_pct']:.1f}%</span></td>
  <td data-sort="{int(r['days_since_peak'])}">{int(r['days_since_peak'])} d</td>
  <td data-sort="{r['severity_pctl']:.4f}">{r['severity_pctl']:.0f}</td>
  <td>{spark}</td>
  {_val_cells(r, has_val)}
</tr>""")
    return "\n".join(out)


def build_report(candidates, prices, universe, warns=None, path=None, news=None):
    warns = warns or {}
    n_uni = len(universe)
    n_cand = len(candidates)
    ts = time.strftime("%Y-%m-%d %H:%M")
    candles = _candles_svg()

    # enriquecer candidatos con nombre/sector/rank del universo
    ucols = [c for c in ("name", "sector", "sp500_rank") if c in universe.columns]
    meta = universe.set_index("symbol")[ucols]
    cand = candidates.copy()
    for c in ucols:
        cand[c] = cand["symbol"].map(meta[c])

    avg_drop = cand["drop_pct"].mean() if n_cand else 0.0
    has_val = "value_z" in cand.columns
    has_qual = "quality_verdict" in cand.columns
    has_news = bool(news)

    # ---- vista canasta: score final (valor+calidad) excluyendo trampas; si no, por valor/severidad
    if has_qual:
        pool = cand[cand["quality_verdict"] != "posible trampa"]
        if not len(pool):
            pool = cand
        basket = pool.sort_values("final_score", ascending=False).head(C.BASKET_TOP_N)
    elif has_val:
        basket = cand.sort_values("value_z", ascending=False).head(C.BASKET_TOP_N)
    else:
        basket = cand.head(C.BASKET_TOP_N)
    sec_counts = basket["sector"].value_counts()
    sec_chips = "".join(f'<span class="chip">{_esc(s)} &middot; {c}</span>'
                        for s, c in sec_counts.items())

    sectors = sorted(set(cand["sector"].dropna().astype(str))) if n_cand else []
    sector_opts = "".join(f'<option value="{_esc(s)}">{_esc(s)}</option>' for s in sectors)

    radar = _radar_rows(cand, prices) if n_cand else \
        '<tr><td colspan="14" class="soon">Ninguna empresa del universo esta caida en la banda ' \
        f'{int(C.DROP_MIN*100)}-{int(C.DROP_MAX*100)}% con pico reciente hoy.</td></tr>'

    # texto honesto adaptado a la fase disponible
    if has_qual:
        fase_li = ("<li>Cruza <b>precio + valuacion + calidad</b>. La columna <b>Calidad</b> marca "
                   "sana / aceptable / fragil / <b>posible trampa</b> (Piotroski F, Altman Z, margenes, "
                   "apalancamiento, momentum + flags; pasa el mouse por la etiqueta para ver los flags).</li>")
        fase_foot = ("Fase 4 (precio + valuacion + calidad + noticias)" if has_news
                     else "Fase 3 (precio + valuacion + calidad)")
    elif has_val:
        fase_li = ("<li>Esta version cruza <b>precio + valuacion</b> (vs industria y vs su historia). "
                   "Falta la <b>Fase 3 (calidad / anti-trampa)</b>: barato NO implica sano.</li>")
        fase_foot = "Fase 2 (precio + valuacion)"
    else:
        fase_li = ("<li>Esta es la <b>Fase 1 (solo precio)</b>. Falta el cruce que separa oportunidad de "
                   "trampa: valuacion (Fase 2) y calidad/anti-trampa (Fase 3).</li>")
        fase_foot = "Fase 1 (precio)"

    if has_qual:
        basket_note = "Ranking por score final (valor + calidad); descarta las 'posible trampa'."
    elif has_val:
        basket_note = "Ranking por score compuesto de valor."
    else:
        basket_note = "Ranking preliminar por severidad (mejora con la Fase 2)."

    # ---- Fase 4: noticias por candidato (el porque) ----
    news_html = ""
    if news:
        order = cand.sort_values("final_score", ascending=False) if "final_score" in cand.columns else cand
        blocks = []
        for _, r in order.iterrows():
            items = news.get(r["symbol"]) or []
            if not items:
                continue
            qv = r.get("quality_verdict")
            pill = (f'<span class="badge {_QUAL_CLASS.get(qv, "vd-mid")}">{_esc(qv)}</span>'
                    if isinstance(qv, str) and qv else "")
            lis = "".join(
                f'<li><a href="{_esc(it.get("url"))}" target="_blank" rel="noopener">{_esc(it.get("title"))}</a>'
                f'<span class="newsmeta">{_esc(it.get("date") or "")} &middot; {_esc(it.get("source") or "")}</span></li>'
                for it in items[:3])
            blocks.append(f'<div class="newscard"><div class="newshead">'
                          f'<span class="tk">{_esc(r["symbol"])}</span> '
                          f'<span class="nm">{_esc(r.get("name", ""))}</span> {pill}</div>'
                          f'<ul class="newslist">{lis}</ul></div>')
        if blocks:
            news_html = ('<h2>Noticias &mdash; el porque de cada caida</h2>'
                         '<p class="note">Titulares recientes por candidato para entender el <b>motivo</b>. '
                         'La maquina trae el contexto; el veredicto de si es <b>temporal</b> (oportunidad) o '
                         '<b>estructural</b> (trampa) lo das tu.</p>'
                         f'<div class="newsgrid">{"".join(blocks)}</div>')

    warn_html = ""
    if warns:
        items = "".join(f"<li><b>{_esc(s)}</b>: {_esc(', '.join(v))}</li>"
                        for s, v in list(warns.items())[:20])
        warn_html = f"""<div class="call blue"><h3>Avisos de datos ({len(warns)})</h3>
<div class="note">Revisar antes de confiar en la caida: posibles ticks malos, splits o historico corto.</div>
<ul>{items}</ul></div>"""

    doc = f"""<!doctype html><html lang="es" data-theme="oscuro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scanner Value en Crisis &middot; {ts}</title><style>{CSS}</style></head><body>
<div class="aurora" aria-hidden="true"></div>
<div class="page-fx" aria-hidden="true"><div class="candles-track">{candles}{candles}</div></div>
<div class="cover">
  <div class="cover-fx" aria-hidden="true"><div class="candles"><div class="candles-track">{candles}{candles}</div></div><div class="sparkles"></div></div>
  <span class="pill">SCANNER &middot; VALUE EN CRISIS</span>
  <h1>Blue chips caidas desde su pico</h1>
  <div class="sub">Universo: top {n_uni} del S&amp;P 500 por capitalizacion &middot;
  Filtro: caida {int(C.DROP_MIN*100)}&ndash;{int(C.DROP_MAX*100)}% desde el pico movil de
  {C.PEAK_WINDOW_DAYS//21} meses, ocurrido en el ultimo ano. Generado {ts}.</div>
  
  </div>
  <div class="themebar" role="group" aria-label="Tema">
    <button data-set="auto">Auto</button>
    <button data-set="claro">Claro</button>
    <button data-set="hibrido">Hibrido</button>
    <button data-set="oscuro" aria-pressed="true">Oscuro</button>

  </div>
  <div class="stats">
    <div class="kpi kpi-cel"><div class="ic">{_IC_UNIVERSO}</div><div class="n">{n_uni}</div><div class="l">Universo</div></div>
    <div class="kpi kpi-neon"><div class="ic">{_IC_CAND}</div><div class="n">{n_cand}</div><div class="l">Candidatos</div></div>
    <div class="kpi kpi-amber"><div class="ic">{_IC_DROP}</div><div class="n">{avg_drop:.0f}%</div><div class="l">Caida media</div></div>
    <div class="kpi kpi-violet"><div class="ic">{_IC_SECT}</div><div class="n">{len(sec_counts)}</div><div class="l">Sectores tocados</div></div>
  </div>
</div>
<div class="wrap">


  <div class="call">
    <h3>HONESTIDAD ANTE TODO &mdash; leer antes de invertir</h3>
    <ul>
      <li>Esto es una <b>lista de investigacion, NO una recomendacion de compra</b>. La caida
          sola no es senal: ~1 de cada 5 blue chips que caen &lt;50% <b>nunca</b> recupera su pico.</li>
      <li>El edge documentado es <b>estadistico y de canasta</b> (grupo diversificado, 3&ndash;5 anos),
          no una proyeccion fiable de una sola accion.</li>
      {fase_li}
      <li>Universo = S&amp;P 500 <i>de hoy</i> &rarr; <b>sesgo de supervivencia</b>: no ve a las que ya cayeron y murieron.</li>
    </ul>
  </div>

  <h2>Vista RADAR &mdash; candidatos para investigar</h2>
  <p class="note">Uno por uno. Orden inicial por severidad. <b>Haz clic en cualquier encabezado
  para ordenar</b> (otro clic invierte). Valuacion: <b>vs Ind.</b> = P/E vs la mediana de su
  industria (negativo = barata que sus pares); <b>vs Hist.</b> = percentil vs sus 5 anios (bajo =
  barata para si misma); <b>Valor</b> = score compuesto (alto = mas barata); <b>Calidad</b> = anti-trampa
  (sana/aceptable/fragil/posible trampa &mdash; pasa el mouse por la etiqueta para ver los flags). &asymp; = datos de yfinance.</p>
  <div class="toolbar">
    <span class="lbl">Sector
      <select id="sectorFilter"><option value="__all__">Todos los sectores</option>{sector_opts}</select>
    </span>
    <button id="resetBtn" type="button">&#8635; Reset</button>
    <span id="counter" class="counter"></span>
  </div>
  <div class="tablewrap"><div class="tablescroll">
  <table id="radar">
    <thead><tr>
      <th>#</th>
      <th class="sortable" data-key="empresa" data-type="text" data-dir="asc">Empresa<span class="caret"></span></th>
      <th class="sortable" data-key="rank" data-type="num" data-dir="asc">Rank S&amp;P<span class="caret"></span></th>
      <th class="sortable" data-key="sector" data-type="text" data-dir="asc">Sector<span class="caret"></span></th>
      <th class="sortable" data-key="precio" data-type="num" data-dir="desc">Precio<span class="caret"></span></th>
      <th class="sortable" data-key="caida" data-type="num" data-dir="asc">Caida<span class="caret"></span></th>
      <th class="sortable" data-key="dias" data-type="num" data-dir="desc">Dias<span class="caret"></span></th>
      <th class="sortable" data-key="sev" data-type="num" data-dir="asc">Sev.<span class="caret"></span></th>
      <th>1 ano</th>
      <th class="sortable" data-key="vsind" data-type="num" data-dir="asc" title="P/E vs la mediana de su industria (negativo = barata vs pares)">vs Ind.<span class="caret"></span></th>
      <th class="sortable" data-key="vshist" data-type="num" data-dir="asc" title="percentil del multiplo vs sus ultimos 5 anios (bajo = barata vs su historia)">vs Hist.<span class="caret"></span></th>
      <th class="sortable" data-key="valz" data-type="num" data-dir="desc" title="score compuesto de valor (alto = mas barata)">Valor<span class="caret"></span></th>
      <th class="sortable" data-key="verd" data-type="text" data-dir="asc">Veredicto<span class="caret"></span></th>
      <th class="sortable" data-key="cal" data-type="num" data-dir="desc">Calidad<span class="caret"></span></th>
    </tr></thead>
    <tbody>{radar}</tbody>
  </table></div></div>
  <p class="hint">El <b>#</b> es el orden en pantalla (se renumera al ordenar/filtrar).
  <b>Rank S&amp;P</b> es el puesto de la empresa por tamano dentro del S&amp;P 500 (dato fijo).
  En pantallas angostas cada fila se vuelve una tarjeta; la columna Empresa queda fija al deslizar.</p>

  <h2>Vista CANASTA &mdash; como cartera diversificada</h2>
  <p class="note">Los primeros {len(basket)} candidatos vistos como grupo. Aqui vive el edge: comprar
  la canasta diversificada, no apostar a un solo nombre. ({basket_note})</p>
  <div class="secbar">{sec_chips or '<span class="chip">sin candidatos</span>'}</div>

  {news_html}

  {warn_html}

  <div class="foot">
    Scanner "Value en Crisis" &middot; {fase_foot} &middot; {ts}<br>
    Parametros: pico movil {C.PEAK_WINDOW_DAYS}d, banda {int(C.DROP_MIN*100)}-{int(C.DROP_MAX*100)}%,
    pico reciente &le; {C.RECENT_DAYS}d, historico {C.PRICE_YEARS}a. Precios ajustados por splits y dividendos.
    <div class="credit">

    path = path or os.path.join(C.OUT_DIR, f"scanner_{time.strftime('%Y%m%d')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path
