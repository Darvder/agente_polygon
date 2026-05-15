"""
volatility_engine.py
Calcula SL/TP/MAX_HORAS dinámicos por mercado usando la serie
histórica de precios del CLOB API de Polymarket.

Lógica económica:
  Cada mercado tiene su propia volatilidad. Un SL fijo de -7%
  es demasiado amplio para mercados estables y muy estrecho para
  mercados volátiles. Este módulo calibra parámetros según el
  comportamiento histórico real de cada activo.
"""

import requests, json, os, logging
import numpy as np
from datetime import datetime

CLOB_URL = "https://clob.polymarket.com"
TIMEOUT  = 10

# Valores por defecto (si no hay datos históricos)
DEFAULT_TP    = 0.09
DEFAULT_SL    = -0.07
DEFAULT_HORAS = 6

# Límites absolutos
MIN_TP = 0.04; MAX_TP = 0.25
MIN_SL = -0.15; MAX_SL = -0.03
MIN_H  = 2;    MAX_H  = 12

CACHE_FILE  = "datos_polymarket/paper_trading/volatility_cache.json"
CACHE_TTL_H = 6

log = logging.getLogger("volatility")


# ── Cache ──────────────────────────────────────────────────────────

def _load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f: return json.load(f)
    return {}

 # Asegúrate de que numpy esté importado al inicio

def _save_cache(c):
    """Guarda el caché convirtiendo tipos de NumPy a nativos para evitar el crash."""
    def convertidor(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj) 
        if isinstance(obj, np.generic):
            return obj.item()
        raise TypeError
    
    try:
        with open(CACHE_FILE, "w") as f:
            # El parámetro 'default' es lo que evita el error de serialización
            json.dump(c, f, indent=4, default=convertidor)
    except Exception as e:
        print(f"Error guardando caché: {e}")
      
def _valid(entry):
    try:
        return (datetime.now() - datetime.fromisoformat(
            entry["ts"])).total_seconds() < CACHE_TTL_H * 3600
    except: return False


# ── CLOB API ───────────────────────────────────────────────────────

def _token_yes(market_id):
    try:
        r = requests.get("https://gamma-api.polymarket.com/markets",
                         params={"id": market_id}, timeout=TIMEOUT)
        if r.status_code == 200 and r.json():
            ids = json.loads(r.json()[0].get("clobTokenIds", "[]"))
            return str(ids[0]) if ids else None
    except: pass
    return None

def _precios_historicos(token_yes):
    """Obtiene serie histórica via CLOB. Retorna lista de floats."""
    try:
        r = requests.get(f"{CLOB_URL}/prices-history",
                         params={"market": token_yes, "interval": "max"},
                         timeout=TIMEOUT)
        if r.status_code != 200: return []
        historia = r.json().get("history", [])
        return [float(h["p"]) for h in
                sorted(historia, key=lambda x: x.get("t", 0)) if "p" in h]
    except: return []


# ── Métricas ───────────────────────────────────────────────────────

def _metricas(precios):
    """Calcula volatilidad y estadísticas de la serie de precios."""
    if len(precios) < 5: return None
    arr = np.array(precios)
    ret = np.diff(np.log(arr + 0.001))

    n1d = min(24, len(ret)); n7d = min(168, len(ret))
    vol_1d = float(np.std(ret[-n1d:])) if n1d > 1 else 0.02
    vol_7d = float(np.std(ret[-n7d:])) if n7d > 1 else 0.02

    # Periodicidad: detectar si hay pulsos regulares (eventos recurrentes)
    # Buscamos picos de volatilidad en ventanas de 24h
    pulsos = []
    if len(ret) >= 48:
        for i in range(0, len(ret)-24, 24):
            ventana = np.std(ret[i:i+24])
            pulsos.append(float(ventana))
        hay_pulsos = np.std(pulsos) > np.mean(pulsos) * 0.5 if pulsos else False
        intervalo_pulso = 24 if hay_pulsos else 0  # horas entre pulsos
    else:
        hay_pulsos = False; intervalo_pulso = 0

    media = float(np.mean(arr)); std = float(np.std(arr))
    en_extremo = abs(arr[-1] - media) > 2 * std if std > 0 else False

    # Tendencia reciente
    tend = 0
    if len(arr) >= 5:
        d = arr[-1] - arr[-5]
        tend = 1 if d > 0.005 else (-1 if d < -0.005 else 0)

    return {
        "vol_1d":        round(vol_1d, 5),
        "vol_7d":        round(vol_7d, 5),
        "rango":         round(float(np.percentile(arr,75) - np.percentile(arr,25)), 4),
        "tendencia":     tend,
        "en_extremo":    en_extremo,
        "hay_pulsos":    hay_pulsos,
        "intervalo_h":   intervalo_pulso,
        "precio_min":    round(float(np.min(arr)), 4),
        "precio_max":    round(float(np.max(arr)), 4),
        "n":             len(precios),
    }


# ── SL/TP dinámicos ────────────────────────────────────────────────

def _calcular_params(m, dias):
    """
    Deriva SL, TP y MAX_HORAS de las métricas de volatilidad.

    SL = 2σ de volatilidad diaria (no perder más que el ruido normal)
    TP = SL × 1.5 (ratio riesgo/beneficio mínimo)
    MAX_HORAS = depende de velocidad del mercado y pulsos detectados
    """
    if m is None:
        return DEFAULT_TP, DEFAULT_SL, DEFAULT_HORAS

    vol = m["vol_1d"]

    sl = max(MIN_SL, min(MAX_SL, -round(max(vol * 2, 0.03), 3)))
    tp = max(MIN_TP, min(MAX_TP,  round(abs(sl) * 1.5, 3)))

    # Velocidad: mercados volátiles se resuelven rápido
    if vol > 0.05:    h = 3
    elif vol > 0.02:  h = 6
    else:             h = 10

    # Si hay pulsos regulares (NBA, NHL) reducir tiempo entre pulsos
    if m["hay_pulsos"] and m["intervalo_h"] > 0:
        h = min(h, m["intervalo_h"] // 2)

    # Evento inminente → salir rápido
    if dias <= 2: h = min(h, 3)

    return tp, sl, max(MIN_H, min(MAX_H, h))


# ══════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class VolatilityEngine:
    """
    Motor de volatilidad con cache.
    Instanciar una vez por ciclo del agente.
    """

    def __init__(self):
        self.cache = _load_cache()

    def get_params(self, market_id, dias):
        """
        Retorna (tp, sl, max_horas, metricas) para el mercado.
        Usa cache de 6h para evitar llamadas repetidas al CLOB.
        """
        key = str(market_id)

        if key in self.cache and _valid(self.cache[key]):
            m = self.cache[key].get("m")
        else:
            tok = _token_yes(market_id)
            m   = _metricas(_precios_historicos(tok)) if tok else None
            self.cache[key] = {"ts": datetime.now().isoformat(), "m": m}
            _save_cache(self.cache)

        tp, sl, h = _calcular_params(m, dias)
        log.info(
            f"Vol [{key[:10]}]: "
            f"tp={tp:.0%} sl={sl:.0%} h={h}h "
            f"vol={m['vol_1d']:.3f} pulsos={'sí' if m and m['hay_pulsos'] else 'no'}"
            if m else
            f"Vol [{key[:10]}]: sin datos → defaults"
        )
        return tp, sl, h, m

    def en_extremo(self, market_id):
        """True si el precio actual está en zona extrema histórica."""
        m = self.cache.get(str(market_id), {}).get("m")
        return m.get("en_extremo", False) if m else False

    def tiene_pulsos(self, market_id):
        """True si el mercado tiene eventos periódicos detectados."""
        m = self.cache.get(str(market_id), {}).get("m")
        return m.get("hay_pulsos", False) if m else False
