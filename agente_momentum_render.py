#!/usr/bin/env python3
"""
agente_momentum_render.py
Versión para Render.com — corre con scheduler continuo cada 30 minutos.
A diferencia de GitHub Actions (ciclo único), este archivo mantiene
el proceso vivo y ejecuta ciclos automáticamente.

Diferencias vs agente_momentum.py:
  1. Usa APScheduler en vez de ciclo único
  2. Guarda CSV localmente en Render (persistente entre ciclos)
  3. Hace commit automático a GitHub cada 3 ciclos para actualizar dashboard
"""

import os, json, time, logging
import requests
import pandas as pd
from groq import Groq
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta

# ── Importar motor Bayesiano ───────────────────────────────────────
from bayesian_engine import BayesianEngine

# ── Timezone ───────────────────────────────────────────────────────
os.environ['TZ'] = 'America/Guayaquil'

# ── API Keys ───────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")

# ── GitHub para commits automáticos ───────────────────────────────
GITHUB_TOKEN = os.environ.get("G_TOKEN_PUSH", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "Darvder/agente_polygon")

BASE_URL = "https://gamma-api.polymarket.com"
TIMEOUT  = 10

# ══════════════════════════════════════════════════════════════════
# PARÁMETROS (sincronizados con agente_momentum.py)
# ══════════════════════════════════════════════════════════════════

TAKE_PROFIT          = 0.09
STOP_LOSS            = -0.07
MAX_HORAS            = 3
CICLO_MINUTOS        = 30      # cada 30 minutos — exacto en Render

MIN_MOMENTUM_30M     = 0.05
MIN_MOMENTUM_1H      = 0.04
MIN_MOMENTUM_4H      = 0.03
MIN_VOLUMEN          = 5_000
MIN_VOLUMEN_MOMENTUM = 75_000
MAX_SPREAD           = 0.08
MIN_PRECIO           = 0.04
MAX_PRECIO           = 0.96
MAX_DIAS_MERCADO     = 180
MAX_POSICIONES       = 12
CAPITAL_INICIAL      = 1_000
CAPITAL_POR_OP       = 20
MAX_EXPOSICION_MERCADO = 40

PATRONES_EXCLUIR = [
    "jesus","christ","second coming","rapture",
    "alien","ufo","zombie","apocalypse",
    "win the 2025-26 english premier",
    "finish in 2nd place",
    "finish in 1st place",
    "finish in 3rd place",
]

ARCHIVO_LIBRO   = "datos_polymarket/paper_trading/libro_momentum.csv"
ARCHIVO_ESTADO  = "datos_polymarket/paper_trading/estado_momentum.json"
ARCHIVO_PRECIOS = "datos_polymarket/paper_trading/historial_precios.json"

os.makedirs("datos_polymarket/logs", exist_ok=True)
os.makedirs("datos_polymarket/paper_trading", exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s | %(levelname)s | %(message)s",
    handlers = [
        logging.FileHandler("datos_polymarket/logs/agente_render.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("render")

# Contador de ciclos para commit periódico
_ciclos_sin_commit = 0
COMMIT_CADA_N_CICLOS = 3  # commit cada 3 ciclos (~90 min)


# ══════════════════════════════════════════════════════════════════
# COMMIT AUTOMÁTICO A GITHUB
# ══════════════════════════════════════════════════════════════════

def commit_a_github():
    """
    Hace push de los archivos CSV/JSON al repo de GitHub
    para que el dashboard se actualice automáticamente.
    Usa la API de GitHub para no necesitar git instalado.
    """
    if not GITHUB_TOKEN:
        log.warning("Sin GITHUB_TOKEN — no se puede hacer commit")
        return

    archivos = [ARCHIVO_LIBRO, ARCHIVO_ESTADO, ARCHIVO_PRECIOS]
    headers  = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    for archivo in archivos:
        if not os.path.exists(archivo):
            continue
        try:
            import base64
            with open(archivo, "rb") as f:
                contenido = base64.b64encode(f.read()).decode()

            # Obtener SHA actual del archivo en GitHub
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{archivo}"
            r   = requests.get(url, headers=headers, timeout=10)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""

            # Actualizar archivo
            payload = {
                "message": f"ciclo {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": contenido,
                "sha":     sha
            }
            r = requests.put(url, headers=headers,
                           json=payload, timeout=15)
            if r.status_code in (200, 201):
                log.info(f"✅ GitHub commit: {archivo}")
            else:
                log.warning(f"GitHub error {r.status_code}: {archivo}")
        except Exception as e:
            log.warning(f"Error commit {archivo}: {e}")


# ══════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES (igual que agente_momentum.py)
# ══════════════════════════════════════════════════════════════════

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f: return json.load(f)
    return {"capital_inicial": CAPITAL_INICIAL, "capital_actual": CAPITAL_INICIAL,
            "capital_en_riesgo": 0, "n_ciclos": 0, "ultima_corrida": "—",
            "n_tp": 0, "n_sl": 0, "n_time": 0, "mercados_rastreados": 0}

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

def registrar_snapshot(mercados):
    historial = cargar_historial()
    ts = datetime.now().isoformat()
    for m in mercados:
        key = m["id"]
        if key not in historial:
            historial[key] = {"pregunta": m["pregunta"][:70], "precios": []}
        historial[key]["precios"].append({"ts": ts, "p": m["mid_price"]})
        historial[key]["precios"] = historial[key]["precios"][-96:]  # 48h a 30min
    guardar_historial(historial)
    return historial

def calcular_momentum(market_id, historial):
    if market_id not in historial:
        return "NEUTRAL", 0, 0, 0, 0, None
    entradas = historial[market_id]["precios"]
    if len(entradas) < 2:
        return "NEUTRAL", 0, 0, 0, 0, entradas[-1]["p"] if entradas else None

    ahora         = datetime.now()
    precio_actual = entradas[-1]["p"]

    def precio_hace(horas):
        cutoff = ahora - timedelta(hours=horas)
        pasados = [e for e in entradas
                   if datetime.fromisoformat(e["ts"]) <= cutoff]
        return pasados[-1]["p"] if pasados else None

    p30m = precio_hace(0.5)
    p1h  = precio_hace(1)
    p4h  = precio_hace(4)

    cambio_30m = (precio_actual - p30m) / p30m if p30m and p30m > 0 else 0
    cambio_1h  = (precio_actual - p1h)  / p1h  if p1h  and p1h  > 0 else 0
    cambio_4h  = (precio_actual - p4h)  / p4h  if p4h  and p4h  > 0 else 0

    momentum = cambio_30m * 0.50 + cambio_1h * 0.35 + cambio_4h * 0.15

    if (abs(cambio_30m) >= MIN_MOMENTUM_30M or
        abs(cambio_1h)  >= MIN_MOMENTUM_1H  or
        abs(cambio_4h)  >= MIN_MOMENTUM_4H):
        señal = "COMPRAR YES" if momentum > 0 else "COMPRAR NO"
    else:
        señal = "NEUTRAL"

    return señal, round(momentum,4), round(cambio_1h,4), round(cambio_4h,4), round(cambio_30m,4), precio_actual

def escanear_mercados():
    hoy = datetime.now().date()
    try:
        r = requests.get(f"{BASE_URL}/markets",
                        params={"active":True,"closed":False,"limit":500},
                        timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        log.error(f"Error API: {e}")
        return []

    mercados = []
    for m in raw:
        try:
            pregunta = m.get("question","")
            if any(p in pregunta.lower() for p in PATRONES_EXCLUIR): continue
            bid = float(m.get("bestBid",0)); ask = float(m.get("bestAsk",0))
            if bid <= 0 or ask <= 0: continue
            spread = round(ask-bid,4); mid = round((bid+ask)/2,4)
            if spread > MAX_SPREAD: continue
            if mid < MIN_PRECIO or mid > MAX_PRECIO: continue
            if float(m.get("volume",0)) < MIN_VOLUMEN: continue
            fecha_str = m.get("endDate","")[:10]
            if not fecha_str: continue
            dias = (datetime.strptime(fecha_str,"%Y-%m-%d").date()-hoy).days
            if dias <= 0 or dias > MAX_DIAS_MERCADO: continue
            mercados.append({"id":m.get("id",pregunta[:30]),"pregunta":pregunta,
                            "mid_price":mid,"spread":spread,
                            "volumen_usd":float(m.get("volume",0)),
                            "dias":dias,"fecha_cierre":fecha_str})
        except: continue
    log.info(f"Mercados rastreables: {len(mercados)}")
    return mercados

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
                cerradas+=1
                log.info(f"{'✅' if pnl>=0 else '❌'} [{razon}] {pos['pregunta'][:45]} | {pct:+.1%} | P&L={pnl:+.2f}$ | {horas_abiertas:.1f}h")
        except Exception as e:
            log.warning(f"Error salida idx={idx}: {e}")
    guardar_libro(df_libro)
    return df_libro, cerradas


# ══════════════════════════════════════════════════════════════════
# CICLO PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def ciclo():
    global _ciclos_sin_commit
    log.info("=" * 55)
    log.info("CICLO RENDER INICIADO")
    log.info("=" * 55)

    estado   = cargar_estado()
    df_libro = cargar_libro()

    # Recalcular capital en riesgo desde CSV
    if not df_libro.empty:
        estado["capital_en_riesgo"] = float(
            df_libro[df_libro["estado"]=="ABIERTA"]["monto_usdc"].sum()
        )

    # Bayesiano
    bayesian = BayesianEngine()
    bayesian.entrenar()
    log.info(bayesian.reporte())

    # Escanear y registrar snapshot
    mercados  = escanear_mercados()
    if not mercados:
        log.warning("Sin mercados")
        return
    historial = registrar_snapshot(mercados)
    estado["mercados_rastreados"] = len(historial)

    # Verificar salidas
    df_libro, n_cerradas = verificar_salidas(df_libro, estado, mercados)
    if n_cerradas: guardar_estado(estado)

    # Anti re-entrada
    hace_2h = (datetime.now()-timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    if not df_libro.empty and "CERRADA" in df_libro["estado"].values:
        cerradas_df = df_libro[df_libro["estado"]=="CERRADA"].copy()
        cerradas_df["fecha_cierre_real"] = cerradas_df["fecha_cierre_real"].fillna("").astype(str)
        recientes = cerradas_df[cerradas_df["fecha_cierre_real"]>=hace_2h]["market_id"].astype(str).tolist()
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        recientes += [str(df_libro.loc[idx,"market_id"]) for idx in df_libro.index
                     if df_libro.loc[idx,"estado"]=="CERRADA"
                     and str(df_libro.loc[idx,"fecha_cierre_real"])==ahora_str]
    else:
        recientes = []

    # Señales
    n_abiertas = len(df_libro[df_libro["estado"]=="ABIERTA"]) if not df_libro.empty else 0
    cupo = MAX_POSICIONES - n_abiertas
    señales = []

    # Filtro hora madrugada
    hora_actual = datetime.now().hour
    if hora_actual < 6:
        log.info(f"Hora madrugada ({hora_actual}h) — sin nuevas entradas")
    else:
        for m in mercados:
            señal, mom, c1h, c4h, c30m, p_act = calcular_momentum(m["id"], historial)
            if señal == "NEUTRAL": continue
            if m["volumen_usd"] < MIN_VOLUMEN_MOMENTUM: continue
            if abs(c4h) > abs(c1h)*2 and abs(c4h) > 0.05:
                log.info(f"Momentum tardío: {m['pregunta'][:40]}")
                continue
            ok, score, feats = bayesian.should_trade(
                pregunta=m["pregunta"], cambio_1h=c1h,
                precio_entrada=m["mid_price"],
                fecha_dt=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            if not ok:
                log.info(f"Bayesiano bloquea (score={score:.0%}): {m['pregunta'][:40]} | {feats['categoria']} mom={feats['mom_bucket']} precio={feats['precio_bucket']}")
                continue
            if m["dias"] <= 2 and abs(c1h) > 0.05:
                log.info(f"Evento inminente: {m['pregunta'][:40]} ({m['dias']}d)")
                continue
            señales.append({**m,"señal":señal,"momentum":mom,"cambio_1h":c1h,"cambio_4h":c4h})

    señales = sorted(señales, key=lambda x: abs(x["momentum"]), reverse=True)
    log.info(f"Señales: {len(señales)} | Cupo: {cupo}")

    if cupo > 0 and señales:
        preguntas_abiertas = set(df_libro[df_libro["estado"]=="ABIERTA"]["pregunta"].tolist()) \
                             if not df_libro.empty else set()
        nuevas  = []
        cliente = Groq(api_key=GROQ_API_KEY)

        for m in señales:
            if len(nuevas) >= cupo: break
            if m["pregunta"][:70] in preguntas_abiertas: continue
            if str(m["id"]) in recientes: continue
            if not df_libro.empty:
                expuesto = df_libro[(df_libro["estado"]=="ABIERTA") &
                                   (df_libro["market_id"].astype(str)==str(m["id"]))]["monto_usdc"].sum()
                if expuesto >= MAX_EXPOSICION_MERCADO: continue

            prompt = (f"Mercado: {m['pregunta']}\nPrecio YES: {m['mid_price']:.2%} | "
                     f"Cambio 1h: {m['cambio_1h']:+.1%}\nSeñal: {m['señal']}\n"
                     f"¿Tiene sentido económico? SOLO JSON: "
                     f'{{"tiene_sentido":true/false,"confianza":0.0-1.0,"nota":"1 oración"}}')
            try:
                resp = cliente.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":prompt}], max_tokens=80)
                txt = resp.choices[0].message.content.strip()
                if "```" in txt: txt = txt.split("```")[1].split("```")[0].replace("json","").strip()
                llm = json.loads(txt)
            except:
                llm = {"tiene_sentido":True,"confianza":0.5,"nota":"sin análisis"}

            if not llm.get("tiene_sentido",True) and llm.get("confianza",0) > 0.7:
                log.info(f"LLM descarta: {m['pregunta'][:45]}")
                time.sleep(1); continue

            confianza    = llm.get("confianza",0.5)
            precio_token = m["mid_price"] if m["señal"]=="COMPRAR YES" else round(1-m["mid_price"],4)
            monto        = round(min(estado["capital_actual"]*abs(m["momentum"])*confianza*0.5, CAPITAL_POR_OP), 2)
            if monto < 5: continue

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
            log.info(f"✅ NUEVA: {m['señal']} | {m['pregunta'][:40]} | mom={m['momentum']:+.1%} | ${monto}")
            time.sleep(1.5)

        if nuevas:
            df_nuevas = pd.DataFrame(nuevas)
            df_libro  = pd.concat([df_libro,df_nuevas],ignore_index=True) if not df_libro.empty else df_nuevas
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
    pnl  = df_libro[df_libro["estado"]=="CERRADA"]["pnl_realizado"].sum() if not df_libro.empty and n_ce>0 else 0

    log.info("─"*55)
    log.info(f"CICLO #{estado['n_ciclos']} | {len(historial)} mercados")
    log.info(f"Abiertas: {n_ab} | Cerradas: {n_ce} | P&L: ${pnl:+.2f}")
    log.info(f"TP:{estado['n_tp']} SL:{estado['n_sl']} Time:{estado['n_time']}")
    log.info("="*55)

    # Commit a GitHub cada N ciclos
    _ciclos_sin_commit += 1
    if _ciclos_sin_commit >= COMMIT_CADA_N_CICLOS:
        commit_a_github()
        _ciclos_sin_commit = 0


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Agente Momentum RENDER iniciando...")
    log.info(f"TP={TAKE_PROFIT:.0%} | SL={STOP_LOSS:.0%} | MaxH={MAX_HORAS}h | Ciclo={CICLO_MINUTOS}min")

    ciclo()  # ejecutar inmediatamente al arrancar

    scheduler = BlockingScheduler()
    scheduler.add_job(ciclo, trigger="interval",
                     minutes=CICLO_MINUTOS, max_instances=1)
    log.info(f"Scheduler activo — ciclo cada {CICLO_MINUTOS} minutos")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Agente detenido")
