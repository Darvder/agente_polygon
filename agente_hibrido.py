#!/usr/bin/env python3
"""
agente_hibrido.py
Señal de entrada: noticias + LLM (divergencia entre precio y probabilidad real)
Salida: TP/SL/TIME activos (no espera resolución del mercado)
Aprendizaje: motor Bayesiano sobre resultados históricos

Lógica económica:
  Las noticias mueven la probabilidad real antes de que el mercado
  la absorba completamente. Si el LLM estima que el evento ocurrirá
  con 70% de probabilidad pero el mercado muestra 50%, hay 20% de edge.
  Entramos y salimos en horas, no esperamos resolución.
"""

import os, json, time, logging
import requests
import pandas as pd
from groq import Groq
from newsapi import NewsApiClient
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from bayesian_engine import BayesianEngine

os.environ['TZ'] = 'America/Guayaquil'

# ── API Keys ───────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ══════════════════════════════════════════════════════════════════
# PARÁMETROS
# ══════════════════════════════════════════════════════════════════

TAKE_PROFIT   = 0.09
STOP_LOSS     = -0.07
MAX_HORAS     = 6        # más tiempo que momentum — noticias tardan más en absorberse
CICLO_HORAS   = 0.5      # cada 30 minutos

MIN_EDGE      = 0.06     # divergencia mínima LLM vs mercado (6%)
MIN_CONFIANZA = 0.55     # confianza mínima del LLM
MIN_VOLUMEN   = 10_000
MAX_SPREAD    = 0.08
MIN_PRECIO    = 0.04
MAX_PRECIO    = 0.96
MAX_DIAS      = 180
MIN_DIAS      = 1

MAX_POSICIONES       = 10
CAPITAL_INICIAL      = 1_000
CAPITAL_POR_OP       = 20
MAX_EXPOSICION       = 40
MAX_PERDIDA_DIA      = 30
NEWS_WINDOW_H        = 48   # noticias de las últimas 48 horas

PATRONES_EXCLUIR = [
    "jesus","christ","second coming","rapture",
    "alien","ufo","zombie","apocalypse",
    "win the 2025-26 english premier",
    "finish in 2nd place","finish in 1st place","finish in 3rd place",
]

ARCHIVO_LIBRO  = "datos_polymarket/paper_trading/libro_hibrido.csv"
ARCHIVO_ESTADO = "datos_polymarket/paper_trading/estado_hibrido.json"

os.makedirs("datos_polymarket/logs", exist_ok=True)
os.makedirs("datos_polymarket/paper_trading", exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s | %(levelname)s | %(message)s",
    handlers = [
        logging.FileHandler("datos_polymarket/logs/agente_hibrido.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("hibrido")

# Prompt diseñado para detectar divergencia noticia-precio
PROMPT_HIBRIDO = """Eres un trader especializado en mercados de predicción.

Mercado: {pregunta}
Precio actual YES: {precio:.1%}
Días hasta resolución: {dias}
Spread: {spread:.1%}

Noticias de las últimas 48 horas relacionadas:
{noticias}

Tu tarea:
1. Estima la probabilidad real de YES basándote en las noticias
2. Si no hay noticias relevantes → estimacion = precio actual (sin edge)
3. Evalúa si vale la pena operar considerando el spread

Responde SOLO con JSON válido:
{{"estimacion": <float 0.0-1.0>, "confianza": <float 0.1-1.0>, "hay_noticia": <true/false>, "razonamiento": "<max 2 oraciones>"}}"""


# ══════════════════════════════════════════════════════════════════
# ESTADO Y LIBRO
# ══════════════════════════════════════════════════════════════════

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f: return json.load(f)
    return {"capital_inicial": CAPITAL_INICIAL, "capital_actual": CAPITAL_INICIAL,
            "capital_en_riesgo": 0, "n_ciclos": 0, "ultima_corrida": "—",
            "n_tp": 0, "n_sl": 0, "n_time": 0}

def guardar_estado(e):
    with open(ARCHIVO_ESTADO, "w") as f: json.dump(e, f, indent=2)

def cargar_libro():
    return pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()

def guardar_libro(df):
    df.to_csv(ARCHIVO_LIBRO, index=False)


# ══════════════════════════════════════════════════════════════════
# SCANNER
# ══════════════════════════════════════════════════════════════════

def escanear_mercados():
    hoy = datetime.now().date()
    try:
        r = requests.get(f"{BASE_URL}/markets",
                        params={"active":True,"closed":False,"limit":500},
                        timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        log.error(f"Error API: {e}"); return []

    mercados = []
    for m in raw:
        try:
            pregunta = m.get("question","")
            if any(p in pregunta.lower() for p in PATRONES_EXCLUIR): continue
            bid = float(m.get("bestBid",0)); ask = float(m.get("bestAsk",0))
            if bid <= 0 or ask <= 0: continue
            spread = round(ask-bid,4); mid = round((bid+ask)/2,4)
            if spread > MAX_SPREAD or mid < MIN_PRECIO or mid > MAX_PRECIO: continue
            if float(m.get("volume",0)) < MIN_VOLUMEN: continue
            fecha_str = m.get("endDate","")[:10]
            if not fecha_str: continue
            dias = (datetime.strptime(fecha_str,"%Y-%m-%d").date()-hoy).days
            if dias < MIN_DIAS or dias > MAX_DIAS: continue
            mercados.append({
                "id":          m.get("id", pregunta[:30]),
                "pregunta":    pregunta,
                "mid_price":   mid,
                "spread":      spread,
                "volumen_usd": float(m.get("volume",0)),
                "dias":        dias,
                "fecha_cierre":fecha_str,
            })
        except: continue

    log.info(f"Mercados escaneados: {len(mercados)}")
    return mercados


# ══════════════════════════════════════════════════════════════════
# NOTICIAS
# ══════════════════════════════════════════════════════════════════

def buscar_noticias(pregunta, cliente_news):
    """Busca noticias relacionadas con el mercado en las últimas 48h."""
    stop_w = {"will","the","a","an","in","on","at","to","for","of","and",
               "or","before","after","by","new","be","is","are","win","2026","2025"}
    palabras = [w for w in pregunta.replace("?","").split()
                if w.lower() not in stop_w and len(w) > 2]
    query = " ".join(palabras[:5])
    fd    = (datetime.now() - timedelta(hours=NEWS_WINDOW_H)).strftime("%Y-%m-%d")
    try:
        resp = cliente_news.get_everything(
            q=query, from_param=fd,
            language="en", sort_by="publishedAt", page_size=5
        )
        arts = resp.get("articles",[])[:5]
        return [{"fecha":  a.get("publishedAt","")[:16],
                 "fuente": a.get("source",{}).get("name",""),
                 "titulo": a.get("title","")} for a in arts]
    except:
        return []


# ══════════════════════════════════════════════════════════════════
# SALIDAS AUTOMÁTICAS
# ══════════════════════════════════════════════════════════════════

def verificar_salidas(df_libro, estado, mercados_actuales):
    if df_libro.empty: return df_libro, 0
    precio_lookup   = {m["id"]: m["mid_price"] for m in mercados_actuales}
    pregunta_lookup = {m["pregunta"][:70]: m["mid_price"] for m in mercados_actuales}
    ahora    = datetime.now()
    abiertas = df_libro[df_libro["estado"]=="ABIERTA"].copy()
    cerradas = 0

    for idx, pos in abiertas.iterrows():
        try:
            dt_entrada     = datetime.strptime(pos["fecha_entrada_dt"],"%Y-%m-%d %H:%M")
            horas_abiertas = abs((ahora-dt_entrada).total_seconds()/3600)
            mid_actual = (precio_lookup.get(str(pos.get("market_id",""))) or
                         pregunta_lookup.get(str(pos["pregunta"])[:70]))
            if mid_actual is None:
                if horas_abiertas >= MAX_HORAS:
                    mid_actual = float(pos["precio_actual"])
                else: continue
            df_libro.loc[idx,"precio_actual"] = mid_actual
            p_token_e = float(pos["precio_token_entrada"])
            p_token_a = mid_actual if pos["señal"]=="COMPRAR YES" else 1-mid_actual
            pct = (p_token_a-p_token_e)/p_token_e
            df_libro["razon_cierre"]      = df_libro["razon_cierre"].astype(object)
            df_libro["fecha_cierre_real"] = df_libro["fecha_cierre_real"].astype(object)
            razon = None
            if   pct >= TAKE_PROFIT:          razon="TAKE_PROFIT"; estado["n_tp"]+=1
            elif pct <= STOP_LOSS:            razon="STOP_LOSS";   estado["n_sl"]+=1
            elif horas_abiertas >= MAX_HORAS: razon="TIME_EXIT";   estado["n_time"]+=1
            if razon:
                pnl = round(float(pos["monto_usdc"])*pct,2)
                df_libro.loc[idx,"estado"]           = "CERRADA"
                df_libro.loc[idx,"precio_cierre"]    = p_token_a
                df_libro.loc[idx,"pct_cambio"]       = round(pct,4)
                df_libro.loc[idx,"pnl_realizado"]    = pnl
                df_libro.loc[idx,"razon_cierre"]     = razon
                df_libro.loc[idx,"fecha_cierre_real"]= ahora.strftime("%Y-%m-%d %H:%M")
                estado["capital_actual"]    = estado.get("capital_actual",CAPITAL_INICIAL)+float(pos["monto_usdc"])+pnl
                estado["capital_en_riesgo"] = max(0,estado.get("capital_en_riesgo",0)-float(pos["monto_usdc"]))
                cerradas += 1
                log.info(f"{'✅' if pnl>=0 else '❌'} [{razon}] {pos['pregunta'][:45]} | {pct:+.1%} | P&L={pnl:+.2f}$ | {horas_abiertas:.1f}h")
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")
    guardar_libro(df_libro)
    return df_libro, cerradas


# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def ciclo():
    log.info("="*55)
    log.info("CICLO HÍBRIDO INICIADO")
    log.info("="*55)

    estado   = cargar_estado()
    df_libro = cargar_libro()

    # Recalcular capital en riesgo desde CSV
    if not df_libro.empty:
        estado["capital_en_riesgo"] = float(
            df_libro[df_libro["estado"]=="ABIERTA"]["monto_usdc"].sum()
        )

    # Circuit breaker
    hoy = datetime.now().strftime("%Y-%m-%d")
    if not df_libro.empty and "CERRADA" in df_libro["estado"].values:
        cerradas_hoy = df_libro[
            (df_libro["estado"]=="CERRADA") &
            (df_libro["fecha_cierre_real"].fillna("").astype(str).str.startswith(hoy))
        ]
        perdida_hoy = cerradas_hoy["pnl_realizado"].sum()
        if perdida_hoy <= -MAX_PERDIDA_DIA:
            log.warning(f"⛔ CIRCUIT BREAKER: pérdida del día ${perdida_hoy:.2f}")
            estado["n_ciclos"] += 1
            estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            guardar_estado(estado)
            return

    # Bayesiano
    bayesian = BayesianEngine(
        archivo_libro="datos_polymarket/paper_trading/libro_momentum.csv",
        archivo_modelo="datos_polymarket/paper_trading/bayesian_hibrido.json"
    )
    bayesian.entrenar()

    # Clientes
    cliente_llm  = Groq(api_key=GROQ_API_KEY)
    cliente_news = NewsApiClient(api_key=NEWS_API_KEY)

    # Escanear mercados
    mercados = escanear_mercados()
    if not mercados:
        log.warning("Sin mercados"); return

    # Verificar salidas
    df_libro, n_cerradas = verificar_salidas(df_libro, estado, mercados)
    if n_cerradas: guardar_estado(estado)

    # Anti re-entrada
    hace_2h = (datetime.now()-timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    if not df_libro.empty and "CERRADA" in df_libro["estado"].values:
        ce_df = df_libro[df_libro["estado"]=="CERRADA"].copy()
        ce_df["fecha_cierre_real"] = ce_df["fecha_cierre_real"].fillna("").astype(str)
        recientes = ce_df[ce_df["fecha_cierre_real"]>=hace_2h]["market_id"].astype(str).tolist()
    else:
        recientes = []

    # Filtro hora madrugada
    hora_actual = datetime.now().hour
    if hora_actual < 6:
        log.info(f"Madrugada ({hora_actual}h) — sin nuevas entradas")
        estado["n_ciclos"] += 1
        estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        guardar_estado(estado)
        return

    # Cupo disponible
    n_abiertas = len(df_libro[df_libro["estado"]=="ABIERTA"]) if not df_libro.empty else 0
    cupo = MAX_POSICIONES - n_abiertas
    if cupo <= 0:
        log.info("Cartera llena")
        estado["n_ciclos"] += 1
        estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        guardar_estado(estado)
        return

    preguntas_abiertas = set(
        df_libro[df_libro["estado"]=="ABIERTA"]["pregunta"].tolist()
    ) if not df_libro.empty else set()

    # Ordenar mercados por volumen (más líquidos primero)
    mercados_ordenados = sorted(mercados, key=lambda x: -x["volumen_usd"])
    nuevas     = []
    analizados = 0

    for m in mercados_ordenados:
        if len(nuevas) >= cupo: break
        if analizados >= min(cupo+8, 20): break
        if m["pregunta"][:70] in preguntas_abiertas: continue
        if str(m["id"]) in recientes: continue

        # Cap por mercado
        if not df_libro.empty:
            expuesto = df_libro[
                (df_libro["estado"]=="ABIERTA") &
                (df_libro["market_id"].astype(str)==str(m["id"]))
            ]["monto_usdc"].sum()
            if expuesto >= MAX_EXPOSICION: continue

        # Buscar noticias
        noticias = buscar_noticias(m["pregunta"], cliente_news)
        nots_txt = "\n".join([
            f"- [{n['fecha']}] {n['fuente']}: {n['titulo']}"
            for n in noticias
        ]) if noticias else "Sin noticias en las últimas 48h."

        # LLM: estimar probabilidad con noticias
        prompt = PROMPT_HIBRIDO.format(
            pregunta = m["pregunta"],
            precio   = m["mid_price"],
            dias     = m["dias"],
            spread   = m["spread"],
            noticias = nots_txt,
        )
        try:
            msg = cliente_llm.chat.completions.create(
                model    = "llama-3.3-70b-versatile",
                messages = [{"role":"user","content":prompt}],
                max_tokens = 150,
            )
            txt = msg.choices[0].message.content.strip()
            if "```" in txt:
                txt = txt.split("```")[1].split("```")[0].replace("json","").strip()
            analisis = json.loads(txt)
        except Exception as e:
            log.warning(f"Error LLM '{m['pregunta'][:35]}': {e}")
            time.sleep(2); analizados += 1; continue

        estimacion  = float(analisis.get("estimacion", m["mid_price"]))
        confianza   = float(analisis.get("confianza", 0.5))
        hay_noticia = bool(analisis.get("hay_noticia", False))
        diferencia  = estimacion - m["mid_price"]
        edge_neto   = round(abs(diferencia) - m["spread"], 4)

        # Sin noticia = sin ventaja informacional = no operar
        if not hay_noticia:
            analizados += 1
            time.sleep(1.5)
            continue

        # Edge insuficiente
        if edge_neto < MIN_EDGE or confianza < MIN_CONFIANZA:
            log.info(f"Sin edge: {m['pregunta'][:40]} | edge={edge_neto:.2%} conf={confianza:.0%}")
            analizados += 1
            time.sleep(1.5)
            continue

        # Señal
        if diferencia > 0:
            señal = "COMPRAR YES"
            precio_token = m["mid_price"]
        else:
            señal = "COMPRAR NO"
            precio_token = round(1 - m["mid_price"], 4)

        # Bayesiano
        ok, score, feats = bayesian.should_trade(
            pregunta       = m["pregunta"],
            cambio_1h      = diferencia,    # usamos divergencia como proxy de momentum
            precio_entrada = m["mid_price"],
            fecha_dt       = datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        if not ok:
            log.info(f"Bayesiano bloquea (score={score:.0%}): {m['pregunta'][:40]}")
            analizados += 1
            time.sleep(1.5)
            continue

        # Tamaño de posición: Kelly conservador
        kelly = edge_neto * confianza * 0.3
        monto = round(min(
            estado["capital_actual"] * kelly,
            CAPITAL_POR_OP
        ), 2)
        if monto < 5:
            analizados += 1
            continue

        nuevas.append({
            "fecha_entrada":        datetime.now().strftime("%Y-%m-%d"),
            "fecha_entrada_dt":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market_id":            m["id"],
            "pregunta":             m["pregunta"][:70],
            "señal":                señal,
            "precio_entrada":       m["mid_price"],
            "precio_token_entrada": precio_token,
            "precio_actual":        m["mid_price"],
            "precio_cierre":        None,
            "pct_cambio":           None,
            "llm_estimacion":       estimacion,
            "llm_confianza":        confianza,
            "llm_edge":             edge_neto,
            "hay_noticia":          hay_noticia,
            "n_noticias":           len(noticias),
            "monto_usdc":           monto,
            "dias_mercado":         m["dias"],
            "fecha_cierre_mercado": m["fecha_cierre"],
            "fecha_cierre_real":    None,
            "pnl_realizado":        None,
            "estado":               "ABIERTA",
            "razon_cierre":         None,
            "razonamiento":         analisis.get("razonamiento","")[:100],
        })

        log.info(
            f"✅ NUEVA: {señal} | {m['pregunta'][:40]} | "
            f"precio={m['mid_price']:.1%} → LLM={estimacion:.1%} | "
            f"edge={edge_neto:.1%} | ${monto}"
        )
        analizados += 1
        time.sleep(2)

    # Guardar nuevas posiciones
    if nuevas:
        df_nuevas = pd.DataFrame(nuevas)
        df_libro  = pd.concat([df_libro,df_nuevas],ignore_index=True) \
                    if not df_libro.empty else df_nuevas
        guardar_libro(df_libro)
        comprometido = sum(p["monto_usdc"] for p in nuevas)
        estado["capital_en_riesgo"] = estado.get("capital_en_riesgo",0)+comprometido
        estado["capital_actual"]    = estado.get("capital_actual",CAPITAL_INICIAL)-comprometido

    # Reporte
    estado["n_ciclos"]      += 1
    estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    guardar_estado(estado)

    n_ab = len(df_libro[df_libro["estado"]=="ABIERTA"]) if not df_libro.empty else 0
    n_ce = len(df_libro[df_libro["estado"]=="CERRADA"]) if not df_libro.empty else 0
    pnl  = df_libro[df_libro["estado"]=="CERRADA"]["pnl_realizado"].sum() \
           if not df_libro.empty and n_ce>0 else 0

    log.info("─"*55)
    log.info(f"CICLO #{estado['n_ciclos']} | Analizados: {analizados} | Nuevas: {len(nuevas)}")
    log.info(f"Abiertas: {n_ab} | Cerradas: {n_ce} | P&L: ${pnl:+.2f}")
    log.info(f"TP:{estado['n_tp']} SL:{estado['n_sl']} Time:{estado['n_time']}")
    log.info("="*55)


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Agente HÍBRIDO iniciando...")
    log.info(f"TP={TAKE_PROFIT:.0%} | SL={STOP_LOSS:.0%} | MaxH={MAX_HORAS}h | Edge mín={MIN_EDGE:.0%}")
    log.info("Señal: noticias+LLM | Salida: TP/SL/TIME activos")
    ciclo()
