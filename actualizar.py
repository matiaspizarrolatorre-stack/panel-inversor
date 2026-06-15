# -*- coding: utf-8 -*-
"""
actualizar.py — Entry point unico: corre A, B, regenera la web y (si esta
configurado) notifica por Telegram. Lo usa tanto el run LOCAL como la GitHub Action.

Uso:
    python actualizar.py            # corre todo y genera index.html
    python actualizar.py --abrir    # ademas abre index.html en el navegador (local)
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

import sistema_a_monitor
import sistema_b_explorador
import generar_web


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--abrir", action="store_true", help="abre index.html al terminar")
    args = ap.parse_args()

    print("== Sistema A (validado) ==")
    estado_a = sistema_a_monitor.main()
    print("\n== Sistema B (especulativo) ==")
    try:
        sistema_b_explorador.main()
    except Exception as e:  # noqa: BLE001 - B no debe tumbar el panel
        print(f"  [B] error no fatal: {e}")
    print("\n== Web ==")
    generar_web.main()

    # Telegram: solo actua si hay token+chat en el entorno (apagado por defecto).
    try:
        import notificar_telegram
        notificar_telegram.notificar(estado_a)
    except Exception as e:  # noqa: BLE001
        print(f"  [telegram] omitido: {e}")

    if args.abrir:
        ruta = os.path.join(os.path.dirname(__file__), "index.html")
        webbrowser.open("file://" + os.path.abspath(ruta))


if __name__ == "__main__":
    sys.exit(main())
