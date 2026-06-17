import pandas as pd
import json
import os
import html
from datetime import datetime

# Rutas de archivos
FILE_LIBRO_HIBRIDO = "datos_polymarket/paper_trading/libro_hibrido.csv"
FILE_ESTADO_HIBRIDO = "datos_polymarket/paper_trading/estado_hibrido.json"

FILE_LIBRO_COPY = "datos_polymarket/copy_trading/libro_copy.csv"
FILE_ESTADO_COPY = "datos_polymarket/copy_trading/estado_copy.json"

FILE_OUTPUT = "datos_polymarket/dashboard_comparativo.html"
FILE_INDEX = "index.html" # Para GitHub Pages

def generar_dashboard():
    # ──────────────────────────────────────────────────────────────
    # 1. CARGAR DATOS - AGENTE HÍBRIDO
    # ──────────────────────────────────────────────────────────────
    cap_inicial_hib = 1000.0; cap_actual_hib = 1000.0
    cap_riesgo_hib = 0.0; n_ciclos_hib = 0; ultima_corrida_hib = "—"
    n_tp_hib = 0; n_sl_hib = 0; n_time_hib = 0

    if os.path.exists(FILE_ESTADO_HIBRIDO):
        try:
            with open(FILE_ESTADO_HIBRIDO) as f:
                est = json.load(f)
                cap_inicial_hib = float(est.get("capital_inicial", cap_inicial_hib))
                cap_actual_hib  = float(est.get("capital_actual", cap_actual_hib))
                cap_riesgo_hib  = float(est.get("capital_en_riesgo", cap_riesgo_hib))
                n_ciclos_hib    = est.get("n_ciclos", 0)
                ultima_corrida_hib = est.get("ultima_corrida", "—")
                n_tp_hib        = est.get("n_tp", 0)
                n_sl_hib        = est.get("n_sl", 0)
                n_time_hib      = est.get("n_time", 0)
        except Exception as e:
            print(f"Error estado híbrido: {e}")

    df_hib = pd.read_csv(FILE_LIBRO_HIBRIDO) if os.path.exists(FILE_LIBRO_HIBRIDO) else pd.DataFrame()
    
    # ──────────────────────────────────────────────────────────────
    # 2. CARGAR DATOS - AGENTE COPY-TRADER
    # ──────────────────────────────────────────────────────────────
    cap_inicial_copy = 1000.0; cap_actual_copy = 1000.0
    cap_riesgo_copy = 0.0; n_ciclos_copy = 0; ultima_corrida_copy = "—"
    n_tp_copy = 0; n_sl_copy = 0

    if os.path.exists(FILE_ESTADO_COPY):
        try:
            with open(FILE_ESTADO_COPY) as f:
                est = json.load(f)
                cap_inicial_copy = float(est.get("capital_inicial", cap_inicial_copy))
                cap_actual_copy  = float(est.get("capital_actual", cap_actual_copy))
                cap_riesgo_copy  = float(est.get("capital_en_riesgo", cap_riesgo_copy))
                n_ciclos_copy    = est.get("n_ciclos", 0)
                ultima_corrida_copy = est.get("ultima_corrida", "—")
                n_tp_copy        = est.get("n_tp", 0)
                n_sl_copy        = est.get("n_sl", 0)
        except Exception as e:
            print(f"Error estado copy-trader: {e}")

    df_copy = pd.read_csv(FILE_LIBRO_COPY) if os.path.exists(FILE_LIBRO_COPY) else pd.DataFrame()

    # ──────────────────────────────────────────────────────────────
    # 3. PROCESAR HISTORIAL - HÍBRIDO
    # ──────────────────────────────────────────────────────────────
    pnl_total_hib = 0.0; pnl_flotante_hib = 0.0; win_rate_hib = 0.0
    ops_abiertas_hib_html = ""; ops_cerradas_hib_html = ""
    historia_pnl_hib = []
    n_abiertas = 0

    if not df_hib.empty:
        df_hib['estado'] = df_hib['estado'].astype(str).str.strip().str.upper()
        
        # Abiertas
        abiertas_hib = df_hib[df_hib['estado'] == 'ABIERTA']
        n_abiertas = len(abiertas_hib)
        for _, p in abiertas_hib.iterrows():
            tp_real = float(p.get('tp_dinamico', 0.09))
            sl_real = float(p.get('sl_dinamico', -0.07))
            confianza = float(p.get('llm_confianza', 0.50))
            edge = float(p.get('llm_edge', 0.03))
            if edge > 1.0: edge /= 100.0
            monto = float(p.get('monto_usdc', 20.0))
            pte = float(p.get('precio_token_entrada', 0.5))
            pta = float(p.get('precio_actual', pte))
            pnl_flot = (pta - pte) * (monto / pte) if pte > 0 else 0.0
            pnl_flotante_hib += pnl_flot

            # HTML Abiertas Hibrido
            pnl_clase = "positive" if pnl_flot >= 0 else "negative"
            ops_abiertas_hib_html += f"""
            <div class="position-row">
                <div class="pos-info">
                    <span class="badge badge-hybrid">YES</span>
                    <span class="pos-title">{p['pregunta']}</span>
                </div>
                <div class="pos-meta">
                    <div><span class="meta-label">Entrada</span><span class="meta-val">${pte:.3f}</span></div>
                    <div><span class="meta-label">Actual</span><span class="meta-val">${pta:.3f}</span></div>
                    <div><span class="meta-label">Monto</span><span class="meta-val">${monto:.2f}</span></div>
                    <div><span class="meta-label">P&L</span><span class="meta-val {pnl_clase}">{"+" if pnl_flot>=0 else ""}${pnl_flot:.2f}</span></div>
                </div>
            </div>"""
        
        # Cerradas
        cerradas_hib = df_hib[df_hib['estado'] == 'CERRADA'].copy()
        if not cerradas_hib.empty:
            cerradas_hib['fecha_dt'] = pd.to_datetime(cerradas_hib['fecha_cierre_real'], errors='coerce')
            cerradas_hib = cerradas_hib.sort_values('fecha_dt')
            
            pnl_acum = 0.0
            for _, p in cerradas_hib.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                historia_pnl_hib.append({"fecha": fecha, "pnl": round(pnl_acum, 2)})
                
                clase_row = "positive" if pnl_op >= 0 else "negative"
                ops_cerradas_hib_html += f"""
                <tr>
                    <td>{fecha}</td>
                    <td class="txt-truncate">{p['pregunta']}</td>
                    <td>{p.get('señal', '—')}</td>
                    <td>${float(p.get('monto_usdc', 0)):.2f}</td>
                    <td class="{clase_row} bold">${pnl_op:+.2f}</td>
                    <td><span class="badge-reason {str(p.get('razon_cierre')).lower()}">{p.get('razon_cierre', 'EXIT')}</span></td>
                </tr>"""
            
            pnl_total_hib = pnl_acum
            total_operativas = len(cerradas_hib[cerradas_hib['razon_cierre'] != 'INACTIVA'])
            wins = len(cerradas_hib[cerradas_hib['pnl_realizado'] > 0])
            win_rate_hib = (wins / total_operativas * 100) if total_operativas > 0 else 0.0

    if not ops_abiertas_hib_html:
        ops_abiertas_hib_html = '<div class="no-data">Sin posiciones activas.</div>'
    if not ops_cerradas_hib_html:
        ops_cerradas_hib_html = '<tr><td colspan="6" class="no-data">Sin historial de operaciones.</td></tr>'

    # ──────────────────────────────────────────────────────────────
    # 4. PROCESAR HISTORIAL - COPY-TRADER
    # ──────────────────────────────────────────────────────────────
    pnl_total_copy = 0.0; pnl_flotante_copy = 0.0; win_rate_copy = 0.0
    ops_abiertas_copy_html = ""; ops_cerradas_copy_html = ""
    historia_pnl_copy = []
    abiertas_copy = pd.DataFrame()

    if not df_copy.empty:
        df_copy['estado'] = df_copy['estado'].astype(str).str.strip().str.upper()

        # Abiertas
        abiertas_copy = df_copy[df_copy['estado'] == 'ABIERTA']
        for _, p in abiertas_copy.iterrows():
            monto = float(p.get('monto_usdc', 20.0))
            pte = float(p.get('precio_token_entrada', 0.5))
            pta = float(p.get('precio_actual', pte))
            pnl_flot = (pta - pte) * (monto / pte) if pte > 0 else 0.0
            pnl_flotante_copy += pnl_flot

            # HTML Abiertas Copy-trader
            pnl_clase = "positive" if pnl_flot >= 0 else "negative"
            ops_abiertas_copy_html += f"""
            <div class="position-row">
                <div class="pos-info">
                    <span class="badge badge-copy">{p.get('outcome', 'YES')}</span>
                    <span class="pos-title">{p['pregunta']}</span>
                </div>
                <div class="pos-meta">
                    <div><span class="meta-label">Entrada</span><span class="meta-val">${pte:.3f}</span></div>
                    <div><span class="meta-label">Actual</span><span class="meta-val">${pta:.3f}</span></div>
                    <div><span class="meta-label">Monto</span><span class="meta-val">${monto:.2f}</span></div>
                    <div><span class="meta-label">P&L</span><span class="meta-val {pnl_clase}">{"+" if pnl_flot>=0 else ""}${pnl_flot:.2f}</span></div>
                </div>
                <div style="font-size:0.7rem; color:var(--muted); margin-top:0.4rem; font-family:var(--font-mono)">
                    Copiando a: {str(p.get('target_wallet'))[:15]}...
                </div>
            </div>"""

        # Cerradas
        cerradas_copy = df_copy[df_copy['estado'] == 'CERRADA'].copy()
        if not cerradas_copy.empty:
            cerradas_copy['fecha_dt'] = pd.to_datetime(cerradas_copy['fecha_cierre_real'], errors='coerce')
            cerradas_copy = cerradas_copy.sort_values('fecha_dt')

            pnl_acum = 0.0
            for _, p in cerradas_copy.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                historia_pnl_copy.append({"fecha": fecha, "pnl": round(pnl_acum, 2)})

                clase_row = "positive" if pnl_op >= 0 else "negative"
                ops_cerradas_copy_html += f"""
                <tr>
                    <td>{fecha}</td>
                    <td class="txt-truncate">{p['pregunta']}</td>
                    <td>{p.get('outcome', '—')}</td>
                    <td>${float(p.get('monto_usdc', 0)):.2f}</td>
                    <td class="{clase_row} bold">${pnl_op:+.2f}</td>
                    <td><span class="badge-reason {str(p.get('razon_cierre')).lower()}">{p.get('razon_cierre', 'EXIT')}</span></td>
                </tr>"""

            pnl_total_copy = pnl_acum
            total_operativas = len(cerradas_copy)
            wins = len(cerradas_copy[cerradas_copy['pnl_realizado'] > 0])
            win_rate_copy = (wins / total_operativas * 100) if total_operativas > 0 else 0.0

    if not ops_abiertas_copy_html:
        ops_abiertas_copy_html = '<div class="no-data">Sin posiciones activas.</div>'
    if not ops_cerradas_copy_html:
        ops_cerradas_copy_html = '<tr><td colspan="6" class="no-data">Sin historial de operaciones.</td></tr>'

    # ──────────────────────────────────────────────────────────────
    # 5. PREPARAR DATOS DEL GRÁFICO COMBINADO
    # ──────────────────────────────────────────────────────────────
    # Unificamos fechas de ambos historiales para graficarlos lado a lado
    # Combinamos las entradas
    datas_dict = {}
    for h in historia_pnl_hib:
        f = h["fecha"][:10]
        datas_dict.setdefault(f, {})["hib"] = h["pnl"]
    for c in historia_pnl_copy:
        f = c["fecha"][:10]
        datas_dict.setdefault(f, {})["copy"] = c["pnl"]

    fechas_ordenadas = sorted(datas_dict.keys())
    
    chart_labels = []
    chart_data_hib = []
    chart_data_copy = []
    
    p_last_hib = 0.0
    p_last_copy = 0.0
    
    for f in fechas_ordenadas:
        val = datas_dict[f]
        if "hib" in val: p_last_hib = val["hib"]
        if "copy" in val: p_last_copy = val["copy"]
        chart_labels.append(f)
        chart_data_hib.append(p_last_hib)
        chart_data_copy.append(p_last_copy)

    # Si no hay datos, inicializar valores
    if not chart_labels:
        chart_labels = [datetime.now().strftime("%Y-%m-%d")]
        chart_data_hib = [0.0]
        chart_data_copy = [0.0]

    # Cuentas totales (Net account value)
    equity_hib = cap_actual_hib + pnl_flotante_hib
    equity_copy = cap_actual_copy + pnl_flotante_copy
    pnl_net_pct_hib = ((equity_hib - cap_inicial_hib) / cap_inicial_hib) * 100
    pnl_net_pct_copy = ((equity_copy - cap_inicial_copy) / cap_inicial_copy) * 100

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Polymarket — Panel Comparativo de Estrategias</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
  --bg: #020617; 
  --surface: rgba(15, 23, 42, 0.45); 
  --surface-card: rgba(22, 34, 57, 0.25);
  --border: rgba(255, 255, 255, 0.06);
  --primary-hib: #8b5cf6; 
  --primary-hib-glow: rgba(139, 92, 246, 0.22);
  --primary-copy: #0284c7;
  --primary-copy-glow: rgba(2, 132, 199, 0.22);
  --green: #10b981; 
  --red: #ef4444; 
  --muted: #94a3b8;
  --text: #f8fafc;
  --font-head: 'Outfit', sans-serif; 
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{ 
  background: var(--bg); 
  color: var(--text); 
  font-family: var(--font-body); 
  padding: 2rem; 
  min-height: 100vh;
  position: relative;
}}

body::before {{ 
  content: ''; 
  position: fixed; 
  inset: 0; 
  background: radial-gradient(circle at 10% 12%, rgba(139, 92, 246, 0.08) 0%, transparent 45%),
              radial-gradient(circle at 90% 80%, rgba(2, 132, 199, 0.08) 0%, transparent 45%); 
  pointer-events: none; 
  z-index: -1;
}}

header {{ 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 2rem; 
  padding-bottom: 1.5rem; 
  border-bottom: 1px solid var(--border); 
}}

.brand h1 {{ 
  font-size: 2.25rem; 
  font-weight: 800; 
  letter-spacing: -0.04em; 
  font-family: var(--font-head);
}}

.brand h1 span.hib {{ color: var(--primary-hib); }}
.brand h1 span.vs {{ color: var(--muted); font-size: 1.5rem; margin: 0 0.5rem; }}
.brand h1 span.copy {{ color: var(--primary-copy); }}

.brand p {{ 
  color: var(--muted); 
  font-size: 0.8rem; 
  font-family: var(--font-mono); 
  letter-spacing: 0.05em; 
}}

.meta-header {{ 
  text-align: right; 
  font-family: var(--font-mono); 
  font-size: 0.8rem; 
  color: var(--muted); 
}}

.grid-estrategias {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 2rem;
}}

@media(max-width: 900px) {{
  .grid-estrategias {{ grid-template-columns: 1fr; }}
}}

.col-panel {{
  background: var(--surface);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.5rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  position: relative;
}}

.col-panel.hib::after {{
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: var(--primary-hib); border-radius: 0 0 18px 18px;
}}

.col-panel.copy::after {{
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: var(--primary-copy); border-radius: 0 0 18px 18px;
}}

.col-panel h2 {{
  font-family: var(--font-head);
  font-size: 1.5rem;
  margin-bottom: 1.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}

.grid-kpis {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}}

.kpi-card {{
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
}}

.kpi-label {{
  font-size: 0.68rem;
  text-transform: uppercase;
  color: var(--muted);
  font-family: var(--font-mono);
}}

.kpi-val {{
  font-size: 1.4rem;
  font-weight: 700;
  margin-top: 0.25rem;
  font-family: var(--font-mono);
}}

.kpi-sub {{
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.15rem;
  font-family: var(--font-mono);
}}

.section-title {{
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 0.75rem;
  display: flex;
  justify-content: space-between;
}}

.positions-container {{
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
  padding-right: 0.25rem;
}}

.position-row {{
  background: rgba(8, 12, 20, 0.45);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem 1rem;
}}

.pos-info {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}}

.badge {{
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 5px;
  font-family: var(--font-mono);
}}

.badge-hybrid {{ background: rgba(139, 92, 246, 0.12); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.25); }}
.badge-copy {{ background: rgba(2, 132, 199, 0.12); color: #38bdf8; border: 1px solid rgba(2, 132, 199, 0.25); }}

.pos-title {{
  font-weight: 600;
  font-size: 0.88rem;
  color: #f1f5f9;
}}

.pos-meta {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}}

.meta-label {{
  font-size: 0.6rem;
  color: var(--muted);
  display: block;
}}

.meta-val {{
  font-size: 0.8rem;
  font-weight: 600;
  font-family: var(--font-mono);
}}

/* Chart Section */
.chart-panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}}

/* Tables */
.table-panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.5rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  margin-bottom: 2rem;
}}

.tabs-headers {{
  display: flex;
  gap: 1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.75rem;
  margin-bottom: 1rem;
}}

.tab-btn {{
  background: none;
  border: none;
  color: var(--muted);
  font-family: var(--font-head);
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  transition: all 0.2s;
  position: relative;
}}

.tab-btn.active {{
  color: #fff;
}}

.tab-btn.active::after {{
  content: ''; position: absolute; bottom: -0.85rem; left: 0; right: 0; height: 2px; background: var(--primary-hib);
}}

.tab-btn.active.copy-tab::after {{
  background: var(--primary-copy);
}}

.table-wrapper {{
  width: 100%;
  overflow-x: auto;
  max-height: 400px;
  border-radius: 10px;
  border: 1px solid var(--border);
}}

table {{
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
}}

th {{
  background: rgba(8, 12, 20, 0.75);
  padding: 0.85rem 1rem;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  text-transform: uppercase;
}}

td {{
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border);
  color: #e2e8f0;
}}

tr:hover td {{
  background: rgba(255,255,255,0.01);
}}

.txt-truncate {{
  max-width: 380px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.badge-reason {{
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-family: var(--font-mono);
}}

.badge-reason.take_profit, .badge-reason.early_exit, .badge-reason.target_sell {{
  background: rgba(16, 185, 129, 0.1); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.2);
}}

.badge-reason.stop_loss {{
  background: rgba(239, 68, 68, 0.1); color: var(--red); border: 1px solid rgba(239, 68, 68, 0.2);
}}

.badge-reason.time_exit, .badge-reason.resolved_exit, .badge-reason.failsafe_sync_exit {{
  background: rgba(245, 158, 11, 0.1); color: var(--amber, #f59e0b); border: 1px solid rgba(245, 158, 11, 0.2);
}}

.badge-reason.inactiva {{
  background: rgba(100, 116, 139, 0.1); color: var(--muted); border: 1px solid rgba(100, 116, 139, 0.2);
}}

.positive {{ color: var(--green); }}
.negative {{ color: var(--red); }}
.bold {{ font-weight: 700; }}
.no-data {{ text-align:center; padding: 2rem; color: var(--muted); font-family:var(--font-mono); font-size:0.8rem; }}

</style>
</head>
<body>

<header>
  <div class="brand">
    <h1><span class="hib">Hybrid AI</span><span class="vs">vs</span><span class="copy">Copy-Trader</span></h1>
    <p>Comparación en vivo de estrategias algorítmicas | Polymarket</p>
  </div>
  <div class="meta-header">
    Actualizado: <strong>{ultima_corrida_hib}</strong><br>
    Ciclos: Híbrido: <strong>{n_ciclos_hib}</strong> | Copy-Trader: <strong>{n_ciclos_copy}</strong>
  </div>
</header>

<!-- KPIs Grid -->
<div class="grid-estrategias">
  <!-- HIBRIDO -->
  <div class="col-panel hib">
    <h2>🤖 Agente Híbrido (IA + Vol)</h2>
    <div class="grid-kpis">
      <div class="kpi-card">
        <div class="kpi-label">Capital Total</div>
        <div class="kpi-val">${equity_hib:,.2f}</div>
        <div class="kpi-sub {('positive' if pnl_net_pct_hib>=0 else 'negative')}">{pnl_net_pct_hib:+.2f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Win Rate Op.</div>
        <div class="kpi-val">{win_rate_hib:.1f}%</div>
        <div class="kpi-sub">excl. inactivos</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Cierres (TP/SL/Time)</div>
        <div class="kpi-val">{n_tp_hib}/{n_sl_hib}/{n_time_hib}</div>
        <div class="kpi-sub">Total: {n_tp_hib+n_sl_hib+n_time_hib}</div>
      </div>
    </div>
    <div class="section-title">
      <span>Posiciones Abiertas</span>
      <span>{n_abiertas} Activas</span>
    </div>
    <div class="positions-container">
      {ops_abiertas_hib_html}
    </div>
  </div>

  <!-- COPY TRADER -->
  <div class="col-panel copy">
    <h2>🎯 Agente Copy-Trader (Whales)</h2>
    <div class="grid-kpis">
      <div class="kpi-card">
        <div class="kpi-label">Capital Total</div>
        <div class="kpi-val">${equity_copy:,.2f}</div>
        <div class="kpi-sub {('positive' if pnl_net_pct_copy>=0 else 'negative')}">{pnl_net_pct_copy:+.2f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Win Rate Op.</div>
        <div class="kpi-val">{win_rate_copy:.1f}%</div>
        <div class="kpi-sub">excl. inactivos</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Cierres (Ganados/Perdidos)</div>
        <div class="kpi-val">{n_tp_copy}/{n_sl_copy}</div>
        <div class="kpi-sub">Total: {n_tp_copy+n_sl_copy}</div>
      </div>
    </div>
    <div class="section-title">
      <span>Posiciones Abiertas</span>
      <span>{len(abiertas_copy)} Activas</span>
    </div>
    <div class="positions-container">
      {ops_abiertas_copy_html}
    </div>
  </div>
</div>

<!-- Chart Panel -->
<div class="chart-panel">
  <div class="section-title" style="margin-bottom: 1.25rem;">📈 Comparativa de Curva de P&L Realizado (USD)</div>
  <div style="height: 350px; width: 100%;">
    <canvas id="pnlChart"></canvas>
  </div>
</div>

<!-- Tables Panel -->
<div class="table-panel">
  <div class="tabs-headers">
    <button class="tab-btn active" id="btn-hib" onclick="switchTab('hib')">Historial Híbrido</button>
    <button class="tab-btn copy-tab" id="btn-copy" onclick="switchTab('copy')">Historial Copy-Trading</button>
  </div>
  
  <div id="tab-hib-content">
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Fecha Cierre</th>
            <th>Mercado</th>
            <th>Señal</th>
            <th>Monto (USDC)</th>
            <th>PnL Realizado</th>
            <th>Razón</th>
          </tr>
        </thead>
        <tbody>
          {ops_cerradas_hib_html}
        </tbody>
      </table>
    </div>
  </div>

  <div id="tab-copy-content" style="display: none;">
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Fecha Cierre</th>
            <th>Mercado</th>
            <th>Resultado</th>
            <th>Monto (USDC)</th>
            <th>PnL Realizado</th>
            <th>Razón</th>
          </tr>
        </thead>
        <tbody>
          {ops_cerradas_copy_html}
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
// Lógica de Tabs
function switchTab(type) {{
  if(type === 'hib') {{
    document.getElementById('btn-hib').classList.add('active');
    document.getElementById('btn-copy').classList.remove('active');
    document.getElementById('tab-hib-content').style.display = 'block';
    document.getElementById('tab-copy-content').style.display = 'none';
  }} else {{
    document.getElementById('btn-hib').classList.remove('active');
    document.getElementById('btn-copy').classList.add('active');
    document.getElementById('tab-hib-content').style.display = 'none';
    document.getElementById('tab-copy-content').style.display = 'block';
  }}
}}

// Lógica de Chart.js
const ctx = document.getElementById('pnlChart').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: {json.dumps(chart_labels)},
    datasets: [
      {{
        label: 'Agente Híbrido',
        data: {json.dumps(chart_data_hib)},
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.05)',
        fill: true,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#8b5cf6'
      }},
      {{
        label: 'Agente Copy-Trader',
        data: {json.dumps(chart_data_copy)},
        borderColor: '#0284c7',
        backgroundColor: 'rgba(2, 132, 199, 0.05)',
        fill: true,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#0284c7'
      }}
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{
        labels: {{
          color: '#f8fafc',
          font: {{ family: 'Inter', size: 12, weight: '500' }}
        }}
      }},
      tooltip: {{
        backgroundColor: '#0f172a',
        titleFont: {{ family: 'Outfit', size: 13, weight: '700' }},
        bodyFont: {{ family: 'Inter', size: 12 }},
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1
      }}
    }},
    scales: {{
      x: {{
        grid: {{ color: 'rgba(255,255,255,0.03)' }},
        ticks: {{ color: '#94a3b8', font: {{ family: 'JetBrains Mono', size: 10 }} }}
      }},
      y: {{
        grid: {{ color: 'rgba(255,255,255,0.03)' }},
        ticks: {{ 
          color: '#94a3b8', 
          font: {{ family: 'JetBrains Mono', size: 10 }},
          callback: function(value) {{ return '$' + value; }}
        }}
      }}
    }}
  }}
}});
</script>

</body>
</html>"""

    # Guardar en las dos ubicaciones
    with open(FILE_OUTPUT, "w") as f:
        f.write(html_content)
    with open(FILE_INDEX, "w") as f:
        f.write(html_content)
    print(f"Dashboard comparativo generado con éxito en {FILE_OUTPUT} e {FILE_INDEX}")

if __name__ == "__main__":
    generar_dashboard()
