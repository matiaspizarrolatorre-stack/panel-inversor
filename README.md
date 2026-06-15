# Panel del Inversor

Panel personal con **dos sistemas de confianza distinta** (no los mezcles):

- 🟢 **Sistema A — Monitor de Miedo/Euforia (VALIDADO).** Lee el CAPE (Shiller PE),
  el VIX y el drawdown del S&P y da un veredicto. El **CAPE manda** (validado con
  backtest riguroso: +4 a +5 pp/año a 1/3/5 años, le gana al azar p=0.02–0.03);
  VIX solo a 1 año; drawdown solo de apoyo. Es un **tilt de décadas, no timing**.
- 🔴 **Sistema B — Explorador de Cadena Temática (ESPECULATIVO).** Mapea la cadena
  de dependencias de un tema (ej. IA) y marca eslabones "todavía temprano" para
  estudiar. **NO es señal de compra.** El juicio lo hace una persona/LLM; el script
  solo refresca datos de mercado y re-clasifica por reglas fijas.

> **Esto NO es asesoría financiera. El pasado no garantiza el futuro.**

La web es **entendible para cualquiera**: una frase de veredicto en lenguaje cotidiano
("En cristiano: ..."), cada término técnico (CAPE, VIX, drawdown, percentil, miedo/
euforia) es **clickeable** y despliega su explicación en simple, y hay un **glosario**
al pie. Sin simplificar hasta engañar: los caveats (tilt de décadas, no es asesoría)
quedan siempre visibles.

### Auditor de salud y frescura (`auditor.py`)
Para prevenir el bug del "dato congelado" (que ya pasó: el CAPE de Shiller estuvo 3
años viejo). Chequea: **frescura** (alerta si CAPE/VIX/S&P superan X días),
**cordura** (CAPE 5–50, VIX 9–90), **cruce de fuentes** (CAPE multpl vs Shiller en su
fecha común) y **salud del deploy** (página responde 200). Muestra un **sello visible**
en la web (✅ fresco / ⚠️ revisar) y, si Telegram está prendido, **avisa cuando algo se
rompe o envejece**. Corre dentro del job semanal y también solo:
```bash
python auditor.py            # auditoría standalone
```
Además hay una **Action diaria** (`auditoria.yml`) que solo audita y alerta (sin
re-publicar), para detectar un dato congelado en 1 día y no en 1 semana.

## Correr local (previsualizar)

Requiere Python 3.10+.

```bash
cd panel-inversor
python -m venv .venv && source .venv/bin/activate     # o usa tu entorno
pip install -r requirements.txt
python actualizar.py --abrir      # corre A+B, genera index.html y lo abre
```

Cada parte por separado: `python sistema_a_monitor.py` · `python sistema_b_explorador.py` · `python generar_web.py`.

## Datos (honesto)
- **CAPE:** multpl.com (fresco, al día) → fallback Shiller xls → fallback cache local.
- **VIX y S&P (^GSPC):** yfinance → fallback Stooq.
- **P/E por empresa (Sistema B):** yfinance; es irregular, se marca cuando falta.

## Agregar / editar candidatos del Sistema B
Editá `datos/candidatos.json` (tema, cadena, y por candidato: eslabón, ticker,
tesis, riesgos, estado_inicial). El refresco semanal recalcula retornos/P/E y
re-marca priced/temprano solo. Para mapear un tema nuevo, pedímelo y lo agrego.

---

## Publicar en GitHub Pages (paso a paso)

1. **Creá el repo** en GitHub: botón **New** → nombre `panel-inversor` → Public → Create.
2. **Subí estos archivos** (desde esta carpeta):
   ```bash
   cd panel-inversor
   git init -b main
   git add .
   git commit -m "Panel del inversor: sistemas A y B + web"
   git remote add origin https://github.com/matiaspizarrolatorre-stack/panel-inversor.git
   git push -u origin main
   ```
3. **Activá Pages con Actions:** en el repo → **Settings** → **Pages** →
   *Build and deployment* → **Source: GitHub Actions**. (No hace falta elegir rama.)
4. **Primer deploy:** pestaña **Actions** → workflow *Panel semanal* → **Run workflow**
   (botón de `workflow_dispatch`). Cuando termine, tu panel queda en:
   **https://matiaspizarrolatorre-stack.github.io/panel-inversor/**
5. **Automático:** ya queda corriendo **todos los lunes 13:00 UTC** y regenera la web.

## (Opcional) Alertas por Telegram — apagadas por defecto
Te avisa FUERTE solo cuando el Sistema A pasa a **"MIEDO / BARATO"** (la oportunidad
rara); digest tranquilo el resto.
1. En Telegram, hablale a **@BotFather** → `/newbot` → copiá el **TOKEN**.
2. Escribile algo a tu bot. Abrí `https://api.telegram.org/bot<TOKEN>/getUpdates`
   y copiá tu **chat id** (campo `"id"`).
3. **Repo → Settings → Secrets and variables → Actions → New repository secret:**
   agregá `TELEGRAM_TOKEN` y `TELEGRAM_CHAT`. Listo: la Action los usa sola.
   (Local: `export TELEGRAM_TOKEN=... TELEGRAM_CHAT=...` antes de `python actualizar.py`.)

## Recordatorios honestos
Sistema A mide el miedo, **no predice cuándo revierte** (podés esperar años).
Sistema B: lo obvio **ya está en el precio** y por cada tesis que pega hay un
cementerio (NFTs, metaverso). Usá umbrales fijos, no optimizados, para no engañarte.
