"""
bayesian_engine.py  v2
Aprende de trades reales. Excluye INACTIVA/TIME_EXIT sin movimiento.
Features accionables: señal, categoría, vol, edge, confianza, noticia.
"""
import json, os, logging, math
import pandas as pd
from datetime import datetime

ARCHIVO_LIBRO  = "datos_polymarket/paper_trading/libro_hibrido.csv"
ARCHIVO_MODELO = "datos_polymarket/paper_trading/bayesian_model.json"

MIN_SAMPLES  = 2    # mínimo trades para activar un feature
MIN_WIN_RATE = 0.40 # umbral para operar

log = logging.getLogger("bayesian")


# ── Features ───────────────────────────────────────────────────────

def get_categoria(pregunta):
    q = str(pregunta).lower()
    if any(k in q for k in ["nba","nfl","nhl","stanley","lakers","knicks","spurs",
                              "cavaliers","pistons","celtics","warriors","heat",
                              "buffalo","montreal","vegas","carolina","sabres",
                              "avalanche","thunder","pistons"]):
        return "deportes"
    if any(k in q for k in ["premier","arsenal","chelsea","city","united","liverpool",
                              "tottenham","manchester","world cup","fifa","la liga"]):
        return "futbol"
    if any(k in q for k in ["president","senate","republican","democrat","election",
                              "vote","congress","trump","paxton","cornyn","bolsonaro",
                              "lula","haddad","balance of power","starmer","mayoral"]):
        return "politica"
    if any(k in q for k in ["bitcoin","crypto","microstrategy","nvidia","alphabet",
                              "metamask","largest company","market cap"]):
        return "crypto_tech"
    if any(k in q for k in ["album","rihanna","carti","taylor","gta","movie"]):
        return "cultura"
    return "otro"

def get_vol_bucket(vol_1d):
    v = float(vol_1d) if vol_1d and str(vol_1d) not in ('nan','None','') else 0.0
    if v < 0.001: return "plano"
    if v < 0.005: return "bajo"
    if v < 0.015: return "medio"
    if v < 0.04:  return "alto"
    return "muy_alto"

def get_edge_bucket(edge):
    try:
        e = float(edge)
        if e > 1.0: e /= 100.0
    except: e = 0.0
    if e < 0.03: return "bajo"
    if e < 0.07: return "medio"
    if e < 0.15: return "alto"
    return "muy_alto"

def get_confianza_bucket(confianza):
    try: c = float(confianza)
    except: c = 0.5
    if c < 0.55: return "baja"
    if c < 0.70: return "media"
    return "alta"

def get_precio_bucket(precio):
    p = float(precio) if precio else 0.5
    if p < 0.15: return "extremo_bajo"
    if p < 0.35: return "bajo"
    if p < 0.65: return "medio"
    if p < 0.85: return "alto"
    return "extremo_alto"

def get_momentum_bucket(momentum):
    try: m = float(momentum)
    except: m = 0.0
    if m < -0.05: return "caida_fuerte"
    if m < -0.01: return "caida_suave"
    if m < 0.01:  return "estable"
    if m < 0.05:  return "alza_suave"
    return "alza_fuerte"

def construir_features(pregunta, precio_entrada, señal, vol_1d, edge, confianza, hay_noticia, momentum_1h):
    s_upper = str(señal).upper()
    is_noticia = str(hay_noticia).lower() in ("true","1","yes","si")
    base = {
        "señal":      "yes" if "YES" in s_upper else "no",
        "categoria":  get_categoria(pregunta),
        "vol":        get_vol_bucket(vol_1d),
        "edge":       get_edge_bucket(edge),
        "confianza":  get_confianza_bucket(confianza),
        "precio":     get_precio_bucket(precio_entrada),
        "noticia":    "si" if is_noticia else "no",
        "momentum":   get_momentum_bucket(momentum_1h),
    }
    interacciones = {
        "int_noticia_vol":      f"{base['noticia']}_{base['vol']}",
        "int_confianza_edge":   f"{base['confianza']}_{base['edge']}",
        "int_precio_senal":     f"{base['precio']}_{base['señal']}",
        "int_noticia_momentum": f"{base['noticia']}_{base['momentum']}",
    }
    return {**base, **interacciones}

def extraer_features(row):
    return construir_features(
        pregunta=row.get("pregunta", ""),
        precio_entrada=row.get("precio_token_entrada", 0.5),
        señal=row.get("señal", ""),
        vol_1d=row.get("vol_1d", 0),
        edge=row.get("llm_edge", 0),
        confianza=row.get("llm_confianza", 0.5),
        hay_noticia=row.get("hay_noticia", False),
        momentum_1h=row.get("momentum_1h", 0)
    )

def es_señal_valida(row):
    """
    Solo aprende de operaciones donde el precio se movió.
    INACTIVA y TIME_EXIT con PnL=0 son ruido, no señal.
    """
    razon = str(row.get("razon_cierre", "")).upper()
    pnl   = float(row.get("pnl_realizado", 0) or 0)
    if razon == "INACTIVA": return False
    if razon == "TIME_EXIT" and abs(pnl) < 0.05: return False
    return True

def es_ganadora(row):
    try: return float(row.get("pnl_realizado", 0) or 0) > 0
    except: return False


# ── Motor ──────────────────────────────────────────────────────────

class BayesianEngine:

    def __init__(self, archivo_libro=None, archivo_modelo=None):
        self.archivo_libro  = archivo_libro or ARCHIVO_LIBRO
        self.archivo_modelo = archivo_modelo or ARCHIVO_MODELO
        self.modelo = self._cargar()

    def _cargar(self):
        if os.path.exists(self.archivo_modelo):
            with open(self.archivo_modelo) as f: return json.load(f)
        return {}

    def _guardar(self):
        os.makedirs(os.path.dirname(self.archivo_modelo), exist_ok=True)
        with open(self.archivo_modelo, "w") as f:
            json.dump(self.modelo, f, indent=2)

    def entrenar(self):
        if not os.path.exists(self.archivo_libro): return
        df = pd.read_csv(self.archivo_libro)
        cerradas = df[df["estado"].str.upper() == "CERRADA"].copy()

        # Solo trades con señal real (excluye INACTIVA y TIME_EXIT nulos)
        validas = cerradas[cerradas.apply(es_señal_valida, axis=1)]

        if validas.empty:
            log.info("Bayesiano: sin trades válidos para aprender aún.")
            return

        modelo = {}
        for _, row in validas.iterrows():
            features = extraer_features(row)
            ganadora = es_ganadora(row)
            for fn, fv in features.items():
                k = f"{fn}:{fv}"
                if k not in modelo:
                    modelo[k] = {"n": 0, "wins": 0, "wr": 0.5}
                modelo[k]["n"]    += 1
                modelo[k]["wins"] += int(ganadora)
                
                # Suavizado de Laplace: wr = (wins + alpha) / (n + 2 * alpha)
                alpha = 1.0
                modelo[k]["wr"]    = round((modelo[k]["wins"] + alpha) / (modelo[k]["n"] + 2 * alpha), 3)

        self.modelo = modelo
        self._guardar()
        n_validas = len(validas)
        log.info(f"Bayesiano: {len(modelo)} condiciones | {n_validas} trades válidos "
                 f"({len(cerradas)-n_validas} INACTIVA/TIME_EXIT excluidos)")

    def score(self, features_dict):
        weighted_sum = 0.0
        total_weight = 0.0
        detalle = {}
        
        for fn, fv in features_dict.items():
            k = f"{fn}:{fv}"
            if k in self.modelo and self.modelo[k]["n"] >= MIN_SAMPLES:
                n = self.modelo[k]["n"]
                wr = self.modelo[k]["wr"]
                # Ponderación logarítmica de confianza por número de muestras
                w = math.log(n + 1)
                
                weighted_sum += wr * w
                total_weight += w
                detalle[k] = f"{wr:.0%} (n={n}, w={w:.1f})"
                
        if total_weight == 0:
            return None, {}  # None = sin datos, no bloquear
            
        score_final = round(weighted_sum / total_weight, 3)
        return score_final, detalle

    def should_trade(self, pregunta, precio_entrada, señal,
                     vol_1d=0, edge=0, confianza=0.5,
                     hay_noticia=False, momentum_1h=0.0, fecha_dt=""):
        features = construir_features(
            pregunta=pregunta, precio_entrada=precio_entrada, señal=señal,
            vol_1d=vol_1d, edge=edge, confianza=confianza,
            hay_noticia=hay_noticia, momentum_1h=momentum_1h
        )
        score, detalle = self.score(features)

        if score is None:
            # Sin datos suficientes: permitir pero loguear
            log.info(f"🧠 [{pregunta[:35]}] Bayesiano sin datos → permitido (neutro)")
            return True, 0.5, features

        ok = score >= MIN_WIN_RATE
        log.info(f"🧠 [{pregunta[:35]}] Bayesiano score={score:.2f} "
                 f"({'✅' if ok else '❌'}) | {detalle}")
        return ok, score, features

    def reporte(self):
        if not self.modelo: return "Sin datos aún."
        lineas = ["\n=== MODELO BAYESIANO v2 ==="]
        por_cat = {}
        for k, info in self.modelo.items():
            if info["n"] >= MIN_SAMPLES:
                cat = k.split(":")[0]
                por_cat.setdefault(cat, []).append((k, info))
        for cat, items in sorted(por_cat.items()):
            lineas.append(f"\n{cat.upper()}:")
            for k, info in sorted(items, key=lambda x: -x[1]["wr"]):
                barra = "█"*int(info["wr"]*10) + "░"*(10-int(info["wr"]*10))
                lineas.append(f"  {k:<35} {barra} {info['wr']:.0%} "
                              f"({info['wins']}/{info['n']})")
        return "\n".join(lineas)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    engine = BayesianEngine()
    engine.entrenar()
    print(engine.reporte())
