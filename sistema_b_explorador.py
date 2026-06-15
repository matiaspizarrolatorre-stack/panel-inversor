# -*- coding: utf-8 -*-
"""
sistema_b_explorador.py — SISTEMA B: Explorador de Cadena Tematica (ESPECULATIVO).

NO es un edge validado. Es un asistente de investigacion. El JUICIO especulativo
(mapear temas y escribir tesis) lo hace una persona/LLM on-demand y se guarda en
datos/candidatos.json. Este script SOLO hace la parte automatizable y honesta:
refresca DATOS DE MERCADO de cada candidato guardado (cuanto subio 1y/3y, P/E) y
re-clasifica 'ya priced (tarde)' vs 'todavia temprano' por REGLAS FIJAS (sin LLM,
sin optimizar). Todos los numeros se redondean.

Reglas de clasificacion (PRE-FIJADAS por convencion, NO barridas):
  - 'priced' (tarde)   : retorno 1y >= +60%  O  P/E >= 45  (corrio fuerte / muy caro).
  - 'temprano' (estudiar): retorno 1y < +25%  Y  (P/E desconocido o < 30).
  - 'mixto' (observar) : el resto.

Salida: datos/estado_b.json (lo consume generar_web.py).

Uso:  python sistema_b_explorador.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DATOS_DIR = os.path.join(os.path.dirname(__file__), "datos")

PRICED_RET = 0.60
PRICED_PE = 45.0
TEMPRANO_RET = 0.25
TEMPRANO_PE = 30.0


def _datos_ticker(ticker: str) -> dict:
    """Retorno 1y/3y y P/E trailing via yfinance. Tolerante a fallos."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="3y", interval="1mo", auto_adjust=True)
        ret_1y = ret_3y = None
        if hist is not None and len(hist) > 13:
            c = hist["Close"].dropna()
            ret_1y = float(c.iloc[-1] / c.iloc[-13] - 1.0)
            ret_3y = float(c.iloc[-1] / c.iloc[0] - 1.0)
        pe = None
        try:
            info = t.get_info()
            pe = info.get("trailingPE") or info.get("forwardPE")
            pe = float(pe) if pe else None
        except Exception:  # noqa: BLE001
            pe = None
        return {"ret_1y": ret_1y, "ret_3y": ret_3y, "pe": pe}
    except Exception as e:  # noqa: BLE001
        print(f"  [B] {ticker} sin datos ({e}).")
        return {"ret_1y": None, "ret_3y": None, "pe": None}


def _clasificar(d: dict) -> tuple:
    r1 = d.get("ret_1y")
    pe = d.get("pe")
    if (r1 is not None and r1 >= PRICED_RET) or (pe is not None and pe >= PRICED_PE):
        return "priced", "Ya corrio / muy caro: probablemente TARDE (lo obvio ya esta en el precio)."
    if (r1 is not None and r1 < TEMPRANO_RET) and (pe is None or pe < TEMPRANO_PE):
        return "temprano", "Aun no re-valuado: CANDIDATO A ESTUDIAR (especulativo, no senal)."
    return "mixto", "Senales mixtas: observar."


def main():
    with open(os.path.join(DATOS_DIR, "candidatos.json"), encoding="utf-8") as f:
        base = json.load(f)

    salida = {"actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "aviso": base["_aviso"], "temas": []}

    for tema in base["temas"]:
        print(f"[B] tema: {tema['tema']}")
        cands = []
        for c in tema["candidatos"]:
            d = _datos_ticker(c["ticker"])
            estado, nota = _clasificar(d)
            cands.append({
                "eslabon": c["eslabon"], "ticker": c["ticker"],
                "tesis": c["tesis"], "riesgos": c["riesgos"],
                "ret_1y_%": round(d["ret_1y"] * 100) if d["ret_1y"] is not None else None,
                "ret_3y_%": round(d["ret_3y"] * 100) if d["ret_3y"] is not None else None,
                "pe": round(d["pe"], 1) if d["pe"] is not None else None,
                "estado": estado, "nota": nota,
            })
            print(f"   {c['ticker']:5s} 1y={cands[-1]['ret_1y_%']} P/E={cands[-1]['pe']} -> {estado}")
        # Ordenar: 'temprano' primero (lo que el usuario quiere estudiar).
        orden = {"temprano": 0, "mixto": 1, "priced": 2}
        cands.sort(key=lambda x: orden.get(x["estado"], 9))
        salida["temas"].append({"tema": tema["tema"], "cadena": tema["cadena"],
                                "fecha_mapa": tema.get("fecha_mapa"), "candidatos": cands})

    ruta = os.path.join(DATOS_DIR, "estado_b.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"\n  -> {ruta}")
    return salida


if __name__ == "__main__":
    main()
