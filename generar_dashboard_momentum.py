"""
generar_dashboard_hibrido.py
Recupera el estilo visual profesional original, adaptado a los datos y métricas
del Agente Híbrido (LLM Confianza, Win Rate, etc).
"""

import pandas as pd, json, os
from datetime import datetime

# Rutas para el Híbrido
ARCHIVO_LIBRO  = "datos_polymarket/paper_trading/libro_hibrido.csv"
ARCHIVO_ESTADO = "datos_polymarket/paper_trading/estado_hibrido.json"
ARCHIVO_OUT    = "datos_polymarket/dashboard_hibrido.html"

def cargar():
    e = {"capital_inicial":1000,"capital_actual":1000,"capital_en_riesgo":0,
         "n_ciclos":0,"ultima_corrida":"—","n_tp":0,"n_sl":0,"n_time":0,
         "mercados_rastreados":0}
    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO) as f: e.update(json.load(f))
        except: pass
    try:
        df = pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()
    except:
        df = pd.DataFrame()
    return e, df

def categoria(pregunta):
    q = str(pregunta).lower()
    if any(k in q for k in ["nba","nfl","nhl","stanley","lakers","knicks","spurs","cavaliers","pistons","celtics","warriors","heat"]): return "🏀", "#6366f1", "NBA/NHL"
    if any(k in q for k in ["premier","epl","arsenal","chelsea","city","united","liverpool","tottenham","la liga","serie a","bundesliga"]): return "⚽", "#0ea5e9", "Fútbol"
    if any(k in q for k in ["president","senate","house","republican","democrat","election","primary","vote","congress","colombian","trump","biden"]): return "🗳️", "#f59e0b", "Política"
    if any(k in q for k in ["bitcoin","btc","ethereum","eth","crypto","token","defi"]): return "₿", "#f97316", "Crypto"
    if any(k in q for k in ["album","song","artist","rihanna","carti","taylor","bond","movie","gta","game"]): return "🎭", "#ec4899", "Cultura"
    return "📊", "#94a3b8", "Otro"

def build_pnl_series(df):
    if df.empty or "CERRADA" not in df["estado"].astype(str).str.upper().values:
        return ["00:00"], ["Inicio"], [0.0]
    ce = df[df["estado"].astype(str).str.upper()=="CERRADA"].copy()
    ce["pnl_realizado"] = pd.to_numeric(ce["pnl_realizado"],errors="coerce").fillna(0)
    
    ce["fecha_cierre_real"] = ce["fecha_cierre_real"].fillna("").astype(str)
    ce["fecha_orden"] = ce["fecha_cierre_real"].replace("", pd.NA)
    if "fecha_entrada_dt" in ce.columns:
        ce["fecha_orden"] = ce["fecha_orden"].fillna(ce["fecha_entrada_dt"])
    else:
        ce["fecha_orden"] = ce["fecha_orden"].fillna("2026-01-01 00:00")
    
    ce = ce.sort_values("fecha_orden")
    ce["pnl_acum"] = ce["pnl_realizado"].cumsum()
    
    labels_short = ce["fecha_orden"].str[11:16].tolist()
    labels_full  = ce["fecha_orden"].str[:16].tolist()
    values = [0.0] + ce["pnl_acum"].round(2).tolist()
    labels_short = ["00:00"] + labels_short
    labels_full  = ["Inicio"] + labels_full
    return labels_short, labels_full, values

def horas_abiertas(fecha_str):
    try:
        dt = datetime.strptime(str(fecha_str)[:16], "%Y-%m-%d %H:%M")
        h  = (datetime.now() - dt).total_seconds() / 3600
        return abs(h)
    except: return 0

def progress_bar(pct):
    # Como el agente híbrido usa SL/TP dinámicos, usamos una referencia visual estándar
    tp = 0.09
    sl = -0.07
    rango = tp - sl
    pos   = max(0, min(1, (pct - sl) / rango)) * 100
    col   = "#10b981" if pct >= tp*0.7 else "#ef4444" if pct <= sl*0.7 else "#f59e0b"
    return f'''<div style="position:relative;height:4px;background:#1e293b;border-radius:2px;margin:10px 0 6px">
  <div style="position:absolute;left:0;top:-4px;width:2px;height:12px;background:#ef4444;border-radius:1px;opacity:.8"></div>
  <div style="position:absolute;right:0;top:-4px;width:2px;height:12px;background:#10b981;border-radius:1px;opacity:.8"></div>
  <div style="position:absolute;left:{pos:.1f}%;top:-6px;width:16px;height:16px;background:{col};
              border-radius:50%;transform:translateX(-50%);border:2px solid #060b14;
              box-shadow:0 0 10px {col}bb"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:10px">
  <span style="color:#f87171;font-weight:600">Referencia SL</span>
  <span style="color:{col};font-weight:700;font-size:12px">{pct:+.1%}</span>
  <span style="color:#34d399;font-weight:600">Referencia TP</span>
</div>'''

def generar():
    e, df = cargar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    capital_inicial = float(e.get("capital_inicial", 1000))
    if not df.empty:
        df['estado_upper'] = df['estado'].astype(str).str.upper()
        ab = df[df["estado_upper"]=="ABIERTA"]
        ce = df[df["estado_upper"]=="CERRADA"]
    else:
        ab = pd.DataFrame()
        ce = pd.DataFrame()

    capital_en_riesgo = float(ab["monto_usdc"].sum()) if (not ab.empty and "monto_usdc" in ab.columns) else 0.0
    pnl_neto_absoluto = float(ce["pnl_realizado"].sum()) if (not ce.empty and "pnl_realizado" in ce.columns) else 0.0
    patrimonio_neto   = capital_inicial + pnl_neto_absoluto
    ret_neto          = (pnl_neto_absoluto / capital_inicial) * 100 if capital_inicial > 0 else 0

    wins = (ce["pnl_realizado"]>0).sum() if not ce.empty else 0
    wr   = wins/len(ce) if not ce.empty and len(ce)>0 else 0

    labels_s, labels_f, values = build_pnl_series(df)
    chart_color = "#8b5cf6" # Color púrpura moderno para el Híbrido
    
    max_pico = max(values) if values else 0
    current_val = values[-1] if values else 0
    drawdown = current_val - max_pico

    # Tarjetas de Posiciones Abiertas
    cards_html = ""
    if ab.empty:
        cards_html = '<div style="text-align:center;color:#475569;padding:32px;font-size:13px">Sin posiciones abiertas</div>'
    else:
        for _, p in ab.sort_values("fecha_entrada_dt", na_position='last').iterrows():
            try:
                pte   = float(p.get("precio_token_entrada", 0))
                pta   = float(p.get("precio_actual", 0))
                if p.get("señal", "") != "COMPRAR YES": pta = 1 - pta
                pct   = (pta-pte)/pte if pte>0 else 0
                pnl_nr = float(p.get("monto_usdc", 0)) * pct
                col   = "#10b981" if pct>=0 else "#ef4444"
                bar   = progress_bar(pct)
            except:
                pct=0; pnl_nr=0; col="#64748b"; bar=progress_bar(0)

            h_ab  = horas_abiertas(p.get("fecha_entrada_dt",""))
            h_col = "#ef4444" if h_ab >= 3*0.8 else "#f59e0b" if h_ab >= 3*0.5 else "#64748b"
            icon, _, cat_name = categoria(str(p.get("pregunta","")))
            sc = "#10b981" if "YES" in str(p.get("señal","")) else "#ef4444"
            
            conf = float(p.get("llm_confianza", 0))

            cards_html += f'''<div style="background:#060b14;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;margin-bottom:10px; transition: all 0.2s ease;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
    <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:0">
      <span style="font-size:14px">{icon}</span>
      <span style="font-size:13px;color:#cbd5e1;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{str(p.get('pregunta',''))[:58]}</span>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <span style="color:{sc};font-weight:700;font-size:12px">{p.get('señal','')}</span>
      <span style="color:#8b5cf6;font-size:11px;margin-left:6px;font-weight:600">🤖 Conf {conf:.2f}</span>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
    <div style="font-size:11px;color:#64748b">
      Entrada <span style="color:#94a3b8">{float(p.get('precio_entrada',0)):.2f}</span> ·
      Actual <span style="color:#94a3b8">{float(p.get('precio_actual',0)):.2f}</span> ·
      Monto <span style="color:#94a3b8">${float(p.get('monto_usdc',0)):.0f}</span> ·
      <span style="color:{h_col};font-weight:600">{h_ab:.1f}h</span>
    </div>
    <span style="color:{col};font-weight:700;font-size:13px">{pnl_nr:+.2f}$</span>
  </div>
  {bar}
</div>'''

    exit_html = ""
    for t, label, ac in [("TAKE_PROFIT","TP Dinámico ✅","#10b981"),
                          ("STOP_LOSS","SL Dinámico ❌","#ef4444"),
                          ("TIME_EXIT","⏱ Tiempo / Evento","#3b82f6")]:
        if ce.empty: continue
        s = ce[ce["razon_cierre"]==t]
        if s.empty: continue
        n=len(s); w=(s["pnl_realizado"]>0).sum(); p_sum=s["pnl_realizado"].sum()
        wr_line = f'<div style="font-size:12px;color:#94a3b8;margin:4px 0">{w/n:.0%} ganadoras</div>'

        exit_html += f'''<div style="background:#060b14;border:1px solid #1e293b;border-radius:10px;padding:16px;text-align:center">
  <div style="color:{ac};font-weight:700;font-size:13px;margin-bottom:8px">{label}</div>
  <div style="font-size:30px;font-weight:800;color:#f1f5f9;font-family:'Space Mono',monospace">{n}</div>
  {wr_line}
  <div style="font-size:15px;font-weight:700;color:{'#10b981' if p_sum>=0 else '#ef4444'}">{p_sum:+.2f}$</div>
</div>'''

    hist_html = ""
    if not ce.empty:
        for _, p in ce.sort_values("fecha_cierre_real",ascending=False, na_position='last').head(20).iterrows():
            pnl = float(p.get("pnl_realizado",0)) if pd.notna(p.get("pnl_realizado")) else 0
            col = "#10b981" if pnl>=0 else "#ef4444"
            r   = str(p.get("razon_cierre",""))
            bm  = {"TAKE_PROFIT":"background:#14532d;color:#86efac", "STOP_LOSS":"background:#450a0a;color:#fca5a5", "TIME_EXIT":"background:#1e3a5f;color:#93c5fd"}
            lm  = {"TAKE_PROFIT":"TP ✅","STOP_LOSS":"SL ❌","TIME_EXIT":"⏱"}
            bs  = bm.get(r,"background:#1e293b;color:#64748b")
            bl  = lm.get(r, r or "—")
            icon, _, cat_name = categoria(str(p.get("pregunta","")))
            fecha = str(p.get("fecha_cierre_real",""))[:16]

            hist_html += f'''<div style="display:grid;grid-template-columns:20px 1fr 80px 70px 65px;
gap:10px;align-items:center;padding:8px 4px;border-bottom:1px solid #0d1829; transition: background 0.2s;">
  <span title="{cat_name}" style="font-size:13px">{icon}</span>
  <div style="font-size:12px;color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{str(p.get('pregunta',''))[:50]}</div>
  <span style="font-size:10px;color:#475569;text-align:center">{fecha[5:]}</span>
  <span style="padding:2px 7px;border-radius:99px;font-size:10px;font-weight:700;text-align:center;{bs}">{bl}</span>
  <span style="color:{col};font-weight:700;font-size:13px;text-align:right;font-family:'Space Mono',monospace">{pnl:+.2f}$</span>
</div>'''

    html = f'''<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Agente Híbrido · Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:'DM Sans',sans-serif; background:#060b14; color:#e2e8f0; padding:28px; min-height:100vh }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
@keyframes fadeUp {{ from{{opacity:0;transform:translateY(10px)}} to{{opacity:1;transform:translateY(0)}} }}
.fade {{ animation:fadeUp .35s ease both }}
.f2 {{ animation-delay:.05s }} .f3 {{ animation-delay:.1s }} .f4 {{ animation-delay:.15s }}
.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:22px }}
.kpi {{ background:#0d1829; border:1px solid #1e293b; border-radius:12px; padding:18px; position:relative; overflow:hidden }}
.kpi::after {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:var(--a,#1e293b) }}
.kpi.g {{ --a:#10b981 }} .kpi.r {{ --a:#ef4444 }} .kpi.b {{ --a:#8b5cf6 }}
.kl {{ font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; font-weight:600 }}
.kv {{ font-family:'Space Mono',monospace; font-size:24px; font-weight:700; line-height:1 }}
.ks {{ font-size:12px; color:#64748b; margin-top:6px }}
.card {{ background:#0d1829; border:1px solid #1e293b; border-radius:12px; padding:20px; margin-bottom:18px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
.ct {{ font-size:11px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px; display:flex; align-items:center; gap:8px }}
.badge {{ display:inline-block; padding:2px 9px; border-radius:99px; font-size:10px; font-weight:700 }}
.grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px }}
.live {{ display:inline-flex; align-items:center; gap:5px; font-size:11px; color:#8b5cf6; font-weight:600 }}
.dot {{ width:6px; height:6px; border-radius:50%; background:#8b5cf6; animation:pulse 2s infinite }}
@media(max-width:900px) {{ .kpis{{grid-template-columns:repeat(2,1fr)}} .grid3{{grid-template-columns:1fr}} }}
</style></head>
<body>

<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px" class="fade">
  <div>
    <div style="font-size:11px;color:#334155;font-family:'Space Mono',monospace;letter-spacing:.1em;margin-bottom:6px">POLYMARKET · AUTOMATED AGENT</div>
    <h1 style="font-size:30px;font-weight:700;letter-spacing:-1px;color:#f1f5f9">
      Agente <span style="color:#8b5cf6">Híbrido (LLM)</span>
    </h1>
    <div style="font-size:12px;color:#64748b;margin-top:5px">Ciclo #{e.get('n_ciclos',0)} · Insights de IA integrados</div>
  </div>
  <div style="text-align:right;font-size:12px;color:#64748b;line-height:2">
    <div class="live"><span class="dot"></span> Auto-refresh 5min</div>
    <div>Último ciclo: <span style="color:#94a3b8">{e.get('ultima_corrida','—')}</span></div>
    <div>Calibración Dinámica de Volatilidad</div>
  </div>
</div>

<div class="kpis fade f2">
  <div class="kpi {'g' if pnl_neto_absoluto >= 0 else 'r'}">
    <div class="kl">Patrimonio Neto (Equity)</div>
    <div class="kv" style="color:#f1f5f9">{patrimonio_neto:,.2f}$</div>
    <div class="ks" style="color:{'#10b981' if pnl_neto_absoluto >= 0 else '#ef4444'}">
        {pnl_neto_absoluto:+.2f}$ ({ret_neto:+.2f}%)
    </div>
  </div>

  <div class="kpi">
    <div class="kl">Capital Líquido</div>
    <div class="kv" style="color:#f1f5f9">{(capital_inicial + pnl_neto_absoluto - capital_en_riesgo):,.2f}$</div>
    <div class="ks">En riesgo: <span style="color:#f59e0b">{capital_en_riesgo:,.2f}$</span></div>
  </div>

  <div class="kpi">
    <div class="kl">P&L Realizado</div>
    <div class="kv" style="color:{'#10b981' if pnl_neto_absoluto >= 0 else '#ef4444'}">{pnl_neto_absoluto:+.2f}$</div>
    <div class="ks">Trades cerrados</div>
  </div>

  <div class="kpi">
    <div class="kl">Drawdown (Pico)</div>
    <div class="kv" style="color:#ef4444">{drawdown:+.2f}$</div>
    <div class="ks">Caída desde máximo</div>
  </div>
  
  <div class="kpi b">
    <div class="kl">Win Rate</div>
    <div class="kv" style="color:#f1f5f9">{wr:.0%}</div>
    <div class="ks">{wins} de {len(ce)} cerradas</div>
  </div>
</div>

<div class="card fade f3">
  <div class="ct">📈 Evolución del P&L Acumulado (Equity Curve)</div>
  <div style="height:170px;position:relative"><canvas id="chart"></canvas></div>
</div>

<div class="card fade f3">
  <div class="ct">
    📌 Posiciones Abiertas
    <span class="badge" style="background:#4c1d95;color:#ddd6fe">{len(ab)}</span>
  </div>
  {cards_html}
</div>

<div class="card fade f4">
  <div class="ct">📊 Rendimiento por tipo de salida</div>
  <div class="grid3">{exit_html}</div>
</div>

<div class="card fade f4">
  <div class="ct">
    🕐 Últimas operaciones
    <span class="badge" style="background:#14532d;color:#86efac">{len(ce)}</span>
  </div>
  <div style="display:grid;grid-template-columns:20px 1fr 80px 70px 65px;gap:10px;
              padding:0 4px 8px;border-bottom:1px solid #1e293b;margin-bottom:4px">
    <span></span>
    <span style="font-size:10px;color:#475569;font-weight:600;text-transform:uppercase;letter-spacing:.06em">Mercado</span>
    <span style="font-size:10px;color:#475569;font-weight:600;text-transform:uppercase;letter-spacing:.06em;text-align:center">Fecha</span>
    <span style="font-size:10px;color:#475569;font-weight:600;text-transform:uppercase;letter-spacing:.06em;text-align:center">Cierre</span>
    <span style="font-size:10px;color:#475569;font-weight:600;text-transform:uppercase;letter-spacing:.06em;text-align:right">P&L</span>
  </div>
  {hist_html}
</div>

<div style="text-align:center;color:#1e293b;font-size:10px;margin-top:16px;font-family:'Space Mono',monospace;letter-spacing:.1em">
  AGENTE HÍBRIDO (LLM) · {ahora}
</div>

<script>
const labelsShort = {json.dumps(labels_s)};
const labelsFull  = {json.dumps(labels_f)};
const values      = {json.dumps(values)};

if (values.length > 0) {{
  const ctx = document.getElementById('chart').getContext('2d');
  const g   = ctx.createLinearGradient(0, 0, 0, 170);
  g.addColorStop(0, '{chart_color}55');
  g.addColorStop(1, '{chart_color}00');

  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: labelsShort,
      datasets: [{{
        data: values,
        borderColor: '{chart_color}',
        backgroundColor: g,
        borderWidth: 2,
        pointRadius: values.map((_,i) => i===values.length-1 ? 6 : 0),
        pointHoverRadius: 5,
        pointBackgroundColor: '{chart_color}',
        fill: true,
        tension: 0.4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#0d1829',
          borderColor: '#1e293b',
          borderWidth: 1,
          titleColor: '#94a3b8',
          bodyColor: '#f1f5f9',
          padding: 10,
          callbacks: {{
            title: items => labelsFull[items[0].dataIndex],
            label: c => ' P&L: $' + c.parsed.y.toFixed(2)
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#475569', font: {{ family: 'Space Mono', size: 9 }}, maxRotation: 0, maxTicksLimit: 10 }},
          grid: {{ color: '#0d1829' }},
          border: {{ color: '#1e293b' }}
        }},
        y: {{
          grid: {{ color: '#0d1829' }},
          border: {{ color: '#1e293b' }},
          ticks: {{ color: '#475569', font: {{ family: 'Space Mono', size: 10 }}, callback: v => '$' + v.toFixed(1) }}
        }}
      }}
    }}
  }});
}} else {{
  document.getElementById('chart').parentElement.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;height:170px;color:#334155;font-size:12px">Sin datos aún</div>';
}}
</script>
</body></html>'''

    os.makedirs(os.path.dirname(ARCHIVO_OUT), exist_ok=True)
    with open(ARCHIVO_OUT, "w", encoding="utf-8") as f: f.write(html)
    print(f"✅ Dashboard Híbrido Profesional Generado → {ARCHIVO_OUT}")

if __name__ == "__main__":
    generar()
