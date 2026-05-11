"""
bayesian_engine.py
Motor de aprendizaje Bayesiano para el agente de momentum.

Aprende de cada operación cerrada y filtra nuevas entradas
basándose en el win rate histórico por condiciones de mercado.

Uso en agente_momentum.py:
    from bayesian_engine import BayesianEngine
    engine = BayesianEngine()
    if engine.should_trade(features):
        # abrir posición
"""

import json, os, logging
import pandas as pd
from datetime import datetime

ARCHIVO_LIBRO   = "datos_polymarket/paper_trading/libro_momentum.csv"
ARCHIVO_MODELO  = "datos_polymarket/paper_trading/bayesian_model.json"
MIN_SAMPLES     = 3    # mínimo de trades para usar el win rate de una condición
MIN_WIN_RATE    = 0.45 # win rate mínimo para operar (45%)

log = logging.getLogger("bayesian")


# ══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE FEATURES
# ══════════════════════════════════════════════════════════════════

def get_categoria(pregunta):
    q = str(pregunta).lower()
    if any(k in q for k in ["nba","nfl","nhl","stanley","lakers","knicks","spurs",
                              "cavaliers","pistons","celtics","warriors","heat",
                              "buffalo","montreal","vegas","carolina","anaheim",
                              "minnesota","detroit","hurricane","sabres"]):
        return "deportes"
    if any(k in q for k in ["premier","epl","arsenal","chelsea","city","united",
                              "liverpool","tottenham","manchester","la liga",
                              "serie a","bundesliga","world cup","fifa"]):
        return "futbol"
    if any(k in q for k in ["president","senate","house","republican","democrat",
                              "election","primary","vote","congress","colombian",
                              "trump","biden","paxton","cornyn","balance of power"]):
        return "politica"
    if any(k in q for k in ["album","song","artist","rihanna","carti","taylor",
                              "bond","movie","gta","game"]):
        return "cultura"
    return "otro"

def get_mom_bucket(cambio_1h):
    """Clasifica el momentum en rangos."""
    a = abs(float(cambio_1h))
    if a < 0.02: return "muy_bajo"
    if a < 0.04: return "bajo"
    if a < 0.08: return "medio"
    if a < 0.15: return "alto"
    return "muy_alto"

def get_precio_bucket(precio):
    """Clasifica el precio de entrada."""
    p = float(precio)
    if p < 0.10: return "muy_bajo"
    if p < 0.25: return "bajo"
    if p < 0.50: return "medio"
    if p < 0.75: return "alto"
    return "muy_alto"

def get_hora_bucket(fecha_dt):
    """Clasifica la hora de entrada."""
    try:
        hora = datetime.strptime(str(fecha_dt)[:16], "%Y-%m-%d %H:%M").hour
        if hora < 6:  return "madrugada"
        if hora < 12: return "manana"
        if hora < 18: return "tarde"
        return "noche"
    except:
        return "desconocida"

def extraer_features(row):
    """Extrae features de una fila del libro."""
    return {
        "categoria":    get_categoria(row.get("pregunta", "")),
        "mom_bucket":   get_mom_bucket(row.get("cambio_1h", 0)),
        "precio_bucket": get_precio_bucket(row.get("precio_entrada", 0.5)),
        "hora_bucket":  get_hora_bucket(row.get("fecha_entrada_dt", "")),
    }

def es_ganadora(row):
    """
    Una operación es ganadora si el P&L es positivo.
    TIME_EXIT con P&L=0 se cuenta como neutra (no ganadora).
    """
    try:
        pnl = float(row.get("pnl_realizado", 0))
        return pnl > 0
    except:
        return False


# ══════════════════════════════════════════════════════════════════
# MODELO BAYESIANO
# ══════════════════════════════════════════════════════════════════

class BayesianEngine:
    """
    Modelo Bayesiano simple que aprende de trades históricos.
    
    Para cada feature individual rastrea:
      - n_trades: cuántas veces se dio esa condición
      - n_wins: cuántas resultaron ganadoras
      - win_rate: n_wins / n_trades
    
    Decisión de entrada: promedio ponderado de win rates
    por cada feature presente en la señal.
    """

    def __init__(self):
        self.modelo = self._cargar_modelo()

    def _cargar_modelo(self):
        if os.path.exists(ARCHIVO_MODELO):
            with open(ARCHIVO_MODELO) as f:
                return json.load(f)
        return {}

    def _guardar_modelo(self):
        os.makedirs(os.path.dirname(ARCHIVO_MODELO), exist_ok=True)
        with open(ARCHIVO_MODELO, "w") as f:
            json.dump(self.modelo, f, indent=2)

    def entrenar(self):
        """
        Lee el libro_momentum.csv y actualiza el modelo
        con todas las operaciones cerradas.
        Se llama al inicio de cada ciclo del agente.
        """
        if not os.path.exists(ARCHIVO_LIBRO):
            return

        df = pd.read_csv(ARCHIVO_LIBRO)
        cerradas = df[
            (df["estado"] == "CERRADA") &
            (df["pnl_realizado"].notna())
        ].copy()

        if cerradas.empty:
            return

        # Reiniciar modelo y reconstruir desde cero
        # (más simple y evita acumulación de errores)
        nuevo_modelo = {}

        for _, row in cerradas.iterrows():
            features = extraer_features(row)
            ganadora = es_ganadora(row)

            for feature_name, feature_val in features.items():
                clave = f"{feature_name}:{feature_val}"
                if clave not in nuevo_modelo:
                    nuevo_modelo[clave] = {"n": 0, "wins": 0, "wr": 0.5}
                nuevo_modelo[clave]["n"]    += 1
                nuevo_modelo[clave]["wins"] += int(ganadora)
                nuevo_modelo[clave]["wr"]    = round(
                    nuevo_modelo[clave]["wins"] / nuevo_modelo[clave]["n"], 3
                )

        self.modelo = nuevo_modelo
        self._guardar_modelo()
        log.info(f"Modelo Bayesiano actualizado: {len(nuevo_modelo)} condiciones aprendidas")

    def score(self, features_dict):
        """
        Calcula el score Bayesiano para un conjunto de features.
        Retorna (score, detalle) donde score es 0.0-1.0.
        
        Features con pocos samples (< MIN_SAMPLES) se ignoran
        para evitar sobreajuste con datos escasos.
        """
        scores = []
        detalle = {}

        for feature_name, feature_val in features_dict.items():
            clave = f"{feature_name}:{feature_val}"
            if clave in self.modelo:
                info = self.modelo[clave]
                if info["n"] >= MIN_SAMPLES:
                    scores.append(info["wr"])
                    detalle[clave] = f"{info['wr']:.0%} ({info['n']} trades)"

        if not scores:
            # Sin datos suficientes → score neutro (no bloquear)
            return 0.5, {"estado": "sin_datos_suficientes"}

        score_final = round(sum(scores) / len(scores), 3)
        return score_final, detalle

    def should_trade(self, pregunta, cambio_1h, precio_entrada, fecha_dt):
        """
        Decide si abrir una posición basándose en el historial.
        
        Retorna (bool, score, motivo)
        True = operar, False = no operar
        """
        features = {
            "categoria":     get_categoria(pregunta),
            "mom_bucket":    get_mom_bucket(cambio_1h),
            "precio_bucket": get_precio_bucket(precio_entrada),
            "hora_bucket":   get_hora_bucket(fecha_dt),
        }

        score, detalle = self.score(features)

        if score >= MIN_WIN_RATE:
            return True, score, features
        else:
            return False, score, features

    def reporte(self):
        """Muestra el modelo aprendido ordenado por win rate."""
        if not self.modelo:
            return "Sin datos aún"

        lineas = ["\n=== MODELO BAYESIANO ==="]
        por_categoria = {}
        for clave, info in self.modelo.items():
            if info["n"] >= MIN_SAMPLES:
                cat = clave.split(":")[0]
                if cat not in por_categoria:
                    por_categoria[cat] = []
                por_categoria[cat].append((clave, info))

        for cat, items in sorted(por_categoria.items()):
            lineas.append(f"\n{cat.upper()}:")
            for clave, info in sorted(items, key=lambda x: -x[1]["wr"]):
                barra = "█" * int(info["wr"] * 10) + "░" * (10 - int(info["wr"] * 10))
                lineas.append(
                    f"  {clave:<35} {barra} {info['wr']:.0%} "
                    f"({info['wins']}/{info['n']} trades)"
                )
        return "\n".join(lineas)


# ══════════════════════════════════════════════════════════════════
# ANÁLISIS STANDALONE (ejecutar directamente para ver el modelo)
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(message)s")
    engine = BayesianEngine()
    engine.entrenar()
    print(engine.reporte())

    # Simulación: ¿operarías Rihanna con momentum alto?
    print("\n=== SIMULACIÓN ===")
    casos = [
        ("New Rihanna Album before GTA VI?", 0.15, 0.65, "2026-05-10 09:00"),
        ("Will Montreal Canadiens win NHL?", 0.03, 0.07, "2026-05-10 14:00"),
        ("Will Ken Paxton win Republican Primary?", 0.04, 0.40, "2026-05-10 16:00"),
        ("Will Arsenal win Premier League?", 0.05, 0.30, "2026-05-10 12:00"),
    ]
    for pregunta, mom, precio, fecha in casos:
        ok, score, feats = engine.should_trade(pregunta, mom, precio, fecha)
        estado = "✅ OPERAR" if ok else "❌ BLOQUEAR"
        print(f"{estado} | score={score:.0%} | {pregunta[:45]}")
        print(f"         features: {feats}")
