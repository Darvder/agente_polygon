"""
event_detector.py
Detecta si una señal corresponde a un evento real o ruido periódico
ya explotado. Gestiona bloqueos inteligentes por mercado.

Lógica económica:
  Un partido NBA mueve el precio de "Spurs NBA Finals" 2-3 horas.
  Si el agente ya operó ese pulso, no hay ventaja en re-entrar
  hasta el siguiente partido (~2 días después).
"""

import pandas as pd, json, os, logging
from datetime import datetime

CACHE_EVENTOS = "datos_polymarket/paper_trading/event_cache.json"

# Bloqueos post-cierre
BLOQUEO_TP   = 48   # ganamos → esperar próximo evento real
BLOQUEO_SL   = 6    # perdimos → breve espera
BLOQUEO_TIME = 4    # ruido → espera corta

# Intervalos típicos entre eventos recurrentes (horas)
INTERVALOS = {
    "nba": 52, "nhl": 52, "nfl": 168,
    "epl": 168, "election": 0, "otro": 0,
}

log = logging.getLogger("event_detector")


def _cat(pregunta):
    q = str(pregunta).lower()
    if any(k in q for k in ["nba","knicks","spurs","cavaliers","pistons","lakers","celtics","timberwolves"]): return "nba"
    if any(k in q for k in ["nhl","stanley","sabres","canadiens","hurricanes","knights","avalanche","wild"]): return "nhl"
    if any(k in q for k in ["nfl","super bowl"]): return "nfl"
    if any(k in q for k in ["premier","epl","arsenal","chelsea","city","liverpool","manchester"]): return "epl"
    if any(k in q for k in ["election","primary","senate","house","president","republican","democrat","colombian"]): return "election"
    return "otro"


class EventDetector:

    def __init__(self, archivo_libro):
        self.archivo_libro = archivo_libro
        self.df    = pd.read_csv(archivo_libro) if os.path.exists(archivo_libro) else pd.DataFrame()
        self.cache = json.load(open(CACHE_EVENTOS)) if os.path.exists(CACHE_EVENTOS) else {}

    def _save(self):
        os.makedirs(os.path.dirname(CACHE_EVENTOS), exist_ok=True)
        with open(CACHE_EVENTOS, "w") as f: json.dump(self.cache, f)

    def puede_entrar(self, market_id, pregunta):
        """
        Retorna (True/False, motivo).
        False = mercado bloqueado por evento reciente ya explotado.
        """
        mid  = str(market_id)
        ahora = datetime.now()
        cat   = _cat(pregunta)

        # ── Historial de trades en este mercado ────────────────────
        if not self.df.empty and "market_id" in self.df.columns:
            cerrados = self.df[
                (self.df["market_id"].astype(str) == mid) &
                (self.df["estado"] == "CERRADA")
            ].copy()

            if not cerrados.empty:
                cerrados["fecha_cierre_real"] = cerrados["fecha_cierre_real"].fillna("").astype(str)
                cerrados = cerrados[cerrados["fecha_cierre_real"] != ""]
                if not cerrados.empty:
                    ultimo = cerrados.sort_values("fecha_cierre_real").iloc[-1]
                    try:
                        dt = datetime.strptime(str(ultimo["fecha_cierre_real"])[:16], "%Y-%m-%d %H:%M")
                        h  = abs((ahora - dt).total_seconds() / 3600)
                        rc = str(ultimo.get("razon_cierre",""))

                        if rc == "TAKE_PROFIT":
                            bloqueo = INTERVALOS.get(cat, BLOQUEO_TP) or BLOQUEO_TP
                        elif rc == "STOP_LOSS":
                            bloqueo = BLOQUEO_SL
                        else:
                            bloqueo = BLOQUEO_TIME

                        if h < bloqueo:
                            motivo = f"Post-{rc} ({h:.1f}h/{bloqueo}h)"
                            log.info(f"🚫 {pregunta[:40]}: {motivo}")
                            return False, motivo
                    except Exception as e:
                        log.warning(f"Error event_detector: {e}")

        # ── Cache de eventos detectados ────────────────────────────
        if mid in self.cache:
            try:
                dt = datetime.fromisoformat(self.cache[mid]["ts"])
                h  = abs((ahora - dt).total_seconds() / 3600)
                bl = self.cache[mid].get("bloqueo_h", 0)
                if h < bl:
                    return False, f"Evento cacheado ({h:.1f}h/{bl}h)"
            except: pass

        return True, "ok"

    def registrar_evento(self, market_id, pregunta):
        """Registra que hubo un evento real en este mercado."""
        cat = _cat(pregunta)
        self.cache[str(market_id)] = {
            "ts":        datetime.now().isoformat(),
            "categoria": cat,
            "bloqueo_h": INTERVALOS.get(cat, 0),
        }
        self._save()

    def patron_mercado(self, market_id):
        """Estadísticas históricas de este mercado específico."""
        if self.df.empty: return {}
        t = self.df[
            (self.df["market_id"].astype(str) == str(market_id)) &
            (self.df["estado"] == "CERRADA")
        ].copy()
        if t.empty: return {}
        t["pnl"] = pd.to_numeric(t["pnl_realizado"], errors="coerce").fillna(0)
        n = len(t); wins = (t["pnl"] > 0).sum()
        return {"n": n, "wr": round(wins/n, 2), "pnl": round(float(t["pnl"].sum()), 2)}
