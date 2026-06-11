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

from bayesian_engine   import BayesianEngine, get_categoria
from volatility_engine import VolatilityEngine
from event_detector    import EventDetector

os.environ['TZ'] = 'America/Guayaquil'


# Definimos un semáforo para permitir máximo 3 peticiones simultáneas a Groq y evitar el Error 429
groq_semaphore = asyncio.Semaphore(2)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")
cliente_llm = AsyncGroq(api_key=GROQ_API_KEY)
MODELOS_LLM = [
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "llama-3.1-8b-instant"
]
BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ── Parámetros globales (los de mercado los calcula VolatilityEngine) ──
MIN_EDGE        = 0.010   # Bajado a 1.0% para capturar más micro-ineficiencias en aprendizaje activo
MIN_CONFIANZA   = 0.50    # Bajado para permitir más operaciones en fase de aprendizaje activo
MIN_VOLUMEN     = 1_500   # Bajado para escanear mercados pequeños y medianos
MAX_SPREAD      = 0.06    # Subido al 6% para permitir más oportunidades en mercados volátiles
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

PROMPT = """Eres un sistema algorítmico avanzado de arbitraje y calibración probabilística en mercados de predicción (Polymarket). Tu objetivo es detectar ineficiencias de precio analizando datos del mercado y noticias recientes de forma fría, racional y matemática.

[DATOS DEL MERCADO ACTUAL]
- Mercado (Pregunta): {pregunta}
- Precio Actual YES en Polymarket: {precio:.1%} (Indica que el mercado asigna un {precio:.1%} de probabilidad a favor del YES)
- Días Restantes para la Resolución: {dias} días
- Variación de Precio (Última 1h): {momentum}
- Spread de Liquidez: {spread:.1%}

[INFORMACIÓN RECIENTE DISPONIBLE (ÚLTIMAS 48-72 HORAS)]
{noticias}

[HISTORIAL DE ESTE MERCADO EN NUESTRO SISTEMA]
{patron}

[INSTRUCCIONES DE RAZONAMIENTO CRÍTICO]
1. Aplica la Sabiduría de Masas: El precio de mercado ({precio:.1%}) ya descuenta la información general. Solo debes diferir del precio si las noticias proveen un catalizador contundente que el mercado aún no ha procesado (asimetría informática).
2. Evita la Sobreconfianza: No asignes valores extremos (0% o 100%) a eventos con incertidumbre estructural (política, deportes, tecnología). Calibrar significa ser conservador.
3. Factor de Decaimiento Temporal: Si faltan muchos días para la resolución, las probabilidades tienden a ser menos extremas debido al riesgo latente.
4. Anclaje de Precios por Falta de Información: Si la sección de noticias dice 'Sin noticias...' o si las noticias no aportan información nueva que altere la probabilidad del evento, tu estimación de probabilidad ("estimacion") DEBE ser exactamente la probabilidad de mercado actual (es decir, {precio:.1%}, que equivale al número entero {precio_entero}). No uses estimaciones genéricas como 50 si el mercado cotiza a un precio extremo.

CRITICAL FORMAT INSTRUCTIONS:
You MUST respond with a single, perfectly formatted JSON object. 
Do NOT include any markdown code blocks (like ```json), do NOT add introductory/concluding text, and NEVER add trailing comments.
The JSON keys MUST follow this exact execution sequence to allow proper cognitive processing:

{{
  "analisis_noticias": "Análisis de 1 frase sobre si las noticias proveen un catalizador real o si son mero ruido de prensa.",
  "conocimiento_base": "Análisis de 1 frase sobre el contexto deportivo/político/histórico de este evento específico.",
  "calibracion_precio": "Análisis de 1 frase evaluando por qué el mercado cotiza a {precio:.1%} y si hay un sesgo visible.",
  "hay_noticia": false, (boolean true/false, strictly true ONLY if there is recent, highly relevant news from the text that alters the event probability),
  "confianza": 0.50, (float between 0.0 and 1.0 representing your statistical confidence based on available data size),
  "estimacion": 50, (integer between 0 and 100 representing your final strictly calibrated probability percentage. MUST be a plain whole number without decimals),
  "razonamiento": "Resumen ejecutivo final de menos de 100 caracteres combinando la lógica de los campos anteriores."
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

# ── Estructura oficial de columnas para el libro de órdenes ──
COLUMNAS_LIBRO = [
    'fecha_entrada', 'fecha_entrada_dt', 'market_id', 'pregunta', 'señal', 
    'precio_entrada', 'precio_token_entrada', 'precio_actual', 'precio_cierre', 
    'pct_cambio', 'llm_estimacion', 'llm_confianza', 'llm_edge', 'hay_noticia', 
    'n_noticias', 'monto_usdc', 'dias_mercado', 'fecha_cierre_mercado', 
    'fecha_cierre_real', 'pnl_realizado', 'estado', 'razon_cierre', 
    'razonamiento', 'tp_dinamico', 'sl_dinamico', 'horas_max', 'vol_1d', 'momentum_1h'
]

def cargar_libro():
    if os.path.exists(ARCHIVO_LIBRO):
        try:
            return pd.read_csv(ARCHIVO_LIBRO)
        except pd.errors.EmptyDataError:
            log.warning(f"⚠️ {ARCHIVO_LIBRO} estaba vacío. Estructurando cabeceras desde cero.")
            return pd.DataFrame(columns=COLUMNAS_LIBRO)
    
    log.info(f"📂 Creando nuevo libro de órdenes virgen: {ARCHIVO_LIBRO}")
    return pd.DataFrame(columns=COLUMNAS_LIBRO)

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
    pl = {m["id"]: m["mid_price"] for m in mercados_actuales}
    ql = {m["pregunta"][:70]: m["mid_price"] for m in mercados_actuales}
    ahora = datetime.now()
    cerradas = 0

    for idx, pos in df[df["estado"] == "ABIERTA"].iterrows():
        try:
            dt = datetime.strptime(pos["fecha_entrada_dt"], "%Y-%m-%d %H:%M")
            h = abs((ahora - dt).total_seconds() / 3600.0)
            mid = pl.get(str(pos.get("market_id", ""))) or ql.get(str(pos["pregunta"])[:70])

            # Manejo estricto si el mercado expiró en Polymarket (Caso Dooley)
            if mid is None:
                if h >= float(pos.get("horas_max", 6)):
                    val_actual = pos.get("precio_actual")
                    # Si la celda es NaN o None, usamos el precio del token de entrada como resguardo de salida
                    if pd.isna(val_actual) or val_actual is None:
                        precio_token_actual = float(pos["precio_token_entrada"])
                    else:
                        precio_token_actual = float(val_actual)
                    razon = "TIME_EXIT"  # Forzamos la salida por tiempo vencido
                else:
                    continue
            else:
                # Si el mercado está activo, calculamos el precio real de nuestro token (YES o NO)
                precio_token_actual = mid if pos["señal"] == "COMPRAR YES" else round(1.0 - mid, 4)

            # Actualizamos el libro con el precio real del token que poseemos
            df.loc[idx, "precio_actual"] = precio_token_actual
            pte = float(pos["precio_token_entrada"])
            pct = (precio_token_actual - pte) / pte

            df["razon_cierre"] = df["razon_cierre"].astype(object)
            df["fecha_cierre_real"] = df["fecha_cierre_real"].astype(object)

            # Si mid era None, ya forzamos la razón a TIME_EXIT, de lo contrario evaluamos TP/SL
            if mid is not None:
                razon = None
                tp_pos = float(pos.get("tp_dinamico", 0.09))
                sl_pos = float(pos.get("sl_dinamico", -0.07))
                h_max = float(pos.get("horas_max", 6))
                
                if pct >= (tp_pos * 0.80) and h < (h_max * 0.20):
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
                pnl = round(float(pos["monto_usdc"]) * pct, 2)
                df.loc[idx, "estado"] = "CERRADA"
                df.loc[idx, "precio_cierre"] = precio_token_actual
                df.loc[idx, "pct_cambio"] = round(pct, 4)
                df.loc[idx, "pnl_realizado"] = pnl
                df.loc[idx, "razon_cierre"] = razon
                df.loc[idx, "fecha_cierre_real"] = ahora.strftime("%Y-%m-%d %H:%M")
                
                # Forzado a tipos nativos para evitar fallos del JSON en Railway
                estado["capital_actual"] = float(estado.get("capital_actual", 1000.0) + float(pos["monto_usdc"]) + pnl)
                estado["capital_en_riesgo"] = float(max(0, estado.get("capital_en_riesgo", 0) - float(pos["monto_usdc"])))
                cerradas += 1
                
                icono = "⚡" if razon == "EARLY_EXIT" else ("✅" if pnl >= 0 else "❌")
                log.info(f"{icono} [{razon}] {pos['pregunta'][:45]} | {pct:+.1%} | ${pnl:+.2f} | {h:.1f}h")
                
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")
            
    guardar_libro(df)
    return df, cerradas

async def procesar_mercado(m, df, estado, vol_engine, bayesian, ev_detector, cliente_news):
    nombre_m = m["pregunta"][:35]

    # 1. Ya Abierta (Filtro ultrarrápido sin semáforos)
    if m["pregunta"][:70] in set(df[df["estado"]=="ABIERTA"]["pregunta"].tolist()) if not df.empty else set():
        log.info(f"⏭️ {nombre_m} | Saltado: Ya existe posición ABIERTA.")
        return None

    # 2. Event Detector
    puede, motivo = ev_detector.puede_entrar(m["id"], m["pregunta"])
    if not puede:
        log.info(f"❌ {nombre_m} | EventDetector: {motivo}")
        return None

    # 3. Volatilidad ANTES de Groq
    tp, sl, max_h, met = vol_engine.get_params(m["id"], m["dias"])
    MIN_VOL_1D = 0.0005; MIN_RANGO = 0.005
    if met and (met.get("vol_1d", 0) < MIN_VOL_1D and met.get("rango", 0) < MIN_RANGO):
        log.info(f"❌ {nombre_m} | Inactivo (vol={met['vol_1d']:.4f}, rango={met['rango']:.3f})")
        return None

    # Inyectar momentum real al mercado para el prompt del LLM
    m["cambio_1h"] = met.get("cambio_1h", 0.0) if met else 0.0

    # Si llegó aquí, el mercado es apto para análisis. Imprimimos el trigger
    log.info(f"Vol [{m['id']}]: tp={int(tp*100)}% sl={int(sl*100)}% h={int(max_h)}h vol={met.get('vol_1d',0):.3f} pulsos=sí")

    # 4. Noticias (Ejecución asíncrona fluida)
    nots = await asyncio.to_thread(noticias, m["pregunta"], cliente_news)
    nots_txt = "\n".join([f"- [{n['f']}] {n['s']}: {n['t']}" for n in nots]) if nots else "Sin noticias recientes en prensa."

    # 5. Configuración del Prompt CoT Optimizado
    patron = ev_detector.patron_mercado(m["id"])
    patron_txt = f"n={patron.get('n',0)} trades" if patron else "sin historial"
    momentum_str = f"{m['cambio_1h']:+.1%}"
    precio_entero = int(m["mid_price"] * 100)
    prompt = PROMPT.format(
        pregunta=m["pregunta"], precio=m["mid_price"],
        dias=m["dias"], spread=m["spread"],
        noticias=nots_txt, patron=patron_txt,
        momentum=momentum_str,
        precio_entero=precio_entero
    )

    # 6. Groq con Control de Flujo y Sistema de Respaldo (Fallback)
    an = None
    for model_name in MODELOS_LLM:
        try:
            async with groq_semaphore:
                msg = await cliente_llm.chat.completions.create(
                    model=model_name,
                    temperature=0.0,
                    messages=[{"role":"user","content":prompt}],
                    max_tokens=450,  # Espacio holgado para el análisis CoT sin truncados
                    response_format={"type": "json_object"}
                )
                # Micro-letargo defensivo para proteger la ventana de Tokens Per Minute (TPM)
                await asyncio.sleep(1.5)

            an = json.loads(msg.choices[0].message.content.strip())
            log.info(f"✅ [{nombre_m}] Analisis exitoso con el modelo {model_name}")
            break  # Éxito, salir del bucle de modelos
        except Exception as e:
            if "rate_limit_exceeded" in str(e) or "429" in str(e):
                log.warning(f"⚠️ [{nombre_m}] Modelo {model_name} con limite excedido (429). Intentando respaldo...")
                continue
            else:
                log.warning(f"⚠️ [{nombre_m}] Error general con el modelo {model_name}: {e}. Intentando respaldo...")
                continue

    if an is None:
        log.error(f"❌ [{nombre_m}] Todos los modelos de LLM fallaron o agotaron su cuota.")
        return None

    # 7. Filtros matemáticos post-IA
    estimacion_raw = an.get("estimacion", m["mid_price"] * 100)
    try:
        estimacion = float(estimacion_raw)
        if estimacion > 1.0: estimacion /= 100.0
    except: 
        estimacion = m["mid_price"]

    confianza   = float(an.get("confianza", 0.5))
    hay_noticia = bool(an.get("hay_noticia", False))
    diferencia  = estimacion - m["mid_price"]
    edge_neto   = round(abs(diferencia) - m["spread"], 4)

    umbral = 0.01 if hay_noticia else 0.012
    if edge_neto < umbral:
        log.info(f"❌ {nombre_m} | Edge ({edge_neto:.2%}) < umbral ({umbral:.2%})")
        return None
    if edge_neto < MIN_EDGE:
        log.info(f"❌ {nombre_m} | Edge mínimo ({edge_neto:.2%} < {MIN_EDGE:.2%})")
        return None
    if confianza < MIN_CONFIANZA:
        log.info(f"❌ {nombre_m} | Confianza ({confianza:.2f} < {MIN_CONFIANZA:.2f})")
        return None
    if edge_neto > 0.25:
        log.info(f"❌ {nombre_m} | Edge muy alto ({edge_neto:.2%}) → señal dudosa")
        return None

    # 7.5 Bifurcación de Estrategias (Trend-Following vs Mean-Reversion) (Fase 9)
    momentum_1h = met.get("cambio_1h", 0.0) if met else 0.0
    if hay_noticia:
        # Modo Trend-Following (Seguidor de Tendencia): no operar contra momentum fuerte
        if diferencia > 0 and momentum_1h < -0.005:
            log.info(f"❌ {nombre_m} | Trend-Following: Señal COMPRAR YES pero momentum es bajista ({momentum_1h:+.1%}) → bloqueado")
            return None
        if diferencia < 0 and momentum_1h > 0.005:
            log.info(f"❌ {nombre_m} | Trend-Following: Señal COMPRAR NO pero momentum es alcista ({momentum_1h:+.1%}) → bloqueado")
            return None
    else:
        # Modo Mean-Reversion (Retorno a la Media): sólo operar extremos
        en_extremo = met.get("en_extremo", False) if met else False
        if not en_extremo:
            log.info(f"❌ {nombre_m} | Mean-Reversion: Sin noticias y fuera de zona extrema → bloqueado")
            return None
            
        media = met.get("media", m["mid_price"]) if met else m["mid_price"]
        # Si el precio actual está arriba de la media histórica, sólo permitimos vender (COMPRAR NO)
        if m["mid_price"] > media and diferencia > 0:
            log.info(f"❌ {nombre_m} | Mean-Reversion: Precio alto ({m['mid_price']:.3f} > {media:.3f}) pero la señal es COMPRAR YES → bloqueado")
            return None
        # Si el precio actual está abajo de la media histórica, sólo permitimos comprar (COMPRAR YES)
        if m["mid_price"] < media and diferencia < 0:
            log.info(f"❌ {nombre_m} | Mean-Reversion: Precio bajo ({m['mid_price']:.3f} < {media:.3f}) pero la señal es COMPRAR NO → bloqueado")
            return None

    # 7.6 Filtro de Diversificación por Categoría (Fase 10)
    categoria_actual = get_categoria(nombre_m)
    exposicion_cat = 0.0
    if not df.empty and "pregunta" in df.columns and "monto_usdc" in df.columns:
        abiertas = df[df["estado"] == "ABIERTA"]
        for _, pos in abiertas.iterrows():
            if get_categoria(pos["pregunta"]) == categoria_actual:
                exposicion_cat += float(pos["monto_usdc"])
                
    max_exposicion_cat = estado["capital_actual"] * 0.3
    if exposicion_cat >= max_exposicion_cat:
        log.info(f"❌ {nombre_m} | Diversificación: Exposición en '{categoria_actual}' (${exposicion_cat:.2f}) supera el límite de 30% (${max_exposicion_cat:.2f}) → bloqueado")
        return None

    # 8. Motor Bayesiano
    señal     = "COMPRAR YES" if diferencia > 0 else "COMPRAR NO"
    precio_tok = m["mid_price"] if señal == "COMPRAR YES" else round(1 - m["mid_price"], 4)

    ok, score, feats = bayesian.should_trade(
        pregunta=nombre_m, precio_entrada=precio_tok, señal=señal,
        vol_1d=met.get("vol_1d", 0) if met else 0,
        edge=edge_neto, confianza=confianza,
        hay_noticia=hay_noticia,
        momentum_1h=met.get("cambio_1h", 0.0) if met else 0.0,
        fecha_dt=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    if not ok and score < 0.5:
        log.info(f"❌ {nombre_m} | Bayesiano bloquea (score={score:.2f})")
        return None

    # 9. Dimensionamiento de Posición (Kelly Dinámico) (Fase 10)
    ratio_capital = estado.get("capital_actual", CAPITAL_INICIAL) / CAPITAL_INICIAL
    factor_kelly = 0.3
    if ratio_capital < 1.0:
        factor_kelly = max(0.1, round(0.3 * ratio_capital, 3))
        
    kelly = edge_neto * confianza * factor_kelly
    monto = round(min(estado["capital_actual"] * kelly, CAPITAL_POR_OP), 2)
    log.info(f"💰 {nombre_m} | monto=${monto:.2f} vol={met['vol_1d']:.4f} TP={tp:.1%} SL={sl:.1%}")
    if monto < 5:
        log.info(f"❌ {nombre_m} | Monto ${monto:.2f} < $5")
        return None

    ev_detector.registrar_evento(m["id"], m["pregunta"])
    return {
        "fecha_entrada":        datetime.now().strftime("%Y-%m-%d"),
        "fecha_entrada_dt":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market_id":            m["id"],
        "pregunta":             m["pregunta"][:70],
        "señal":                señal,
        "precio_entrada":       m["mid_price"],
        "precio_token_entrada": precio_tok,
        "precio_actual":        precio_tok,
        "tp_dinamico":          tp,
        "sl_dinamico":          sl,
        "horas_max":            max_h,
        "monto_usdc":           monto,
        "estado":               "ABIERTA",
        "razonamiento":         an.get("razonamiento", ""),
        "llm_confianza":        confianza,
        "llm_edge":             edge_neto,
        "vol_1d":               met.get("vol_1d", 0.0) if met else 0.0,
        "momentum_1h":          met.get("cambio_1h", 0.0) if met else 0.0,
    }

def actualizar_precios_abiertos(df):
    if df.empty or 'estado' not in df.columns:
        return df
    abiertas = df[df['estado'] == 'ABIERTA']
    if abiertas.empty: return df
    for idx, pos in abiertas.iterrows():
        try:
            r = requests.get("https://gamma-api.polymarket.com/markets",
                             params={"id": pos['market_id']}, timeout=8)
            if r.status_code == 200 and r.json():
                m = r.json()[0]
                bid = float(m.get("bestBid", 0))
                ask = float(m.get("bestAsk", 0))
                if bid > 0 and ask > 0:
                    precio_yes = round((bid + ask) / 2, 4)
                    señal = str(pos.get('señal', 'COMPRAR YES')).upper()
                    # Para NO, el precio del token es el complemento
                    precio_token = precio_yes if "YES" in señal else round(1 - precio_yes, 4)
                    df.loc[idx, 'precio_actual'] = precio_token
        except: pass
    return df

import re

def extraer_json_puro(texto):
    """Extrae el bloque JSON {} incluso si la IA añade texto extra o comete errores de formato."""
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return match.group(0) if match else texto
    except:
        return texto

# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════

async def ciclo():
    global estado
    log.info("="*55)
    log.info("🚀 INICIANDO CICLO HÍBRIDO ASÍNCRONO v3")
    log.info("="*55)
  
    df = cargar_libro()
    estado = cargar_estado()

# ══════════════════════════════════════════════════════════════════
    # HARD PATCH DE AUTO-SANACIÓN (Intercepta y corrige el volumen)
    # ══════════════════════════════════════════════════════════════════
    try:
        if not df.empty:
            # 3. AUDITORÍA FINANCIERA DINÁMICA (Sanea el JSON contra el CSV)
            monto_en_riesgo_real = float(df[df['estado'] == 'ABIERTA']['monto_usdc'].sum())
            
            if float(estado.get("capital_en_riesgo", 0)) != monto_en_riesgo_real:
                desfase = float(estado.get("capital_en_riesgo", 0)) - monto_en_riesgo_real
                estado["capital_en_riesgo"] = monto_en_riesgo_real
                estado["capital_actual"] = float(estado.get("capital_actual", 1000.0) + desfase)
                
                log.info(f"⚖️ [AUDITORÍA] Contabilidad cuadrada: Riesgo ajustado a ${monto_en_riesgo_real} USDC. Retornado: ${desfase} USDC.")
                guardar_estado(estado)

    except Exception as patch_err:
        log.warning(f"⚠️ Error al ejecutar la auditoría contable: {patch_err}")
    # ══════════════════════════════════════════════════════════════════
  
    # 1. ACTUALIZAR PRECIOS ANTES DE EVALUAR APUESTAS
    df = actualizar_precios_abiertos(df)
    guardar_libro(df)

    # 2. EVALUAR AGRESIVIDAD DE CIERRES
    df, n_inactivas = cerrar_inactivas(df, estado)
    if n_inactivas: guardar_estado(estado)

    # Filtro de cupo disponible
    n_ab = len(df[df["estado"]=="ABIERTA"]) if not df.empty else 0
    cupo = MAX_POSICIONES - n_ab
    if cupo <= 0:
        log.info("Cartera llena")
        return
    
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



    # 2. CREAR TAREAS ASÍNCRONAS EN PARALELO
    # Filtramos los top 40 mercados con mayor volumen para optimizar la cuota de tokens
    # Ordenar por volumen (más líquidos primero) y tomar top 60
    import random
    top100 = sorted(mercados, key=lambda x: x["volumen_usd"], reverse=True)[:100]
    mercados_a_revisar = random.sample(top100, min(20, len(top100)))
    
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
    import sys
    
    # ══════════════════════════════════════════════════════════════════
    # INTERRUPTOR ESTRICTO DE SALIDA PARA GITHUB ACTIONS
    # ══════════════════════════════════════════════════════════════════
    try:
        # Ejecuta un ÚNICO ciclo operativo completo por invocación del cron
        asyncio.run(ciclo())
        
        print("🏁 [ÉXITO] Ciclo completado. Forzando liberación de sockets y salida limpia para GitHub Actions.")
        # Corta de raíz cualquier socket Keep-Alive o hilo persistente de la API de Groq
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error crítico en la ejecución del contenedor: {e}")
        sys.exit(1)
