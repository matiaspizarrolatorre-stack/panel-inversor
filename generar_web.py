# -*- coding: utf-8 -*-
"""
generar_web.py — Arma index.html (landing estatica) desde los outputs de A y B.

Lee datos/estado_a.json, datos/estado_b.json y datos/cape_historico.csv y produce
un index.html limpio, responsive, sin dependencias externas (CSS embebido + mini
grafico en SVG inline, para que funcione tal cual en GitHub Pages).

Tono: sobrio. Sin promesas. ESTO NO ES ASESORIA FINANCIERA.

Uso:  python generar_web.py
"""

from __future__ import annotations

import json
import os

import pandas as pd

DIR = os.path.dirname(__file__)
DATOS = os.path.join(DIR, "datos")

COLORES = {"verde": "#1a7f37", "amarillo": "#9a6700", "rojo": "#cf222e"}


def _leer(nombre):
    p = os.path.join(DATOS, nombre)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sparkline_cape(valor_actual: float) -> str:
    """Mini-grafico SVG inline del CAPE historico, con la marca del valor actual."""
    csv = os.path.join(DATOS, "cape_historico.csv")
    if not os.path.exists(csv):
        return ""
    s = pd.read_csv(csv, index_col=0, parse_dates=True)["cape"].dropna()
    s = s.iloc[:: max(1, len(s) // 240)]                    # downsample
    W, H, pad = 640, 130, 6
    lo, hi = float(s.min()), float(max(s.max(), valor_actual))
    xs = [pad + i * (W - 2 * pad) / (len(s) - 1) for i in range(len(s))]
    ys = [H - pad - (v - lo) / (hi - lo) * (H - 2 * pad) for v in s.values]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))

    def y_de(v):
        return H - pad - (v - lo) / (hi - lo) * (H - 2 * pad)

    lineas = ""
    for ref, etiq in [(16, "mediana ~16"), (44, "record ~44")]:
        if lo <= ref <= hi:
            y = y_de(ref)
            lineas += (f'<line x1="{pad}" y1="{y:.1f}" x2="{W-pad}" y2="{y:.1f}" '
                       f'stroke="#ccc" stroke-dasharray="3 3"/>'
                       f'<text x="{W-pad}" y="{y-3:.1f}" font-size="10" fill="#999" '
                       f'text-anchor="end">{etiq}</text>')
    yc = y_de(valor_actual)
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:680px">'
            f'{lineas}'
            f'<polyline points="{pts}" fill="none" stroke="#6f42c1" stroke-width="1.6"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{yc:.1f}" r="4" fill="#cf222e"/>'
            f'<text x="{xs[-1]-6:.1f}" y="{yc-7:.1f}" font-size="11" fill="#cf222e" '
            f'text-anchor="end">hoy {valor_actual:.0f}</text>'
            f'<text x="{pad}" y="{H-1}" font-size="9" fill="#999">{s.index[0].year}</text>'
            f'<text x="{W-pad}" y="{H-1}" font-size="9" fill="#999" '
            f'text-anchor="end">{s.index[-1].year}</text></svg>')


def barra_rango(pct: int, color: str) -> str:
    """Barrita 0-100 marcando la posicion (percentil) del valor en su rango."""
    pct = max(0, min(100, int(pct)))
    return (f'<div class="rango"><div class="marca" style="left:{pct}%;'
            f'background:{color}"></div></div>'
            f'<div class="rango-lbl"><span>barato</span><span>caro</span></div>')


def tarjeta(titulo, valor, sub, texto, color, barra=""):
    return (f'<div class="card"><div class="card-top"><span class="card-tit">{titulo}</span>'
            f'<span class="card-val" style="color:{color}">{valor}</span></div>'
            f'<div class="card-sub">{sub}</div>{barra}'
            f'<div class="card-txt">{texto}</div></div>')


def seccion_a(a: dict) -> str:
    if not a:
        return "<p>Sistema A sin datos. Corre sistema_a_monitor.py.</p>"
    color = COLORES.get(a["color"], "#333")
    cape, vix, dd = a["cape"], a["vix"], a["drawdown"]
    spark = sparkline_cape(cape["valor"])
    cards = (
        tarjeta("CAPE (Shiller PE)", cape["valor"],
                f"percentil historico {cape['percentil_historico']} · {cape['banda']} · {cape['ref']}",
                cape["texto"], color, barra_rango(cape["percentil_historico"], color))
        + tarjeta("VIX (miedo corto plazo)", vix["valor"], f"estado: {vix['banda']}",
                  vix["texto"], "#444")
        + tarjeta("Drawdown S&P", f"{dd['valor']}%", f"estado: {dd['banda']}",
                  dd["texto"], "#444")
    )
    return f"""
<section class="sec">
  <div class="sec-head">
    <h2>Sistema A — Monitor de Miedo / Euforia</h2>
    <span class="badge val">VALIDADO · backtest riguroso</span>
  </div>
  <div class="semaforo" style="border-color:{color}">
    <div class="ver-big" style="color:{color}">{a['veredicto']}</div>
    <div class="ver-sum">{a['resumen']}</div>
  </div>
  <div class="chart"><div class="chart-tit">CAPE historico (1871 → hoy)</div>{spark}</div>
  <div class="cards">{cards}</div>
  <p class="metodo">{a['nota_metodo']}</p>
  <p class="upd">Actualizado: {a['actualizado_utc']}</p>
</section>"""


def seccion_b(b: dict) -> str:
    if not b:
        return ""
    bloques = ""
    for tema in b["temas"]:
        items = ""
        for c in tema["candidatos"]:
            cls = {"temprano": "early", "priced": "late", "mixto": "mid"}.get(c["estado"], "mid")
            etq = {"temprano": "CANDIDATO A ESTUDIAR", "priced": "tarde / ya priced",
                   "mixto": "observar"}.get(c["estado"], "")
            r1 = "—" if c["ret_1y_%"] is None else f"{c['ret_1y_%']:+}%"
            pe = "—" if c["pe"] is None else c["pe"]
            items += (f'<div class="cand {cls}"><div class="cand-h">'
                      f'<b>{c["eslabon"]}</b> <span class="tk">{c["ticker"]}</span>'
                      f'<span class="etq {cls}">{etq}</span></div>'
                      f'<div class="cand-d">1 año: <b>{r1}</b> · P/E: <b>{pe}</b></div>'
                      f'<div class="cand-t">{c["tesis"]}</div>'
                      f'<div class="cand-r">⚠ {c["riesgos"]}</div></div>')
        bloques += (f'<div class="tema"><h3>{tema["tema"]}</h3>'
                    f'<div class="cadena">Cadena: {tema["cadena"]}</div>{items}</div>')
    return f"""
<section class="sec">
  <div class="sec-head">
    <h2>Sistema B — Explorador de Cadena Temática</h2>
    <span class="badge spec">ESPECULATIVO · NO es señal de compra</span>
  </div>
  <p class="aviso">{b['aviso']}</p>
  {bloques}
  <p class="upd">Datos de mercado actualizados: {b['actualizado_utc']} · clasificación priced/temprano por reglas fijas (no es predicción).</p>
</section>"""


def main():
    a = _leer("estado_a.json")
    b = _leer("estado_b.json")
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel del Inversor</title>
<style>
  :root {{ --bg:#fbfbfa; --tx:#1c1c1c; --mut:#666; --bd:#e5e5e5; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif; margin:0;
         background:var(--bg); color:var(--tx); line-height:1.5; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:24px 18px 60px; }}
  h1 {{ font-size:26px; margin:6px 0 2px; }}
  .lede {{ color:var(--mut); margin:0 0 24px; font-size:14px; }}
  .sec {{ background:#fff; border:1px solid var(--bd); border-radius:14px;
          padding:20px; margin:18px 0; }}
  .sec-head {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center;
               justify-content:space-between; margin-bottom:14px; }}
  .sec-head h2 {{ font-size:19px; margin:0; }}
  .badge {{ font-size:11px; font-weight:700; padding:4px 10px; border-radius:20px; }}
  .badge.val {{ background:#e7f5ec; color:#1a7f37; border:1px solid #1a7f3733; }}
  .badge.spec {{ background:#fdecea; color:#cf222e; border:1px solid #cf222e44; }}
  .semaforo {{ border:2px solid; border-radius:12px; padding:16px 18px; margin:8px 0 16px; }}
  .ver-big {{ font-size:26px; font-weight:800; letter-spacing:.3px; }}
  .ver-sum {{ font-size:14px; color:#333; margin-top:4px; }}
  .chart {{ margin:10px 0 18px; }}
  .chart-tit {{ font-size:12px; color:var(--mut); margin-bottom:4px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
  .card {{ border:1px solid var(--bd); border-radius:10px; padding:13px; background:#fff; }}
  .card-top {{ display:flex; justify-content:space-between; align-items:baseline; }}
  .card-tit {{ font-size:13px; color:var(--mut); }}
  .card-val {{ font-size:24px; font-weight:800; }}
  .card-sub {{ font-size:11px; color:var(--mut); margin:2px 0 8px; }}
  .card-txt {{ font-size:12.5px; color:#333; }}
  .rango {{ position:relative; height:6px; background:linear-gradient(90deg,#1a7f3733,#9a670033,#cf222e33);
            border-radius:4px; margin:4px 0 2px; }}
  .marca {{ position:absolute; top:-3px; width:3px; height:12px; border-radius:2px; transform:translateX(-1px); }}
  .rango-lbl {{ display:flex; justify-content:space-between; font-size:9px; color:#aaa; margin-bottom:8px; }}
  .metodo {{ font-size:12.5px; color:#444; background:#f6f6f4; border-left:3px solid #6f42c1;
             padding:10px 12px; border-radius:6px; margin-top:16px; }}
  .upd {{ font-size:11px; color:#aaa; margin-top:10px; }}
  .aviso {{ font-size:12.5px; color:#8a3a3a; background:#fdecea; border-radius:8px; padding:11px 13px; }}
  .tema h3 {{ font-size:16px; margin:16px 0 4px; }}
  .cadena {{ font-size:12px; color:var(--mut); margin-bottom:12px; }}
  .cand {{ border:1px solid var(--bd); border-left:4px solid #ccc; border-radius:8px;
           padding:11px 13px; margin:9px 0; }}
  .cand.early {{ border-left-color:#1a7f37; background:#f4faf6; }}
  .cand.late {{ border-left-color:#cf222e; opacity:.7; }}
  .cand.mid {{ border-left-color:#9a6700; }}
  .cand-h {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
  .tk {{ font-family:monospace; font-size:12px; background:#eee; padding:1px 6px; border-radius:4px; }}
  .etq {{ font-size:10px; font-weight:700; padding:2px 8px; border-radius:12px; margin-left:auto; }}
  .etq.early {{ background:#1a7f37; color:#fff; }}
  .etq.late {{ background:#eee; color:#999; }}
  .etq.mid {{ background:#9a6700; color:#fff; }}
  .cand-d {{ font-size:12px; color:#444; margin:5px 0; }}
  .cand-t {{ font-size:13px; }}
  .cand-r {{ font-size:12px; color:#a05a00; margin-top:4px; }}
  footer {{ font-size:11.5px; color:#888; text-align:center; margin-top:24px;
            border-top:1px solid var(--bd); padding-top:16px; }}
</style></head><body><div class="wrap">
  <h1>Panel del Inversor</h1>
  <p class="lede">Dos sistemas con niveles de confianza distintos. Lee cada badge.</p>
  {seccion_a(a)}
  {seccion_b(b)}
  <footer>
    Sistema A es un <b>tilt de décadas</b>, no market timing: mide el miedo, no predice cuándo revierte.
    Sistema B es <b>especulativo</b>: lo obvio ya está en el precio y por cada tesis que pega hay un cementerio.<br>
    El pasado no garantiza el futuro. <b>Esto NO es asesoría financiera.</b>
  </footer>
</div></body></html>"""
    ruta = os.path.join(DIR, "index.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  index.html generado -> {ruta}")


if __name__ == "__main__":
    main()
