"""
generar_dashboard_momentum.py
Dashboard avanzado con:
  1. Gráfico P&L acumulado en el tiempo
  2. Barras de progreso TP/SL por posición abierta
  3. Auto-refresh cada 5 minutos
"""

import pandas as pd, json, os
from datetime import datetime

ARCHIVO_LIBRO  = "datos_polymarket/paper_trading/libro_momentum.csv"
ARCHIVO_ESTADO = "datos_polymarket/paper_trading/estado_momentum.json"
ARCHIVO_OUT    = "datos_polymarket/dashboard_momentum.html"

def cargar():
    e = {"capital_inicial":1000,"capital_actual":1000,"capital_en_riesgo":0,
         "n_ciclos":0,"ultima_corrida":"—","n_tp":0,"n_sl":0,"n_time":0,
         "mercados_rastreados":0}
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f: e.update(json.load(f))
    df = pd.read_csv(ARCHIVO_LIBRO) if os.path.exists(ARCHIVO_LIBRO) else pd.DataFrame()
    return e, df

def build_pnl_series(df):
    if df.empty or "CERRADA" not in df["estado"].values:
        return [], []
    ce = df[df["estado"]=="CERRADA"].copy()
    ce["fecha_cierre_real"] = ce["fecha_cierre_real"].fillna("").astype(str)
    ce = ce[ce["fecha_cierre_real"] != ""].sort_values("fecha_cierre_real")
    if ce.empty: return [], []
    ce["pnl_realizado"] = pd.to_numeric(ce["pnl_realizado"], errors="coerce").fillna(0)
    ce["pnl_acum"] = ce["pnl_realizado"].cumsum()
    labels = ce["fecha_cierre_real"].str[:16].tolist()
    values = ce["pnl_acum"].round(2).tolist()
    return labels, values

def progress_bar(pct, tp=0.09, sl=-0.05):
    rango = tp - sl
    pos   = max(0, min(1, (pct - sl) / rango)) * 100
    col   = "#10b981" if pct >= tp*0.7 else "#ef4444" if pct <= sl*0.7 else "#f59e0b"
    return f"""<div style="position:relative;height:5px;background:#162033;border-radius:3px;margin:8px 0 4px">
  <div style="position:absolute;left:0;top:-4px;width:2px;height:13px;background:#ef4444;border-radius:1px"></div>
  <div style="position:absolute;right:0;top:-4px;width:2px;height:13px;background:#10b981;border-radius:1px"></div>
  <div style="position:absolute;left:{pos:.1f}%;top:-5px;width:15px;height:15px;background:{col};
              border-radius:50%;transform:translateX(-50%);border:2px solid #060b14;box-shadow:0 0 8px {col}99"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:10px;margin-top:10px">
  <span style="color:#ef4444">SL {sl:.0%}</span>
  <span style="color:{col};font-weight:700">{pct:+.1%}</span>
  <span style="color:#10b981">TP +{tp:.0%}</span>
</div>"""

def generar():
    e, df = cargar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    ab = df[df["estado"]=="ABIERTA"] if not df.empty else pd.DataFrame()
    ce = df[df["estado"]=="CERRADA"] if not df.empty else pd.DataFrame()

    pnl_total = ce["pnl_realizado"].sum() if not ce.empty else 0
    ret  = pnl_total / e["capital_inicial"] * 100
    wins = (ce["pnl_realizado"]>0).sum() if not ce.empty else 0
    wr   = wins/len(ce) if not ce.empty else 0
    avg_win  = ce[ce["pnl_realizado"]>0]["pnl_realizado"].mean() if not ce.empty and wins>0 else 0
    avg_loss = ce[ce["pnl_realizado"]<=0]["pnl_realizado"].mean() if not ce.empty and (len(ce)-wins)>0 else 0
    tp_sl_ratio = e['n_tp']/(e['n_sl'] if e['n_sl']>0 else 1)

    labels, values = build_pnl_series(df)
    chart_color = "#10b981" if pnl_total >= 0 else "#ef4444"

    # ── Posiciones abiertas ────────────────────────────────────────
    cards_html = ""
    if ab.empty:
        cards_html = '<div style="text-align:center;color:#334155;padding:32px;font-size:13px">Sin posiciones abiertas actualmente</div>'
    else:
        for _, p in ab.iterrows():
            try:
                pte = float(p["precio_token_entrada"])
                pta = float(p["precio_actual"]) if p["señal"]=="COMPRAR YES" else 1-float(p["precio_actual"])
                pct = (pta-pte)/pte if pte>0 else 0
                pnl_nr = float(p["monto_usdc"]) * pct
                col = "#10b981" if pct>=0 else "#ef4444"
                bar = progress_bar(pct)
            except:
                pct=0; pnl_nr=0; col="#64748b"; bar=progress_bar(0)
            sc = "#10b981" if "YES" in str(p["señal"]) else "#ef4444"
            mom = float(p.get("momentum_entrada",0))
            cards_html += f"""<div style="background:#060b14;border:1px solid #162033;border-radius:10px;padding:14px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
    <div style="font-size:13px;color:#cbd5e1;font-weight:500;max-width:68%">{str(p['pregunta'])[:58]}</div>
    <div style="text-align:right;font-size:11px">
      <span style="color:{sc};font-weight:700">{p['señal']}</span>
      <span style="color:#475569;margin-left:6px">mom {mom:+.1%}</span>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:11px;color:#475569">
    <span>Entrada {float(p['precio_entrada']):.1%} · Actual {float(p['precio_actual']):.1%} · ${float(p['monto_usdc']):.0f}</span>
    <span style="color:{col};font-weight:700">{pnl_nr:+.2f}$</span>
  </div>
  {bar}
</div>"""

    # ── Historial ─────────────────────────────────────────────────
    hist_html = ""
    if not ce.empty:
        for _, p in ce.sort_values("fecha_cierre_real", ascending=False).head(15).iterrows():
            pnl = float(p.get("pnl_realizado",0)) if pd.notna(p.get("pnl_realizado")) else 0
            col = "#10b981" if pnl>=0 else "#ef4444"
            r = str(p.get("razon_cierre",""))
            bm = {"TAKE_PROFIT":"#14532d;color:#86efac","STOP_LOSS":"#450a0a;color:#fca5a5","TIME_EXIT":"#1e3a5f;color:#93c5fd"}
            lm = {"TAKE_PROFIT":"TP ✅","STOP_LOSS":"SL ❌","TIME_EXIT":"⏱ Time"}
            bs = bm.get(r,"#1e293b;color:#64748b"); bl = lm.get(r,r or "—")
            sc = "#10b981" if "YES" in str(p["señal"]) else "#ef4444"
            hist_html += f"""<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:10px;
align-items:center;padding:9px 0;border-bottom:1px solid #0d1829">
  <div style="font-size:12px;color:#64748b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{str(p['pregunta'])[:50]}</div>
  <span style="font-size:10px;color:{sc};font-weight:600">{p['señal']}</span>
  <span style="padding:2px 7px;border-radius:99px;font-size:10px;font-weight:700;background:{bs}">{bl}</span>
  <span style="color:{col};font-weight:700;font-size:13px;font-family:'Space Mono',monospace">{pnl:+.2f}$</span>
</div>"""

    # ── Exit stats ────────────────────────────────────────────────
    exit_html = ""
    for t,label,ac in [("TAKE_PROFIT","TP ✅","#10b981"),("STOP_LOSS","SL ❌","#ef4444"),("TIME_EXIT","⏱ Tiempo","#3b82f6")]:
        if ce.empty: continue
        s=ce[ce["razon_cierre"]==t]
        if s.empty: continue
        n=len(s); w=(s["pnl_realizado"]>0).sum(); p=s["pnl_realizado"].sum()
        exit_html+=f"""<div style="background:#060b14;border:1px solid #162033;border-radius:10px;
padding:16px;text-align:center">
  <div style="color:{ac};font-weight:700;font-size:13px;margin-bottom:8px">{label}</div>
  <div style="font-size:28px;font-weight:800;color:#f1f5f9;font-family:'Space Mono',monospace">{n}</div>
  <div style="font-size:11px;color:#475569;margin:4px 0">{w/n:.0%} ganadoras</div>
  <div style="font-size:15px;font-weight:700;color:{'#10b981' if p>=0 else '#ef4444'}">{p:+.2f}$</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Agente Momentum · Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:'DM Sans',sans-serif; background:#060b14; color:#e2e8f0;
       min-height:100vh; padding:28px; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
@keyframes fadeIn {{ from{{opacity:0;transform:translateY(8px)}} to{{opacity:1;transform:translateY(0)}} }}
.fade {{ animation: fadeIn .4s ease both }}
.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:22px }}
.kpi {{ background:#0d1829; border:1px solid #162033; border-radius:12px; padding:18px;
        position:relative; overflow:hidden }}
.kpi::after {{ content:''; position:absolute; top:0; left:0; right:0; height:1px;
               background:var(--a,#1e293b) }}
.kpi.g {{ --a:#10b981 }} .kpi.r {{ --a:#ef4444 }} .kpi.b {{ --a:#3b82f6 }}
.kl {{ font-size:10px; color:#475569; text-transform:uppercase; letter-spacing:.1em; margin-bottom:8px }}
.kv {{ font-family:'Space Mono',monospace; font-size:24px; font-weight:700; line-height:1 }}
.ks {{ font-size:11px; color:#334155; margin-top:6px }}
.card {{ background:#0d1829; border:1px solid #162033; border-radius:12px; padding:20px; margin-bottom:18px }}
.ct {{ font-size:11px; font-weight:600; color:#475569; text-transform:uppercase;
       letter-spacing:.1em; margin-bottom:16px; display:flex; align-items:center; gap:8px }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:99px; font-size:10px; font-weight:700 }}
.grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px }}
.live {{ display:inline-flex; align-items:center; gap:5px; font-size:10px; color:#10b981 }}
.dot {{ width:5px; height:5px; border-radius:50%; background:#10b981; animation:pulse 2s infinite }}
@media(max-width:700px){{ .kpis{{grid-template-columns:repeat(2,1fr)}} .grid3{{grid-template-columns:1fr}} }}
</style></head>
<body>

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px" class="fade">
  <div>
    <div style="font-size:11px;color:#334155;font-family:'Space Mono',monospace;margin-bottom:6px">POLYMARKET · PAPER TRADING</div>
    <h1 style="font-size:30px;font-weight:700;letter-spacing:-1px">
      Agente <span style="color:#10b981">Momentum</span>
    </h1>
    <div style="font-size:12px;color:#334155;margin-top:4px">Ciclo #{e['n_ciclos']} · {e.get('mercados_rastreados',0)} mercados rastreados</div>
  </div>
  <div style="text-align:right;font-size:11px;color:#334155;line-height:2">
    <div class="live"><span class="dot"></span> Auto-refresh 5min</div>
    <div>Último ciclo: {e['ultima_corrida']}</div>
    <div>TP +8% · SL -5% · Max 4h</div>
  </div>
</div>

<!-- KPIs -->
<div class="kpis fade">
  <div class="kpi {'g' if pnl_total>=0 else 'r'}">
    <div class="kl">P&L Total</div>
    <div class="kv" style="color:{'#10b981' if pnl_total>=0 else '#ef4444'}">{pnl_total:+.2f}$</div>
    <div class="ks">{ret:+.2f}% retorno</div>
  </div>
  <div class="kpi b">
    <div class="kl">Capital</div>
    <div class="kv">{e['capital_actual']:,.0f}$</div>
    <div class="ks">En riesgo {e.get('capital_en_riesgo',0):.0f}$</div>
  </div>
  <div class="kpi">
    <div class="kl">Win Rate</div>
    <div class="kv">{wr:.0%}</div>
    <div class="ks">{wins}/{len(ce)} cerradas</div>
  </div>
  <div class="kpi">
    <div class="kl">Avg Win / Loss</div>
    <div style="margin-top:4px">
      <span style="color:#10b981;font-size:18px;font-weight:700;font-family:'Space Mono',monospace">{avg_win:+.2f}$</span>
      <span style="color:#334155;font-size:12px"> / </span>
      <span style="color:#ef4444;font-size:18px;font-weight:700;font-family:'Space Mono',monospace">{avg_loss:+.2f}$</span>
    </div>
    <div class="ks">por operación</div>
  </div>
  <div class="kpi">
    <div class="kl">TP · SL · ⏱</div>
    <div style="margin-top:6px;font-size:16px;font-weight:700">
      <span style="color:#10b981">{e['n_tp']}</span>
      <span style="color:#334155;font-size:12px;margin:0 4px">·</span>
      <span style="color:#ef4444">{e['n_sl']}</span>
      <span style="color:#334155;font-size:12px;margin:0 4px">·</span>
      <span style="color:#3b82f6">{e['n_time']}</span>
    </div>
    <div class="ks">ratio TP/SL {tp_sl_ratio:.2f}</div>
  </div>
</div>

<!-- Chart -->
<div class="card fade">
  <div class="ct">📈 P&L Acumulado</div>
  <div style="height:160px;position:relative"><canvas id="chart"></canvas></div>
</div>

<!-- Abiertas -->
<div class="card fade">
  <div class="ct">
    📌 Posiciones Abiertas
    <span class="badge" style="background:#1e3a5f;color:#93c5fd">{len(ab)}</span>
    <span style="font-size:10px;font-weight:400;color:#334155">barra → SL (-5%) hasta TP (+8%)</span>
  </div>
  {cards_html}
</div>

<!-- Exit stats -->
<div class="card fade">
  <div class="ct">📊 Rendimiento por tipo de salida</div>
  <div class="grid3">{exit_html}</div>
</div>

<!-- Historial -->
<div class="card fade">
  <div class="ct">🕐 Últimas operaciones <span class="badge" style="background:#14532d;color:#86efac">{len(ce)}</span></div>
  {hist_html}
</div>

<div style="text-align:center;color:#162033;font-size:10px;margin-top:16px;font-family:'Space Mono',monospace">
  AGENTE MOMENTUM · {ahora}
</div>

<script>
const labels={json.dumps(labels)}, values={json.dumps(values)};
if(labels.length>0){{
  const ctx=document.getElementById('chart').getContext('2d');
  const g=ctx.createLinearGradient(0,0,0,160);
  g.addColorStop(0,'{chart_color}44'); g.addColorStop(1,'{chart_color}00');
  new Chart(ctx,{{
    type:'line',
    data:{{labels,datasets:[{{data:values,borderColor:'{chart_color}',backgroundColor:g,
      borderWidth:2,pointRadius:values.map((_,i)=>i===values.length-1?5:0),
      pointBackgroundColor:'{chart_color}',fill:true,tension:0.4}}]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#0d1829',
        borderColor:'#162033',borderWidth:1,bodyColor:'#f8fafc',
        callbacks:{{label:c=>' $'+c.parsed.y.toFixed(2)}}}}}},
      scales:{{x:{{display:false}},y:{{grid:{{color:'#0d1829'}},
        ticks:{{color:'#334155',font:{{family:'Space Mono',size:10}},
        callback:v=>'$'+v.toFixed(1)}}}}}}}}
  }});
}} else {{
  document.getElementById('chart').parentElement.innerHTML=
    '<div style="display:flex;align-items:center;justify-content:center;height:160px;color:#1e293b;font-size:12px">Sin datos de cierre aún</div>';
}}
</script>
</body></html>"""

    os.makedirs(os.path.dirname(ARCHIVO_OUT), exist_ok=True)
    with open(ARCHIVO_OUT,"w",encoding="utf-8") as f: f.write(html)
    print(f"✅ Dashboard → {ARCHIVO_OUT}")

if __name__ == "__main__":
    generar()
