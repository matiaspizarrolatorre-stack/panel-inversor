# -*- coding: utf-8 -*-
"""
auditor.py — Auditor de SALUD y FRESCURA del panel.

Existe para prevenir el bug del "dato congelado" (el CAPE de Shiller que estuvo
3 anios viejo sin que se notara). Corre como parte del job semanal Y por separado
(p.ej. una Action diaria). Si Telegram esta prendido, avisa cuando algo se rompe
o envejece.

Chequeos:
  1. FRESCURA: que CAPE / VIX / S&P no tengan mas de X dias de antiguedad.
  2. CORDURA: valores dentro de rangos plausibles (CAPE 5-50, VIX 9-90, DD -90..5).
  3. CRUCE DE FUENTES: compara el CAPE de multpl vs Shiller en su ultima fecha
     comun; si difieren mucho, hay un bug de parseo o de fuente.
  4. SALUD DEL DEPLOY: la pagina publica responde 200 (best-effort).

Salida: datos/salud.json + un sello (✅ fresco / ⚠️ revisar) que la web muestra.

Uso:  python auditor.py
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

import pandas as pd

import sistema_a_monitor as A

DATOS_DIR = os.path.join(os.path.dirname(__file__), "datos")
PAGINA_URL = "https://matiaspizarrolatorre-stack.github.io/panel-inversor/"

# Umbrales de frescura (dias) y cordura (rangos). PRE-FIJADOS, no optimizados.
MAX_DIAS = {"CAPE": 45, "VIX": 6, "S&P": 6}      # CAPE es mensual; VIX/S&P diarios
RANGOS = {"CAPE": (5, 50), "VIX": (9, 90), "drawdown": (-90, 5)}
CRUCE_CAPE_TOL = 0.05    # 5% de diferencia maxima entre fuentes en la fecha comun


def _dias(fecha: str) -> int:
    d = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).days


def _check(nombre, estado, detalle):
    return {"nombre": nombre, "estado": estado, "detalle": detalle}


def chequear_frescura(estado_a: dict) -> list:
    res = []
    pares = [("CAPE", estado_a["cape"]["fecha_dato"]),
             ("VIX", estado_a["vix"]["fecha_dato"]),
             ("S&P", estado_a["drawdown"]["fecha_dato"])]
    for nombre, fecha in pares:
        d = _dias(fecha)
        lim = MAX_DIAS[nombre]
        est = "ok" if d <= lim else ("warn" if d <= lim * 2 else "error")
        res.append(_check(f"Frescura {nombre}", est,
                          f"ultimo dato {fecha} ({d} dias; limite {lim})"))
    return res


def chequear_cordura(estado_a: dict) -> list:
    res = []
    vals = {"CAPE": estado_a["cape"]["valor"], "VIX": estado_a["vix"]["valor"],
            "drawdown": estado_a["drawdown"]["valor"]}
    for nombre, (lo, hi) in RANGOS.items():
        v = vals[nombre]
        est = "ok" if lo <= v <= hi else "error"
        res.append(_check(f"Cordura {nombre}", est,
                          f"valor {v} (rango plausible {lo}..{hi})"))
    return res


def chequear_cruce_cape() -> list:
    """Compara CAPE multpl vs Shiller en su ultima fecha mensual comun."""
    try:
        m = A._cape_multpl()
        s = A._cape_shiller()
        m_m = m.resample("MS").last()
        s_m = s.resample("MS").last()
        comun = m_m.index.intersection(s_m.index)
        if len(comun) == 0:
            return [_check("Cruce CAPE multpl vs Shiller", "warn", "sin fecha comun")]
        f = comun[-1]
        vm, vs = float(m_m.loc[f]), float(s_m.loc[f])
        dif = abs(vm - vs) / max(vs, 1e-9)
        est = "ok" if dif <= CRUCE_CAPE_TOL else "error"
        return [_check("Cruce CAPE multpl vs Shiller", est,
                       f"en {f.date()}: multpl {vm:.1f} vs Shiller {vs:.1f} "
                       f"(dif {dif*100:.1f}%)")]
    except Exception as e:  # noqa: BLE001
        return [_check("Cruce CAPE multpl vs Shiller", "warn", f"no se pudo comparar ({e})")]


def chequear_deploy() -> list:
    try:
        req = urllib.request.Request(PAGINA_URL, headers={"User-Agent": "auditor"})
        code = urllib.request.urlopen(req, timeout=20).getcode()
        est = "ok" if code == 200 else "warn"
        return [_check("Pagina en vivo (HTTP 200)", est, f"HTTP {code}")]
    except Exception as e:  # noqa: BLE001
        return [_check("Pagina en vivo (HTTP 200)", "warn",
                       f"no respondio ({e}) — normal en el primer deploy")]


def auditar(estado_a: dict = None) -> dict:
    if estado_a is None:
        with open(os.path.join(DATOS_DIR, "estado_a.json"), encoding="utf-8") as f:
            estado_a = json.load(f)

    checks = []
    checks += chequear_frescura(estado_a)
    checks += chequear_cordura(estado_a)
    checks += chequear_cruce_cape()
    checks += chequear_deploy()

    if any(c["estado"] == "error" for c in checks):
        estado = "error"
    elif any(c["estado"] == "warn" for c in checks):
        estado = "warn"
    else:
        estado = "ok"
    sello = "✅ datos frescos y sanos" if estado == "ok" else (
        "⚠️ revisar (algo envejecio o no cuadra)" if estado == "warn"
        else "⛔ ALGO SE ROMPIO")

    salud = {"actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
             "estado": estado, "sello": sello, "checks": checks}
    os.makedirs(DATOS_DIR, exist_ok=True)
    with open(os.path.join(DATOS_DIR, "salud.json"), "w", encoding="utf-8") as f:
        json.dump(salud, f, ensure_ascii=False, indent=2)
    return salud


def main():
    # Standalone: se asegura de tener un estado_a fresco (no depende de una corrida previa).
    ruta_a = os.path.join(DATOS_DIR, "estado_a.json")
    if os.path.exists(ruta_a):
        with open(ruta_a, encoding="utf-8") as f:
            estado_a = json.load(f)
    else:
        estado_a = A.construir_estado()
    salud = auditar(estado_a)
    print(f"\n  SALUD: {salud['estado'].upper()} — {salud['sello']}")
    for c in salud["checks"]:
        icono = {"ok": "  ✓", "warn": "  !", "error": "  ✗"}[c["estado"]]
        print(f"{icono} {c['nombre']}: {c['detalle']}")

    # Telegram: avisa si hay problemas (solo si esta configurado).
    if salud["estado"] != "ok":
        try:
            import notificar_telegram
            notificar_telegram.notificar_salud(salud)
        except Exception as e:  # noqa: BLE001
            print(f"  [telegram] omitido: {e}")
    return salud


if __name__ == "__main__":
    main()
