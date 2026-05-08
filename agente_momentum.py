#!/usr/bin/env python3
"""
agente_momentum.py
Agente intraday basado en momentum de precios.

Estrategia: detectar mercados donde el precio se movió significativamente
en las últimas 1-4 horas y operar en esa dirección.

Sin filtros de categoría — opera cualquier mercado con movimiento real.
Ciclos cada 1 hora. Salidas automáticas TP/SL/tiempo.

Por qué funciona el momentum en predicción:
  La información llega gradualmente. Los traders informados mueven el
  precio primero, el resto sigue. Detectar ese movimiento temprano
  y montarse en él es la ventaja de corto plazo.
"""

from groq import Groq
from apscheduler.schedulers.blocking import BlockingScheduler
import requests, pandas as pd, json, os, time, logging
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════

import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ── Parámetros intraday ────────────────────────────────────────────
TAKE_PROFIT       = 0.08    # +8% → cerrar con ganancia
STOP_LOSS         = -0.05   # -5% → cortar pérdida
MAX_HORAS         = 8       # máx tiempo abierto (intraday real)
MIN_MOMENTUM_1H   = 0.01# movimiento mínimo en 1h para señal (3%)
MIN_MOMENTUM_4H   = 0.02    # movimiento mínimo en 4h (5%)
CICLO_HORAS       = 0.10       # frecuencia del ciclo

# ── Filtros de mercado ─────────────────────────────────────────────
MIN_VOLUMEN       = 5_000   # bajo — queremos capturar mercados activos pequeños
MAX_SPREAD        = 0.08
MIN_PRECIO        = 0.04
MAX_PRECIO        = 0.96
MAX_DIAS_MERCADO  = 180     # mercados hasta 6 meses (la restricción viene del momentum)

# ── Posiciones ────────────────────────────────────────────────────
CAPITAL_INICIAL   = 1_000
CAPITAL_POR_OP    = 20      # pequeño — muchas operaciones, aprender rápido
MAX_POSICIONES    = 30

# Excluir solo lo imposible de analizar
PATRONES_EXCLUIR  = ["jesus","christ","second coming","rapture",
                     "alien","ufo","zombie","apocalypse"]

ARCHIVO_LIBRO    = "datos_polymarket/paper_trading/libro_momentum.csv"
ARCHIVO_ESTADO   = "datos_polymarket/paper_trading/estado_momentum.json"
ARCHIVO_PRECIOS  = "datos_polymarket/paper_trading/historial_precios.json"

os.makedirs("datos_polymarket/logs", exist_ok=True)
os.makedirs("datos_polymarket/paper_trading", exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s | %(levelname)s | %(message)s",
    handlers = [
        logging.FileHandler("datos_polymarket/logs/agente_momentum.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("momentum")


# ══════════════════════════════════════════════════════════════════
# ESTADO, LIBRO, HISTORIAL DE PRECIOS
# ══════════════════════════════════════════════════════════════════

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f:
            return json.load(f)
    return {
        "capital_inicial": CAPITAL_INICIAL, "capital_actual": CAPITAL_INICIAL,
        "capital_en_riesgo": 0, "n_ciclos": 0, "ultima_corrida": "—",
        "n_tp": 0, "n_sl": 0, "n_time": 0,
        "mercados_rastreados": 0,   # cuántos mercados tenemos en historial
    }

def guardar_estado(e):
    with open(ARCHIVO_ESTADO, "w") as f: json.dump(e, f, indent=2)

def cargar_libro():
    return pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()

def guardar_libro(df):
    df.to_csv(ARCHIVO_LIBRO, index=False)

def cargar_historial():
    if os.path.exists(ARCHIVO_PRECIOS):
        with open(ARCHIVO_PRECIOS) as f: return json.load(f)
    return {}

def guardar_historial(h):
    with open(ARCHIVO_PRECIOS, "w") as f: json.dump(h, f)


# ══════════════════════════════════════════════════════════════════
# HISTORIAL DE PRECIOS LOCAL
#
# El agente guarda un snapshot de precios cada ciclo.
# Con eso calcula momentum sin depender de APIs externas complejas.
# Primer ciclo: solo registra. Segundo ciclo en adelante: opera.
# ══════════════════════════════════════════════════════════════════

def registrar_snapshot(mercados):
    """Guarda precio actual de cada mercado con timestamp."""
    historial = cargar_historial()
    ts = datetime.now().isoformat()

    for m in mercados:
        key = m["id"]  # usamos market ID como clave, más confiable que la pregunta
        if key not in historial:
            historial[key] = {"pregunta": m["pregunta"][:70], "precios": []}
        historial[key]["precios"].append({"ts": ts, "p": m["mid_price"]})
        # Conservar solo últimas 48 entradas (48h si ciclo = 1h)
        historial[key]["precios"] = historial[key]["precios"][-48:]

    guardar_historial(historial)
    return historial


def calcular_momentum(market_id, historial):
    """
    Calcula cuánto se movió el precio en las últimas 1h y 4h.
    Retorna (señal, momentum_score, cambio_1h, cambio_4h, precio_actual)
    """
    if market_id not in historial:
        return "NEUTRAL", 0, 0, 0, None

    entradas = historial[market_id]["precios"]
    if len(entradas) < 2:
        return "NEUTRAL", 0, 0, 0, entradas[-1]["p"] if entradas else None

    ahora          = datetime.now()
    precio_actual  = entradas[-1]["p"]

    def precio_hace(horas):
        cutoff = ahora - timedelta(hours=horas)
        pasados = [e for e in entradas
                   if datetime.fromisoformat(e["ts"]) <= cutoff]
        return pasados[-1]["p"] if pasados else None

    p1h  = precio_hace(1)
    p4h  = precio_hace(4)

    cambio_1h = (precio_actual - p1h)  / p1h  if p1h  and p1h  > 0 else 0
    cambio_4h = (precio_actual - p4h)  / p4h  if p4h  and p4h  > 0 else 0

    # Score combinado: más peso a movimiento reciente (1h)
    momentum = cambio_1h * 0.65 + cambio_4h * 0.35

    # Señal: solo si supera umbral mínimo en al menos una ventana
    if abs(cambio_1h) >= MIN_MOMENTUM_1H or abs(cambio_4h) >= MIN_MOMENTUM_4H:
        señal = "COMPRAR YES" if momentum > 0 else "COMPRAR NO"
    else:
        señal = "NEUTRAL"

    return señal, round(momentum, 4), round(cambio_1h, 4), round(cambio_4h, 4), precio_actual


# ══════════════════════════════════════════════════════════════════
# SCANNER: TODOS LOS MERCADOS LÍQUIDOS
# ══════════════════════════════════════════════════════════════════

def escanear_mercados():
    """Sin filtro de categoría. Solo liquidez mínima."""
    hoy = datetime.now().date()
    try:
        r = requests.get(f"{BASE_URL}/markets",
                         params={"active": True, "closed": False, "limit": 200},
                         timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        log.error(f"Error API: {e}")
        return []

    mercados = []
    for m in raw:
        try:
            pregunta = m.get("question", "")
            if any(p in pregunta.lower() for p in PATRONES_EXCLUIR):
                continue

            bid = float(m.get("bestBid", 0))
            ask = float(m.get("bestAsk", 0))
            if bid <= 0 or ask <= 0:
                continue

            spread    = round(ask - bid, 4)
            mid_price = round((bid + ask) / 2, 4)

            if spread > MAX_SPREAD: continue
            if mid_price < MIN_PRECIO or mid_price > MAX_PRECIO: continue
            if float(m.get("volume", 0)) < MIN_VOLUMEN: continue

            fecha_str = m.get("endDate", "")[:10]
            if not fecha_str: continue
            dias = (datetime.strptime(fecha_str, "%Y-%m-%d").date() - hoy).days
            if dias <= 0 or dias > MAX_DIAS_MERCADO: continue

            mercados.append({
                "id":          m.get("id", pregunta[:30]),
                "pregunta":    pregunta,
                "mid_price":   mid_price,
                "spread":      spread,
                "volumen_usd": float(m.get("volume", 0)),
                "dias":        dias,
                "fecha_cierre": fecha_str,
            })
        except:
            continue

    log.info(f"Mercados activos rastreables: {len(mercados)}")
    return mercados


# ══════════════════════════════════════════════════════════════════
# SALIDAS AUTOMÁTICAS (igual que agente_corto_plazo)
# ══════════════════════════════════════════════════════════════════

def verificar_salidas(df_libro, estado, mercados_actuales):
    if df_libro.empty: return df_libro, 0

    precio_lookup   = {m["id"]: m["mid_price"] for m in mercados_actuales}
    pregunta_lookup = {m["pregunta"][:70]: m["mid_price"] for m in mercados_actuales}

    ahora    = datetime.now()
    abiertas = df_libro[df_libro["estado"] == "ABIERTA"].copy()
    cerradas = 0

    for idx, pos in abiertas.iterrows():
        try:
            dt_entrada     = datetime.strptime(pos["fecha_entrada_dt"], "%Y-%m-%d %H:%M")
            horas_abiertas = (ahora - dt_entrada).total_seconds() / 3600

            mid_actual = (precio_lookup.get(str(pos.get("market_id", ""))) or
                          pregunta_lookup.get(str(pos["pregunta"])[:70]))
            if mid_actual is None:
                continue

            df_libro.loc[idx, "precio_actual"] = mid_actual

            p_token_e = float(pos["precio_token_entrada"])
            p_token_a = mid_actual if pos["señal"] == "COMPRAR YES" else 1 - mid_actual
            pct       = (p_token_a - p_token_e) / p_token_e

            razon = None
            if   pct >= TAKE_PROFIT:          razon = "TAKE_PROFIT"; estado["n_tp"]   += 1
            elif pct <= STOP_LOSS:            razon = "STOP_LOSS";   estado["n_sl"]   += 1
            elif horas_abiertas >= MAX_HORAS: razon = "TIME_EXIT";   estado["n_time"] += 1

            if razon:
                pnl = round(float(pos["monto_usdc"]) * pct, 2)
                df_libro.loc[idx, "estado"]            = "CERRADA"
                df_libro.loc[idx, "precio_cierre"]     = p_token_a
                df_libro.loc[idx, "pct_cambio"]        = round(pct, 4)
                df_libro.loc[idx, "pnl_realizado"]     = pnl
                df_libro.loc[idx, "razon_cierre"]      = razon
                df_libro.loc[idx, "fecha_cierre_real"] = ahora.strftime("%Y-%m-%d %H:%M")
                estado["capital_actual"]    = estado.get("capital_actual", CAPITAL_INICIAL) \
                                              + float(pos["monto_usdc"]) + pnl
                estado["capital_en_riesgo"] = max(0, estado.get("capital_en_riesgo", 0)
                                              - float(pos["monto_usdc"]))
                cerradas += 1
                log.info(f"{'✅' if pnl>=0 else '❌'} [{razon}] {pos['pregunta'][:45]} "
                         f"| {pct:+.1%} | P&L={pnl:+.2f}$ | {horas_abiertas:.1f}h")
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")

    guardar_libro(df_libro)
    return df_libro, cerradas


# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def ciclo():
    log.info("=" * 55)
    log.info(f"CICLO MOMENTUM INICIADO")
    log.info("=" * 55)

    estado   = cargar_estado()
    df_libro = cargar_libro()

    # ── 1. Escanear todos los mercados ───────────────────────────
    mercados = escanear_mercados()
    if not mercados:
        log.warning("Sin mercados disponibles")
        return

    # ── 2. Registrar snapshot de precios ─────────────────────────
    # Esto alimenta el cálculo de momentum. En el primer ciclo
    # solo registra — desde el segundo ciclo ya hay datos para operar.
    historial = registrar_snapshot(mercados)
    estado["mercados_rastreados"] = len(historial)

    # ── 3. Verificar salidas de posiciones abiertas ───────────────
    df_libro, n_cerradas = verificar_salidas(df_libro, estado, mercados)
    if n_cerradas:
        guardar_estado(estado)

    # ── 4. Calcular momentum y buscar señales ─────────────────────
    n_abiertas = len(df_libro[df_libro["estado"] == "ABIERTA"]) \
                 if not df_libro.empty else 0
    cupo = MAX_POSICIONES - n_abiertas

    señales = []
    for m in mercados:
        señal, mom, c1h, c4h, p_act = calcular_momentum(m["id"], historial)
        if señal == "NEUTRAL":
            continue
        señales.append({**m, "señal": señal, "momentum": mom,
                        "cambio_1h": c1h, "cambio_4h": c4h})

    # Ordenar por momentum absoluto (mayor movimiento = más urgente)
    señales = sorted(señales, key=lambda x: abs(x["momentum"]), reverse=True)
    log.info(f"Señales de momentum: {len(señales)} | Cupo: {cupo}")

    if cupo <= 0 or not señales:
        log.info("Sin cupo o sin señales — fin de ciclo")
    else:
        preguntas_abiertas = set(
            df_libro[df_libro["estado"] == "ABIERTA"]["pregunta"].tolist()
        ) if not df_libro.empty else set()

        nuevas = []
        cliente = Groq(api_key=GROQ_API_KEY)

        for m in señales:
            if len(nuevas) >= cupo: break
            if m["pregunta"][:70] in preguntas_abiertas: continue

            # ── LLM: sanity check rápido (opcional pero útil) ──
            # Pregunta concisa: ¿tiene sentido este movimiento?
            prompt = (
                f"Mercado: {m['pregunta']}\n"
                f"Precio YES: {m['mid_price']:.2%} | "
                f"Cambio 1h: {m['cambio_1h']:+.1%} | Cambio 4h: {m['cambio_4h']:+.1%}\n"
                f"Señal momentum: {m['señal']}\n\n"
                f"¿Tiene sentido económico este movimiento? "
                f"Responde SOLO JSON: "
                f'{{ "tiene_sentido": true/false, "confianza": 0.0-1.0, "nota": "1 oración" }}'
            )
            try:
                resp  = cliente.chat.completions.create(
                    model    = "llama-3.3-70b-versatile",
                    messages = [{"role": "user", "content": prompt}],
                    max_tokens = 80,
                )
                txt = resp.choices[0].message.content.strip()
                if "```" in txt:
                    txt = txt.split("```")[1].split("```")[0].replace("json","").strip()
                llm = json.loads(txt)
            except:
                llm = {"tiene_sentido": True, "confianza": 0.5, "nota": "sin análisis"}

            # Abrir posición si el LLM no lo contradice fuertemente
            if not llm.get("tiene_sentido", True) and llm.get("confianza", 0) > 0.7:
                log.info(f"LLM descarta: {m['pregunta'][:45]}")
                time.sleep(1)
                continue

            confianza    = llm.get("confianza", 0.5)
            precio_token = m["mid_price"] if m["señal"] == "COMPRAR YES" \
                           else round(1 - m["mid_price"], 4)
            monto        = round(min(
                estado["capital_actual"] * abs(m["momentum"]) * confianza * 0.5,
                CAPITAL_POR_OP
            ), 2)

            if monto < 5: continue  # mínimo $5

            nuevas.append({
                "fecha_entrada":        datetime.now().strftime("%Y-%m-%d"),
                "fecha_entrada_dt":     datetime.now().strftime("%Y-%m-%d %H:%M"),
                "market_id":            m["id"],
                "pregunta":             m["pregunta"][:70],
                "señal":                m["señal"],
                "precio_entrada":       m["mid_price"],
                "precio_token_entrada": precio_token,
                "precio_actual":        m["mid_price"],
                "precio_cierre":        None,
                "pct_cambio":           None,
                "momentum_entrada":     m["momentum"],
                "cambio_1h":            m["cambio_1h"],
                "cambio_4h":            m["cambio_4h"],
                "llm_confianza":        confianza,
                "llm_nota":             llm.get("nota","")[:80],
                "monto_usdc":           monto,
                "dias_mercado":         m["dias"],
                "fecha_cierre_mercado": m["fecha_cierre"],
                "fecha_cierre_real":    None,
                "pnl_realizado":        None,
                "estado":               "ABIERTA",
                "razon_cierre":         None,
            })

            log.info(
                f"✅ NUEVA: {m['señal']} | {m['pregunta'][:40]} | "
                f"mom={m['momentum']:+.1%} (1h={m['cambio_1h']:+.1%}) | ${monto}"
            )
            time.sleep(1.5)

        if nuevas:
            df_nuevas = pd.DataFrame(nuevas)
            df_libro  = pd.concat([df_libro, df_nuevas], ignore_index=True) \
                        if not df_libro.empty else df_nuevas
            guardar_libro(df_libro)
            comprometido = sum(p["monto_usdc"] for p in nuevas)
            estado["capital_en_riesgo"] = estado.get("capital_en_riesgo", 0) + comprometido
            estado["capital_actual"]    = estado.get("capital_actual", CAPITAL_INICIAL) - comprometido

    # ── 5. Reporte ────────────────────────────────────────────────
    estado["n_ciclos"]      += 1
    estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    guardar_estado(estado)

    n_ab = len(df_libro[df_libro["estado"] == "ABIERTA"]) if not df_libro.empty else 0
    n_ce = len(df_libro[df_libro["estado"] == "CERRADA"]) if not df_libro.empty else 0
    pnl  = df_libro[df_libro["estado"] == "CERRADA"]["pnl_realizado"].sum() \
           if not df_libro.empty and n_ce > 0 else 0

    log.info("─" * 55)
    log.info(f"CICLO #{estado['n_ciclos']} | Rastreando {len(historial)} mercados")
    log.info(f"Abiertas: {n_ab} | Cerradas: {n_ce} | P&L: ${pnl:+.2f}")
    log.info(f"TP:{estado['n_tp']} SL:{estado['n_sl']} Time:{estado['n_time']}")
    log.info("=" * 55)


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("Ejecutando ciclo único (GitHub Actions)")
    ciclo()
