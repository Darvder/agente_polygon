import pandas as pd
import json
import os
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
    ultima_corrida = datetime.now().strftime("%Y-%m-%d %H:%M")
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
    pnl_total = 0.0; win_rate = 0.0
    total_ganadas = 0; total_perdidas = 0; total_cerradas = 0
    n_inactiva = 0; n_tp = 0; n_sl = 0; n_time = 0
    avg_win = 0.0; avg_loss = 0.0
    fechas_rendimiento = []; valores_rendimiento = []
    pnl_acumulado = 0.0
    n_abiertas = 0

    if not df.empty:
        df['estado'] = df['estado'].astype(str).str.strip().str.upper()
        abiertas = df[df['estado'] == 'ABIERTA']
        n_abiertas = len(abiertas)

        if abiertas.empty:
            ops_abiertas_html = '<div class="no-data">Sin posiciones abiertas. Buscando oportunidades...</div>'
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
                horas_max = p.get('horas_max', 10)
                razon_ia  = str(p.get('razonamiento', '—'))[:80]

                if "YES" in senal.upper():
                    pnl_flotante = (precio_act - precio_ent) * (monto / precio_ent) if precio_ent > 0 else 0
                else:
                    pnl_flotante = ((1.0 - precio_act) - precio_ent) * (monto / precio_ent) if precio_ent > 0 else 0

                pnl_clase = "positive" if pnl_flotante >= 0 else "negative"
                pct_burbuja = calcular_posicion_barra(precio_ent, precio_act, tp_real, sl_real)

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
                        <div class="meta-item" style="grid-column: span 3"><span class="meta-label">🧠 IA</span><span class="meta-value" style="font-size:0.78rem;font-weight:400;color:#9ca3af">{razon_ia}</span></div>
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
                ops_cerradas_html += f"""
                <tr class="{clase_row}">
                    <td>{fecha_cierre[:16]}</td>
                    <td class="txt-truncate" title="{p['pregunta']}">{str(p['pregunta'])[:48]}…</td>
                    <td><span class="badge-tabla">{p.get('señal','—')}</span></td>
                    <td>${float(p.get('monto_usdc',0)):,.2f}</td>
                    <td class="bold-pnl">{"+" if pnl_op>=0 else ""}${pnl_op:,.2f}</td>
                    <td><span class="badge-razon {razon.lower()}">{razon}</span></td>
                </tr>"""

            win_rate = total_ganadas / total_cerradas if total_cerradas > 0 else 0.0
            avg_win  = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0

    if not ops_cerradas_html:
        ops_cerradas_html = '<tr><td colspan="6" class="no-data">Sin operaciones cerradas aún.</td></tr>'
    if not fechas_rendimiento:
        fechas_rendimiento = [datetime.now().strftime("%Y-%m-%d")]
        valores_rendimiento = [0.0]

    pnl_clase_total = "positive" if pnl_total >= 0 else "negative"
    pnl_signo = "+" if pnl_total > 0 else ""

    # Donut data
    donut_labels = ['TP / Early', 'Stop Loss', 'Time Exit', 'Inactiva']
    donut_data   = [n_tp, n_sl, n_time, n_inactiva]
    donut_colors = ['#10b981', '#ef4444', '#f59e0b', '#6b7280']

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agente Híbrido — Panel de Control</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
  --bg: #080c12; --surface: #0f1724; --border: #1a2640;
  --purple: #7c3aed; --purple-light: #a78bfa;
  --green: #10b981; --red: #ef4444; --amber: #f59e0b; --gray: #6b7280;
  --text: #e2e8f0; --muted: #64748b;
  --font-head: 'Syne', sans-serif; --font-mono: 'JetBrains Mono', monospace;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:var(--font-head); padding:2rem; min-height:100vh; }}
body::before {{ content:''; position:fixed; inset:0; background:radial-gradient(ellipse 80% 50% at 20% 0%, rgba(124,58,237,0.07) 0%, transparent 60%); pointer-events:none; }}

/* Header */
header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:2.5rem; padding-bottom:1.5rem; border-bottom:1px solid var(--border); }}
.brand h1 {{ font-size:1.6rem; font-weight:800; letter-spacing:-0.03em; }}
.brand h1 span {{ color:var(--purple-light); }}
.brand p {{ color:var(--muted); font-size:0.8rem; margin-top:0.3rem; font-family:var(--font-mono); }}
.meta-header {{ text-align:right; font-family:var(--font-mono); font-size:0.78rem; color:var(--muted); line-height:1.8; }}
.meta-header strong {{ color:var(--purple-light); }}

/* Metric cards */
.grid-metricas {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; margin-bottom:2rem; }}
.card-m {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:1.25rem 1.5rem; position:relative; overflow:hidden; }}
.card-m::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:2px; background:var(--accent,var(--border)); }}
.card-m h4 {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted); font-family:var(--font-mono); }}
.card-m .val {{ font-size:1.7rem; font-weight:700; margin-top:0.4rem; font-family:var(--font-mono); }}
.card-m .sub {{ font-size:0.72rem; color:var(--muted); margin-top:0.25rem; font-family:var(--font-mono); }}
.positive {{ color:var(--green); }} .negative {{ color:var(--red); }}

/* Layout */
.row-2 {{ display:grid; grid-template-columns:1.6fr 1fr; gap:1.5rem; margin-bottom:1.5rem; }}
.row-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:1.5rem; margin-bottom:1.5rem; }}
@media(max-width:1100px) {{ .row-2,.row-3 {{ grid-template-columns:1fr; }} }}

/* Panels */
.panel {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.5rem; }}
.panel h3 {{ font-size:0.8rem; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted); font-family:var(--font-mono); margin-bottom:1.25rem; display:flex; align-items:center; gap:0.5rem; }}
.panel h3::before {{ content:''; display:inline-block; width:3px; height:12px; background:var(--purple); border-radius:2px; }}

/* Open positions */
.abiertas-wrapper {{ display:flex; flex-direction:column; gap:1rem; max-height:600px; overflow-y:auto; }}
.card-orden {{ background:#0d1929; border:1px solid var(--border); border-radius:10px; padding:1.1rem; transition:border-color 0.2s; }}
.card-orden:hover {{ border-color:#2d4a6e; }}
.card-orden-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem; }}
.badge-senal {{ font-size:0.68rem; font-weight:700; padding:0.2rem 0.55rem; border-radius:5px; text-transform:uppercase; font-family:var(--font-mono); }}
.badge-senal.comprar-yes {{ background:rgba(16,185,129,0.15); color:var(--green); }}
.badge-senal.comprar-no  {{ background:rgba(239,68,68,0.15);  color:var(--red); }}
.monto-orden {{ font-size:0.85rem; font-weight:600; font-family:var(--font-mono); }}
.pregunta-titulo {{ font-size:0.88rem; font-weight:600; margin-bottom:0.75rem; line-height:1.4; }}
.metadatos-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:0.6rem; background:rgba(8,12,18,0.5); padding:0.65rem; border-radius:7px; margin-bottom:0.9rem; }}
.meta-item {{ display:flex; flex-direction:column; }}
.meta-label {{ font-size:0.65rem; color:var(--muted); font-family:var(--font-mono); }}
.meta-value {{ font-size:0.82rem; font-weight:600; margin-top:0.1rem; font-family:var(--font-mono); }}
.riesgo-labels {{ display:flex; justify-content:space-between; font-size:0.68rem; margin-bottom:0.35rem; font-family:var(--font-mono); }}
.label-sl {{ color:var(--red); }} .label-tp {{ color:var(--green); }}
.riesgo-barra-bg {{ height:6px; background:linear-gradient(to right,var(--red) 0%,#1a2640 30%,#1a2640 70%,var(--green) 100%); border-radius:3px; position:relative; margin-bottom:0.35rem; }}
.riesgo-burbuja {{ width:12px; height:12px; background:#fff; border:2px solid var(--purple-light); border-radius:50%; position:absolute; top:50%; transform:translate(-50%,-50%); box-shadow:0 0 6px rgba(167,139,250,0.7); }}
.riesgo-precios {{ display:flex; justify-content:space-between; font-size:0.65rem; color:var(--muted); font-family:var(--font-mono); }}

/* Table */
.tabla-contenedor {{ width:100%; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:0.83rem; font-family:var(--font-mono); }}
th {{ background:rgba(8,12,18,0.7); color:var(--muted); font-weight:600; padding:0.65rem 0.9rem; border-bottom:1px solid var(--border); text-transform:uppercase; font-size:0.65rem; letter-spacing:0.08em; }}
td {{ padding:0.7rem 0.9rem; border-bottom:1px solid var(--border); color:#94a3b8; }}
tr:hover td {{ background:rgba(26,38,64,0.3); }}
.row-ganancia .bold-pnl {{ color:var(--green); font-weight:700; }}
.row-perdida  .bold-pnl {{ color:var(--red); font-weight:700; }}
.badge-tabla {{ background:#1a2640; padding:0.15rem 0.4rem; border-radius:4px; font-size:0.68rem; font-weight:600; }}
.badge-razon {{ font-size:0.65rem; font-weight:700; padding:0.15rem 0.45rem; border-radius:4px; }}
.badge-razon.take_profit,.badge-razon.early_exit {{ background:rgba(16,185,129,0.15); color:var(--green); }}
.badge-razon.stop_loss   {{ background:rgba(239,68,68,0.15);  color:var(--red); }}
.badge-razon.time_exit   {{ background:rgba(245,158,11,0.15); color:var(--amber); }}
.badge-razon.inactiva    {{ background:rgba(107,114,128,0.15);color:var(--gray); }}
.txt-truncate {{ max-width:260px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.no-data {{ text-align:center; color:var(--muted); padding:2rem; font-size:0.85rem; font-style:italic; }}

/* Breakdown */
.breakdown-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; }}
.bk-item {{ background:rgba(8,12,18,0.5); border-radius:8px; padding:0.85rem; display:flex; align-items:center; gap:0.75rem; }}
.bk-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
.bk-label {{ font-family:var(--font-mono); font-size:0.72rem; color:var(--muted); }}
.bk-count {{ font-family:var(--font-mono); font-size:1.2rem; font-weight:700; }}
</style>
</head>
<body>

<header>
  <div class="brand">
    <h1>🤖 Agente Híbrido <span>v3</span></h1>
    <p>CLOB · Bayesian · Volatility · LLM News Signal</p>
  </div>
  <div class="meta-header">
    <div>Ciclos: <strong>#{n_ciclos}</strong></div>
    <div>Última corrida: <strong>{ultima_corrida}</strong></div>
    <div>Posiciones abiertas: <strong>{n_abiertas}</strong></div>
  </div>
</header>

<!-- Métricas principales -->
<div class="grid-metricas">
  <div class="card-m" style="--accent:var(--purple)">
    <h4>Capital Disponible</h4>
    <div class="val">${capital_actual:,.2f}</div>
    <div class="sub">USDC · inicial ${capital_inicial:,.0f}</div>
  </div>
  <div class="card-m" style="--accent:#a78bfa">
    <h4>En Riesgo</h4>
    <div class="val" style="color:var(--purple-light)">${capital_en_riesgo:,.2f}</div>
    <div class="sub">USDC · {n_abiertas} posiciones</div>
  </div>
  <div class="card-m" style="--accent:{'var(--green)' if pnl_total>=0 else 'var(--red)'}">
    <h4>P&L Realizado</h4>
    <div class="val {pnl_clase_total}">{pnl_signo}${pnl_total:,.2f}</div>
    <div class="sub">{total_cerradas} ops cerradas</div>
  </div>
  <div class="card-m" style="--accent:#38bdf8">
    <h4>Win Rate</h4>
    <div class="val" style="color:#38bdf8">{win_rate:.1%}</div>
    <div class="sub">{total_ganadas}W · {total_perdidas}L</div>
  </div>
  <div class="card-m" style="--accent:var(--green)">
    <h4>Avg Win</h4>
    <div class="val positive">+${avg_win:.2f}</div>
    <div class="sub">por operación ganadora</div>
  </div>
  <div class="card-m" style="--accent:var(--red)">
    <h4>Avg Loss</h4>
    <div class="val negative">${avg_loss:.2f}</div>
    <div class="sub">por operación perdedora</div>
  </div>
</div>

<!-- Curva + Posiciones abiertas -->
<div class="row-2">
  <div class="panel">
    <h3>Curva P&L Acumulado</h3>
    <div style="height:300px;position:relative">
      <canvas id="chartPnl"></canvas>
    </div>
  </div>
  <div class="panel">
    <h3>Distribución de Salidas</h3>
    <div style="height:200px;position:relative;margin-bottom:1rem">
      <canvas id="chartDonut"></canvas>
    </div>
    <div class="breakdown-grid">
      <div class="bk-item"><div class="bk-dot" style="background:var(--green)"></div><div><div class="bk-label">TP / Early</div><div class="bk-count" style="color:var(--green)">{n_tp}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--red)"></div><div><div class="bk-label">Stop Loss</div><div class="bk-count" style="color:var(--red)">{n_sl}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--amber)"></div><div><div class="bk-label">Time Exit</div><div class="bk-count" style="color:var(--amber)">{n_time}</div></div></div>
      <div class="bk-item"><div class="bk-dot" style="background:var(--gray)"></div><div><div class="bk-label">Inactiva</div><div class="bk-count" style="color:var(--gray)">{n_inactiva}</div></div></div>
    </div>
  </div>
</div>

<!-- Posiciones abiertas -->
<div class="panel" style="margin-bottom:1.5rem">
  <h3>Posiciones Activas ({n_abiertas})</h3>
  <div class="abiertas-wrapper" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1rem">
    {ops_abiertas_html}
  </div>
</div>

<!-- Historial -->
<div class="panel">
  <h3>Historial de Operaciones</h3>
  <div class="tabla-contenedor">
    <table>
      <thead><tr>
        <th>Fecha Cierre</th><th>Mercado</th><th>Señal</th>
        <th>Monto</th><th>P&L</th><th>Salida</th>
      </tr></thead>
      <tbody>{ops_cerradas_html}</tbody>
    </table>
  </div>
</div>

<script>
// P&L Chart
new Chart(document.getElementById('chartPnl').getContext('2d'), {{
  type:'line',
  data:{{
    labels:{json.dumps(fechas_rendimiento)},
    datasets:[{{
      data:{json.dumps(valores_rendimiento)},
      borderColor:'#7c3aed', backgroundColor:'rgba(124,58,237,0.07)',
      borderWidth:2, fill:true, tension:0.3,
      pointBackgroundColor:'#a78bfa', pointRadius:3
    }}]
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{display:false}}}},
    scales:{{
      x:{{grid:{{color:'#1a2640'}}, ticks:{{color:'#64748b',font:{{size:9,family:'JetBrains Mono'}}}}}},
      y:{{grid:{{color:'#1a2640'}}, ticks:{{color:'#64748b',font:{{size:10,family:'JetBrains Mono'}}}}}}
    }}
  }}
}});
// Donut
new Chart(document.getElementById('chartDonut').getContext('2d'), {{
  type:'doughnut',
  data:{{
    labels:{json.dumps(donut_labels)},
    datasets:[{{
      data:{json.dumps(donut_data)},
      backgroundColor:{json.dumps(donut_colors)},
      borderWidth:0, hoverOffset:4
    }}]
  }},
  options:{{
    responsive:true, maintainAspectRatio:false, cutout:'70%',
    plugins:{{legend:{{display:false}}}}
  }}
}});
</script>
</body>
</html>"""

    with open(ARCHIVO_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Dashboard generado: {ARCHIVO_OUTPUT}")

if __name__ == "__main__":
    generar_dashboard()
