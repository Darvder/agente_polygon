#!/usr/bin/env python3
"""
agente_hibrido.py — v2
Orquesta tres módulos especializados:
  - volatility_engine: SL/TP/MAX_HORAS dinámicos por mercado
  - event_detector:    bloqueos inteligentes por evento ya explotado
  - bayesian_engine:   aprendizaje de win rate por condición

Señal de entrada: noticias + LLM (divergencia precio vs estimación)
Salida: TP/SL/TIME dinámicos adaptados a cada mercado
"""

import os, json, time, logging
import requests
import pandas as pd
from groq import Groq
from newsapi import NewsApiClient
from datetime import datetime, timedelta

from bayesian_engine   import BayesianEngine
from volatility_engine import VolatilityEngine
from event_detector    import EventDetector

os.environ['TZ'] = 'America/Guayaquil'

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ── Parámetros globales (los de mercado los calcula VolatilityEngine) ──
MIN_EDGE        = 0.03
MIN_CONFIANZA   = 0.50
MIN_VOLUMEN     = 10_000
MAX_SPREAD      = 0.08
MIN_PRECIO      = 0.04
MAX_PRECIO      = 0.96
MAX_DIAS        = 180
MIN_DIAS        = 1
MAX_POSICIONES  = 10
CAPITAL_INICIAL = 1_000
CAPITAL_POR_OP  = 20
MAX_EXPOSICION  = 40
MAX_PERDIDA_DIA = 30
NEWS_WINDOW_H   = 48

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

PROMPT = """Eres un trader especializado en mercados de predicción.

Mercado: {pregunta}
Precio actual YES: {precio:.1%}
Días hasta resolución: {dias}
Spread: {spread:.1%}

Noticias de las últimas 48 horas:
{noticias}

Historial de este mercado: {patron}

Estima la probabilidad real de YES. Si no hay noticias relevantes → estimacion = precio actual.

Responde SOLO con JSON:
{{"estimacion":<float>,"confianza":<float>,"hay_noticia":<bool>,"razonamiento":"<max 2 oraciones>"}}"""


# ── Estado y libro ─────────────────────────────────────────────────

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f: return json.load(f)
    return {"capital_inicial":CAPITAL_INICIAL,"capital_actual":CAPITAL_INICIAL,
            "capital_en_riesgo":0,"n_ciclos":0,"ultima_corrida":"—",
            "n_tp":0,"n_sl":0,"n_time":0}

def guardar_estado(e):
    with open(ARCHIVO_ESTADO,"w") as f: json.dump(e,f,indent=2)

def cargar_libro():
    return pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()

def guardar_libro(df): df.to_csv(ARCHIVO_LIBRO,index=False)


# ── Scanner ────────────────────────────────────────────────────────

def escanear():
    hoy = datetime.now().date()
    try:
        r = requests.get(f"{BASE_URL}/markets",
                        params={"active":True,"closed":False,"limit":500},
                        timeout=TIMEOUT)
        r.raise_for_status(); raw = r.json()
    except Exception as e:
        log.error(f"Error API: {e}"); return []
    mercados = []
    for m in raw:
        try:
            q = m.get("question","")
            if any(p in q.lower() for p in PATRONES_EXCLUIR): continue
            bid=float(m.get("bestBid",0)); ask=float(m.get("bestAsk",0))
            if bid<=0 or ask<=0: continue
            sp=round(ask-bid,4); mid=round((bid+ask)/2,4)
            if sp>MAX_SPREAD or mid<MIN_PRECIO or mid>MAX_PRECIO: continue
            if float(m.get("volume",0))<MIN_VOLUMEN: continue
            fs=m.get("endDate","")[:10]
            if not fs: continue
            dias=(datetime.strptime(fs,"%Y-%m-%d").date()-hoy).days
            if dias<MIN_DIAS or dias>MAX_DIAS: continue
            mercados.append({"id":m.get("id",q[:30]),"pregunta":q,
                            "mid_price":mid,"spread":sp,
                            "volumen_usd":float(m.get("volume",0)),
                            "dias":dias,"fecha_cierre":fs})
        except: continue
    log.info(f"Mercados: {len(mercados)}")
    return mercados


# ── Noticias ───────────────────────────────────────────────────────

def noticias(pregunta, cn):
    stop = {"will","the","a","an","in","on","at","to","for","of","and",
            "or","before","after","by","new","be","is","are","win","2026","2025"}
    q    = " ".join([w for w in pregunta.replace("?","").split()
                     if w.lower() not in stop and len(w)>2][:5])
    fd   = (datetime.now()-timedelta(hours=NEWS_WINDOW_H)).strftime("%Y-%m-%d")
    try:
        arts = cn.get_everything(q=q,from_param=fd,language="en",
                                 sort_by="publishedAt",page_size=5).get("articles",[])[:5]
        return [{"f":a.get("publishedAt","")[:16],
                 "s":a.get("source",{}).get("name",""),
                 "t":a.get("title","")} for a in arts]
    except: return []


# ── Verificar salidas (usa TP/SL/HORAS dinámicos guardados) ───────

def verificar_salidas(df, estado, mercados_actuales):
    if df.empty: return df, 0
    pl = {m["id"]:m["mid_price"] for m in mercados_actuales}
    ql = {m["pregunta"][:70]:m["mid_price"] for m in mercados_actuales}
    ahora = datetime.now(); cerradas = 0

    for idx, pos in df[df["estado"]=="ABIERTA"].iterrows():
        try:
            dt  = datetime.strptime(pos["fecha_entrada_dt"],"%Y-%m-%d %H:%M")
            h   = abs((ahora-dt).total_seconds()/3600)
            mid = pl.get(str(pos.get("market_id",""))) or ql.get(str(pos["pregunta"])[:70])

            # TP/SL/HORAS específicos guardados en la posición
            tp_pos = float(pos.get("tp_dinamico", 0.09))
            sl_pos = float(pos.get("sl_dinamico", -0.07))
            h_max  = float(pos.get("horas_max",   6))

            if mid is None:
                if h >= h_max: mid = float(pos["precio_actual"])
                else: continue

            df.loc[idx,"precio_actual"] = mid
            pte = float(pos["precio_token_entrada"])
            pta = mid if pos["señal"]=="COMPRAR YES" else 1-mid
            pct = (pta-pte)/pte

            df["razon_cierre"]      = df["razon_cierre"].astype(object)
            df["fecha_cierre_real"] = df["fecha_cierre_real"].astype(object)

            razon = None
            if   pct >= tp_pos: razon="TAKE_PROFIT"; estado["n_tp"]+=1
            elif pct <= sl_pos: razon="STOP_LOSS";   estado["n_sl"]+=1
            elif h >= h_max:    razon="TIME_EXIT";   estado["n_time"]+=1

            if razon:
                pnl = round(float(pos["monto_usdc"])*pct,2)
                df.loc[idx,"estado"]           = "CERRADA"
                df.loc[idx,"precio_cierre"]    = pta
                df.loc[idx,"pct_cambio"]       = round(pct,4)
                df.loc[idx,"pnl_realizado"]    = pnl
                df.loc[idx,"razon_cierre"]     = razon
                df.loc[idx,"fecha_cierre_real"]= ahora.strftime("%Y-%m-%d %H:%M")
                estado["capital_actual"]   = estado.get("capital_actual",CAPITAL_INICIAL)+float(pos["monto_usdc"])+pnl
                estado["capital_en_riesgo"]= max(0,estado.get("capital_en_riesgo",0)-float(pos["monto_usdc"]))
                cerradas+=1
                log.info(f"{'✅' if pnl>=0 else '❌'} [{razon}] {pos['pregunta'][:45]} | {pct:+.1%} | ${pnl:+.2f} | {h:.1f}h")
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")
    guardar_libro(df)
    return df, cerradas


# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def ciclo():
    log.info("="*55)
    log.info("CICLO HÍBRIDO v2 INICIADO")
    log.info("="*55)

    estado = cargar_estado()
    df     = cargar_libro()

    if not df.empty:
        estado["capital_en_riesgo"] = float(
            df[df["estado"]=="ABIERTA"]["monto_usdc"].sum()
        )

    # Circuit breaker
    hoy = datetime.now().strftime("%Y-%m-%d")
    if not df.empty and "CERRADA" in df["estado"].values:
        ce_hoy = df[
            (df["estado"]=="CERRADA") &
            (df["fecha_cierre_real"].fillna("").astype(str).str.startswith(hoy))
        ]
        if ce_hoy["pnl_realizado"].sum() <= -MAX_PERDIDA_DIA:
            log.warning("⛔ CIRCUIT BREAKER activado")
            estado["n_ciclos"]+=1; estado["ultima_corrida"]=datetime.now().strftime("%Y-%m-%d %H:%M")
            guardar_estado(estado); return

    # Inicializar módulos
    bayesian  = BayesianEngine(
        archivo_libro  = ARCHIVO_LIBRO,
        archivo_modelo = "datos_polymarket/paper_trading/bayesian_hibrido.json"
    )
    bayesian.entrenar()
    log.info(bayesian.reporte())

    vol_engine = VolatilityEngine()
    ev_detector = EventDetector(archivo_libro=ARCHIVO_LIBRO)

    # Clientes
    cliente_llm  = Groq(api_key=GROQ_API_KEY)
    cliente_news = NewsApiClient(api_key=NEWS_API_KEY)

    # Escanear y verificar salidas
    mercados = escanear()
    if not mercados: return

    df, n_cerradas = verificar_salidas(df, estado, mercados)
    if n_cerradas: guardar_estado(estado)

    # Filtro hora madrugada
    if datetime.now().hour < 6:
        log.info("Madrugada — sin nuevas entradas")
        estado["n_ciclos"]+=1; estado["ultima_corrida"]=datetime.now().strftime("%Y-%m-%d %H:%M")
        guardar_estado(estado); return

    # Cupo
    n_ab = len(df[df["estado"]=="ABIERTA"]) if not df.empty else 0
    cupo = MAX_POSICIONES - n_ab
    if cupo <= 0:
        log.info("Cartera llena")
        estado["n_ciclos"]+=1; estado["ultima_corrida"]=datetime.now().strftime("%Y-%m-%d %H:%M")
        guardar_estado(estado); return

    preguntas_ab = set(df[df["estado"]=="ABIERTA"]["pregunta"].tolist()) if not df.empty else set()
    nuevas = []; analizados = 0

    for m in sorted(mercados, key=lambda x: -x["volumen_usd"]):
        if len(nuevas) >= cupo: break
        if analizados >= min(cupo+8, 100): break
        if m["pregunta"][:70] in preguntas_ab: continue

        # ── Event detector ─────────────────────────────────────────
        puede, motivo = ev_detector.puede_entrar(m["id"], m["pregunta"])
        if not puede:
            log.info(f"EventDetector: {m['pregunta'][:40]} → {motivo}")
            analizados+=1; continue

        # ── Cap por mercado ────────────────────────────────────────
        if not df.empty:
            exp = df[(df["estado"]=="ABIERTA") &
                     (df["market_id"].astype(str)==str(m["id"]))]["monto_usdc"].sum()
            if exp >= MAX_EXPOSICION: continue

        # ── Noticias ───────────────────────────────────────────────
        nots = noticias(m["pregunta"], cliente_news)
        nots_txt = "\n".join([f"- [{n['f']}] {n['s']}: {n['t']}" for n in nots]) \
                   if nots else "Sin noticias en las últimas 48h."

        # ── Patrón histórico del mercado ───────────────────────────
        patron = ev_detector.patron_mercado(m["id"])
        patron_txt = f"n={patron.get('n',0)} trades, wr={patron.get('wr',0):.0%}, pnl=${patron.get('pnl',0):+.2f}" \
                     if patron else "sin historial"

        # ── LLM ────────────────────────────────────────────────────
        prompt = PROMPT.format(
            pregunta=m["pregunta"], precio=m["mid_price"],
            dias=m["dias"], spread=m["spread"],
            noticias=nots_txt, patron=patron_txt
        )
        try:
            msg = cliente_llm.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}], max_tokens=150)
            txt = msg.choices[0].message.content.strip()
            if "```" in txt: txt = txt.split("```")[1].split("```")[0].replace("json","").strip()
            an = json.loads(txt)
        except Exception as e:
            log.warning(f"Error LLM: {e}"); time.sleep(2); analizados+=1; continue

        estimacion  = float(an.get("estimacion", m["mid_price"]))
        confianza   = float(an.get("confianza", 0.5))
        hay_noticia = bool(an.get("hay_noticia", False))
        diferencia  = estimacion - m["mid_price"]
        edge_neto   = round(abs(diferencia) - m["spread"], 4)

        if not hay_noticia:
            analizados+=1; time.sleep(1); continue
        if edge_neto < MIN_EDGE or confianza < MIN_CONFIANZA:
            log.info(f"Sin edge: {m['pregunta'][:40]} | edge={edge_neto:.1%}")
            analizados+=1; time.sleep(1); continue

        # ── Bayesiano ──────────────────────────────────────────────
        ok, score, feats = bayesian.should_trade(
            pregunta=m["pregunta"], cambio_1h=diferencia,
            precio_entrada=m["mid_price"],
            fecha_dt=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        if not ok:
            log.info(f"Bayesiano bloquea ({score:.0%}): {m['pregunta'][:40]}")
            analizados+=1; time.sleep(1); continue

        # ── Volatility Engine → SL/TP/HORAS dinámicos ─────────────
        tp, sl, max_h, met = vol_engine.get_params(m["id"], m["dias"])

        # ── Señal y posición ───────────────────────────────────────
        señal       = "COMPRAR YES" if diferencia > 0 else "COMPRAR NO"
        precio_tok  = m["mid_price"] if señal=="COMPRAR YES" else round(1-m["mid_price"],4)
        kelly       = edge_neto * confianza * 0.3
        monto       = round(min(estado["capital_actual"]*kelly, CAPITAL_POR_OP), 2)
        if monto < 5: analizados+=1; continue

        # Registrar evento en detector
        ev_detector.registrar_evento(m["id"], m["pregunta"])

        nuevas.append({
            "fecha_entrada":        datetime.now().strftime("%Y-%m-%d"),
            "fecha_entrada_dt":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market_id":            m["id"],
            "pregunta":             m["pregunta"][:70],
            "señal":                señal,
            "precio_entrada":       m["mid_price"],
            "precio_token_entrada": precio_tok,
            "precio_actual":        m["mid_price"],
            "precio_cierre":        None,
            "pct_cambio":           None,
            "llm_estimacion":       estimacion,
            "llm_confianza":        confianza,
            "llm_edge":             edge_neto,
            "hay_noticia":          hay_noticia,
            "n_noticias":           len(nots),
            "tp_dinamico":          tp,       # ← guardados por posición
            "sl_dinamico":          sl,
            "horas_max":            max_h,
            "vol_1d":               met["vol_1d"] if met else None,
            "monto_usdc":           monto,
            "dias_mercado":         m["dias"],
            "fecha_cierre_mercado": m["fecha_cierre"],
            "fecha_cierre_real":    None,
            "pnl_realizado":        None,
            "estado":               "ABIERTA",
            "razon_cierre":         None,
            "razonamiento":         an.get("razonamiento","")[:100],
        })

        log.info(
            f"✅ NUEVA: {señal} | {m['pregunta'][:38]} | "
            f"edge={edge_neto:.1%} | TP={tp:.0%} SL={sl:.0%} {max_h}h | ${monto}"
        )
        analizados+=1; time.sleep(2)

    if nuevas:
        df_n = pd.DataFrame(nuevas)
        df   = pd.concat([df,df_n],ignore_index=True) if not df.empty else df_n
        guardar_libro(df)
        comp = sum(p["monto_usdc"] for p in nuevas)
        estado["capital_en_riesgo"] = estado.get("capital_en_riesgo",0)+comp
        estado["capital_actual"]    = estado.get("capital_actual",CAPITAL_INICIAL)-comp

    estado["n_ciclos"]+=1
    estado["ultima_corrida"]=datetime.now().strftime("%Y-%m-%d %H:%M")
    guardar_estado(estado)

    n_ab = len(df[df["estado"]=="ABIERTA"]) if not df.empty else 0
    n_ce = len(df[df["estado"]=="CERRADA"]) if not df.empty else 0
    pnl  = df[df["estado"]=="CERRADA"]["pnl_realizado"].sum() if not df.empty and n_ce>0 else 0

    log.info("─"*55)
    log.info(f"CICLO #{estado['n_ciclos']} | Analizados={analizados} Nuevas={len(nuevas)}")
    log.info(f"Abiertas={n_ab} Cerradas={n_ce} P&L=${pnl:+.2f}")
    log.info(f"TP:{estado['n_tp']} SL:{estado['n_sl']} Time:{estado['n_time']}")
    log.info("="*55)


if __name__ == "__main__":
    log.info("Agente HÍBRIDO v2 iniciando...")
    log.info(f"Módulos: BayesianEngine + VolatilityEngine + EventDetector")
    ciclo()
