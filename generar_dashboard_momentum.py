"""
generar_dashboard_momentum.py
Uso: python generar_dashboard_momentum.py
     → datos_polymarket/dashboard_momentum.html
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

def c(v):
    try: return "#16a34a" if float(v)>=0 else "#dc2626"
    except: return "#94a3b8"

def fp(v):
    try: return f"{float(v):+.1%}"
    except: return "—"

def fu(v):
    try: return f"${float(v):+.2f}"
    except: return "—"

def badge_r(r):
    m = {"TAKE_PROFIT":("background:#14532d;color:#86efac","TP ✅"),
         "STOP_LOSS":  ("background:#450a0a;color:#fca5a5","SL ❌"),
         "TIME_EXIT":  ("background:#1e3a5f;color:#93c5fd","⏱ Tiempo")}
    s,l = m.get(r,("background:#334155;color:#94a3b8",r or "—"))
    return f'<span style="padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600;{s}">{l}</span>'

def badge_s(s):
    col = "#16a34a" if "YES" in str(s) else "#dc2626"
    return f'<span style="color:{col};font-weight:700">{s}</span>'

def tarjetas(e, df):
    ab = df[df["estado"]=="ABIERTA"] if not df.empty else pd.DataFrame()
    ce = df[df["estado"]=="CERRADA"] if not df.empty else pd.DataFrame()
    pnl = ce["pnl_realizado"].sum() if not ce.empty else 0
    ret = pnl/e["capital_inicial"]*100
    wins = (ce["pnl_realizado"]>0).sum() if not ce.empty else 0
    wr = f"{wins/len(ce):.0%}" if not ce.empty else "—"
    avg_mom = ce["momentum_entrada"].mean() if not ce.empty and "momentum_entrada" in ce.columns else 0

    return f"""<div class="grid4">
  <div class="card"><div class="lbl">Capital actual</div>
    <div class="val">${e['capital_actual']:,.0f}</div>
    <div class="sub">Inicial ${e['capital_inicial']:,} · En riesgo ${e.get('capital_en_riesgo',0):.0f}</div></div>
  <div class="card"><div class="lbl">P&L realizado</div>
    <div class="val" style="color:{c(pnl)}">{fu(pnl)}</div>
    <div class="sub" style="color:{c(pnl)}">{ret:+.2f}% retorno</div></div>
  <div class="card"><div class="lbl">Win Rate</div>
    <div class="val">{wr}</div>
    <div class="sub">{wins}/{len(ce)} ops cerradas</div></div>
  <div class="card"><div class="lbl">Actividad</div>
    <div class="val" style="font-size:16px">
      <span style="color:#86efac">TP {e['n_tp']}</span> ·
      <span style="color:#fca5a5">SL {e['n_sl']}</span> ·
      <span style="color:#93c5fd">⏱ {e['n_time']}</span></div>
    <div class="sub">Ciclo #{e['n_ciclos']} · {e['ultima_corrida']} · {e.get('mercados_rastreados',0)} mercados</div></div>
</div>"""

def tabla_abiertas(df):
    ab = df[df["estado"]=="ABIERTA"] if not df.empty else pd.DataFrame()
    filas = ""
    if ab.empty:
        filas='<tr><td colspan="8" style="text-align:center;color:#6b7280;padding:20px">Sin posiciones abiertas</td></tr>'
    else:
        for _,p in ab.iterrows():
            try:
                pte = float(p["precio_token_entrada"])
                pta = float(p["precio_actual"]) if p["señal"]=="COMPRAR YES" else 1-float(p["precio_actual"])
                pct = (pta-pte)/pte; pnl = float(p["monto_usdc"])*pct
                ps,pu,cp = fp(pct),fu(pnl),c(pnl)
            except: ps=pu="—"; cp="#94a3b8"
            mom = float(p.get("momentum_entrada",0))
            filas+=f"""<tr>
<td style="max-width:220px;font-size:13px">{str(p['pregunta'])[:60]}</td>
<td>{badge_s(p['señal'])}</td>
<td style="color:{'#16a34a' if mom>0 else '#dc2626'};font-weight:700">{mom:+.1%}</td>
<td>{float(p['precio_entrada']):.1%}</td>
<td>{float(p['precio_actual']):.1%}</td>
<td style="color:{cp};font-weight:600">{ps}</td>
<td style="color:{cp};font-weight:600">{pu}</td>
<td>${float(p['monto_usdc']):.0f}</td></tr>"""
    return f"""<div class="section">
  <div class="stitle">📌 Abiertas <span class="badge blue">{len(ab)}</span></div>
  <table><thead><tr><th>Mercado</th><th>Señal</th><th>Momentum</th>
  <th>Entrada</th><th>Actual</th><th>Var%</th><th>P&L</th><th>Monto</th></tr></thead>
  <tbody>{filas}</tbody></table></div>"""

def tabla_cerradas(df):
    ce = df[df["estado"]=="CERRADA"].sort_values("fecha_cierre_real",ascending=False) \
         if not df.empty and "CERRADA" in df["estado"].values else pd.DataFrame()
    filas=""
    if ce.empty:
        filas='<tr><td colspan="7" style="text-align:center;color:#6b7280;padding:20px">Sin operaciones cerradas</td></tr>'
    else:
        for _,p in ce.iterrows():
            pnl=p.get("pnl_realizado"); col=c(pnl)
            mom=float(p.get("momentum_entrada",0)) if p.get("momentum_entrada") else 0
            filas+=f"""<tr>
<td style="max-width:200px;font-size:13px">{str(p['pregunta'])[:55]}</td>
<td>{badge_s(p['señal'])}</td>
<td style="color:{'#16a34a' if mom>0 else '#dc2626'}">{mom:+.1%}</td>
<td>{badge_r(p.get('razon_cierre',''))}</td>
<td style="color:{col};font-weight:600">{fp(p.get('pct_cambio'))}</td>
<td style="color:{col};font-weight:600">{fu(pnl)}</td>
<td style="font-size:11px;color:#6b7280">{str(p.get('fecha_cierre_real',''))[:16]}</td></tr>"""
    return f"""<div class="section">
  <div class="stitle">✅ Historial <span class="badge green">{len(ce)}</span></div>
  <table><thead><tr><th>Mercado</th><th>Señal</th><th>Mom.</th>
  <th>Cierre</th><th>Var%</th><th>P&L</th><th>Fecha</th></tr></thead>
  <tbody>{filas}</tbody></table></div>"""

def tabla_stats(df):
    if df.empty or "CERRADA" not in df["estado"].values: return ""
    ce = df[df["estado"]=="CERRADA"].copy()

    # Stats por tipo de salida
    tipos = [("TAKE_PROFIT","#86efac"),("STOP_LOSS","#fca5a5"),("TIME_EXIT","#93c5fd")]
    filas=""
    for t,col in tipos:
        s=ce[ce["razon_cierre"]==t]
        if s.empty: continue
        n=len(s); w=(s["pnl_realizado"]>0).sum(); p=s["pnl_realizado"].sum()
        filas+=f'<tr><td>{badge_r(t)}</td><td style="text-align:center">{n}</td>\
<td style="text-align:center">{w/n:.0%}</td>\
<td style="color:{c(p)};font-weight:600">{fu(p)}</td></tr>'

    # Momentum promedio de ops ganadoras vs perdedoras
    ganadoras = ce[ce["pnl_realizado"]>0]
    perdedoras = ce[ce["pnl_realizado"]<=0]
    mg = ganadoras["momentum_entrada"].mean() if not ganadoras.empty and "momentum_entrada" in ce.columns else None
    mp = perdedoras["momentum_entrada"].mean() if not perdedoras.empty and "momentum_entrada" in ce.columns else None

    insight = ""
    if mg is not None and mp is not None:
        insight = f"""<div style="margin-top:12px;padding:10px;background:#0f172a;border-radius:8px;font-size:12px;color:#94a3b8">
  💡 Momentum promedio ganadoras: <span style="color:#86efac">{mg:+.1%}</span> ·
  Perdedoras: <span style="color:#fca5a5">{mp:+.1%}</span>
  {"· Señal: momentum mayor = mejor" if abs(mg)>abs(mp) else "· Señal: momentum no predice bien aún"}
</div>"""

    return f"""<div class="section">
  <div class="stitle">📊 Análisis de salidas</div>
  <table><thead><tr><th>Tipo</th><th style="text-align:center">Ops</th>
  <th style="text-align:center">Win%</th><th>P&L</th></tr></thead>
  <tbody>{filas}</tbody></table>{insight}</div>"""

def generar():
    e, df = cargar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Momentum Agent Dashboard</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:#0f172a;color:#e2e8f0;padding:24px}}
h1{{font-size:20px;font-weight:700;color:#f8fafc;margin-bottom:4px}}
.sub0{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.lbl{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
.val{{font-size:24px;font-weight:700;color:#f8fafc}}
.sub{{font-size:11px;color:#64748b;margin-top:4px}}
.section{{background:#1e293b;border-radius:10px;padding:18px;
          border:1px solid #334155;margin-bottom:16px}}
.stitle{{font-size:14px;font-weight:600;color:#f8fafc;margin-bottom:14px;
         display:flex;align-items:center;gap:8px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;
    padding:7px 10px;border-bottom:1px solid #334155}}
td{{padding:8px 10px;border-bottom:1px solid #1a2744;font-size:13px;vertical-align:middle}}
tr:hover td{{background:#253349}}
.badge{{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600}}
.blue{{background:#1e3a5f;color:#93c5fd}}
.green{{background:#14532d;color:#86efac}}
@media(max-width:700px){{.grid4{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<h1>⚡ Agente Momentum — Polymarket</h1>
<div class="sub0">{ahora} · TP +8% · SL -5% · Max 8h · Ciclo 15min</div>
{tarjetas(e,df)}
{tabla_abiertas(df)}
{tabla_stats(df)}
{tabla_cerradas(df)}
<div style="text-align:center;color:#475569;font-size:11px;margin-top:14px">
  Paper Trading · <code>python generar_dashboard_momentum.py</code>
</div></body></html>"""

    os.makedirs(os.path.dirname(ARCHIVO_OUT), exist_ok=True)
    with open(ARCHIVO_OUT,"w",encoding="utf-8") as f: f.write(html)
    print(f"✅ Dashboard → {ARCHIVO_OUT}")

if __name__ == "__main__":
    generar()
