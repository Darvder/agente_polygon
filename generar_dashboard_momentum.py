import pandas as pd
import json
import os
import html
from datetime import datetime

ARCHIVO_LIBRO  = "datos_polymarket/paper_trading/libro_hibrido.csv"
ARCHIVO_ESTADO = "datos_polymarket/paper_trading/estado_hibrido.json"
ARCHIVO_OUTPUT = "datos_polymarket/dashboard_hibrido.html"

def calcular_posicion_barra(precio_entrada, precio_actual, tp, sl):
    try:
        pe = float(precio_entrada); pa = float(precio_actual)
        tp = float(tp); sl = float(sl)
        precio_sl = pe * (1.0 + sl); precio_tp = pe * (1.0 + tp)
        rango = precio_tp - precio_sl
        if rango == 0: return 50.0
        return max(0.0, min(100.0, ((pa - precio_sl) / rango) * 100.0))
    except: return 50.0

def generar_dashboard():
    # ── Estado ────────────────────────────────────────────────────
    capital_inicial = 1000.0; capital_actual = 900.0
    capital_en_riesgo = 100.0; n_ciclos = 0
    from zoneinfo import ZoneInfo
    ultima_corrida = datetime.now(ZoneInfo("America/Guayaquil")).strftime("%Y-%m-%d %H:%M")
    n_tp_est = 0; n_sl_est = 0; n_time_est = 0

    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO) as f:
                est = json.load(f)
                capital_actual    = float(est.get("capital_actual", capital_actual))
                capital_en_riesgo = float(est.get("capital_en_riesgo", capital_en_riesgo))
                n_ciclos          = est.get("n_ciclos", 0)
                ultima_corrida    = est.get("ultima_corrida", ultima_corrida)
                n_tp_est          = est.get("n_tp", 0)
                n_sl_est          = est.get("n_sl", 0)
                n_time_est        = est.get("n_time", 0)
        except Exception as e:
            print(f"⚠️ Estado: {e}")

    # ── CSV ───────────────────────────────────────────────────────
    df = pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()

    ops_abiertas_html = ""; ops_cerradas_html = ""
    pnl_total = 0.0; win_rate = 0.0; pnl_flotante_total = 0.0
    total_ganadas = 0; total_perdidas = 0; total_cerradas = 0
    n_inactiva = 0; n_tp = 0; n_sl = 0; n_time = 0
    avg_win = 0.0; avg_loss = 0.0
    fechas_rendimiento = []; valores_rendimiento = []
    pnl_acumulado = 0.0
    n_abiertas = 0
    
    # YES/NO counters
    yes_count = 0
    no_count = 0
    pct_yes = 0
    pct_no = 0

    if not df.empty:
        df['estado'] = df['estado'].astype(str).str.strip().str.upper()
        abiertas = df[df['estado'] == 'ABIERTA']
        n_abiertas = len(abiertas)

        # Count signals
        df_valid_signals = df[df['señal'].notna()]
        yes_count = len(df_valid_signals[df_valid_signals['señal'].astype(str).str.upper().str.contains("YES")])
        no_count = len(df_valid_signals[df_valid_signals['señal'].astype(str).str.upper().str.contains("NO")])
        total_signals = yes_count + no_count
        if total_signals > 0:
            pct_yes = (yes_count / total_signals) * 100
            pct_no = (no_count / total_signals) * 100

        # Loop active positions
        if abiertas.empty:
            ops_abiertas_html = '<div class="no-data" style="grid-column: span 3;">Sin posiciones abiertas. Buscando oportunidades...</div>'
        else:
            for _, p in abiertas.iterrows():
                tp_real   = float(p.get('tp_dinamico', 0.05))
                sl_real   = float(p.get('sl_dinamico', -0.04))
                confianza = float(p.get('llm_confianza', 0.50))
                edge      = float(p.get('llm_edge', 0.03))
                if edge > 1.0: edge /= 100.0
                senal     = str(p.get('señal', 'COMPRAR YES'))
                monto     = float(p.get('monto_usdc', 0.0))
                precio_ent = float(p.get('precio_token_entrada', p.get('precio_entrada', 0.5)))
                precio_act = float(p.get('precio_actual', precio_ent))
                vol_1d    = float(p.get('vol_1d', 0.0))
                momentum_1h = float(p.get('momentum_1h', 0.0))
                horas_max = p.get('horas_max', 10)
                razonamiento_completo = str(p.get('razonamiento', '—'))
                razon_ia  = razonamiento_completo[:80] + ("..." if len(razonamiento_completo) > 80 else "")

                if "YES" in senal.upper():
                    pnl_flotante = (precio_act - precio_ent) * (monto / precio_ent) if precio_ent > 0 else 0
                else:
                    pnl_flotante = ((1.0 - precio_act) - precio_ent) * (monto / precio_ent) if precio_ent > 0 else 0
                
                pnl_flotante_total += pnl_flotante
                pnl_clase = "positive" if pnl_flotante >= 0 else "negative"
                precio_act_token = precio_act if "YES" in senal.upper() else round(1 - precio_act, 4)
                pct_burbuja = calcular_posicion_barra(precio_ent, precio_act_token, tp_real, sl_real)

                mom_color = "#10b981" if momentum_1h >= 0 else "#ef4444"
                
                # Payload for Javascript Modal
                datos_js = {
                    "pregunta": p['pregunta'],
                    "senal": senal,
                    "monto": f"${monto:,.2f} USDC",
                    "confianza": f"{confianza:.0%}",
                    "edge": f"+{edge:.1%}",
                    "precio_entrada": f"{precio_ent:.3f}",
                    "precio_actual": f"{precio_act:.3f}",
                    "pnl": f"{'+' if pnl_flotante>=0 else ''}${pnl_flotante:.2f}",
                    "pnl_raw": pnl_flotante,
                    "salida": "ACTIVA",
                    "razonamiento": razonamiento_completo
                }

                ops_abiertas_html += f"""
                <div class="card-orden">
                    <div class="card-orden-header">
                        <span class="badge-senal {senal.lower().replace(' ', '-')}">{senal}</span>
                        <span class="monto-orden">${monto:,.2f} USDC</span>
                    </div>
                    <div class="pregunta-titulo">{p['pregunta']}</div>
                    <div class="metadatos-grid">
                        <div class="meta-item"><span class="meta-label">🤖 Confianza</span><span class="meta-value">{confianza:.0%}</span></div>
                        <div class="meta-item"><span class="meta-label">📈 Edge</span><span class="meta-value">+{edge:.1%}</span></div>
                        <div class="meta-item"><span class="meta-label">⏱️ Límite</span><span class="meta-value">{horas_max}h</span></div>
                        <div class="meta-item"><span class="meta-label">📊 P&L</span><span class="meta-value {pnl_clase}">{"+" if pnl_flotante>=0 else ""}${pnl_flotante:.2f}</span></div>
                        <div class="meta-item"><span class="meta-label">📉 Vol 1d</span><span class="meta-value">{vol_1d:.4f}</span></div>
                        <div class="meta-item"><span class="meta-label">⚡ Mom 1h</span><span class="meta-value" style="color:{mom_color}">{momentum_1h:+.1%}</span></div>
                    </div>
                    <div class="riesgo-container">
                        <div class="riesgo-labels">
                            <span class="label-sl">SL {sl_real:.1%}</span>
                            <span>Entrada {precio_ent:.3f}</span>
                            <span class="label-tp">TP {tp_real:.1%}</span>
                        </div>
                        <div class="riesgo-barra-bg">
                            <div class="riesgo-burbuja" style="left:{pct_burbuja}%;"></div>
                        </div>
                        <div class="riesgo-precios">
                            <span>${precio_ent*(1+sl_real):.3f}</span>
                            <span style="color:#a78bfa;font-weight:600">Actual ${precio_act:.3f}</span>
                            <span>${precio_ent*(1+tp_real):.3f}</span>
                        </div>
                    </div>
                    <div class="card-orden-footer">
                        <div class="ia-summary-box">
                            <span class="meta-label">🧠 IA:</span> <span class="ia-summary-text">{razon_ia}</span>
                        </div>
                        <button class="btn-ver-cot" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js))}">Ver Análisis</button>
                    </div>
                </div>"""

        # ── Cerradas ──────────────────────────────────────────────
        cerradas = df[df['estado'] == 'CERRADA'].copy()
        if not cerradas.empty:
            if 'fecha_cierre_real' in cerradas.columns:
                cerradas['fecha_sort'] = pd.to_datetime(cerradas['fecha_cierre_real'], errors='coerce')
                cerradas = cerradas.sort_values('fecha_sort', ascending=True)

            total_cerradas = len(cerradas)
            pnl_total = float(df['pnl_realizado'].fillna(0.0).sum())

            wins = []; losses = []
            for _, p in cerradas.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                razon  = str(p.get('razon_cierre', 'EXIT')).upper()
                fecha_cierre = str(p.get('fecha_cierre_real', p.get('fecha_entrada', '---')))
                razonamiento_completo = str(p.get('razonamiento', '—'))

                if pnl_op > 0: total_ganadas += 1; wins.append(pnl_op)
                elif pnl_op < 0: total_perdidas += 1; losses.append(pnl_op)

                if razon == 'TAKE_PROFIT': n_tp += 1
                elif razon == 'STOP_LOSS': n_sl += 1
                elif razon == 'TIME_EXIT': n_time += 1
                elif razon == 'INACTIVA':  n_inactiva += 1
                elif razon == 'EARLY_EXIT': n_tp += 1  # cuenta como TP

                pnl_acumulado += pnl_op
                fechas_rendimiento.append(fecha_cierre[:10])
                valores_rendimiento.append(round(pnl_acumulado, 2))

                clase_row = "row-ganancia" if pnl_op >= 0 else "row-perdida"
                
                # Payload for Javascript Modal on Closed Position
                datos_js_closed = {
                    "pregunta": p['pregunta'],
                    "senal": p.get('señal', '—'),
                    "monto": f"${float(p.get('monto_usdc',0)):,.2f} USDC",
                    "confianza": f"{float(p.get('llm_confianza',0.5)):.0%}" if p.get('llm_confianza') else "—",
                    "edge": f"+{float(p.get('llm_edge',0)):.1%}" if p.get('llm_edge') else "—",
                    "precio_entrada": f"{float(p.get('precio_entrada',0.5)):.3f}",
                    "precio_actual": f"{float(p.get('precio_cierre',0.5)):.3f}",
                    "pnl": f"{'+' if pnl_op>=0 else ''}${pnl_op:,.2f}",
                    "pnl_raw": pnl_op,
                    "salida": razon,
                    "razonamiento": razonamiento_completo
                }

                ops_cerradas_html += f"""
                <tr class="{clase_row}">
                    <td>{fecha_cierre[:16]}</td>
                    <td class="txt-truncate" title="{p['pregunta']}">{str(p['pregunta'])[:48]}…</td>
                    <td><span class="badge-tabla">{p.get('señal','—')}</span></td>
                    <td>${float(p.get('monto_usdc',0)):,.2f}</td>
                    <td class="bold-pnl">{"+" if pnl_op>=0 else ""}${pnl_op:,.2f}</td>
                    <td><span class="badge-razon {razon.lower()}">{razon}</span></td>
                    <td>
                        <button class="btn-ver-cot-tabla" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js_closed))}">🔍</button>
                    </td>
                </tr>"""

            trades_reales = total_ganadas + total_perdidas
            win_rate = total_ganadas / trades_reales if trades_reales > 0 else 0.0
            avg_win  = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0

    if not ops_cerradas_html:
        ops_cerradas_html = '<tr><td colspan="7" class="no-data">Sin operaciones cerradas aún.</td></tr>'
    if not fechas_rendimiento:
        fechas_rendimiento = [datetime.now().strftime("%Y-%m-%d")]
        valores_rendimiento = [0.0]

    pnl_clase_total = "positive" if pnl_total >= 0 else "negative"
    pnl_signo = "+" if pnl_total > 0 else ""

    pnl_flotante_clase = "positive" if pnl_flotante_total >= 0 else "negative"
    pnl_flotante_signo = "+" if pnl_flotante_total > 0 else ""

    # Profit Factor
    sum_wins = sum(wins) if 'wins' in locals() else 0.0
    sum_losses = abs(sum(losses)) if 'losses' in locals() else 0.0
    if sum_losses == 0:
        profit_factor_str = "∞" if sum_wins > 0 else "0.00"
        profit_factor_clase = "positive" if sum_wins > 0 else "neutral"
    else:
        pf_val = sum_wins / sum_losses
        profit_factor_str = f"{pf_val:.2f}"
        profit_factor_clase = "positive" if pf_val >= 1.0 else "negative"

    # Net account balance with floating P&L included
    net_equity = capital_actual + pnl_flotante_total
    equity_clase = "positive" if net_equity >= capital_inicial else "negative"

    # Donut data
    donut_labels = ['TP / Early', 'Stop Loss', 'Time Exit', 'Inactiva']
    donut_data   = [n_tp, n_sl, n_time, n_inactiva]
    donut_colors = ['#10b981', '#ef4444', '#f59e0b', '#6b7280']

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agente Híbrido — Panel de Control v3</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
  --bg: #030712; 
  --surface: rgba(15, 23, 42, 0.45); 
  --surface-card: rgba(22, 34, 57, 0.35);
  --border: rgba(255, 255, 255, 0.06);
  --border-hover: rgba(139, 92, 246, 0.35);
  --primary: #8b5cf6; 
  --primary-glow: rgba(139, 92, 246, 0.22);
  --green: #10b981; 
  --red: #ef4444; 
  --amber: #f59e0b; 
  --gray: #64748b;
  --text: #f8fafc; 
  --muted: #94a3b8;
  --font-head: 'Outfit', sans-serif; 
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{ 
  background: var(--bg); 
  color: var(--text); 
  font-family: var(--font-body); 
  padding: 2.5rem; 
  min-height: 100vh;
  position: relative;
}}

body::before {{ 
  content: ''; 
  position: fixed; 
  inset: 0; 
  background: radial-gradient(circle at 10% 12%, rgba(139, 92, 246, 0.07) 0%, transparent 45%),
              radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.04) 0%, transparent 45%); 
  pointer-events: none; 
  z-index: -1;
}}

/* Header */
header {{ 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 2.5rem; 
  padding-bottom: 1.5rem; 
  border-bottom: 1px solid var(--border); 
}}

.brand {{
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}}

.brand h1 {{ 
  font-size: 2.25rem; 
  font-weight: 800; 
  letter-spacing: -0.04em; 
  font-family: var(--font-head);
  background: linear-gradient(135deg, #fff 40%, var(--muted) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.brand h1 span {{ 
  background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 15px rgba(139, 92, 246, 0.35);
}}

.brand p {{ 
  color: var(--muted); 
  font-size: 0.8rem; 
  font-family: var(--font-mono); 
  letter-spacing: 0.05em; 
}}

.header-meta-container {{
  display: flex;
  align-items: center;
  gap: 2rem;
}}

.status-badge {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  padding: 0.4rem 0.8rem;
  border-radius: 9999px;
}}

.status-dot {{
  width: 8px;
  height: 8px;
  background-color: var(--green);
  border-radius: 50%;
  box-shadow: 0 0 10px var(--green);
}}

.pulse {{
  animation: pulseGlow 2s infinite ease-in-out;
}}

@keyframes pulseGlow {{
  0%, 100% {{ opacity: 0.4; transform: scale(1); }}
  50% {{ opacity: 1; transform: scale(1.15); }}
}}

.status-text {{
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 0.05em;
}}

.meta-header {{ 
  text-align: right; 
  font-family: var(--font-mono); 
  font-size: 0.8rem; 
  color: var(--muted); 
  line-height: 1.6; 
}}

.meta-header strong {{ 
  color: var(--text); 
}}

/* Metric cards grid */
.grid-metricas {{ 
  display: grid; 
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); 
  gap: 1.25rem; 
  margin-bottom: 2.5rem; 
}}

.card-m {{ 
  background: var(--surface); 
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border); 
  border-radius: 16px; 
  padding: 1.25rem 1.5rem; 
  position: relative; 
  overflow: hidden; 
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}

.card-m:hover {{
  transform: translateY(-3px);
  border-color: var(--accent-hover, var(--border-hover));
  box-shadow: 0 15px 30px -10px rgba(0, 0, 0, 0.6), 0 0 15px var(--accent-glow, var(--primary-glow));
}}

.card-m::after {{ 
  content: ''; 
  position: absolute; 
  bottom: 0; 
  left: 0; 
  right: 0; 
  height: 3px; 
  background: var(--accent, var(--border)); 
}}

.card-m h4 {{ 
  font-size: 0.72rem; 
  text-transform: uppercase; 
  letter-spacing: 0.1em; 
  color: var(--muted); 
  font-family: var(--font-mono); 
}}

.card-m .val {{ 
  font-size: 1.9rem; 
  font-weight: 700; 
  margin-top: 0.5rem; 
  font-family: var(--font-mono); 
}}

.card-m .sub {{ 
  font-size: 0.75rem; 
  color: var(--muted); 
  margin-top: 0.3rem; 
  font-family: var(--font-mono); 
}}

.positive {{ color: var(--green); }} 
.negative {{ color: var(--red); }}
.neutral {{ color: var(--text); }}

/* Layout */
.row-2 {{ 
  display: grid; 
  grid-template-columns: 1.8fr 1fr; 
  gap: 1.75rem; 
  margin-bottom: 2.5rem; 
}}

@media(max-width:1100px) {{ 
  .row-2 {{ grid-template-columns: 1fr; }} 
}}

/* Panels */
.panel {{ 
  background: var(--surface); 
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border); 
  border-radius: 18px; 
  padding: 1.75rem; 
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
}}

.panel h3 {{ 
  font-size: 0.85rem; 
  text-transform: uppercase; 
  letter-spacing: 0.12em; 
  color: var(--muted); 
  font-family: var(--font-mono); 
  margin-bottom: 1.5rem; 
  display: flex; 
  align-items: center; 
  gap: 0.6rem; 
}}

.panel h3::before {{ 
  content: ''; 
  display: inline-block; 
  width: 4px; 
  height: 14px; 
  background: var(--primary); 
  border-radius: 2px; 
  box-shadow: 0 0 8px var(--primary);
}}

/* Active Positions */
.abiertas-wrapper {{ 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); 
  gap: 1.25rem; 
}}

.card-orden {{ 
  background: var(--surface-card); 
  border: 1px solid var(--border); 
  border-radius: 14px; 
  padding: 1.5rem; 
  display: flex; 
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 5px 15px rgba(0,0,0,0.2);
  transition: all 0.25s ease; 
}}

.card-orden:hover {{ 
  border-color: rgba(139, 92, 246, 0.3); 
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.4), 0 0 10px rgba(139,92,246,0.1);
}}

.card-orden-header {{ 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 0.85rem; 
}}

.badge-senal {{ 
  font-size: 0.68rem; 
  font-weight: 700; 
  padding: 0.25rem 0.6rem; 
  border-radius: 6px; 
  text-transform: uppercase; 
  font-family: var(--font-mono); 
  letter-spacing: 0.03em;
}}

.badge-senal.comprar-yes {{ 
  background: rgba(16, 185, 129, 0.1); 
  color: var(--green); 
  border: 1px solid rgba(16, 185, 129, 0.2); 
}}

.badge-senal.comprar-no  {{ 
  background: rgba(239, 68, 68, 0.1); 
  color: var(--red); 
  border: 1px solid rgba(239, 68, 68, 0.2); 
}}

.monto-orden {{ 
  font-size: 0.95rem; 
  font-weight: 700; 
  font-family: var(--font-mono); 
  color: #e2e8f0; 
}}

.pregunta-titulo {{ 
  font-size: 0.98rem; 
  font-weight: 600; 
  margin-bottom: 1rem; 
  line-height: 1.45; 
  color: #fff; 
  font-family: var(--font-head);
}}

.metadatos-grid {{ 
  display: grid; 
  grid-template-columns: repeat(3, 1fr); 
  gap: 0.75rem; 
  background: rgba(8, 12, 20, 0.55); 
  padding: 0.8rem 1rem; 
  border-radius: 10px; 
  margin-bottom: 1.25rem; 
  border: 1px solid rgba(255,255,255,0.03);
}}

.meta-item {{ 
  display: flex; 
  flex-direction: column; 
}}

.meta-label {{ 
  font-size: 0.65rem; 
  color: var(--muted); 
  font-family: var(--font-mono); 
  text-transform: uppercase; 
  letter-spacing: 0.05em; 
}}

.meta-value {{ 
  font-size: 0.88rem; 
  font-weight: 600; 
  margin-top: 0.15rem; 
  font-family: var(--font-mono); 
  color: #f8fafc; 
}}

.riesgo-container {{ 
  margin-bottom: 1.25rem; 
}}

.riesgo-labels {{ 
  display: flex; 
  justify-content: space-between; 
  font-size: 0.72rem; 
  margin-bottom: 0.45rem; 
  font-family: var(--font-mono); 
  color: var(--muted); 
}}

.label-sl {{ color: var(--red); font-weight: 600; }} 
.label-tp {{ color: var(--green); font-weight: 600; }}

.riesgo-barra-bg {{ 
  height: 6px; 
  background: linear-gradient(to right, var(--red) 0%, rgba(30, 41, 59, 0.8) 35%, rgba(30, 41, 59, 0.8) 65%, var(--green) 100%); 
  border-radius: 3px; 
  position: relative; 
  margin-bottom: 0.45rem; 
}}

.riesgo-burbuja {{ 
  width: 12px; 
  height: 12px; 
  background: #fff; 
  border: 2.5px solid var(--primary); 
  border-radius: 50%; 
  position: absolute; 
  top: 50%; 
  transform: translate(-50%, -50%); 
  box-shadow: 0 0 10px var(--primary); 
  transition: left 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}}

.riesgo-precios {{ 
  display: flex; 
  justify-content: space-between; 
  font-size: 0.7rem; 
  color: var(--muted); 
  font-family: var(--font-mono); 
}}

/* Card Orden Footer */
.card-orden-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}}

.ia-summary-box {{
  font-size: 0.75rem;
  color: var(--muted);
  max-width: 68%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.ia-summary-text {{
  color: #94a3b8;
  font-style: italic;
}}

.btn-ver-cot {{
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.25);
  color: #c084fc;
  padding: 0.4rem 0.8rem;
  font-size: 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-family: var(--font-head);
  transition: all 0.2s ease;
}}

.btn-ver-cot:hover {{
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.45);
}}

/* Filter Bar & Search */
.filter-bar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}}

.search-box {{
  flex-grow: 1;
  max-width: 320px;
}}

.search-box input {{
  width: 100%;
  background: rgba(8, 12, 20, 0.65);
  border: 1px solid var(--border);
  padding: 0.6rem 1.1rem;
  border-radius: 10px;
  color: #fff;
  font-family: var(--font-body);
  font-size: 0.85rem;
  outline: none;
  transition: all 0.2s;
}}

.search-box input:focus {{
  border-color: var(--primary);
  box-shadow: 0 0 10px rgba(139, 92, 246, 0.15);
  background: rgba(8, 12, 20, 0.85);
}}

.filter-tabs {{
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}}

.filter-tab {{
  background: rgba(22, 34, 57, 0.2);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-size: 0.75rem;
  cursor: pointer;
  font-family: var(--font-head);
  font-weight: 600;
  transition: all 0.2s;
}}

.filter-tab:hover {{
  border-color: rgba(255, 255, 255, 0.15);
  color: #fff;
}}

.filter-tab.active {{
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.3);
}}

/* Yes/No Signal Bar */
.panel-distribucion {{
  margin-top: 1.75rem;
  padding-top: 1.75rem;
  border-top: 1px solid var(--border);
}}

.yes-no-bar-container {{
  height: 8px;
  background: var(--red);
  border-radius: 99px;
  overflow: hidden;
  display: flex;
  margin: 0.75rem 0;
}}

.yes-no-bar-yes {{
  background: var(--green);
  height: 100%;
  transition: width 0.5s ease-in-out;
}}

.yes-no-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--muted);
}}

/* Table styling */
.tabla-contenedor {{ 
  width: 100%; 
  overflow-x: auto; 
  margin-top: 0.5rem; 
  border-radius: 12px;
  border: 1px solid var(--border);
}}

table {{ 
  width: 100%; 
  border-collapse: collapse; 
  font-size: 0.85rem; 
  font-family: var(--font-mono); 
}}

th {{ 
  background: rgba(8, 12, 20, 0.7); 
  color: var(--muted); 
  font-weight: 600; 
  padding: 0.85rem 1.2rem; 
  border-bottom: 1px solid var(--border); 
  text-transform: uppercase; 
  font-size: 0.68rem; 
  letter-spacing: 0.08em; 
  text-align: left;
}}

td {{ 
  padding: 0.9rem 1.2rem; 
  border-bottom: 1px solid var(--border); 
  color: #cbd5e1; 
}}

tr {{ 
  transition: all 0.2s; 
}}

tr:hover td {{ 
  background: rgba(26, 38, 64, 0.25); 
}}

.row-ganancia .bold-pnl {{ color: var(--green); font-weight: 700; }}
.row-perdida  .bold-pnl {{ color: var(--red); font-weight: 700; }}

.badge-tabla {{ 
  background: #1e293b; 
  padding: 0.25rem 0.5rem; 
  border-radius: 6px; 
  font-size: 0.7rem; 
  font-weight: 600; 
  color: #cbd5e1; 
  border: 1px solid rgba(255,255,255,0.05);
}}

.badge-razon {{ 
  font-size: 0.68rem; 
  font-weight: 700; 
  padding: 0.25rem 0.6rem; 
  border-radius: 6px; 
  text-transform: uppercase; 
}}

.badge-razon.take_profit, .badge-razon.early_exit {{ 
  background: rgba(16, 185, 129, 0.1); 
  color: var(--green); 
  border: 1px solid rgba(16, 185, 129, 0.2); 
}}

.badge-razon.stop_loss   {{ 
  background: rgba(239, 68, 68, 0.1); 
  color: var(--red); 
  border: 1px solid rgba(239, 68, 68, 0.2); 
}}

.badge-razon.time_exit   {{ 
  background: rgba(245, 158, 11, 0.1); 
  color: var(--amber); 
  border: 1px solid rgba(245, 158, 11, 0.2); 
}}

.badge-razon.inactiva    {{ 
  background: rgba(100, 116, 139, 0.1); 
  color: var(--gray); 
  border: 1px solid rgba(100, 116, 139, 0.2); 
}}

.txt-truncate {{ 
  max-width: 300px; 
  white-space: nowrap; 
  overflow: hidden; 
  text-overflow: ellipsis; 
}}

.no-data {{ 
  text-align: center; 
  color: var(--muted); 
  padding: 2.5rem; 
  font-size: 0.85rem; 
  font-style: italic; 
}}

.btn-ver-cot-tabla {{
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0.25rem;
  border-radius: 6px;
  transition: all 0.15s;
}}

.btn-ver-cot-tabla:hover {{
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}}

/* Breakdown Outputs */
.breakdown-grid {{ 
  display: grid; 
  grid-template-columns: 1fr 1fr; 
  gap: 0.75rem; 
}}

.bk-item {{ 
  background: rgba(8, 12, 20, 0.45); 
  border: 1px solid var(--border); 
  border-radius: 10px; 
  padding: 0.85rem; 
  display: flex; 
  align-items: center; 
  gap: 0.75rem; 
}}

.bk-dot {{ 
  width: 8px; 
  height: 8px; 
  border-radius: 50%; 
  flex-shrink: 0; 
}}

.bk-label {{ 
  font-family: var(--font-mono); 
  font-size: 0.72rem; 
  color: var(--muted); 
}}

.bk-count {{ 
  font-family: var(--font-mono); 
  font-size: 1.2rem; 
  font-weight: 700; 
  margin-top: 0.15rem; 
}}

/* Modal Overlay & content */
.modal-overlay {{
  position: fixed;
  inset: 0;
  background: rgba(3, 7, 18, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
}}

.modal-overlay.open {{
  opacity: 1;
  visibility: visible;
}}

.modal-content {{
  background: #0f1626;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  width: 90%;
  max-width: 640px;
  padding: 2.25rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(139, 92, 246, 0.15);
  transform: scale(0.95);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  max-height: 85vh;
  overflow-y: auto;
}}

.modal-overlay.open .modal-content {{
  transform: scale(1);
}}

.modal-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  border-bottom: none;
  padding-bottom: 0;
}}

.modal-header h3 {{
  font-size: 1.35rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.4;
  padding-right: 1.5rem;
  font-family: var(--font-head);
}}

.modal-close-btn {{
  background: none;
  border: none;
  color: var(--muted);
  font-size: 1.8rem;
  cursor: pointer;
  line-height: 1;
  transition: color 0.15s;
}}

.modal-close-btn:hover {{
  color: #fff;
}}

.modal-status-bar {{
  display: flex;
  gap: 1.25rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}}

.modal-grid-specs {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
  margin-bottom: 1.75rem;
}}

.spec-item {{
  background: rgba(8, 12, 20, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.03);
  padding: 0.8rem 1rem;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
}}

.spec-label {{
  font-size: 0.65rem;
  color: var(--muted);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}

.spec-value {{
  font-size: 0.95rem;
  font-weight: 700;
  font-family: var(--font-mono);
  margin-top: 0.25rem;
  color: #fff;
}}

.modal-reasoning-section {{
  background: rgba(139, 92, 246, 0.03);
  border: 1px solid rgba(139, 92, 246, 0.1);
  padding: 1.25rem 1.5rem;
  border-radius: 14px;
}}

.modal-reasoning-section h4 {{
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a78bfa;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-head);
}}

.modal-reasoning-section p {{
  font-size: 0.9rem;
  line-height: 1.6;
  color: #cbd5e1;
}}
</style>
</head>
<body>

<header>
  <div class="brand">
    <h1>🤖 Agente Híbrido <span>v3</span></h1>
    <p>CLOB · Bayesian · Volatility · LLM News Signal</p>
  </div>
  <div class="header-meta-container">
    <div class="status-badge">
      <span class="status-dot pulse"></span>
      <span class="status-text">OPERATIVO</span>
    </div>
    <div class="meta-header">
      <div>Ciclos de Operación: <strong>#{n_ciclos}</strong></div>
      <div>Última corrida local: <strong>{ultima_corrida}</strong></div>
      <div>Posiciones abiertas: <strong>{n_abiertas}</strong></div>
    </div>
  </div>
</header>

<!-- Métricas principales -->
<div class="grid-metricas">
  <div class="card-m" style="--accent: var(--primary); --accent-hover: #c084fc; --accent-glow: rgba(139, 92, 246, 0.25)">
    <h4>Capital Disponible</h4>
    <div class="val">${capital_actual:,.2f}</div>
    <div class="sub">USDC · inicial {capital_inicial:,.0f}</div>
  </div>
  <div class="card-m" style="--accent: #38bdf8; --accent-hover: #7dd3fc; --accent-glow: rgba(56, 189, 248, 0.25)">
    <h4>Valor Neto Flotante</h4>
    <div class="val {equity_clase}">${net_equity:,.2f}</div>
    <div class="sub">Capital + P&L temporal</div>
  </div>
  <div class="card-m" style="--accent: #6366f1; --accent-hover: #818cf8; --accent-glow: rgba(99, 102, 241, 0.25)">
    <h4>USDC En Riesgo</h4>
    <div class="val" style="color:#818cf8">${capital_en_riesgo:,.2f}</div>
    <div class="sub">En {n_abiertas} posiciones</div>
  </div>
  <div class="card-m" style="--accent: {'var(--green)' if pnl_total>=0 else 'var(--red)'}; --accent-hover: {'#34d399' if pnl_total>=0 else '#f87171'}; --accent-glow: {'rgba(16, 185, 129, 0.25)' if pnl_total>=0 else 'rgba(239, 68, 68, 0.25)'}">
    <h4>P&L Realizado</h4>
    <div class="val {pnl_clase_total}">{pnl_signo}${pnl_total:,.2f}</div>
    <div class="sub">{total_cerradas} ops cerradas</div>
  </div>
  <div class="card-m" style="--accent: {'var(--green)' if pnl_flotante_total>=0 else 'var(--red)'}; --accent-hover: {'#34d399' if pnl_flotante_total>=0 else '#f87171'}; --accent-glow: {'rgba(16, 185, 129, 0.25)' if pnl_flotante_total>=0 else 'rgba(239, 68, 68, 0.25)'}">
    <h4>P&L Temp Flotante</h4>
    <div class="val {pnl_flotante_clase}">{pnl_flotante_signo}${pnl_flotante_total:,.2f}</div>
    <div class="sub">De posiciones activas</div>
  </div>
  <div class="card-m" style="--accent: #f59e0b; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.25)">
    <h4>Win Rate</h4>
    <div class="val" style="color:#fbbf24">{win_rate:.1%}</div>
    <div class="sub">{total_ganadas}W · {total_perdidas}L</div>
  </div>
  <div class="card-m" style="--accent: {'var(--green)' if profit_factor_clase=='positive' else 'var(--red)'}; --accent-hover: {'#34d399' if profit_factor_clase=='positive' else '#f87171'}; --accent-glow: {'rgba(16, 185, 129, 0.25)' if profit_factor_clase=='positive' else 'rgba(239, 68, 68, 0.25)'}">
    <h4>Profit Factor</h4>
    <div class="val" style="color:{'var(--green)' if profit_factor_clase=='positive' else 'var(--red)'}">{profit_factor_str}</div>
    <div class="sub">Retorno ganancias/pérdidas</div>
  </div>
  <div class="card-m" style="--accent: var(--green); --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.25)">
    <h4>Avg Win / Loss</h4>
    <div class="val" style="font-size:1.15rem;display:flex;align-items:center;gap:0.4rem;height:2.7rem">
      <span class="positive">+${avg_win:.2f}</span>
      <span style="color:var(--muted);font-weight:400">/</span>
      <span class="negative">${avg_loss:.2f}</span>
    </div>
    <div class="sub">Promedio ganadores/perdedores</div>
  </div>
</div>

<!-- Curva + Distribución -->
<div class="row-2">
  <div class="panel">
    <h3>Curva P&L Acumulado</h3>
    <div style="height:320px;position:relative">
      <canvas id="chartPnl"></canvas>
    </div>
  </div>
  <div class="panel">
    <h3>Distribución de Salidas</h3>
    <div style="height:190px;position:relative;margin-bottom:1.25rem">
      <canvas id="chartDonut"></canvas>
    </div>
    <div class="breakdown-grid">
      <div class="bk-item"><div class="bk-dot" style="background:var(--green)"></div><div><div class="bk-label">TP / Early</div><div class="bk-count" style="color:var(--green)">{n_tp}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--red)"></div><div><div class="bk-label">Stop Loss</div><div class="bk-count" style="color:var(--red)">{n_sl}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--amber)"></div><div><div class="bk-label">Time Exit</div><div class="bk-count" style="color:var(--amber)">{n_time}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--gray)"></div><div><div class="bk-label">Inactiva</div><div class="bk-count" style="color:var(--gray)">{n_inactiva}</div></div></div>
    </div>
    
    <!-- Distribución YES/NO -->
    <div class="panel-distribucion">
      <h3>Distribución de Señales</h3>
      <div class="yes-no-bar-container">
        <div class="yes-no-bar-yes" style="width: {pct_yes}%;"></div>
      </div>
      <div class="yes-no-labels">
        <span class="positive">YES: {yes_count} ({pct_yes:.0%})</span>
        <span class="negative">NO: {no_count} ({pct_no:.0%})</span>
      </div>
    </div>
  </div>
</div>

<!-- Posiciones abiertas -->
<div class="panel" style="margin-bottom:2.5rem">
  <h3>Posiciones Activas ({n_abiertas})</h3>
  <div class="abiertas-wrapper">
    {ops_abiertas_html}
  </div>
</div>

<!-- Historial -->
<div class="panel">
  <h3>Historial de Operaciones</h3>
  
  <div class="filter-bar">
    <div class="search-box">
      <input type="text" id="tablaBuscar" placeholder="Buscar mercado..." onkeyup="filtrarTabla()">
    </div>
    <div class="filter-tabs">
      <button class="filter-tab active" onclick="setFiltro('todos')">Todos</button>
      <button class="filter-tab" onclick="setFiltro('ganancias')">Ganados</button>
      <button class="filter-tab" onclick="setFiltro('perdidas')">Perdidos</button>
      <button class="filter-tab" onclick="setFiltro('tp')">TP / Early</button>
      <button class="filter-tab" onclick="setFiltro('sl')">Stop Loss</button>
      <button class="filter-tab" onclick="setFiltro('time')">Time Exit</button>
      <button class="filter-tab" onclick="setFiltro('inactiva')">Inactivas</button>
    </div>
  </div>

  <div class="tabla-contenedor">
    <table>
      <thead><tr>
        <th>Fecha Cierre</th><th>Mercado</th><th>Señal</th>
        <th>Monto</th><th>P&L</th><th>Salida</th><th>Detalle</th>
      </tr></thead>
      <tbody id="tablaCerradosBody">{ops_cerradas_html}</tbody>
    </table>
  </div>
</div>

<!-- Modal Overlay -->
<div id="modalDetalle" class="modal-overlay">
  <div class="modal-content">
    <div class="modal-header">
      <h3 id="modalTitulo">Detalle de Operación</h3>
      <button class="modal-close-btn" onclick="cerrarModal()">&times;</button>
    </div>
    <div class="modal-status-bar">
      <span id="modalBadge" class="badge-senal"></span>
      <span id="modalMonto" class="monto-orden"></span>
    </div>
    <div class="modal-grid-specs">
      <div class="spec-item"><span class="spec-label">Confianza IA</span><span id="modalConfianza" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Edge Neto</span><span id="modalEdge" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Entrada</span><span id="modalPrecioEnt" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Cierre/Actual</span><span id="modalPrecioAct" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Resultado / P&L</span><span id="modalPnl" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Tipo Salida</span><span id="modalSalida" class="spec-value"></span></div>
    </div>
    <div class="modal-reasoning-section">
      <h4>🧠 Razonamiento CoT Completo</h4>
      <p id="modalRazonamientoText"></p>
    </div>
  </div>
</div>

<script>
// Modal Functions
function abrirModal(datos) {{
  const modal = document.getElementById('modalDetalle');
  document.getElementById('modalTitulo').textContent = datos.pregunta;
  
  // Set badge signal
  const badge = document.getElementById('modalBadge');
  badge.textContent = datos.senal;
  badge.className = 'badge-senal ' + datos.senal.toLowerCase().replace(' ', '-');
  
  document.getElementById('modalMonto').textContent = datos.monto;
  document.getElementById('modalConfianza').textContent = datos.confianza;
  document.getElementById('modalEdge').textContent = datos.edge;
  document.getElementById('modalPrecioEnt').textContent = datos.precio_entrada;
  document.getElementById('modalPrecioAct').textContent = datos.precio_actual;
  
  const pnlEl = document.getElementById('modalPnl');
  pnlEl.textContent = datos.pnl;
  pnlEl.className = 'spec-value ' + (datos.pnl_raw >= 0 ? 'positive' : 'negative');
  
  const salidaEl = document.getElementById('modalSalida');
  salidaEl.textContent = datos.salida;
  salidaEl.className = 'spec-value ' + datos.salida.toLowerCase();
  
  document.getElementById('modalRazonamientoText').textContent = datos.razonamiento || 'Sin razonamiento registrado.';
  
  modal.classList.add('open');
}}

function abrirModalDesdeBtn(btn) {{
  const datos = JSON.parse(btn.getAttribute('data-info'));
  abrirModal(datos);
}}

function cerrarModal() {{
  document.getElementById('modalDetalle').classList.remove('open');
}}

document.getElementById('modalDetalle').addEventListener('click', function(e) {{
  if (e.target === this) cerrarModal();
}});

// Filtering and Search Functions
let filtroActual = 'todos';

function setFiltro(tipo) {{
  filtroActual = tipo;
  document.querySelectorAll('.filter-tab').forEach(tab => tab.classList.remove('active'));
  event.target.classList.add('active');
  filtrarTabla();
}}

function filtrarTabla() {{
  const query = document.getElementById('tablaBuscar').value.toLowerCase();
  const rows = document.querySelectorAll('#tablaCerradosBody tr');
  
  rows.forEach(row => {{
    const nameCell = row.querySelector('.txt-truncate');
    if (!nameCell) return;
    
    const text = nameCell.textContent.toLowerCase();
    const badgeRazonEl = row.querySelector('.badge-razon');
    const razon = badgeRazonEl ? badgeRazonEl.textContent.trim().toUpperCase() : 'EXIT';
    
    const pnlEl = row.querySelector('.bold-pnl');
    const pnl = pnlEl ? parseFloat(pnlEl.textContent.replace('$', '').replace('+', '').replace(/,/g, '')) : 0.0;
    
    let matchesQuery = text.includes(query);
    let matchesFiltro = false;
    
    if (filtroActual === 'todos') {{
      matchesFiltro = true;
    }} else if (filtroActual === 'ganancias') {{
      matchesFiltro = pnl >= 0;
    }} else if (filtroActual === 'perdidas') {{
      matchesFiltro = pnl < 0;
    }} else if (filtroActual === 'tp') {{
      matchesFiltro = razon === 'TAKE_PROFIT' || razon === 'EARLY_EXIT';
    }} else if (filtroActual === 'sl') {{
      matchesFiltro = razon === 'STOP_LOSS';
    }} else if (filtroActual === 'time') {{
      matchesFiltro = razon === 'TIME_EXIT';
    }} else if (filtroActual === 'inactiva') {{
      matchesFiltro = razon === 'INACTIVA';
    }}
    
    if (matchesQuery && matchesFiltro) {{
      row.style.display = '';
    }} else {{
      row.style.display = 'none';
    }}
  }});
}}

// Chart.js Configurations
const ctxPnl = document.getElementById('chartPnl').getContext('2d');
const gradPnl = ctxPnl.createLinearGradient(0, 0, 0, 320);
gradPnl.addColorStop(0, 'rgba(139, 92, 246, 0.35)');
gradPnl.addColorStop(1, 'rgba(139, 92, 246, 0.0)');

new Chart(ctxPnl, {{
  type: 'line',
  data: {{
    labels: {json.dumps(fechas_rendimiento)},
    datasets: [{{
      data: {json.dumps(valores_rendimiento)},
      borderColor: '#8b5cf6',
      backgroundColor: gradPnl,
      borderWidth: 3,
      fill: true,
      tension: 0.35,
      pointBackgroundColor: '#a78bfa',
      pointHoverBackgroundColor: '#ffffff',
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBorderColor: 'transparent'
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ 
      legend: {{ display: false }} 
    }},
    scales: {{
      x: {{ 
        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}, 
        ticks: {{ color: '#94a3b8', font: {{ size: 10, family: 'JetBrains Mono' }} }} 
      }},
      y: {{ 
        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}, 
        ticks: {{ color: '#94a3b8', font: {{ size: 10, family: 'JetBrains Mono' }} }} 
      }}
    }}
  }}
}});

// Donut Chart
new Chart(document.getElementById('chartDonut').getContext('2d'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(donut_labels)},
    datasets: [{{
      data: {json.dumps(donut_data)},
      backgroundColor: {json.dumps(donut_colors)},
      borderWidth: 0,
      hoverOffset: 6
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    cutout: '78%',
    plugins: {{ 
      legend: {{ display: false }} 
    }}
  }}
}});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(ARCHIVO_OUTPUT), exist_ok=True)
    with open(ARCHIVO_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Dashboard generado con éxito en: {ARCHIVO_OUTPUT}")
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ Copia de Dashboard guardada en: index.html")

if __name__ == "__main__":
    generar_dashboard()
