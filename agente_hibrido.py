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
from newsapi import NewsApiClient
from datetime import datetime, timedelta
import re
import asyncio
from groq import AsyncGroq

def extraer_json_puro(texto):
    """Extrae solo el bloque JSON si la IA agrega texto extra."""
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return match.group(0) if match else texto
    except:
        return texto

from bayesian_engine   import BayesianEngine
from volatility_engine import VolatilityEngine
from event_detector    import EventDetector

os.environ['TZ'] = 'America/Guayaquil'


# Definimos un semáforo para permitir máximo 3 peticiones simultáneas a Groq y evitar el Error 429
groq_semaphore = asyncio.Semaphore(1)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")
cliente_llm = AsyncGroq(api_key=GROQ_API_KEY)
BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ── Parámetros globales (los de mercado los calcula VolatilityEngine) ──
MIN_EDGE        = 0.025   # Bajado a 2.5% para capturar más micro-ineficiencias
MIN_CONFIANZA   = 0.50    # Mantenido (umbral equilibrado para Llama-3)
MIN_VOLUMEN     = 4_000   # Bajado para escanear mercados medianos con más fallos de precio
MAX_SPREAD      = 0.10    # Subido al 10% para tolerar libros de órdenes más jóvenes
MIN_PRECIO      = 0.02    # Permite buscar oportunidades en "long-shots" baratos
MAX_PRECIO      = 0.98    # Permite operar contratos casi resueltos con ventajas seguras
MAX_DIAS        = 180     # Mantenido (6 meses máximo de retención)
MIN_DIAS        = 1       
MAX_POSICIONES  = 20     
CAPITAL_INICIAL = 1_000   
CAPITAL_POR_OP  = 20      
MAX_EXPOSICION  = 40      
MAX_PERDIDA_DIA = 30      
NEWS_WINDOW_H   = 72

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

PROMPT = """Eres un trader experto y especializado en mercados de predicción.

Mercado: {pregunta}
Precio actual YES: {precio:.1%}
Días hasta resolución: {dias}
Variación de Precio (Última 1h): {momentum}
Spread: {spread:.1%}

Noticias de las últimas 48 horas:
{noticias}

Historial de este mercado: {patron}

Estima la probabilidad real de YES usando tu conocimiento sobre el evento, el contexto deportivo/político, y las noticias si las hay. Tu estimación puede diferir del precio de mercado si tienes razones fundamentales para ello.

CRITICAL FORMAT INSTRUCTIONS:
You MUST respond with a single, perfectly formatted JSON object. 
Do NOT include any markdown code blocks (like ```json), do NOT add any introductory or concluding text outside the curly braces, and NEVER add trailing comments or orphan strings inside the JSON object.

Your response must contain EXACTLY these 4 keys and nothing else:
{{
  "estimacion": (integer between 0 and 100 representing your probability percentage. MUST be a plain whole number like 14, 4, or 75. NEVER use decimals, slashes, or divisions),
  "confianza": (float between 0.0 and 1.0 representing your confidence level),
  "hay_noticia": (boolean true/false, true if there is recent relevant news from the text provided),
  "razonamiento": (string, brief text under 100 characters summarizing your logic. Place ALL your comments, notes, or history warnings strictly INSIDE this string value)
}}"""

# Cerrar inactivas __________________________________________________
def cerrar_inactivas(df, estado):
    """Cierra posiciones donde el mercado no se ha movido (vol implícita = 0)."""
    if df.empty: return df, 0
    cerradas = 0
    for idx, pos in df[df["estado"] == "ABIERTA"].iterrows():
        pte = float(pos["precio_token_entrada"])
        pta = float(pos["precio_actual"])
        if pte == 0: continue
        pct = (pta - pte) / pte
        # Si precio no se movió nada desde entrada → cerrar
        if abs(pct) < 0.001:
            pnl = round(float(pos["monto_usdc"]) * pct, 2)
            df.loc[idx, "estado"]            = "CERRADA"
            df.loc[idx, "precio_cierre"]     = pta
            df.loc[idx, "pct_cambio"]        = round(pct, 4)
            df.loc[idx, "pnl_realizado"]     = pnl
            df.loc[idx, "razon_cierre"]      = "INACTIVA"
            df.loc[idx, "fecha_cierre_real"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            estado["capital_actual"]    = estado.get("capital_actual", 1000.0) + float(pos["monto_usdc"]) + pnl
            estado["capital_en_riesgo"] = max(0, estado.get("capital_en_riesgo", 0) - float(pos["monto_usdc"]))
            cerradas += 1
            log.info(f"🔒 [INACTIVA] {pos['pregunta'][:45]} | Precio sin movimiento → capital liberado")
    guardar_libro(df)
    return df, cerradas

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
    raw = []
    offset = 0
    BATCH = 100
    MAX_PAGINAS = 20  # hasta 3000 mercados
    try:
        while len(raw) < MAX_PAGINAS * BATCH:
            r = requests.get(f"{BASE_URL}/markets",
                            params={"active":True,"closed":False,
                                    "limit":BATCH,"offset":offset},
                            timeout=TIMEOUT)
            r.raise_for_status()
            batch = r.json()
            if not batch: break
            raw.extend(batch)
            if len(batch) < BATCH: break  # última página
            offset += BATCH
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
    log.info(f"Mercados escaneados: {len(raw)} | Elegibles: {len(mercados)}")
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

            if mid is None:
                if h >= float(pos.get("horas_max", 6)): mid = float(pos["precio_actual"])
                else: continue

            # TP/SL/HORAS específicos guardados en la posición
            tp_pos = float(pos.get("tp_dinamico", 0.09))
            sl_pos = float(pos.get("sl_dinamico", -0.07))
            h_max  = float(pos.get("horas_max",   6))
            
            df.loc[idx,"precio_actual"] = mid
            pte = float(pos["precio_token_entrada"])
            pta = mid if pos["señal"]=="COMPRAR YES" else 1-mid
            pct = (pta-pte)/pte

            df["razon_cierre"]      = df["razon_cierre"].astype(object)
            df["fecha_cierre_real"] = df["fecha_cierre_real"].astype(object)

            razon = None
            
            # REGLA DE EARLY EXIT (Rotación de Capital)
            # Si logramos el 70% del TP esperado en menos del 25% del tiempo permitido, cerramos.
            if pct >= (tp_pos * 0.70) and h < (h_max * 0.25):
                razon = "EARLY_EXIT"
            elif pct >= tp_pos: 
                razon = "TAKE_PROFIT"
                estado["n_tp"] = estado.get("n_tp", 0) + 1
            elif pct <= sl_pos: 
                razon = "STOP_LOSS"
                estado["n_sl"] = estado.get("n_sl", 0) + 1
            elif h >= h_max:    
                razon = "TIME_EXIT"
                estado["n_time"] = estado.get("n_time", 0) + 1

            if razon:
                pnl = round(float(pos["monto_usdc"])*pct,2)
                df.loc[idx,"estado"]           = "CERRADA"
                df.loc[idx,"precio_cierre"]    = pta
                df.loc[idx,"pct_cambio"]       = round(pct,4)
                df.loc[idx,"pnl_realizado"]    = pnl
                df.loc[idx,"razon_cierre"]     = razon
                df.loc[idx,"fecha_cierre_real"]= ahora.strftime("%Y-%m-%d %H:%M")
                estado["capital_actual"]   = estado.get("capital_actual", CAPITAL_INICIAL) + float(pos["monto_usdc"]) + pnl
                estado["capital_en_riesgo"]= max(0, estado.get("capital_en_riesgo", 0) - float(pos["monto_usdc"]))
                cerradas += 1
                
                icono = "⚡" if razon == "EARLY_EXIT" else ("✅" if pnl >= 0 else "❌")
                log.info(f"{icono} [{razon}] {pos['pregunta'][:45]} | {pct:+.1%} | ${pnl:+.2f} | {h:.1f}h")
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")
            
    guardar_libro(df)
    return df, cerradas

async def procesar_mercado(m, df, estado, vol_engine, bayesian, ev_detector, cliente_news):
    """Procesa un único mercado de forma asíncrona e informa descarte por logs."""
    nombre_m = m["pregunta"][:35]
    
    async with groq_semaphore:
        # Filtro: Ya Abierta
        if m["pregunta"][:70] in set(df[df["estado"]=="ABIERTA"]["pregunta"].tolist()) if not df.empty else set():
            log.info(f"⏭️ {nombre_m} | Saltado: Ya existe posición ABIERTA.")
            return None
            
        # 1. --- Event Detector ---
        puede, motivo = ev_detector.puede_entrar(m["id"], m["pregunta"])
        if not puede:
            log.info(f"❌ {nombre_m} | Descartado por EventDetector: {motivo}")
            return None

        # 2. --- Noticias ---
        nots = await asyncio.to_thread(noticias, m["pregunta"], cliente_news)
        nots_txt = "\n".join([f"- [{n['f']}] {n['s']}: {n['t']}" for n in nots]) if nots else "Sin noticias."

        # 3. --- Prompt y Llamada Asíncrona a Groq ---
        patron = ev_detector.patron_mercado(m["id"])
        patron_txt = f"n={patron.get('n',0)} trades" if patron else "sin historial"
        
        prompt = PROMPT.format(
            pregunta=m["pregunta"], precio=m["mid_price"],
            dias=m["dias"], spread=m["spread"],
            noticias=nots_txt, patron=patron_txt,
            momentum=m.get("cambio_1h", 0.0) 
        )

        try:
            await asyncio.sleep(2) # Evita saturación de TPM
            msg = await cliente_llm.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role":"user","content":prompt}],
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            txt = msg.choices[0].message.content.strip()
            an = json.loads(txt)
        except Exception as e:
            log.warning(f"⚠️ {nombre_m} | Error en API Groq / Validación JSON: {e}")
            return None

        # 4. --- Filtros Matemáticos y Edge ---
        estimacion_raw = an.get("estimacion", m["mid_price"] * 100)
        try:
            estimacion = float(estimacion_raw)
            if estimacion > 1.0: 
                estimacion /= 100.0  # Convierte entero (ej: 14) a float (0.14)
        except Exception:
            estimacion = m["mid_price"]
        
        confianza = float(an.get("confianza", 0.5))
        hay_noticia = bool(an.get("hay_noticia", False))
        diferencia = estimacion - m["mid_price"]
        edge_neto = round(abs(diferencia) - m["spread"], 4)

        # Filtro: Bypass de Noticias
        EDGE_SIN_NOTICIA = 0.03   # 3% sin noticias (más exigente)
        EDGE_CON_NOTICIA = 0.015  # 1.5% con noticias (más permisivo)
        
        umbral = EDGE_CON_NOTICIA if hay_noticia else EDGE_SIN_NOTICIA
        if edge_neto < umbral:
            log.info(f"❌ {nombre_m} | Edge ({edge_neto:.2%}) < umbral ({'con' if hay_noticia else 'sin'} noticia: {umbral:.2%})")
            return None
        # Filtro: Umbrales Mínimos Básicos
        if edge_neto < MIN_EDGE:
            log.info(f"❌ {nombre_m} | Descartado: Edge Neto ({edge_neto:.2%}) inferior al mínimo ({MIN_EDGE:.2%}).")
            return None
            
        if confianza < MIN_CONFIANZA:
            log.info(f"❌ {nombre_m} | Descartado: Confianza de la IA ({confianza:.2f}) inferior al mínimo ({MIN_CONFIANZA:.2f}).")
            return None

        # 5. --- Motor Bayesiano y de Volatilidad ---
        ok, score, feats = bayesian.should_trade(
            pregunta=m["pregunta"], cambio_1h=m.get("cambio_1h", 0.0),
            precio_entrada=m["mid_price"], fecha_dt=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        log.info(f"🧠 Bayesiano Score para {nombre_m}: {score:.4f} | Forzado a True para entrenamiento.")
        # ANTES (línea 326):
        # DESPUÉS: úsalo como filtro suave (no bloquea, pero sí filtra cuando hay historial)
        if not ok and patron.get('n', 0) > 5:  # solo bloquea si hay suficiente historial
            log.info(f"🧠 {nombre_m} | Bayesiano bloquea (score={score:.3f}, n={patron.get('n',0)} trades)")
            return None
        log.info(f"🧠 {nombre_m} | Bayesiano: score={score:.4f} ({'bloqueado→ignorado' if not ok else 'OK'})")

        tp, sl, max_h, met = vol_engine.get_params(m["id"], m["dias"])

        MIN_VOL_1D = 0.001   # < 0.1% vol diaria → precio no se mueve
        MIN_RANGO  = 0.015   # < 1.5% rango histórico IQR → mercado plano
        if met and met.get("vol_1d", 0) < MIN_VOL_1D or met.get("rango", 0) < MIN_RANGO:
            log.info(f"❌ {nombre_m} | Descartado: Mercado inactivo (vol={met['vol_1d']:.4f}, rango={met['rango']:.3f})")
            return None

        # NUEVO LOG: Visualización detallada de Volatilidad y Momentum
        log.info(
            f"📊 Volatilidad {nombre_m} | "
            f"Movimiento 1h: {m.get('cambio_1h', 0.0):+.2%} | "
            f"TP: {tp:+.1%} | "
            f"SL: {sl:+.1%} | "
            f"Límite: {max_h}h | "
            f"Cálculo: {met}"
        )
        
        # Generar Estructura de la Nueva Posición
        señal = "COMPRAR YES" if diferencia > 0 else "COMPRAR NO"
        precio_tok = m["mid_price"] if señal=="COMPRAR YES" else round(1-m["mid_price"],4)
        kelly = edge_neto * confianza * 0.3
        monto = round(min(estado["capital_actual"] * kelly, CAPITAL_POR_OP), 2)
        
        # Filtro: Capital Mínimo por Trade
        if monto < 5:
            log.info(f"❌ {nombre_m} | Descartado: Tamaño de posición Kelly (${monto}) menor al mínimo de $5 USDC.")
            return None
        
        ev_detector.registrar_evento(m["id"], m["pregunta"])
        return {
            "fecha_entrada": datetime.now().strftime("%Y-%m-%d"),
            "fecha_entrada_dt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market_id": m["id"],
            "pregunta": m["pregunta"][:70],
            "señal": señal,
            "precio_entrada": m["mid_price"],
            "precio_token_entrada": precio_tok,
            "precio_actual": m["mid_price"],
            "tp_dinamico": tp,
            "sl_dinamico": sl,
            "horas_max": max_h,
            "monto_usdc": monto,
            "estado": "ABIERTA",
            "razonamiento": an.get("razonamiento","")[:100],
            "llm_confianza": confianza,
            "llm_edge":      edge_neto,
            "vol_1d":        met.get("vol_1d", 0.0) if met else 0.0,
        }


# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════
import re

def extraer_json_puro(texto):
    """Extrae el bloque JSON {} incluso si la IA añade texto extra o comete errores de formato."""
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return match.group(0) if match else texto
    except:
        return texto
async def ciclo():
    log.info("="*55)
    log.info("🚀 INICIANDO CICLO HÍBRIDO ASÍNCRONO v3")
    log.info("="*55)
    
    estado = cargar_estado()
    df = cargar_libro()
    df, n_inactivas = cerrar_inactivas(df, estado)
    if n_inactivas: guardar_estado(estado)
    
    # Inicialización de Módulos
    bayesian = BayesianEngine(archivo_libro=ARCHIVO_LIBRO, archivo_modelo="datos_polymarket/paper_trading/bayesian_hibrido.json")
    bayesian.entrenar()
    vol_engine = VolatilityEngine()
    ev_detector = EventDetector(archivo_libro=ARCHIVO_LIBRO)
    cliente_news = NewsApiClient(api_key=NEWS_API_KEY)

    # 1. Verificar salidas (Incluye la nueva lógica de Early Exit)
    df, n_cerradas = verificar_salidas(df, estado, escanear())
    if n_cerradas: guardar_estado(estado)

    # Escanear mercados del CLOB
    mercados = escanear()
    if not mercados: return

    # Filtro de cupo disponible
    n_ab = len(df[df["estado"]=="ABIERTA"]) if not df.empty else 0
    cupo = MAX_POSICIONES - n_ab
    if cupo <= 0:
        log.info("Cartera llena")
        return

    # 2. CREAR TAREAS ASÍNCRONAS EN PARALELO
    # Filtramos los top 40 mercados con mayor volumen para optimizar la cuota de tokens
    # Ordenar por volumen (más líquidos primero) y tomar top 60
    mercados_a_revisar = sorted(
        mercados,
        key=lambda x: x["volumen_usd"],
        reverse=True
    )[:60]
    
    tareas = [
        procesar_mercado(m, df, estado, vol_engine, bayesian, ev_detector, cliente_news)
        for m in mercados_a_revisar
    ]

    
    # Ejecución paralela masiva
    resultados = await asyncio.gather(*tareas)
    
    # 3. PROCESAR RESULTADOS DE MANERA SECUENCIAL
    nuevas_posiciones = [r for r in resultados if r is not None]
    
    nuevas_guardadas = []
    for pos in nuevas_posiciones:
        if len(nuevas_guardadas) >= cupo: break
        nuevas_guardadas.append(pos)
        log.info(f"✅ NUEVA POSICIÓN ASYNC: {pos['señal']} | {pos['pregunta'][:35]} | Monto: ${pos['monto_usdc']}")
        
    if nuevas_guardadas:
        df_n = pd.DataFrame(nuevas_guardadas)
        df = pd.concat([df, df_n], ignore_index=True) if not df.empty else df_n
        guardar_libro(df)
        
        # Re-calcular balances del estado financiero
        comp = sum(p["monto_usdc"] for p in nuevas_guardadas)
        estado["capital_en_riesgo"] = estado.get("capital_en_riesgo", 0) + comp
        estado["capital_actual"] = estado.get("capital_actual", 1000.0) - comp
        
    estado["n_ciclos"] += 1
    estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    guardar_estado(estado)
    
    log.info(f"🏁 FIN DEL CICLO ASÍNCRONO #{estado['n_ciclos']} | Nuevas Abiertas: {len(nuevas_guardadas)}")
    log.info("="*55)
  
if __name__ == "__main__":
    # Este es el nuevo "botón de encendido" asíncrono para el script
    asyncio.run(ciclo())
