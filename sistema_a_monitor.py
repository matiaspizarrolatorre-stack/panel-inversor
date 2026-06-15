# -*- coding: utf-8 -*-
"""
sistema_a_monitor.py — SISTEMA A: Monitor de Miedo/Euforia EN VIVO (VALIDADO).

Es la version en vivo de los hallazgos de miedo_extremo.py (backtest riguroso).
Lee el estado ACTUAL del mercado y da un veredicto, respetando la JERARQUIA
validada:
  1. CAPE (Shiller PE) = el motor robusto (peso alto). Valido a 1/3/5 anios
     (le gana al azar p=0.02-0.03). MANDA el veredicto.
  2. VIX = senal de corto plazo (solo 1 anio). Solo modula.
  3. Drawdown = solo de apoyo (debil aislado). Solo modula.

Umbrales PRE-FIJADOS por convencion (NO optimizados). Todos los numeros se
redondean. ESTO NO ES ASESORIA FINANCIERA.

Salida: datos/estado_a.json (lo consume generar_web.py).

Uso:  python sistema_a_monitor.py
"""

from __future__ import annotations

import io
import json
import os
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

DATOS_DIR = os.path.join(os.path.dirname(__file__), "datos")
# multpl actualiza el CAPE al dia (Shiller xls suele quedar meses/anios atras).
MULTPL_URL = "https://www.multpl.com/shiller-pe/table/by-month"
SHILLER_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"

# --- Umbrales de convencion (pre-fijados; referencias historicas del CAPE:
#     minimo ~5, mediana ~16, record ~44). NO se optimizan. ---
CAPE_BANDAS = [
    (16.0, "barato", "Tercil barato: senal fuerte de 'comprar mas' (validado: "
                     "+4 a +5pp/anio a 1/3/5 anios)."),
    (25.0, "neutral", "Valoracion normal: expectativas de retorno medias."),
    (30.0, "caro", "Caro: modera expectativas, los retornos futuros suelen ser flacos."),
    (999.0, "muy caro", "Muy caro: retornos futuros historicamente bajos. No cargues."),
]
VIX_PANICO = 30.0   # > pánico -> oportunidad de rebote a 1 anio
VIX_CALMA = 14.0    # < calma
DD_APOYO = 20.0     # drawdown > 20% como apoyo de 'miedo'


# -----------------------------------------------------------------------------
# Datos (con fallbacks para correr en CI)
# -----------------------------------------------------------------------------

def _descargar_yf(simbolo: str, start: str) -> pd.Series:
    """Cierre diario via yfinance; fallback a Stooq si falla."""
    try:
        import yfinance as yf
        df = yf.download(simbolo, start=start, interval="1d",
                         auto_adjust=False, progress=False, threads=False)
        if df is not None and len(df) > 0:
            if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
                df.columns = [c[0] for c in df.columns]
            s = df["Close"].dropna()
            s.index = pd.to_datetime(s.index)
            return s
    except Exception as e:  # noqa: BLE001
        print(f"  [yf] {simbolo} fallo ({e}); intento Stooq.")
    # Fallback Stooq.
    mapa = {"^VIX": "^vix", "^GSPC": "^spx"}
    sym = mapa.get(simbolo, simbolo)
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    raw = urllib.request.urlopen(url, timeout=30).read().decode()
    df = pd.read_csv(io.StringIO(raw))
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date")["Close"].dropna()


def _cape_multpl() -> pd.Series:
    """CAPE mensual FRESCO desde multpl (1871 -> hoy)."""
    import re
    req = urllib.request.Request(MULTPL_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    filas = re.findall(
        r"<td>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td>.*?([0-9]+\.[0-9]+)",
        html, re.DOTALL)
    s = pd.Series({pd.to_datetime(d): float(v) for d, v in filas}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _cape_shiller() -> pd.Series:
    """CAPE de Shiller (xls). Historia larga pero suele quedar atras en frescura."""
    req = urllib.request.Request(SHILLER_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data", skiprows=7, header=None)
    fecha = pd.to_numeric(df[0], errors="coerce")
    anio = np.floor(fecha)
    mes = np.round((fecha - anio) * 100)
    cape = pd.to_numeric(df[12], errors="coerce")
    ok = fecha.notna() & mes.between(1, 12) & cape.notna()
    idx = pd.to_datetime({"year": anio[ok].astype(int), "month": mes[ok].astype(int),
                          "day": 1})
    return pd.Series(cape[ok].values, index=pd.DatetimeIndex(idx.values)).sort_index()


def cargar_cape() -> pd.Series:
    """
    CAPE mensual. Fuente FRESCA = multpl; fallback Shiller; ultimo recurso cache.
    Cachea siempre para no depender de la red en cada corrida.
    """
    cache = os.path.join(DATOS_DIR, "cape_historico.csv")
    for nombre, fn in [("multpl", _cape_multpl), ("shiller", _cape_shiller)]:
        try:
            s = fn()
            if s is not None and len(s) > 12:
                os.makedirs(DATOS_DIR, exist_ok=True)
                s.to_csv(cache, header=["cape"])
                print(f"  [cape] fuente: {nombre} (ultimo: {s.index[-1].date()} = "
                      f"{round(float(s.iloc[-1]),1)})")
                return s
        except Exception as e:  # noqa: BLE001
            print(f"  [cape] {nombre} fallo ({e}).")
    print("  [cape] uso cache local.")
    return pd.read_csv(cache, index_col=0, parse_dates=True)["cape"]


# -----------------------------------------------------------------------------
# Logica del veredicto (CAPE manda; VIX y drawdown modulan)
# -----------------------------------------------------------------------------

def _banda_cape(valor: float):
    for techo, nombre, texto in CAPE_BANDAS:
        if valor < techo:
            return nombre, texto
    return CAPE_BANDAS[-1][1], CAPE_BANDAS[-1][2]


def construir_estado() -> dict:
    print("[A] descargando CAPE (Shiller), VIX y S&P (yfinance/Stooq)...")
    cape_s = cargar_cape()
    vix_s = _descargar_yf("^VIX", "1990-01-01")
    spx_s = _descargar_yf("^GSPC", "1970-01-01")

    cape = float(cape_s.iloc[-1])
    cape_pct = float((cape_s <= cape).mean() * 100)     # percentil historico
    cape_banda, cape_texto = _banda_cape(cape)

    vix = float(vix_s.iloc[-1])
    if vix > VIX_PANICO:
        vix_banda = "panico"
        vix_texto = "Panico: oportunidad de rebote a ~1 anio (efecto valido solo a corto)."
    elif vix < VIX_CALMA:
        vix_banda = "calma"
        vix_texto = "Calma. OJO: VIX bajo NO es bajista (no predice caidas)."
    else:
        vix_banda = "neutral"
        vix_texto = "Nivel medio, neutral."

    pico = float(spx_s.cummax().iloc[-1])
    spx = float(spx_s.iloc[-1])
    dd = (spx / pico - 1.0) * 100.0
    if dd <= -DD_APOYO:
        dd_banda = "caida fuerte"
        dd_texto = f"Drawdown >{DD_APOYO:.0f}%: apoya 'miedo', pero DEBIL solo (necesita CAPE barato o VIX alto)."
    else:
        dd_banda = "normal"
        dd_texto = "Sin caida relevante desde maximos. Estar cerca de maximos NO es bajista."

    # --- Veredicto combinado: el CAPE manda; VIX/drawdown solo modulan ---
    if cape_banda == "barato":
        veredicto = "MIEDO / BARATO"
        color = "verde"
        resumen = ("Valoracion barata (CAPE en tercil bajo): el unico momento con "
                   "senal fuerte de inclinarse a comprar mas. Raro historicamente.")
    elif cape_banda in ("caro", "muy caro"):
        veredicto = "EUFORIA / CARO"
        color = "rojo"
        resumen = ("Valoracion cara (CAPE alto): los retornos futuros a 1/3/5 anios "
                   "suelen ser flacos. Modera expectativas, no cargues de golpe.")
        if vix_banda == "panico":
            resumen += (" PERO el VIX en panico abre una ventana TACTICA de rebote a "
                        "~1 anio (efecto de corto plazo, no cambia el cuadro de decadas).")
    else:
        veredicto = "NEUTRAL"
        color = "amarillo"
        resumen = "Valoracion normal: expectativas de retorno medias, sin tilt fuerte."
        if vix_banda == "panico":
            resumen += " El VIX en panico sugiere posible rebote tactico a ~1 anio."

    # --- Frase en lenguaje cotidiano (sin enganar) ---
    if cape_banda == "barato":
        frase = ("En cristiano: las acciones estan historicamente BARATAS. Es de los "
                 "pocos momentos en que inclinarse a comprar mas rindio a 1, 3 y 5 anios. "
                 "Aun asi, puede seguir cayendo antes de subir.")
    elif cape_banda in ("caro", "muy caro"):
        frase = ("En cristiano: las acciones estan CARAS hoy, asi que lo mas probable es "
                 "que rindan POCO en los proximos anios. No es momento de cargar de golpe "
                 "(pero caro puede seguir caro por anios: no es senal de vender ni de timing).")
    else:
        frase = ("En cristiano: precios NORMALES, sin senal fuerte para ningun lado. "
                 "Seguir el plan de siempre.")
    if vix_banda == "panico":
        frase += " Ademas hay panico (VIX alto): historicamente, comprar el panico rebota a ~1 anio."

    return {
        "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "veredicto": veredicto,
        "color": color,
        "frase_cotidiana": frase,
        "resumen": resumen,
        "cape": {"valor": round(cape, 1), "percentil_historico": round(cape_pct),
                 "banda": cape_banda, "texto": cape_texto,
                 "fecha_dato": cape_s.index[-1].strftime("%Y-%m-%d"),
                 "ref": "min ~5 · mediana ~16 · record ~44"},
        "vix": {"valor": round(vix, 1), "banda": vix_banda, "texto": vix_texto,
                "fecha_dato": vix_s.index[-1].strftime("%Y-%m-%d")},
        "drawdown": {"valor": round(dd, 1), "banda": dd_banda, "texto": dd_texto,
                     "fecha_dato": spx_s.index[-1].strftime("%Y-%m-%d")},
        "nota_metodo": ("El CAPE manda (validado a 1/3/5 anios); VIX solo a 1 anio; "
                        "drawdown solo de apoyo. Es un TILT DE DECADAS, no market "
                        "timing: mide el miedo, NO predice cuando revierte."),
    }


def main():
    estado = construir_estado()
    os.makedirs(DATOS_DIR, exist_ok=True)
    ruta = os.path.join(DATOS_DIR, "estado_a.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    print(f"\n  VEREDICTO: {estado['veredicto']}")
    print(f"  CAPE {estado['cape']['valor']} (pct {estado['cape']['percentil_historico']}, "
          f"{estado['cape']['banda']}) | VIX {estado['vix']['valor']} "
          f"({estado['vix']['banda']}) | DD {estado['drawdown']['valor']}%")
    print(f"  -> {ruta}")
    return estado


if __name__ == "__main__":
    main()
