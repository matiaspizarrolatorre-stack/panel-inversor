# -*- coding: utf-8 -*-
"""
notificar_telegram.py — Hook de alertas por Telegram (APAGADO por defecto).

Solo hace algo si existen las variables de entorno TELEGRAM_TOKEN y TELEGRAM_CHAT.
Logica: alerta FUERTE cuando el Sistema A esta en "MIEDO / BARATO" (la oportunidad
rara); digest tranquilo el resto. Es stateless (no requiere persistir estado): la
condicion de oportunidad ya es rara, asi que alertar cuando se cumple equivale a
avisarte cuando aparece.

Para activarlo (ver README):
  1. @BotFather en Telegram -> /newbot -> copia el TOKEN.
  2. Escribile algo a tu bot, luego abri
     https://api.telegram.org/bot<TOKEN>/getUpdates  -> copia tu chat id.
  3. Exporta TELEGRAM_TOKEN y TELEGRAM_CHAT (local) o agregalos como Secrets del repo.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _enviar(token: str, chat: str, texto: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": texto,
                                   "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20).read()


def notificar(estado_a: dict | None = None):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT")
    if not token or not chat:
        raise RuntimeError("sin TELEGRAM_TOKEN/TELEGRAM_CHAT (hook apagado)")

    if estado_a is None:
        with open(os.path.join(os.path.dirname(__file__), "datos", "estado_a.json"),
                  encoding="utf-8") as f:
            estado_a = json.load(f)

    cape = estado_a["cape"]; vix = estado_a["vix"]; dd = estado_a["drawdown"]
    if estado_a["veredicto"] == "MIEDO / BARATO":
        texto = (f"🟢 <b>OPORTUNIDAD — MIEDO / BARATO</b>\n"
                 f"CAPE {cape['valor']} (pct {cape['percentil_historico']}). "
                 f"Es el unico estado con senal fuerte de inclinarse a comprar mas.\n"
                 f"VIX {vix['valor']} · DD {dd['valor']}%\n"
                 f"Recorda: tilt de decadas, no timing. NO es asesoria financiera.")
    else:
        texto = (f"📊 Digest semanal — {estado_a['veredicto']}\n"
                 f"CAPE {cape['valor']} (pct {cape['percentil_historico']}, {cape['banda']}) · "
                 f"VIX {vix['valor']} · DD {dd['valor']}%\n"
                 f"Sin oportunidad de 'barato' por ahora.")
    _enviar(token, chat, texto)
    print("  [telegram] enviado.")


if __name__ == "__main__":
    notificar()
