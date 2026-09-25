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
FILE_CONFIG_COPY = "datos_polymarket/copy_trading/config_copy.json"

FILE_OUTPUT_COMPARATIVO = "datos_polymarket/dashboard_comparativo.html"
FILE_OUTPUT_HIBRIDO = "datos_polymarket/dashboard_hibrido.html"
FILE_INDEX = "index.html" # Para GitHub Pages

# Diccionario de traducción de Wallets a nombres legibles
WHALE_NAMES = {
    "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb": "mintblade",
    "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate",
    "0x26437896ed9dfeb2f69765edcafe8fdceaab39ae": "Latina"
}
WHALE_NAMES_NORM = {k.lower(): v for k, v in WHALE_NAMES.items()}

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
    # Configurar TZ ecuatoriana
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Guayaquil")
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    except Exception:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ──────────────────────────────────────────────────────────────
    # 1. CARGAR DATOS - AGENTE HÍBRIDO
    # ──────────────────────────────────────────────────────────────
    capital_inicial_hib = 1000.0; capital_actual_hib = 1000.0
    capital_en_riesgo_hib = 0.0; n_ciclos_hib = 0; ultima_corrida_hib = "—"
    n_tp_hib = 0; n_sl_hib = 0; n_time_hib = 0

    if os.path.exists(FILE_ESTADO_HIBRIDO):
        try:
            with open(FILE_ESTADO_HIBRIDO) as f:
                est = json.load(f)
                capital_inicial_hib = float(est.get("capital_inicial", capital_inicial_hib))
                capital_actual_hib  = float(est.get("capital_actual", capital_actual_hib))
                capital_en_riesgo_hib  = float(est.get("capital_en_riesgo", capital_en_riesgo_hib))
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
    capital_inicial_copy = 1000.0; capital_actual_copy = 1000.0
    capital_en_riesgo_copy = 0.0; n_ciclos_copy = 0; ultima_corrida_copy = "—"
    n_tp_copy = 0; n_sl_copy = 0

    if os.path.exists(FILE_ESTADO_COPY):
        try:
            with open(FILE_ESTADO_COPY) as f:
                est = json.load(f)
                capital_inicial_copy = float(est.get("capital_inicial", capital_inicial_copy))
                capital_actual_copy  = float(est.get("capital_actual", capital_actual_copy))
                capital_en_riesgo_copy  = float(est.get("capital_en_riesgo", capital_en_riesgo_copy))
                n_ciclos_copy    = est.get("n_ciclos", 0)
                ultima_corrida_copy = est.get("ultima_corrida", "—")
                n_tp_copy        = est.get("n_tp", 0)
                n_sl_copy        = est.get("n_sl", 0)
        except Exception as e:
            print(f"Error estado copy-trader: {e}")

    df_copy = pd.read_csv(FILE_LIBRO_COPY) if os.path.exists(FILE_LIBRO_COPY) else pd.DataFrame()

    # Cargar wallets a copiar configurados
    wallets = []
    if os.path.exists(FILE_CONFIG_COPY):
        try:
            with open(FILE_CONFIG_COPY) as f:
                cfg = json.load(f)
                wallets = cfg.get("wallets_to_copy", [])
        except Exception as e:
            print(f"Error cargando config copy: {e}")
    if not wallets:
        wallets = [
            "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb",
            "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2",
            "0x26437896ed9dfeb2f69765edcafe8fdceaab39ae"
        ]

    # ──────────────────────────────────────────────────────────────
    # 3. PROCESAR HISTORIAL - HÍBRIDO
    # ──────────────────────────────────────────────────────────────
    pnl_total_hib = 0.0; pnl_flotante_hib = 0.0; win_rate_hib = 0.0
    ops_abiertas_hib_html = ""; ops_cerradas_hib_html = ""
    historia_pnl_hib = []
    total_ganadas_hib = 0; total_perdidas_hib = 0; total_cerradas_hib = 0
    n_tp_calc = 0; n_sl_calc = 0; n_time_calc = 0; n_inactiva_calc = 0
    wins_list_hib = []; losses_list_hib = []
    yes_count_hib = 0; no_count_hib = 0
    pct_yes_hib = 0; pct_no_hib = 0
    n_abiertas_hib = 0

    if not df_hib.empty:
        df_hib['estado'] = df_hib['estado'].astype(str).str.strip().str.upper()
        
        # Conteo de señales YES/NO
        df_valid_signals_hib = df_hib[df_hib['señal'].notna()]
        yes_count_hib = len(df_valid_signals_hib[df_valid_signals_hib['señal'].astype(str).str.upper().str.contains("YES")])
        no_count_hib = len(df_valid_signals_hib[df_valid_signals_hib['señal'].astype(str).str.upper().str.contains("NO")])
        total_signals_hib = yes_count_hib + no_count_hib
        if total_signals_hib > 0:
            pct_yes_hib = (yes_count_hib / total_signals_hib) * 100
            pct_no_hib = (no_count_hib / total_signals_hib) * 100

        # Abiertas Híbrido
        abiertas_hib = df_hib[df_hib['estado'] == 'ABIERTA']
        n_abiertas_hib = len(abiertas_hib)
        for _, p in abiertas_hib.iterrows():
            tp_real = float(p.get('tp_dinamico', 0.09))
            sl_real = float(p.get('sl_dinamico', -0.07))
            confianza = float(p.get('llm_confianza', 0.50))
            edge = float(p.get('llm_edge', 0.03))
            if edge > 1.0: edge /= 100.0
            senal = str(p.get('señal', 'COMPRAR YES'))
            monto = float(p.get('monto_usdc', 20.0))
            pte = float(p.get('precio_token_entrada', p.get('precio_entrada', 0.5)))
            pta = float(p.get('precio_actual', pte))
            vol_1d = float(p.get('vol_1d', 0.0))
            momentum_1h = float(p.get('momentum_1h', 0.0))
            horas_max = p.get('horas_max', 10)
            razonamiento_completo = str(p.get('razonamiento', '—'))
            razon_ia = razonamiento_completo[:80] + ("..." if len(razonamiento_completo) > 80 else "")
            
            pnl_flot = (pta - pte) * (monto / pte) if pte > 0 else 0.0
            pnl_flotante_hib += pnl_flot

            pnl_clase = "positive" if pnl_flot >= 0 else "negative"
            pct_burbuja = calcular_posicion_barra(pte, pta, tp_real, sl_real)
            mom_color = "#10b981" if momentum_1h >= 0 else "#ef4444"

            datos_js = {
                "pregunta": p['pregunta'],
                "senal": senal,
                "monto": f"${monto:,.2f} USDC",
                "confianza": f"{confianza:.0%}",
                "edge": f"+{edge:.1%}",
                "precio_entrada": f"{pte:.3f}",
                "precio_actual": f"{pta:.3f}",
                "pnl": f"{'+' if pnl_flot>=0 else ''}${pnl_flot:.2f}",
                "pnl_raw": pnl_flot,
                "salida": "ACTIVA",
                "razonamiento": razonamiento_completo
            }

            ops_abiertas_hib_html += f"""
            <div class="card-orden card-hib">
                <div class="card-orden-header">
                    <span class="badge-senal {senal.lower().replace(' ', '-')}">{senal}</span>
                    <span class="monto-orden">${monto:,.2f} USDC</span>
                </div>
                <div class="pregunta-titulo">{p['pregunta']}</div>
                <div class="metadatos-grid">
                    <div class="meta-item"><span class="meta-label">🤖 Confianza</span><span class="meta-value">{confianza:.0%}</span></div>
                    <div class="meta-item"><span class="meta-label">📈 Edge</span><span class="meta-value">+{edge:.1%}</span></div>
                    <div class="meta-item"><span class="meta-label">⏱️ Límite</span><span class="meta-value">{horas_max}h</span></div>
                    <div class="meta-item"><span class="meta-label">📊 P&L Temp</span><span class="meta-value {pnl_clase}">{"+" if pnl_flot>=0 else ""}${pnl_flot:.2f}</span></div>
                    <div class="meta-item"><span class="meta-label">📉 Vol 1d</span><span class="meta-value">{vol_1d:.4f}</span></div>
                    <div class="meta-item"><span class="meta-label">⚡ Mom 1h</span><span class="meta-value" style="color:{mom_color}">{momentum_1h:+.1%}</span></div>
                </div>
                <div class="riesgo-container">
                    <div class="riesgo-labels">
                        <span class="label-sl">SL {sl_real:.1%}</span>
                        <span>Entrada {pte:.3f}</span>
                        <span class="label-tp">TP {tp_real:.1%}</span>
                    </div>
                    <div class="riesgo-barra-bg">
                        <div class="riesgo-burbuja" style="left:{pct_burbuja}%;"></div>
                    </div>
                    <div class="riesgo-precios">
                        <span>${pte*(1+sl_real):.3f}</span>
                        <span style="color:#a78bfa;font-weight:600">Actual ${pta:.3f}</span>
                        <span>${pte*(1+tp_real):.3f}</span>
                    </div>
                </div>
                <div class="card-orden-footer">
                    <div class="ia-summary-box">
                        <span class="meta-label">🧠 IA:</span> <span class="ia-summary-text">{razon_ia}</span>
                    </div>
                    <button class="btn-ver-cot" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js))}">Ver Análisis</button>
                </div>
            </div>"""
        
        # Cerradas Híbrido
        cerradas_hib = df_hib[df_hib['estado'] == 'CERRADA'].copy()
        if not cerradas_hib.empty:
            cerradas_hib['fecha_dt'] = pd.to_datetime(cerradas_hib['fecha_cierre_real'], errors='coerce')
            cerradas_hib = cerradas_hib.sort_values('fecha_dt')
            total_cerradas_hib = len(cerradas_hib)
            
            pnl_acum = 0.0
            rows_hib = []
            for _, p in cerradas_hib.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                dt_h = p.get('fecha_dt')
                fecha_fmt_h = dt_h.strftime("%d %b %H:%M") if pd.notna(dt_h) else fecha
                historia_pnl_hib.append({"fecha": fecha, "fecha_fmt": fecha_fmt_h, "pnl": round(pnl_acum, 2)})
                
                razon = str(p.get('razon_cierre', 'EXIT')).upper()
                if razon == 'TAKE_PROFIT' or razon == 'EARLY_EXIT': n_tp_calc += 1
                elif razon == 'STOP_LOSS': n_sl_calc += 1
                elif razon == 'TIME_EXIT': n_time_calc += 1
                elif razon == 'INACTIVA': n_inactiva_calc += 1
                
                if pnl_op > 0:
                    total_ganadas_hib += 1
                    wins_list_hib.append(pnl_op)
                elif pnl_op < 0:
                    total_perdidas_hib += 1
                    losses_list_hib.append(pnl_op)

                clase_row = "row-ganancia" if pnl_op >= 0 else "row-perdida"
                razonamiento_completo = str(p.get('razonamiento', '—'))

                datos_js_closed = {
                    "pregunta": p['pregunta'],
                    "senal": p.get('señal', '—'),
                    "monto": f"${float(p.get('monto_usdc', 0)):,.2f} USDC",
                    "confianza": f"{float(p.get('llm_confianza', 0.5)):.0%}" if p.get('llm_confianza') else "—",
                    "edge": f"+{float(p.get('llm_edge', 0)):.1%}" if p.get('llm_edge') else "—",
                    "precio_entrada": f"{float(p.get('precio_entrada', 0.5)):.3f}",
                    "precio_actual": f"{float(p.get('precio_cierre', 0.5)):.3f}",
                    "pnl": f"{'+' if pnl_op>=0 else ''}${pnl_op:,.2f}",
                    "pnl_raw": pnl_op,
                    "salida": razon,
                    "razonamiento": razonamiento_completo
                }

                row_html = f"""
                <tr class="{clase_row}">
                    <td>{fecha}</td>
                    <td class="txt-truncate" title="{p['pregunta']}">{p['pregunta']}</td>
                    <td><span class="badge-tabla">{p.get('señal', '—')}</span></td>
                    <td>${float(p.get('monto_usdc', 0)):.2f}</td>
                    <td class="bold-pnl">{"+" if pnl_op>=0 else ""}${pnl_op:.2f}</td>
                    <td><span class="badge-razon {razon.lower()}">{razon}</span></td>
                    <td>
                        <button class="btn-ver-cot-tabla" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js_closed))}">🔍</button>
                    </td>
                </tr>"""
                rows_hib.append(row_html)
            
            ops_cerradas_hib_html = "".join(reversed(rows_hib))
            pnl_total_hib = pnl_acum
            trades_reales_hib = total_ganadas_hib + total_perdidas_hib
            win_rate_hib = (total_ganadas_hib / trades_reales_hib) if trades_reales_hib > 0 else 0.0

    if not ops_abiertas_hib_html:
        ops_abiertas_hib_html = '<div class="no-data" style="grid-column: span 3;">Sin posiciones abiertas en este momento.</div>'
    if not ops_cerradas_hib_html:
        ops_cerradas_hib_html = '<tr><td colspan="7" class="no-data">Sin historial de operaciones registradas.</td></tr>'

    # Calcular promedios y Profit Factor Híbrido
    avg_win_hib = sum(wins_list_hib) / len(wins_list_hib) if wins_list_hib else 0.0
    avg_loss_hib = sum(losses_list_hib) / len(losses_list_hib) if losses_list_hib else 0.0
    sum_wins_hib = sum(wins_list_hib)
    sum_losses_hib = abs(sum(losses_list_hib))
    if sum_losses_hib == 0:
        profit_factor_str_hib = "∞" if sum_wins_hib > 0 else "0.00"
        profit_factor_clase_hib = "positive" if sum_wins_hib > 0 else "neutral"
    else:
        pf_val_hib = sum_wins_hib / sum_losses_hib
        profit_factor_str_hib = f"{pf_val_hib:.2f}"
        profit_factor_clase_hib = "positive" if pf_val_hib >= 1.0 else "negative"

    equity_hib = capital_actual_hib + pnl_flotante_hib
    pnl_net_pct_hib = ((equity_hib - capital_inicial_hib) / capital_inicial_hib) * 100

    # Rendimiento Semanal Híbrido
    pnl_7d_hib = 0.0; roi_7d_hib = 0.0; ops_7d_hib = 0; wr_7d_hib = 0.0
    if not cerradas_hib.empty and 'fecha_dt' in cerradas_hib.columns:
        now_dt_hib = cerradas_hib['fecha_dt'].max()
        if pd.notna(now_dt_hib):
            t_7d_hib = now_dt_hib - pd.Timedelta(days=7)
            c_7d_hib = cerradas_hib[cerradas_hib['fecha_dt'] >= t_7d_hib]
            if not c_7d_hib.empty:
                pnl_7d_hib = float(pd.to_numeric(c_7d_hib['pnl_realizado'], errors='coerce').fillna(0.0).sum())
                roi_7d_hib = (pnl_7d_hib / capital_inicial_hib) * 100.0
                ops_7d_hib = len(c_7d_hib)
                wr_7d_hib = ((pd.to_numeric(c_7d_hib['pnl_realizado'], errors='coerce') > 0).sum() / ops_7d_hib * 100.0) if ops_7d_hib > 0 else 0.0

    # ──────────────────────────────────────────────────────────────
    # 4. PROCESAR HISTORIAL - COPY-TRADER
    # ──────────────────────────────────────────────────────────────
    pnl_total_copy = 0.0; pnl_flotante_copy = 0.0; win_rate_copy = 0.0
    ops_abiertas_copy_html = ""; ops_cerradas_copy_html = ""
    historia_pnl_copy = []
    abiertas_copy = pd.DataFrame()
    total_ganadas_copy = 0; total_perdidas_copy = 0; total_cerradas_copy = 0
    n_target_sell_copy = 0; n_resolved_copy = 0; n_failsafe_copy = 0
    wins_list_copy = []; losses_list_copy = []
    yes_count_copy = 0; no_count_copy = 0
    pct_yes_copy = 0; pct_no_copy = 0
    n_abiertas_copy = 0

    # Inicializar estadísticas por Whale
    whales_stats = {}
    for w in wallets:
        whales_stats[w.lower()] = {
            "address": w,
            "name": WHALE_NAMES_NORM.get(w.lower(), w[:8] + "..." + w[-4:]),
            "active_count": 0,
            "total_count": 0,
            "closed_pnl": 0.0,
            "floating_pnl": 0.0,
            "wins": 0,
            "losses": 0
        }

    if not df_copy.empty:
        df_copy['estado'] = df_copy['estado'].astype(str).str.strip().str.upper()
        df_copy['target_wallet_lower'] = df_copy['target_wallet'].astype(str).str.strip().str.lower()

        # Abiertas Copy
        abiertas_copy = df_copy[df_copy['estado'] == 'ABIERTA']
        n_abiertas_copy = len(abiertas_copy)
        for _, p in abiertas_copy.iterrows():
            monto = float(p.get('monto_usdc', 20.0))
            pte = float(p.get('precio_token_entrada', 0.5))
            pta = float(p.get('precio_actual', pte))
            pnl_flot = (pta - pte) * (monto / pte) if pte > 0 else 0.0
            pnl_flotante_copy += pnl_flot

            # Estadísticas por Whale
            w_addr = p.get('target_wallet_lower')
            if w_addr in whales_stats:
                whales_stats[w_addr]["active_count"] += 1
                whales_stats[w_addr]["total_count"] += 1
                whales_stats[w_addr]["floating_pnl"] += pnl_flot
            else:
                whales_stats[w_addr] = {
                    "address": p.get('target_wallet'),
                    "name": WHALE_NAMES_NORM.get(w_addr, p.get('target_wallet')[:10] + "..."),
                    "active_count": 1,
                    "total_count": 1,
                    "closed_pnl": 0.0,
                    "floating_pnl": pnl_flot,
                    "wins": 0,
                    "losses": 0
                }

            # Señal e Historial
            outcome = str(p.get('outcome', 'YES')).upper()
            if 'YES' in outcome: yes_count_copy += 1
            else: no_count_copy += 1

            pnl_clase = "positive" if pnl_flot >= 0 else "negative"
            pct_pnl = (pta - pte) / pte if pte > 0 else 0.0
            
            # Cálculo de la barra de P&L (-100% a +100%)
            if pct_pnl >= 0:
                bar_left = 50.0
                bar_width = min(50.0, pct_pnl * 50.0)
            else:
                bar_left = max(0.0, 50.0 + pct_pnl * 50.0)
                bar_width = min(50.0, abs(pct_pnl) * 50.0)

            whale_name = whales_stats[w_addr]["name"]
            tx_h = str(p.get('tx_hash', ''))
            tx_link = f'https://polygonscan.com/tx/{tx_h}' if tx_h and tx_h != 'nan' else '#'
            tx_display = tx_h[:10] + '...' if tx_h and tx_h != 'nan' else 'Ver tx'

            datos_js = {
                "pregunta": p['pregunta'],
                "senal": f"COPIAR {outcome}",
                "monto": f"${monto:,.2f} USDC",
                "confianza": "—",
                "edge": "—",
                "precio_entrada": f"{pte:.3f}",
                "precio_actual": f"{pta:.3f}",
                "pnl": f"{'+' if pnl_flot>=0 else ''}${pnl_flot:.2f} ({pct_pnl:+.1%})",
                "pnl_raw": pnl_flot,
                "salida": "ACTIVA (COPIADA)",
                "razonamiento": f"Posición abierta de forma automática al copiar la transacción del Whale <strong>{whale_name}</strong> ({p.get('target_wallet')}).<br><br>Sujeta a sincronización Failsafe y cierre automático cuando el Whale venda o el mercado resuelva.<br><br>Hash de Transacción: <a href='{tx_link}' target='_blank' style='color:#38bdf8;text-decoration:none;'>{tx_h}</a>"
            }

            ops_abiertas_copy_html += f"""
            <div class="card-orden card-copy">
                <div class="card-orden-header">
                    <span class="badge-senal comprar-yes">{outcome}</span>
                    <span class="monto-orden">${monto:,.2f} USDC</span>
                </div>
                <div class="pregunta-titulo">{p['pregunta']}</div>
                <div class="metadatos-grid">
                    <div class="meta-item"><span class="meta-label">🐳 Whale</span><span class="meta-value">{whale_name}</span></div>
                    <div class="meta-item"><span class="meta-label">📈 Entrada</span><span class="meta-value">${pte:.3f}</span></div>
                    <div class="meta-item"><span class="meta-label">📊 P&L Temp</span><span class="meta-value {pnl_clase}">{"+" if pnl_flot>=0 else ""}${pnl_flot:.2f}</span></div>
                    <div class="meta-item"><span class="meta-label">🔄 Actual</span><span class="meta-value">${pta:.3f}</span></div>
                    <div class="meta-item"><span class="meta-label">⚡ Retorno</span><span class="meta-value {pnl_clase}">{pct_pnl:+.1%}</span></div>
                    <div class="meta-item"><span class="meta-label">🔗 Transacción</span><span class="meta-value" style="font-size:0.75rem;"><a href="{tx_link}" target="_blank" style="color:#38bdf8;text-decoration:none;">{tx_display}</a></span></div>
                </div>
                <div class="riesgo-container">
                    <div class="riesgo-labels">
                        <span class="label-sl">-100%</span>
                        <span>Entrada {pte:.3f}</span>
                        <span class="label-tp">+100%</span>
                    </div>
                    <div class="riesgo-barra-bg" style="background: linear-gradient(to right, var(--red) 0%, rgba(30, 41, 59, 0.8) 50%, var(--green) 100%);">
                        <div class="riesgo-burbuja" style="left:{bar_left + bar_width}%; border-color: var(--primary-copy);"></div>
                    </div>
                    <div class="riesgo-precios">
                        <span>$0.000</span>
                        <span style="color:#38bdf8;font-weight:600">Actual ${pta:.3f}</span>
                        <span>$1.000</span>
                    </div>
                </div>
                <div class="card-orden-footer">
                    <div class="ia-summary-box">
                        <span class="meta-label">Whale:</span> <span class="ia-summary-text">{p.get('target_wallet')[:15]}...</span>
                    </div>
                    <button class="btn-ver-cot btn-ver-copy" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js))}">Detalles</button>
                </div>
            </div>"""

        # Cerradas Copy
        cerradas_copy = df_copy[df_copy['estado'] == 'CERRADA'].copy()
        if not cerradas_copy.empty:
            cerradas_copy['fecha_dt'] = pd.to_datetime(cerradas_copy['fecha_cierre_real'], errors='coerce')
            cerradas_copy = cerradas_copy.sort_values('fecha_dt')
            total_cerradas_copy = len(cerradas_copy)

            pnl_acum = 0.0
            rows_copy = []
            peak_copy = capital_inicial_copy
            drawdown_series_copy = []
            rolling_wr_window = []
            rolling_wr_series_copy = []

            for _, p in cerradas_copy.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                dt_c = p.get('fecha_dt')
                fecha_fmt_c = dt_c.strftime("%d %b %H:%M") if pd.notna(dt_c) else fecha
                historia_pnl_copy.append({"fecha": fecha, "fecha_fmt": fecha_fmt_c, "pnl": round(pnl_acum, 2)})

                # Tracking Drawdown
                eq_curr = capital_inicial_copy + pnl_acum
                if eq_curr > peak_copy: peak_copy = eq_curr
                dd_val = ((eq_curr - peak_copy) / peak_copy) * 100.0
                drawdown_series_copy.append(round(dd_val, 2))

                # Tracking Rolling Win Rate (20 ops)
                rolling_wr_window.append(1 if pnl_op > 0 else 0)
                if len(rolling_wr_window) > 20: rolling_wr_window.pop(0)
                rolling_wr_series_copy.append(round(sum(rolling_wr_window) / len(rolling_wr_window) * 100.0, 1))

                # Whale tracking
                w_addr = p.get('target_wallet_lower')
                if w_addr in whales_stats:
                    whales_stats[w_addr]["total_count"] += 1
                    whales_stats[w_addr]["closed_pnl"] += pnl_op
                    if pnl_op > 0: whales_stats[w_addr]["wins"] += 1
                    elif pnl_op < 0: whales_stats[w_addr]["losses"] += 1
                else:
                    whales_stats[w_addr] = {
                        "address": p.get('target_wallet'),
                        "name": WHALE_NAMES_NORM.get(w_addr, p.get('target_wallet')[:10] + "..."),
                        "active_count": 0,
                        "total_count": 1,
                        "closed_pnl": pnl_op,
                        "floating_pnl": 0.0,
                        "wins": 1 if pnl_op > 0 else 0,
                        "losses": 1 if pnl_op < 0 else 0
                    }

                # Outcome y Razón
                outcome = str(p.get('outcome', 'YES')).upper()
                if 'YES' in outcome: yes_count_copy += 1
                else: no_count_copy += 1

                razon = str(p.get('razon_cierre', 'EXIT')).upper()
                if razon == 'TARGET_SELL': n_target_sell_copy += 1
                elif razon == 'RESOLVED_EXIT': n_resolved_copy += 1
                elif razon == 'FAILSAFE_SYNC_EXIT': n_failsafe_copy += 1

                if pnl_op > 0:
                    total_ganadas_copy += 1
                    wins_list_copy.append(pnl_op)
                elif pnl_op < 0:
                    total_perdidas_copy += 1
                    losses_list_copy.append(pnl_op)

                clase_row = "row-ganancia" if pnl_op >= 0 else "row-perdida"
                tx_h = str(p.get('tx_hash', ''))
                tx_link = f'https://polygonscan.com/tx/{tx_h}' if tx_h and tx_h != 'nan' else '#'
                whale_name = whales_stats[w_addr]["name"]

                datos_js_closed = {
                    "pregunta": p['pregunta'],
                    "senal": f"COPIAR {outcome}",
                    "monto": f"${float(p.get('monto_usdc', 0)):,.2f} USDC",
                    "confianza": "—",
                    "edge": "—",
                    "precio_entrada": f"{float(p.get('precio_token_entrada', 0.5)):.3f}",
                    "precio_actual": f"{float(p.get('precio_cierre', 0.5)):.3f}",
                    "pnl": f"{'+' if pnl_op>=0 else ''}${pnl_op:,.2f}",
                    "pnl_raw": pnl_op,
                    "salida": razon,
                    "razonamiento": f"Operación cerrada. Copiado del Whale <strong>{whale_name}</strong> ({p.get('target_wallet')}).<br><br>Razón de salida: <strong>{razon}</strong>.<br>P&L Realizado: ${pnl_op:+.2f} USDC.<br><br>Transacción en Polygonscan: <a href='{tx_link}' target='_blank' style='color:#38bdf8'>{tx_h}</a>"
                }

                row_html = f"""
                <tr class="{clase_row}">
                    <td>{fecha}</td>
                    <td class="txt-truncate" title="{p['pregunta']}">{p['pregunta']}</td>
                    <td><span class="badge-tabla">{outcome}</span></td>
                    <td>${float(p.get('monto_usdc', 0)):.2f}</td>
                    <td class="bold-pnl">{"+" if pnl_op>=0 else ""}${pnl_op:.2f}</td>
                    <td><span class="badge-razon {razon.lower()}">{razon}</span></td>
                    <td>
                        <button class="btn-ver-cot-tabla" onclick="abrirModalDesdeBtn(this)" data-info="{html.escape(json.dumps(datos_js_closed))}">🔍</button>
                    </td>
                </tr>"""
                rows_copy.append(row_html)

            ops_cerradas_copy_html = "".join(reversed(rows_copy))
            pnl_total_copy = pnl_acum
            trades_reales_copy = total_ganadas_copy + total_perdidas_copy
            win_rate_copy = (total_ganadas_copy / trades_reales_copy) if trades_reales_copy > 0 else 0.0

    if not ops_abiertas_copy_html:
        ops_abiertas_copy_html = '<div class="no-data" style="grid-column: span 3;">Sin posiciones de copia activas en este momento.</div>'
    if not ops_cerradas_copy_html:
        ops_cerradas_copy_html = '<tr><td colspan="7" class="no-data">Sin historial de operaciones de copia registradas.</td></tr>'

    # Calcular promedios y Profit Factor Copy
    avg_win_copy = sum(wins_list_copy) / len(wins_list_copy) if wins_list_copy else 0.0
    avg_loss_copy = sum(losses_list_copy) / len(losses_list_copy) if losses_list_copy else 0.0
    sum_wins_copy = sum(wins_list_copy)
    sum_losses_copy = abs(sum(losses_list_copy))
    if sum_losses_copy == 0:
        profit_factor_str_copy = "∞" if sum_wins_copy > 0 else "0.00"
        profit_factor_clase_copy = "positive" if sum_wins_copy > 0 else "neutral"
    else:
        pf_val_copy = sum_wins_copy / sum_losses_copy
        profit_factor_str_copy = f"{pf_val_copy:.2f}"
        profit_factor_clase_copy = "positive" if pf_val_copy >= 1.0 else "negative"

    equity_copy = capital_actual_copy + pnl_flotante_copy
    pnl_net_pct_copy = ((equity_copy - capital_inicial_copy) / capital_inicial_copy) * 100

    # Drawdown global
    max_drawdown_copy = min(drawdown_series_copy) if 'drawdown_series_copy' in locals() and drawdown_series_copy else 0.0
    current_drawdown_copy = drawdown_series_copy[-1] if 'drawdown_series_copy' in locals() and drawdown_series_copy else 0.0

    # Win Rate Estratégico (TP vs SL)
    total_tp_sl_copy = n_tp_copy + n_sl_copy
    win_rate_estrat_copy = (n_tp_copy / total_tp_sl_copy * 100.0) if total_tp_sl_copy > 0 else 0.0

    # Agrupación y Retorno Diario Copy
    daily_labels_copy = []
    daily_pnl_copy = []
    daily_roi_copy = []
    daily_colors_copy = []
    pnl_hoy_copy = 0.0
    ops_hoy_copy = 0
    wins_hoy_copy = 0
    wr_hoy_copy = 0.0
    dia_nombre_hoy = "Hoy"
    roi_hoy_pct_copy = 0.0

    # Métricas temporales y cuantitativas Copy
    pnl_7d_copy = 0.0; roi_7d_copy = 0.0; ops_7d_copy = 0; wr_7d_copy = 0.0
    pnl_30d_copy = 0.0; roi_30d_copy = 0.0; ops_30d_copy = 0; wr_30d_copy = 0.0
    avg_daily_pnl_copy = 0.0; avg_daily_roi_copy = 0.0
    volatilidad_copy = 0.0; sharpe_copy = 0.0
    expectancy_copy = 0.0; expectancy_pct_copy = 0.0

    if not cerradas_copy.empty and 'fecha_dt' in cerradas_copy.columns:
        cerradas_copy['dia_str'] = cerradas_copy['fecha_dt'].dt.strftime('%d %b')
        daily_grouped = cerradas_copy.groupby('dia_str', sort=False).agg(
            pnl_dia=('pnl_realizado', 'sum'),
            ops=('pnl_realizado', 'count'),
            wins=('pnl_realizado', lambda x: (x > 0).sum())
        ).reset_index()

        daily_labels_copy = daily_grouped['dia_str'].tolist()
        daily_pnl_copy = [round(float(v), 2) for v in daily_grouped['pnl_dia'].tolist()]
        daily_roi_copy = [round((float(v) / capital_inicial_copy) * 100.0, 2) for v in daily_pnl_copy]
        daily_colors_copy = ['#10b981' if v >= 0 else '#ef4444' for v in daily_pnl_copy]

        if not daily_grouped.empty:
            ultimo_dia = daily_grouped.iloc[-1]
            pnl_hoy_copy = float(ultimo_dia['pnl_dia'])
            ops_hoy_copy = int(ultimo_dia['ops'])
            wins_hoy_copy = int(ultimo_dia['wins'])
            wr_hoy_copy = (wins_hoy_copy / ops_hoy_copy * 100.0) if ops_hoy_copy > 0 else 0.0
            dia_nombre_hoy = str(ultimo_dia['dia_str'])
            roi_hoy_pct_copy = (pnl_hoy_copy / capital_inicial_copy) * 100.0

        # Rendimiento Semanal y Mensual Copy
        now_dt = cerradas_copy['fecha_dt'].max()
        if pd.notna(now_dt):
            t_7d = now_dt - pd.Timedelta(days=7)
            t_30d = now_dt - pd.Timedelta(days=30)
            
            c_7d = cerradas_copy[cerradas_copy['fecha_dt'] >= t_7d]
            if not c_7d.empty:
                pnl_7d_copy = float(pd.to_numeric(c_7d['pnl_realizado'], errors='coerce').fillna(0.0).sum())
                roi_7d_copy = (pnl_7d_copy / capital_inicial_copy) * 100.0
                ops_7d_copy = len(c_7d)
                wr_7d_copy = ((pd.to_numeric(c_7d['pnl_realizado'], errors='coerce') > 0).sum() / ops_7d_copy * 100.0) if ops_7d_copy > 0 else 0.0
            
            c_30d = cerradas_copy[cerradas_copy['fecha_dt'] >= t_30d]
            if not c_30d.empty:
                pnl_30d_copy = float(pd.to_numeric(c_30d['pnl_realizado'], errors='coerce').fillna(0.0).sum())
                roi_30d_copy = (pnl_30d_copy / capital_inicial_copy) * 100.0
                ops_30d_copy = len(c_30d)
                wr_30d_copy = ((pd.to_numeric(c_30d['pnl_realizado'], errors='coerce') > 0).sum() / ops_30d_copy * 100.0) if ops_30d_copy > 0 else 0.0

        # Rendimiento Promedio Diario, Volatilidad y Sharpe (periodo continuo activo >= 2026-09-18)
        cerradas_active = cerradas_copy[cerradas_copy['fecha_dt'] >= '2026-09-18']
        if not cerradas_active.empty:
            daily_active = cerradas_active.groupby(cerradas_active['fecha_dt'].dt.date)['pnl_realizado'].sum()
            avg_daily_pnl_copy = float(daily_active.mean())
            avg_daily_roi_copy = (avg_daily_pnl_copy / capital_inicial_copy) * 100.0
            
            daily_rets_pct = (daily_active / capital_inicial_copy) * 100.0
            volatilidad_copy = float(daily_rets_pct.std()) if len(daily_rets_pct) > 1 else 0.0
            sharpe_copy = (daily_rets_pct.mean() / (volatilidad_copy if volatilidad_copy > 0 else 1.0)) * (365 ** 0.5) if volatilidad_copy > 0 else 0.0

        total_ops_closed = len(cerradas_copy)
        expectancy_copy = (pnl_total_copy / total_ops_closed) if total_ops_closed > 0 else 0.0

    # Dynamic Sizing Distribution
    montos_copy = df_copy['monto_usdc'].dropna().astype(float) if not df_copy.empty and 'monto_usdc' in df_copy.columns else pd.Series()
    min_sizing_copy = float(montos_copy.min()) if not montos_copy.empty else 0.0
    max_sizing_copy = float(montos_copy.max()) if not montos_copy.empty else 0.0
    avg_sizing_copy = float(montos_copy.mean()) if not montos_copy.empty else 0.0
    median_sizing_copy = float(montos_copy.median()) if not montos_copy.empty else 0.0
    avg_sz = avg_sizing_copy if avg_sizing_copy > 0 else 20.0
    expectancy_pct_copy = (expectancy_copy / avg_sz) * 100.0

    total_m = len(montos_copy) if len(montos_copy) > 0 else 1
    cnt_def = int((montos_copy <= 12.0).sum())
    cnt_bal = int(((montos_copy > 12.0) & (montos_copy <= 18.0)).sum())
    cnt_asym = int((montos_copy > 18.0).sum())
    pct_def = (cnt_def / total_m) * 100.0
    pct_bal = (cnt_bal / total_m) * 100.0
    pct_asym = (cnt_asym / total_m) * 100.0

    # Time in trade (duraciones)
    avg_dur_win_h = 0.0; avg_dur_loss_h = 0.0; avg_dur_global_h = 0.0
    if not cerradas_copy.empty and 'fecha_entrada' in cerradas_copy.columns:
        cerradas_copy['dt_in'] = pd.to_datetime(cerradas_copy['fecha_entrada'], errors='coerce')
        cerradas_copy['dur_h'] = (cerradas_copy['fecha_dt'] - cerradas_copy['dt_in']).dt.total_seconds() / 3600.0
        valid_dur = cerradas_copy[cerradas_copy['dur_h'] >= 0]
        if not valid_dur.empty:
            avg_dur_win_h = float(valid_dur[valid_dur['pnl_realizado'] > 0]['dur_h'].mean())
            avg_dur_loss_h = float(valid_dur[valid_dur['pnl_realizado'] < 0]['dur_h'].mean())
            avg_dur_global_h = float(valid_dur['dur_h'].mean())

    # Rendimiento por Categoría de Mercado
    def clasificar_categoria(pregunta):
        p = str(pregunta).lower()
        if any(k in p for k in ['bitcoin', 'btc', 'eth', 'solana', 'sol', 'crypto', 'token', 'price of', 'hit $', 'all-time high', 'ath', 'market cap']):
            return 'Cripto / Web3'
        if any(k in p for k in ['counter-strike', 'cs:go', 'csgo', 'dota', 'league of legends', 'lol', 'valorant', 'major', 'iem', 'blast', 'esports', 'map 1', 'map 2']):
            return 'Esports / Gaming'
        if any(k in p for k in ['premier league', 'la liga', 'champions league', 'fc ', 'arsenal', 'madrid', 'barcelona', 'manchester', 'liverpool', 'bayern', 'serie a', 'liga mx', 'soccer', 'inter ', 'chelsea', 'ac milan', 'juventus', 'dortmund', 'atletico']):
            return 'Fútbol'
        if any(k in p for k in ['nba', 'nfl', 'mlb', 'nhl', 'ufc', 'boxing', 'tennis', 'grand slam', 'formula 1', 'f1', 'us open', 'wimbledon']):
            return 'Otros Deportes'
        if any(k in p for k in ['election', 'president', 'trump', 'kamala', 'harris', 'biden', 'senate', 'governor', 'democrat', 'republican', 'vote', 'cabinet', 'nominee', 'poll']):
            return 'Política'
        if any(k in p for k in ['fed', 'interest rate', 'cpi', 'inflation', 'gdp', 'recession', 'temperature', 'weather', 'hurricane', 'spacex', 'starship', 'ai ', 'openai', 'gpt']):
            return 'Macro / Clima'
        return 'General'

    categorias_html = ""
    if not cerradas_copy.empty and 'pregunta' in cerradas_copy.columns:
        cerradas_copy['categoria'] = cerradas_copy['pregunta'].apply(clasificar_categoria)
        cat_grouped = cerradas_copy.groupby('categoria').agg(
            ops=('pnl_realizado', 'count'),
            pnl=('pnl_realizado', 'sum'),
            wins=('pnl_realizado', lambda x: (x > 0).sum())
        ).reset_index()
        cat_grouped['wr'] = (cat_grouped['wins'] / cat_grouped['ops'] * 100).round(1)
        cat_grouped['pnl'] = cat_grouped['pnl'].round(2)
        cat_grouped = cat_grouped.sort_values('pnl', ascending=False)

        cat_icons = {
            'Cripto / Web3': '🚀',
            'Esports / Gaming': '🎮',
            'Fútbol': '⚽',
            'Otros Deportes': '🏆',
            'Política': '🗳️',
            'Macro / Clima': '🌦️',
            'General': '🌐'
        }

        for _, cat in cat_grouped.iterrows():
            c_name = cat['categoria']
            icon = cat_icons.get(c_name, '📊')
            c_pnl = cat['pnl']
            c_ops = int(cat['ops'])
            c_wr = cat['wr']
            c_sign = "+" if c_pnl > 0 else ""
            c_clase = "positive" if c_pnl >= 0 else "negative"
            
            categorias_html += f'''
            <div class="cat-card">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
                <span style="font-family:var(--font-head); font-weight:700; font-size:0.92rem; color:#fff; display:flex; align-items:center; gap:0.35rem;">
                  {icon} {c_name}
                </span>
                <span class="badge {c_clase} bold" style="font-size:0.85rem; font-family:var(--font-mono);">
                  {c_sign}${c_pnl:.2f}
                </span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:var(--muted); font-family:var(--font-mono);">
                <span>Ops: <strong style="color:#fff;">{c_ops}</strong></span>
                <span>Win Rate: <strong style="color:{'#10b981' if c_wr>=50 else '#ef4444'}">{c_wr:.1f}%</strong></span>
              </div>
              <div style="width:100%; height:4px; background:rgba(255,255,255,0.05); border-radius:2px; margin-top:0.5rem; overflow:hidden;">
                <div style="height:100%; width:{min(100.0, max(5.0, c_wr))}%; background:{'#10b981' if c_wr>=50 else '#ef4444'}; border-radius:2px;"></div>
              </div>
            </div>'''

    # Construir Tabla Interactiva de Whales
    whales_list = list(whales_stats.values())
    whales_list.sort(key=lambda w: (w["closed_pnl"] + w["floating_pnl"]), reverse=True)
    whales_table_html = ""
    for w in whales_list:
        total_pnl = w["closed_pnl"] + w["floating_pnl"]
        p_clase = "positive" if total_pnl >= 0 else "negative"
        p_sign = "+" if total_pnl > 0 else ""
        t_closed = w["wins"] + w["losses"]
        w_wr = (w["wins"] / t_closed * 100) if t_closed > 0 else 0.0
        w_wr_str = f"{w_wr:.1f}%" if t_closed > 0 else "—"
        wr_color = "#10b981" if w_wr >= 50 else ("#ef4444" if t_closed > 0 else "var(--muted)")
        avg_pnl = (w["closed_pnl"] / t_closed) if t_closed > 0 else 0.0
        avg_clase = "positive" if avg_pnl >= 0 else "negative"
        
        is_active = w["active_count"] > 0
        dot_color = "var(--green)" if is_active else "var(--gray)"
        dot_glow = "0 0 6px var(--green)" if is_active else "none"
        addr_short = w["address"][:8] + "..." + w["address"][-6:] if len(w["address"]) > 14 else w["address"]
        tx_link = f'https://polygonscan.com/address/{w["address"]}'
        
        whales_table_html += f'''
        <tr class="whale-row" data-search="{w['name'].lower()} {w['address'].lower()}">
          <td>
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <span class="status-dot" style="width:7px; height:7px; background-color:{dot_color}; box-shadow:{dot_glow}; flex-shrink:0;"></span>
              <div>
                <strong style="color:#fff; font-family:var(--font-head); font-size:0.9rem;">{w['name']}</strong>
                <div style="font-size:0.68rem; font-family:var(--font-mono); color:var(--muted);">
                  <a href="{tx_link}" target="_blank" style="color:var(--muted); text-decoration:none;">{addr_short} ↗</a>
                </div>
              </div>
            </div>
          </td>
          <td style="text-align:center; font-family:var(--font-mono); font-weight:700; color:{'var(--primary-copy)' if is_active else 'var(--muted)'};">{w['active_count']}</td>
          <td style="text-align:center; font-family:var(--font-mono); color:var(--muted);">{t_closed}</td>
          <td style="text-align:center; font-family:var(--font-mono);">{w['total_count']}</td>
          <td style="text-align:center; font-family:var(--font-mono); font-weight:600; color:{wr_color};">{w_wr_str} <span style="font-size:0.68rem; color:var(--muted); font-weight:400;">({w['wins']}W/{w['losses']}L)</span></td>
          <td style="text-align:right; font-family:var(--font-mono); font-weight:700;" class="{'positive' if w['closed_pnl'] >= 0 else 'negative'}">{'+' if w['closed_pnl'] > 0 else ''}${w['closed_pnl']:.2f}</td>
          <td style="text-align:right; font-family:var(--font-mono);" class="{'positive' if w['floating_pnl'] >= 0 else 'negative'}">{'+' if w['floating_pnl'] > 0 else ''}${w['floating_pnl']:.2f}</td>
          <td style="text-align:right; font-family:var(--font-mono); font-weight:700;" class="{p_clase}">{p_sign}${total_pnl:.2f}</td>
          <td style="text-align:center; font-family:var(--font-mono);"><span class="badge {'positive' if avg_pnl >= 0 else 'negative'}" style="font-size:0.75rem;">{'+' if avg_pnl > 0 else ''}${avg_pnl:.2f}</span></td>
        </tr>'''


    # Construir HTML de las estadísticas de Whales
    whales_html = ""
    for w_addr, w_info in whales_stats.items():
        total_pnl = w_info["closed_pnl"] + w_info["floating_pnl"]
        p_clase = "positive" if total_pnl >= 0 else "negative"
        p_sign = "+" if total_pnl > 0 else ""
        
        t_closed = w_info["wins"] + w_info["losses"]
        w_wr = (w_info["wins"] / t_closed * 100) if t_closed > 0 else 0.0
        w_wr_str = f"{w_wr:.0f}% WR" if t_closed > 0 else "Sin cerradas"
        tx_link = f'https://polygonscan.com/address/{w_info["address"]}'
        
        whales_html += f"""
        <div class="card-m card-whale" style="--accent: var(--primary-copy); --accent-hover: #7dd3fc; --accent-glow: var(--primary-copy-glow); padding: 1.25rem;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 0.75rem;">
                <div>
                    <h4 style="color:#fff; font-size:1.1rem; font-weight:700; display:flex; align-items:center; gap:0.4rem; font-family:var(--font-head)">
                        🐳 {w_info["name"]}
                        <span class="status-dot pulse" style="width:6px; height:6px; background-color:{'var(--green)' if w_info['active_count'] > 0 else 'var(--gray)'}; box-shadow:0 0 6px {'var(--green)' if w_info['active_count'] > 0 else 'var(--gray)'}"></span>
                    </h4>
                    <span style="font-size:0.65rem; font-family:var(--font-mono); color:var(--muted);">
                        <a href="{tx_link}" target="_blank" style="color:var(--muted); text-decoration:none;">{w_info["address"][:12]}...{w_info["address"][-6:]} ↗</a>
                    </span>
                </div>
                <div style="text-align:right;">
                    <span class="badge {p_clase} bold" style="font-size:0.95rem; font-family:var(--font-mono); padding: 0.15rem 0.4rem; background:rgba(255,255,255,0.02); border-radius:6px;">
                        {p_sign}${total_pnl:.2f}
                    </span>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.85rem; border-top: 1px solid rgba(255,255,255,0.04); padding-top:0.75rem; text-align:center;">
                <div>
                    <div style="font-size:0.6rem; color:var(--muted); text-transform:uppercase; font-family:var(--font-mono)">Activas</div>
                    <div style="font-size:0.9rem; font-weight:700; color:#fff; font-family:var(--font-mono)">{w_info["active_count"]}</div>
                </div>
                <div>
                    <div style="font-size:0.6rem; color:var(--muted); text-transform:uppercase; font-family:var(--font-mono)">Total Ops</div>
                    <div style="font-size:0.9rem; font-weight:700; color:#fff; font-family:var(--font-mono)">{w_info["total_count"]}</div>
                </div>
                <div>
                    <div style="font-size:0.6rem; color:var(--muted); text-transform:uppercase; font-family:var(--font-mono)">Efectividad</div>
                    <div style="font-size:0.75rem; font-weight:700; color:#fbbf24; font-family:var(--font-mono); margin-top: 0.1rem;">{w_wr_str}</div>
                </div>
            </div>
        </div>"""

    # Conteo general de señales copy para el gráfico
    total_signals_copy = yes_count_copy + no_count_copy
    if total_signals_copy > 0:
        pct_yes_copy = (yes_count_copy / total_signals_copy) * 100
        pct_no_copy = (no_count_copy / total_signals_copy) * 100

    # ──────────────────────────────────────────────────────────────
    # 5. PREPARAR DATOS DEL GRÁFICO COMBINADO (VS) Y SERIES HORARIAS
    # ──────────────────────────────────────────────────────────────
    start_chart_dt = pd.to_datetime('2026-09-19 00:00:00')

    max_dts = []
    if not cerradas_copy.empty and 'fecha_dt' in cerradas_copy.columns:
        valid_copy_dts = cerradas_copy['fecha_dt'].dropna()
        if not valid_copy_dts.empty: max_dts.append(valid_copy_dts.max())
    if not cerradas_hib.empty and 'fecha_dt' in cerradas_hib.columns:
        valid_hib_dts = cerradas_hib['fecha_dt'].dropna()
        if not valid_hib_dts.empty: max_dts.append(valid_hib_dts.max())

    end_chart_dt = max(max_dts) if max_dts else (start_chart_dt + pd.Timedelta(hours=24))
    if end_chart_dt < start_chart_dt + pd.Timedelta(hours=24):
        end_chart_dt = start_chart_dt + pd.Timedelta(hours=24)

    hourly_idx = pd.date_range(start=start_chart_dt, end=end_chart_dt, freq='1h')
    df_grid = pd.DataFrame(index=hourly_idx)

    # Copy-Trader Serie Horaria Regular
    if not cerradas_copy.empty and 'fecha_dt' in cerradas_copy.columns:
        c_sorted = cerradas_copy.dropna(subset=['fecha_dt']).sort_values('fecha_dt').copy()
        c_sorted['pnl_realizado'] = pd.to_numeric(c_sorted['pnl_realizado'], errors='coerce').fillna(0.0)
        pnl_prev_copy = float(c_sorted[c_sorted['fecha_dt'] < start_chart_dt]['pnl_realizado'].sum())

        c_active = c_sorted[c_sorted['fecha_dt'] >= start_chart_dt].copy()
        c_active['pnl_acum'] = pnl_prev_copy + c_active['pnl_realizado'].cumsum()

        c_sorted['is_win'] = (c_sorted['pnl_realizado'] > 0).astype(int)
        c_sorted['rolling_wr'] = c_sorted['is_win'].rolling(window=20, min_periods=1).mean() * 100.0

        c_hourly_pnl = c_active.set_index('fecha_dt')[['pnl_acum']].resample('1h').last()
        c_hourly_wr = c_sorted.set_index('fecha_dt')[['rolling_wr']].resample('1h').last()

        df_grid['copy_pnl'] = c_hourly_pnl['pnl_acum']
        df_grid['copy_wr'] = c_hourly_wr['rolling_wr']
        df_grid['copy_pnl'] = df_grid['copy_pnl'].ffill().fillna(pnl_prev_copy)

        init_wr = float(c_sorted['rolling_wr'].iloc[0]) if not c_sorted.empty else 50.0
        df_grid['copy_wr'] = df_grid['copy_wr'].ffill().fillna(init_wr)

        eq_curve_copy = capital_inicial_copy + df_grid['copy_pnl']
        peak_curve_copy = eq_curve_copy.cummax()
        df_grid['copy_drawdown'] = ((eq_curve_copy - peak_curve_copy) / peak_curve_copy) * 100.0
    else:
        df_grid['copy_pnl'] = 0.0
        df_grid['copy_wr'] = 50.0
        df_grid['copy_drawdown'] = 0.0

    # Híbrido Serie Horaria Regular
    if not cerradas_hib.empty and 'fecha_dt' in cerradas_hib.columns:
        h_sorted = cerradas_hib.dropna(subset=['fecha_dt']).sort_values('fecha_dt').copy()
        h_sorted['pnl_realizado'] = pd.to_numeric(h_sorted['pnl_realizado'], errors='coerce').fillna(0.0)
        pnl_prev_hib = float(h_sorted[h_sorted['fecha_dt'] < start_chart_dt]['pnl_realizado'].sum())

        h_active = h_sorted[h_sorted['fecha_dt'] >= start_chart_dt].copy()
        h_active['pnl_acum'] = pnl_prev_hib + h_active['pnl_realizado'].cumsum()

        h_hourly_pnl = h_active.set_index('fecha_dt')[['pnl_acum']].resample('1h').last()
        df_grid['hib_pnl'] = h_hourly_pnl['pnl_acum']
        df_grid['hib_pnl'] = df_grid['hib_pnl'].ffill().fillna(pnl_prev_hib)
    else:
        df_grid['hib_pnl'] = 0.0

    # Series para Chart.js
    chart_labels_comp = [dt.strftime("%d %b %H:%M") for dt in df_grid.index]
    chart_data_hib_comp = [round(float(v), 2) for v in df_grid['hib_pnl']]
    chart_data_copy_comp = [round(float(v), 2) for v in df_grid['copy_pnl']]

    fechas_copy = chart_labels_comp
    valores_copy = chart_data_copy_comp
    drawdown_series_copy = [round(float(v), 2) for v in df_grid['copy_drawdown']]
    rolling_wr_series_copy = [round(float(v), 1) for v in df_grid['copy_wr']]

    # Individual charts
    fechas_hib = chart_labels_comp
    valores_hib = chart_data_hib_comp

    # Donut Charts Data
    donut_labels_hib = ['TP / Early', 'Stop Loss', 'Time Exit', 'Inactiva']
    donut_data_hib = [n_tp_calc, n_sl_calc, n_time_calc, n_inactiva_calc]
    donut_colors_hib = ['#10b981', '#ef4444', '#f59e0b', '#6b7280']

    donut_labels_copy = ['Whale Sell', 'Market Resolved', 'Failsafe Exit']
    donut_data_copy = [n_target_sell_copy, n_resolved_copy, n_failsafe_copy]
    donut_colors_copy = ['#06b6d4', '#10b981', '#f59e0b']

    # ──────────────────────────────────────────────────────────────
    # 6. COMPILAR HTML MAESTRO
    # ──────────────────────────────────────────────────────────────
    with open("generar_dashboard_comparativo.py", "r") as f:
        # Esto es solo para verificar la lectura
        pass

    # HTML TEMPLATE
    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Polymarket AI — Terminal Operativa Unificada</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {
  --bg: #030712; 
  --surface: rgba(15, 23, 42, 0.45); 
  --surface-card: rgba(22, 34, 57, 0.25);
  --border: rgba(255, 255, 255, 0.06);
  --border-hover: rgba(139, 92, 246, 0.35);
  
  --primary-hib: #8b5cf6; 
  --primary-hib-glow: rgba(139, 92, 246, 0.22);
  --primary-copy: #0284c7;
  --primary-copy-glow: rgba(2, 132, 199, 0.22);
  --primary-comp: #6366f1;
  --primary-comp-glow: rgba(99, 102, 241, 0.22);

  --green: #10b981; 
  --red: #ef4444; 
  --amber: #f59e0b;
  --gray: #64748b;
  --text: #f8fafc;
  --muted: #94a3b8;
  
  --font-head: 'Outfit', sans-serif; 
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* { margin:0; padding:0; box-sizing:border-box; }

body { 
  background: var(--bg); 
  color: var(--text); 
  font-family: var(--font-body); 
  min-height: 100vh;
  position: relative;
  padding-bottom: 4rem;
}

body::before { 
  content: ''; 
  position: fixed; 
  inset: 0; 
  background: radial-gradient(circle at 10% 12%, rgba(139, 92, 246, 0.05) 0%, transparent 45%),
              radial-gradient(circle at 90% 80%, rgba(2, 132, 199, 0.05) 0%, transparent 45%); 
  pointer-events: none; 
  z-index: -1;
}

/* Navigation Bar */
.main-navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: rgba(8, 12, 28, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 0.85rem 2rem;
}

.navbar-container {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-emoji {
  font-size: 1.8rem;
  background: linear-gradient(135deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.logo-text h3 {
  font-family: var(--font-head);
  font-weight: 800;
  font-size: 1.25rem;
  letter-spacing: -0.02em;
  color: #fff;
}

.logo-text p {
  font-size: 0.65rem;
  color: var(--muted);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nav-links {
  display: flex;
  gap: 0.75rem;
}

.main-nav-btn {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: var(--font-head);
  font-size: 0.88rem;
  font-weight: 600;
  padding: 0.6rem 1.25rem;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.main-nav-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.15);
}

.main-nav-btn.active {
  background: rgba(99, 102, 241, 0.12);
  color: #818cf8;
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.15);
}

.main-nav-btn.active#nav-btn-hibrido {
  background: rgba(139, 92, 246, 0.12);
  color: #c084fc;
  border-color: rgba(139, 92, 246, 0.4);
  box-shadow: 0 0 15px rgba(139, 92, 246, 0.15);
}

.main-nav-btn.active#nav-btn-copy {
  background: rgba(2, 132, 199, 0.12);
  color: #38bdf8;
  border-color: rgba(2, 132, 199, 0.4);
  box-shadow: 0 0 15px rgba(2, 132, 199, 0.15);
}

/* Master Layout */
.dashboard-wrapper {
  max-width: 1400px;
  margin: 2rem auto;
  padding: 0 2rem;
}

/* Sticky Header inside Tab View */
header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 2.25rem; 
  padding-bottom: 1.5rem; 
  border-bottom: 1px solid var(--border); 
}

.tab-title-desc h1 {
  font-size: 2rem; 
  font-weight: 800; 
  letter-spacing: -0.04em; 
  font-family: var(--font-head);
  background: linear-gradient(135deg, #fff 40%, var(--muted) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.tab-title-desc h1 span.accent-hib {
  background: linear-gradient(135deg, #a78bfa 0%, var(--primary-hib) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 15px rgba(139, 92, 246, 0.25);
}

.tab-title-desc h1 span.accent-copy {
  background: linear-gradient(135deg, #38bdf8 0%, var(--primary-copy) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 15px rgba(2, 132, 199, 0.25);
}

.tab-title-desc p { 
  color: var(--muted); 
  font-size: 0.8rem; 
  font-family: var(--font-mono); 
  letter-spacing: 0.05em; 
}

.header-meta-container {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  padding: 0.4rem 0.8rem;
  border-radius: 9999px;
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: var(--green);
  border-radius: 50%;
  box-shadow: 0 0 10px var(--green);
}

.pulse {
  animation: pulseGlow 2s infinite ease-in-out;
}

@keyframes pulseGlow {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}

.status-text {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 0.05em;
}

.meta-header { 
  text-align: right; 
  font-family: var(--font-mono); 
  font-size: 0.78rem; 
  color: var(--muted); 
  line-height: 1.5; 
}

.meta-header strong { 
  color: var(--text); 
}

/* Metric Cards Grid */
.grid-metricas { 
  display: grid; 
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
  gap: 1.25rem; 
  margin-bottom: 2.5rem; 
}

.card-m { 
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
}

.card-m:hover {
  transform: translateY(-3px);
  border-color: var(--accent-hover, var(--border-hover));
  box-shadow: 0 15px 30px -10px rgba(0, 0, 0, 0.6), 0 0 15px var(--accent-glow, var(--primary-hib-glow));
}

.card-m::after { 
  content: ''; 
  position: absolute; 
  bottom: 0; 
  left: 0; 
  right: 0; 
  height: 3px; 
  background: var(--accent, var(--border)); 
}

.card-m h4 { 
  font-size: 0.72rem; 
  text-transform: uppercase; 
  letter-spacing: 0.15em; 
  color: var(--muted); 
  font-family: var(--font-mono); 
}

.card-m .val { 
  font-size: 1.8rem; 
  font-weight: 700; 
  margin-top: 0.5rem; 
  font-family: var(--font-mono); 
}

.card-m .sub { 
  font-size: 0.75rem; 
  color: var(--muted); 
  margin-top: 0.3rem; 
  font-family: var(--font-mono); 
}

/* Panel Layouts */
.row-2 { 
  display: grid; 
  grid-template-columns: 1.7fr 1fr; 
  gap: 1.75rem; 
  margin-bottom: 2.5rem; 
}

@media(max-width: 1100px) { 
  .row-2 { grid-template-columns: 1fr; } 
}

.panel { 
  background: var(--surface); 
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border); 
  border-radius: 18px; 
  padding: 1.75rem; 
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
  margin-bottom: 2rem;
}

.panel h3 { 
  font-size: 0.85rem; 
  text-transform: uppercase; 
  letter-spacing: 0.12em; 
  color: var(--muted); 
  font-family: var(--font-mono); 
  margin-bottom: 1.5rem; 
  display: flex; 
  align-items: center; 
  gap: 0.6rem; 
}

.panel h3::before { 
  content: ''; 
  display: inline-block; 
  width: 4px; 
  height: 14px; 
  background: var(--primary, var(--primary-comp)); 
  border-radius: 2px; 
  box-shadow: 0 0 8px var(--primary, var(--primary-comp));
}

.panel-distribucion {
  margin-top: 1.75rem;
  padding-top: 1.75rem;
  border-top: 1px solid var(--border);
}

.yes-no-bar-container {
  height: 8px;
  background: var(--red);
  border-radius: 99px;
  overflow: hidden;
  display: flex;
  margin: 0.75rem 0;
}

.yes-no-bar-yes {
  background: var(--green);
  height: 100%;
  transition: width 0.5s ease-in-out;
}

.yes-no-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--muted);
}

/* Grids and Cards for Active Positions */
.abiertas-wrapper { 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); 
  gap: 1.25rem; 
}

.card-orden { 
  background: var(--surface-card); 
  border: 1px solid var(--border); 
  border-radius: 14px; 
  padding: 1.5rem; 
  display: flex; 
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 5px 15px rgba(0,0,0,0.2);
  transition: all 0.25s ease; 
}

.card-orden:hover { 
  border-color: rgba(139, 92, 246, 0.3); 
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.4), 0 0 10px rgba(139,92,246,0.1);
}

.card-copy:hover {
  border-color: rgba(2, 132, 199, 0.3);
  box-shadow: 0 10px 25px rgba(0,0,0,0.4), 0 0 10px rgba(2, 132, 199, 0.1);
}

.card-orden-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 0.85rem; 
}

.badge-senal { 
  font-size: 0.68rem; 
  font-weight: 700; 
  padding: 0.25rem 0.6rem; 
  border-radius: 6px; 
  text-transform: uppercase; 
  font-family: var(--font-mono); 
  letter-spacing: 0.03em;
}

.badge-senal.comprar-yes, .badge-senal.yes, .badge-senal.yes-signal { 
  background: rgba(16, 185, 129, 0.1); 
  color: var(--green); 
  border: 1px solid rgba(16, 185, 129, 0.2); 
}

.badge-senal.comprar-no, .badge-senal.no, .badge-senal.no-signal  { 
  background: rgba(239, 68, 68, 0.1); 
  color: var(--red); 
  border: 1px solid rgba(239, 68, 68, 0.2); 
}

.monto-orden { 
  font-size: 0.95rem; 
  font-weight: 700; 
  font-family: var(--font-mono); 
  color: #e2e8f0; 
}

.pregunta-titulo { 
  font-size: 0.98rem; 
  font-weight: 600; 
  margin-bottom: 1rem; 
  line-height: 1.45; 
  color: #fff; 
  font-family: var(--font-head);
}

.metadatos-grid { 
  display: grid; 
  grid-template-columns: repeat(3, 1fr); 
  gap: 0.75rem; 
  background: rgba(8, 12, 20, 0.55); 
  padding: 0.8rem 1rem; 
  border-radius: 10px; 
  margin-bottom: 1.25rem; 
  border: 1px solid rgba(255,255,255,0.03);
}

.meta-item { 
  display: flex; 
  flex-direction: column; 
}

.meta-label { 
  font-size: 0.65rem; 
  color: var(--muted); 
  font-family: var(--font-mono); 
  text-transform: uppercase; 
  letter-spacing: 0.05em; 
}

.meta-value { 
  font-size: 0.88rem; 
  font-weight: 600; 
  margin-top: 0.15rem; 
  font-family: var(--font-mono); 
  color: #f8fafc; 
}

.riesgo-container { 
  margin-bottom: 1.25rem; 
}

.riesgo-labels { 
  display: flex; 
  justify-content: space-between; 
  font-size: 0.72rem; 
  margin-bottom: 0.45rem; 
  font-family: var(--font-mono); 
  color: var(--muted); 
}

.label-sl { color: var(--red); font-weight: 600; } 
.label-tp { color: var(--green); font-weight: 600; }

.riesgo-barra-bg { 
  height: 6px; 
  background: linear-gradient(to right, var(--red) 0%, rgba(30, 41, 59, 0.8) 35%, rgba(30, 41, 59, 0.8) 65%, var(--green) 100%); 
  border-radius: 3px; 
  position: relative; 
  margin-bottom: 0.45rem; 
}

.riesgo-burbuja { 
  width: 12px; 
  height: 12px; 
  background: #fff; 
  border: 2.5px solid var(--primary-hib); 
  border-radius: 50%; 
  position: absolute; 
  top: 50%; 
  transform: translate(-50%, -50%); 
  box-shadow: 0 0 10px var(--primary-hib); 
  transition: left 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.riesgo-precios { 
  display: flex; 
  justify-content: space-between; 
  font-size: 0.7rem; 
  color: var(--muted); 
  font-family: var(--font-mono); 
}

.card-orden-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.ia-summary-box {
  font-size: 0.75rem;
  color: var(--muted);
  max-width: 68%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ia-summary-text {
  color: #94a3b8;
  font-style: italic;
}

.btn-ver-cot {
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
}

.btn-ver-cot:hover {
  background: var(--primary-hib);
  color: #fff;
  border-color: var(--primary-hib);
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.45);
}

.btn-ver-copy {
  background: rgba(2, 132, 199, 0.12);
  border: 1px solid rgba(2, 132, 199, 0.25);
  color: #38bdf8;
}

.btn-ver-copy:hover {
  background: var(--primary-copy);
  color: #fff;
  border-color: var(--primary-copy);
  box-shadow: 0 0 12px rgba(2, 132, 199, 0.45);
}

/* Tables and Filters */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.search-box {
  flex-grow: 1;
  max-width: 320px;
}

.search-box input {
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
}

.search-box input:focus {
  border-color: #818cf8;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.15);
  background: rgba(8, 12, 20, 0.85);
}

.filter-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-tab {
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
}

.filter-tab:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.filter-tab.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.3);
}

.filter-tab-hib.active {
  background: var(--primary-hib);
  border-color: var(--primary-hib);
}

.filter-tab-copy.active {
  background: var(--primary-copy);
  border-color: var(--primary-copy);
}

.tabla-contenedor { 
  width: 100%; 
  max-height: 520px;
  overflow-y: auto;
  overflow-x: auto; 
  margin-top: 0.5rem; 
  border-radius: 12px;
  border: 1px solid var(--border);
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}

.tabla-contenedor::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.tabla-contenedor::-webkit-scrollbar-track {
  background: transparent;
}

.tabla-contenedor::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.tabla-contenedor::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.35);
}

.metric-toggle-group {
  display: inline-flex;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}

.metric-toggle-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.metric-toggle-btn:hover {
  color: #fff;
}

.metric-toggle-btn.active {
  background: var(--primary-copy);
  color: #fff;
  box-shadow: 0 0 10px rgba(2, 132, 199, 0.3);
}

table { 
  width: 100%; 
  border-collapse: collapse; 
  font-size: 0.85rem; 
  font-family: var(--font-mono); 
}

th { 
  position: sticky;
  top: 0;
  z-index: 5;
  background: #090e17; 
  color: var(--muted); 
  font-weight: 600; 
  padding: 0.85rem 1.2rem; 
  border-bottom: 1px solid var(--border); 
  text-transform: uppercase; 
  font-size: 0.68rem; 
  letter-spacing: 0.08em; 
  text-align: left;
}

td { 
  padding: 0.9rem 1.2rem; 
  border-bottom: 1px solid var(--border); 
  color: #cbd5e1; 
}

tr { 
  transition: all 0.2s; 
}

tr:hover td { 
  background: rgba(26, 38, 64, 0.25); 
}

.row-ganancia .bold-pnl { color: var(--green); font-weight: 700; }
.row-perdida  .bold-pnl { color: var(--red); font-weight: 700; }

.badge-tabla { 
  background: #1e293b; 
  padding: 0.25rem 0.5rem; 
  border-radius: 6px; 
  font-size: 0.7rem; 
  font-weight: 600; 
  color: #cbd5e1; 
  border: 1px solid rgba(255,255,255,0.05);
}

.badge-razon { 
  font-size: 0.68rem; 
  font-weight: 700; 
  padding: 0.25rem 0.6rem; 
  border-radius: 6px; 
  text-transform: uppercase; 
  font-family: var(--font-mono);
}

.badge-razon.take_profit, .badge-razon.early_exit, .badge-razon.target_sell { 
  background: rgba(16, 185, 129, 0.1); 
  color: var(--green); 
  border: 1px solid rgba(16, 185, 129, 0.2); 
}

.badge-razon.stop_loss { 
  background: rgba(239, 68, 68, 0.1); 
  color: var(--red); 
  border: 1px solid rgba(239, 68, 68, 0.2); 
}

.badge-razon.time_exit, .badge-razon.resolved_exit, .badge-razon.failsafe_sync_exit { 
  background: rgba(245, 158, 11, 0.1); 
  color: var(--amber); 
  border: 1px solid rgba(245, 158, 11, 0.2); 
}

.badge-razon.inactiva { 
  background: rgba(100, 116, 139, 0.1); 
  color: var(--gray); 
  border: 1px solid rgba(100, 116, 139, 0.2); 
}

.txt-truncate { 
  max-width: 380px; 
  white-space: nowrap; 
  overflow: hidden; 
  text-overflow: ellipsis; 
}

.no-data { 
  text-align: center; 
  color: var(--muted); 
  padding: 2.5rem; 
  font-size: 0.85rem; 
  font-style: italic; 
}

.btn-ver-cot-tabla {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0.25rem;
  border-radius: 6px;
  transition: all 0.15s;
}

.btn-ver-cot-tabla:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

/* Modals */
.modal-overlay {
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
}

.modal-overlay.open {
  opacity: 1;
  visibility: visible;
}

.modal-content {
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
}

.modal-overlay.open .modal-content {
  transform: scale(1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  border-bottom: none;
  padding-bottom: 0;
}

.modal-header h3 {
  font-size: 1.35rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.4;
  padding-right: 1.5rem;
  font-family: var(--font-head);
}

.modal-close-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 1.8rem;
  cursor: pointer;
  line-height: 1;
  transition: color 0.15s;
}

.modal-close-btn:hover {
  color: #fff;
}

.modal-status-bar {
  display: flex;
  gap: 1.25rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.modal-grid-specs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
  margin-bottom: 1.75rem;
}

.spec-item {
  background: rgba(8, 12, 20, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.03);
  padding: 0.8rem 1rem;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
}

.spec-label {
  font-size: 0.65rem;
  color: var(--muted);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.spec-value {
  font-size: 0.95rem;
  font-weight: 700;
  font-family: var(--font-mono);
  margin-top: 0.25rem;
  color: #fff;
}

.modal-reasoning-section {
  background: rgba(139, 92, 246, 0.03);
  border: 1px solid rgba(139, 92, 246, 0.1);
  padding: 1.25rem 1.5rem;
  border-radius: 14px;
}

.modal-reasoning-section h4 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a78bfa;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-head);
}

.modal-reasoning-section p {
  font-size: 0.9rem;
  line-height: 1.6;
  color: #cbd5e1;
}

/* Tabs main switcher */
.tab-view {
  transition: opacity 0.3s ease;
  opacity: 1;
}

.hidden-tab-view {
  position: absolute;
  left: -9999px;
  top: -9999px;
  opacity: 0;
  height: 0;
  overflow: hidden;
  pointer-events: none;
}

/* Tab 1 Layout special rules */
.kpi-row-comp {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

@media(max-width: 900px) {
  .kpi-row-comp { grid-template-columns: 1fr; }
}

.panel-comp-agent {
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.5rem;
  position: relative;
}

.panel-comp-agent::after {
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px; border-radius: 0 0 18px 18px;
}

.panel-comp-agent.hib::after { background: var(--primary-hib); }
.panel-comp-agent.copy::after { background: var(--primary-copy); }

.panel-comp-agent h2 {
  font-family: var(--font-head);
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 1.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Whales grid and cards */
.grid-whales {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.card-whale::after {
  background: var(--primary-copy) !important;
}

.breakdown-grid { 
  display: grid; 
  grid-template-columns: 1fr 1fr; 
  gap: 0.75rem; 
}

.bk-item { 
  background: rgba(8, 12, 20, 0.45); 
  border: 1px solid var(--border); 
  border-radius: 10px; 
  padding: 0.85rem; 
  display: flex; 
  align-items: center; 
  gap: 0.75rem; 
}

.bk-dot { 
  width: 8px; 
  height: 8px; 
  border-radius: 50%; 
  flex-shrink: 0; 
}

.bk-label { 
  font-family: var(--font-mono); 
  font-size: 0.72rem; 
  color: var(--muted); 
}

.bk-count { 
  font-family: var(--font-mono); 
  font-size: 1.2rem; 
  font-weight: 700; 
  margin-top: 0.15rem; 
}

.positive { color: var(--green); } 
.negative { color: var(--red); }
.neutral { color: var(--text); }
.bold { font-weight: 700; }

/* Institutional Terminal Additions */
.whale-table th {
  padding: 0.75rem 1rem;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
}
.whale-table td {
  padding: 0.7rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  font-size: 0.82rem;
}
.whale-table tr:hover td {
  background: rgba(2, 132, 199, 0.08);
}
.cat-card {
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  transition: all 0.2s;
}
.cat-card:hover {
  border-color: rgba(2, 132, 199, 0.35);
  transform: translateY(-2px);
}
.custom-select {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid var(--border);
  color: #fff;
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  outline: none;
  cursor: pointer;
}
.custom-select:focus {
  border-color: var(--primary-copy);
}
.btn-csv-export {
  background: rgba(2, 132, 199, 0.12);
  border: 1px solid rgba(2, 132, 199, 0.3);
  color: #38bdf8;
  padding: 0.4rem 0.85rem;
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-csv-export:hover {
  background: rgba(2, 132, 199, 0.25);
  border-color: #38bdf8;
  color: #fff;
}
.hidden-by-limit {
  display: none !important;
}

</style>
</head>
<body>

<nav class="main-navbar">
  <div class="navbar-container">
    <div class="nav-brand">
      <span class="logo-emoji">⚡</span>
      <div class="logo-text">
        <h3>POLYAIDAS TERMINAL</h3>
        <p>Agente Híbrido & Copy-Trading</p>
      </div>
    </div>
    <div class="nav-links">
      <button class="main-nav-btn active" id="nav-btn-comparativo" onclick="switchMainTab('comparativo')">
        <span class="btn-icon">📊</span> Comparativa
      </button>
      <button class="main-nav-btn" id="nav-btn-hibrido" onclick="switchMainTab('hibrido')">
        <span class="btn-icon">🤖</span> Agente Híbrido
      </button>
      <button class="main-nav-btn" id="nav-btn-copy" onclick="switchMainTab('copy')">
        <span class="btn-icon">🎯</span> Agente Copy-Trader
      </button>
    </div>
  </div>
</nav>

<div class="dashboard-wrapper">

  <!-- ========================================== -->
  <!-- TAB 1: COMPARATIVA GENERAL                 -->
  <!-- ========================================== -->
  <div id="view-comparativo" class="tab-view active">
    <header>
      <div class="tab-title-desc">
        <h1>Hybrid AI <span style="color:var(--muted); font-size:1.5rem; font-weight:400;">vs</span> Copy-Trader</h1>
        <p>Comparación en tiempo real de estrategias algorítmicas | Polymarket</p>
      </div>
      <div class="header-meta-container">
        <div class="status-badge">
          <span class="status-dot pulse"></span>
          <span class="status-text">LIVE VS</span>
        </div>
        <div class="meta-header">
          Actualizado: <strong>__ULTIMA_ACTUALIZACION__</strong><br>
          Ciclos: Híbrido <strong>#__CICLOS_HIB__</strong> | Copy <strong>#__CICLOS_COPY__</strong>
        </div>
      </div>
    </header>

    <div class="kpi-row-comp">
      <!-- Hybrid Comp Card -->
      <div class="panel-comp-agent hib">
        <h2>🤖 Agente Híbrido (IA + Vol)</h2>
        <div class="grid-metricas" style="margin-bottom:0; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
          <div class="card-m" style="--accent: var(--primary-hib); --accent-hover: #c084fc; --accent-glow: var(--primary-hib-glow)">
            <h4>Capital Total</h4>
            <div class="val">__NET_EQUITY_HIB_VAL__</div>
            <div class="sub __EQUITY_CLASE_HIB__">__PNL_NET_PCT_HIB__%</div>
          </div>
          <div class="card-m" style="--accent: #a78bfa; --accent-hover: #c084fc; --accent-glow: rgba(167, 139, 250, 0.2)">
            <h4>Retorno 7D</h4>
            <div class="val __PNL_7D_CLASE_HIB__">__PNL_7D_HIB__</div>
            <div class="sub">__ROI_7D_HIB__% · __OPS_7D_HIB__ ops</div>
          </div>
          <div class="card-m" style="--accent: var(--green); --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.2)">
            <h4>Win Rate</h4>
            <div class="val">__WIN_RATE_HIB__%</div>
            <div class="sub">__TOTAL_GANADAS_HIB__W - __TOTAL_PERDIDAS_HIB__L</div>
          </div>
          <div class="card-m" style="--accent: var(--amber); --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
            <h4>Posiciones</h4>
            <div class="val">__ACTIVE_COUNT_HIB__ / __TOTAL_CERRADAS_HIB__</div>
            <div class="sub">Activas / Cerradas</div>
          </div>
        </div>
      </div>

      <!-- Copy Comp Card -->
      <div class="panel-comp-agent copy">
        <h2>🎯 Agente Copy-Trader (Whales)</h2>
        <div class="grid-metricas" style="margin-bottom:0; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
          <div class="card-m" style="--accent: var(--primary-copy); --accent-hover: #7dd3fc; --accent-glow: var(--primary-copy-glow)">
            <h4>Capital Total</h4>
            <div class="val">__NET_EQUITY_COPY_VAL__</div>
            <div class="sub __EQUITY_CLASE_COPY__">__PNL_NET_PCT_COPY__%</div>
          </div>
          <div class="card-m" style="--accent: #38bdf8; --accent-hover: #7dd3fc; --accent-glow: rgba(56, 189, 248, 0.2)">
            <h4>Retorno 7D</h4>
            <div class="val positive">__PNL_7D_COPY__</div>
            <div class="sub">__ROI_7D_COPY__% · __OPS_7D_COPY__ ops</div>
          </div>
          <div class="card-m" style="--accent: var(--green); --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.2)">
            <h4>Win Rate</h4>
            <div class="val">__WIN_RATE_COPY__%</div>
            <div class="sub">__TOTAL_GANADAS_COPY__W - __TOTAL_PERDIDAS_COPY__L</div>
          </div>
          <div class="card-m" style="--accent: var(--primary-copy); --accent-hover: #7dd3fc; --accent-glow: var(--primary-copy-glow)">
            <h4>Posiciones</h4>
            <div class="val">__ACTIVE_COUNT_COPY__ / __TOTAL_CERRADAS_COPY__</div>
            <div class="sub">Activas / Cerradas</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Comparative Chart -->
    <div class="panel">
      <h3>📈 Curva Comparativa de P&L Realizado (USD)</h3>
      <div style="height: 380px; position: relative;">
        <canvas id="chartCompPnl"></canvas>
      </div>
    </div>

    <!-- Double Historial Tables side-by-side -->
    <div class="panel">
      <div class="filter-bar">
        <h3 style="margin-bottom:0; display:flex; align-items:center; gap:0.5rem;">📋 Historial Cruzado de Operaciones</h3>
        <div class="filter-tabs">
          <button class="filter-tab active" id="comp-btn-hib" onclick="switchCompTab('hib')">Historial Híbrido</button>
          <button class="filter-tab" id="comp-btn-copy" onclick="switchCompTab('copy')">Historial Copy-Trading</button>
        </div>
      </div>

      <div id="comp-tab-hib-content">
        <div class="tabla-contenedor">
          <table>
            <thead>
              <tr>
                <th>Fecha Cierre</th>
                <th>Mercado</th>
                <th>Señal</th>
                <th>Monto</th>
                <th>P&L</th>
                <th>Salida</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              __OPS_CERRADAS_HIB_HTML__
            </tbody>
          </table>
        </div>
      </div>

      <div id="comp-tab-copy-content" style="display:none;">
        <div class="tabla-contenedor">
          <table>
            <thead>
              <tr>
                <th>Fecha Cierre</th>
                <th>Mercado</th>
                <th>Resultado</th>
                <th>Monto</th>
                <th>P&L</th>
                <th>Salida</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              __OPS_CERRADAS_COPY_HTML__
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>


  <!-- ========================================== -->
  <!-- TAB 2: DETALLE AGENTE HÍBRIDO              -->
  <!-- ========================================== -->
  <div id="view-hibrido" class="tab-view hidden-tab-view">
    <header>
      <div class="tab-title-desc">
        <h1>🤖 Agente Híbrido <span class="accent-hib">Detalle</span></h1>
        <p>CLOB · Bayesian Calibration · Volatility Filter · LLM Signals</p>
      </div>
      <div class="header-meta-container">
        <div class="status-badge">
          <span class="status-dot pulse"></span>
          <span class="status-text">OPERATIVO</span>
        </div>
        <div class="meta-header">
          Ciclos de Operación: <strong>#__CICLOS_HIB__</strong><br>
          Última corrida local: <strong>__ULTIMA_ACTUALIZACION__</strong><br>
          Posiciones activas: <strong>__ACTIVE_COUNT_HIB__</strong>
        </div>
      </div>
    </header>

    <!-- Métricas detalladas -->
    <div class="grid-metricas">
      <div class="card-m" style="--accent: var(--primary-hib); --accent-hover: #c084fc; --accent-glow: var(--primary-hib-glow)">
        <h4>Capital Disponible</h4>
        <div class="val">__CAPITAL_ACTUAL_HIB__</div>
        <div class="sub">USDC · inicial __CAPITAL_INITIAL_HIB__</div>
      </div>
      <div class="card-m" style="--accent: #38bdf8; --accent-hover: #7dd3fc; --accent-glow: rgba(56, 189, 248, 0.2)">
        <h4>Valor Neto Flotante</h4>
        <div class="val __EQUITY_CLASE_HIB__">__NET_EQUITY_HIB_VAL__</div>
        <div class="sub">Capital + P&L temporal</div>
      </div>
      <div class="card-m" style="--accent: #6366f1; --accent-hover: #818cf8; --accent-glow: var(--primary-comp-glow)">
        <h4>USDC En Riesgo</h4>
        <div class="val" style="color:#818cf8">__CAPITAL_EN_RIESGO_HIB__</div>
        <div class="sub">En __ACTIVE_COUNT_HIB__ posiciones</div>
      </div>
      <div class="card-m" style="--accent: __PNL_COLOR_HIB__; --accent-hover: __PNL_COLOR_HOVER_HIB__; --accent-glow: __PNL_GLOW_HIB__">
        <h4>P&L Realizado</h4>
        <div class="val __PNL_CLASE_HIB__">__PNL_REALIZADO_HIB__</div>
        <div class="sub">__TOTAL_CERRADAS_HIB__ ops cerradas</div>
      </div>
      <div class="card-m" style="--accent: __FLOT_COLOR_HIB__; --accent-hover: __FLOT_COLOR_HOVER_HIB__; --accent-glow: __FLOT_GLOW_HIB__">
        <h4>P&L Temp Flotante</h4>
        <div class="val __FLOT_CLASE_HIB__">__PNL_FLOTANTE_HIB__</div>
        <div class="sub">De posiciones activas</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Win Rate</h4>
        <div class="val" style="color:#fbbf24">__WIN_RATE_HIB__%</div>
        <div class="sub">__TOTAL_GANADAS_HIB__W · __TOTAL_PERDIDAS_HIB__L</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Profit Factor</h4>
        <div class="val __PF_CLASE_HIB__">__PROFIT_FACTOR_HIB__</div>
        <div class="sub">Retorno ganancias/pérdidas</div>
      </div>
      <div class="card-m" style="--accent: var(--green); --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.2)">
        <h4>Avg Win / Loss</h4>
        <div class="val" style="font-size:1.15rem; display:flex; align-items:center; gap:0.4rem; height:2.7rem">
          <span class="positive">+__AVG_WIN_HIB__</span>
          <span style="color:var(--muted); font-weight:400">/</span>
          <span class="negative">__AVG_LOSS_HIB__</span>
        </div>
        <div class="sub">Promedio ganadores/perdedores</div>
      </div>
    </div>

    <!-- Gráficos Row -->
    <div class="row-2">
      <div class="panel">
        <h3>🤖 Curva P&L Acumulado Híbrido</h3>
        <div style="height:320px; position:relative">
          <canvas id="chartHibPnl"></canvas>
        </div>
      </div>
      <div class="panel">
        <h3>🤖 Distribución de Salidas</h3>
        <div style="height:190px; position:relative; margin-bottom:1.25rem">
          <canvas id="chartHibDonut"></canvas>
        </div>
        <div class="breakdown-grid" style="margin-bottom: 1.25rem;">
          <div class="bk-item"><div class="bk-dot" style="background:var(--green)"></div><div><div class="bk-label">TP / Early</div><div class="bk-count" style="color:var(--green)">__N_TP_HIB__</div></div></div>
          <div class="bk-item"><div class="bk-dot" style="background:var(--red)"></div><div><div class="bk-label">Stop Loss</div><div class="bk-count" style="color:var(--red)">__N_SL_HIB__</div></div></div>
          <div class="bk-item"><div class="bk-dot" style="background:var(--amber)"></div><div><div class="bk-label">Time Exit</div><div class="bk-count" style="color:var(--amber)">__N_TIME_HIB__</div></div></div>
          <div class="bk-item"><div class="bk-dot" style="background:var(--gray)"></div><div><div class="bk-label">Inactiva</div><div class="bk-count" style="color:var(--gray)">__N_INACTIVA_HIB__</div></div></div>
        </div>
        <div class="panel-distribucion">
          <h3>Distribución de Señales</h3>
          <div class="yes-no-bar-container">
            <div class="yes-no-bar-yes" style="width: __PCT_YES_HIB__%;"></div>
          </div>
          <div class="yes-no-labels">
            <span class="positive">YES: __YES_COUNT_HIB__ (__PCT_YES_HIB_STR__%)</span>
            <span class="negative">NO: __NO_COUNT_HIB__ (__PCT_NO_HIB_STR__%)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Grid -->
    <div class="panel">
      <h3>🤖 Posiciones Activas Híbrido (__ACTIVE_COUNT_HIB__)</h3>
      <div class="abiertas-wrapper">
        __OPS_ABIERTAS_HIB_HTML__
      </div>
    </div>

    <!-- Historial detailed -->
    <div class="panel">
      <h3>🤖 Historial Detallado de Operaciones Híbrido</h3>
      <div class="filter-bar">
        <div class="search-box">
          <input type="text" id="buscarTablaHib" placeholder="Buscar mercado..." onkeyup="filtrarTabla('Hib')">
        </div>
        <div class="filter-tabs">
          <button class="filter-tab filter-tab-hib active" onclick="setFiltro('todos', 'Hib')">Todos</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('ganancias', 'Hib')">Ganados</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('perdidas', 'Hib')">Perdidos</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('tp', 'Hib')">TP / Early</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('sl', 'Hib')">Stop Loss</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('time', 'Hib')">Time Exit</button>
          <button class="filter-tab filter-tab-hib" onclick="setFiltro('inactiva', 'Hib')">Inactivas</button>
        </div>
      </div>
      <div class="tabla-contenedor">
        <table>
          <thead>
            <tr>
              <th>Fecha Cierre</th><th>Mercado</th><th>Señal</th>
              <th>Monto</th><th>P&L</th><th>Salida</th><th>Detalle</th>
            </tr>
          </thead>
          <tbody id="tablaHibBody">
            __OPS_CERRADAS_HIB_HTML__
          </tbody>
        </table>
      </div>
    </div>
  </div>


  <!-- ========================================== -->
  <!-- TAB 3: DETALLE AGENTE COPY-TRADER          -->
  <!-- ========================================== -->
  <div id="view-copy" class="tab-view hidden-tab-view">
    <header>
      <div class="tab-title-desc">
        <h1>🎯 Agente Copy-Trader <span class="accent-copy">Detalle</span></h1>
        <p>Smart Money Follower · Whale Monitoring · Failsafe Sync Engine</p>
      </div>
      <div class="header-meta-container">
        <div class="status-badge">
          <span class="status-dot pulse" style="background-color:var(--primary-copy); box-shadow:0 0 10px var(--primary-copy)"></span>
          <span class="status-text" style="color:var(--primary-copy)">SEGUIMIENTO ACTIVO</span>
        </div>
        <div class="meta-header">
          Ciclos de Monitoreo: <strong>#__CICLOS_COPY__</strong><br>
          Última corrida local: <strong>__ULTIMA_ACTUALIZACION__</strong><br>
          Posiciones activas: <strong>__ACTIVE_COUNT_COPY__</strong>
        </div>
      </div>
    </header>

    <!-- Métricas Copy Detailed -->
    <div class="grid-metricas">
      <div class="card-m" style="--accent: var(--primary-copy); --accent-hover: #7dd3fc; --accent-glow: var(--primary-copy-glow)">
        <h4>Capital Disponible</h4>
        <div class="val">__CAPITAL_ACTUAL_COPY__</div>
        <div class="sub">USDC · inicial __CAPITAL_INITIAL_COPY__</div>
      </div>
      <div class="card-m" style="--accent: #38bdf8; --accent-hover: #7dd3fc; --accent-glow: rgba(56, 189, 248, 0.2)">
        <h4>Valor Neto Flotante</h4>
        <div class="val __EQUITY_CLASE_COPY__">__NET_EQUITY_COPY_VAL__</div>
        <div class="sub">Capital + P&L temporal</div>
      </div>
      <div class="card-m" style="--accent: #6366f1; --accent-hover: #818cf8; --accent-glow: var(--primary-comp-glow)">
        <h4>USDC En Riesgo</h4>
        <div class="val" style="color:#818cf8">__CAPITAL_EN_RIESGO_COPY__</div>
        <div class="sub">En __ACTIVE_COUNT_COPY__ posiciones</div>
      </div>
      <div class="card-m" style="--accent: __PNL_COLOR_COPY__; --accent-hover: __PNL_COLOR_HOVER_COPY__; --accent-glow: __PNL_GLOW_COPY__">
        <h4>P&L Realizado Total</h4>
        <div class="val __PNL_CLASE_COPY__">__PNL_REALIZADO_COPY__</div>
        <div class="sub">__TOTAL_CERRADAS_COPY__ ops cerradas</div>
      </div>
      <div class="card-m" style="--accent: #10b981; --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.25)">
        <h4>Retorno Hoy (__DIA_NOMBRE_HOY__)</h4>
        <div class="val positive">__PNL_HOY_COPY__</div>
        <div class="sub">__ROI_HOY_COPY__% ROI · __OPS_HOY_COPY__ ops (__WR_HOY_COPY__% WR)</div>
      </div>
      <div class="card-m" style="--accent: #38bdf8; --accent-hover: #7dd3fc; --accent-glow: rgba(56, 189, 248, 0.25)">
        <h4>Retorno Semanal (7D)</h4>
        <div class="val positive">__PNL_7D_COPY__</div>
        <div class="sub">__ROI_7D_COPY__% ROI · __OPS_7D_COPY__ ops (__WR_7D_COPY__% WR)</div>
      </div>
      <div class="card-m" style="--accent: #0284c7; --accent-hover: #38bdf8; --accent-glow: rgba(2, 132, 199, 0.25)">
        <h4>Retorno Mensual (30D)</h4>
        <div class="val positive">__PNL_30D_COPY__</div>
        <div class="sub">__ROI_30D_COPY__% ROI · __OPS_30D_COPY__ ops (__WR_30D_COPY__% WR)</div>
      </div>
      <div class="card-m" style="--accent: #a78bfa; --accent-hover: #c084fc; --accent-glow: rgba(167, 139, 250, 0.2)">
        <h4>Promedio Diario Activo</h4>
        <div class="val" style="color:#c084fc">__AVG_DAILY_PNL_COPY__</div>
        <div class="sub">__AVG_DAILY_ROI_COPY__% / día en periodo activo</div>
      </div>
      <div class="card-m" style="--accent: #34d399; --accent-hover: #6ee7b7; --accent-glow: rgba(52, 211, 153, 0.2)">
        <h4>Expectativa / Trade</h4>
        <div class="val" style="color:#34d399">__EXPECTANCY_COPY__</div>
        <div class="sub">__EXPECTANCY_PCT_COPY__% sobre tamaño medio</div>
      </div>
      <div class="card-m" style="--accent: #f59e0b; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Volatilidad & Sharpe</h4>
        <div class="val" style="font-size:1.15rem; display:flex; align-items:center; gap:0.4rem; height:2.7rem; color:#fbbf24">
          <span>__VOLATILIDAD_COPY__%</span>
          <span style="color:var(--muted); font-weight:400; font-size:0.85rem">/ SR</span>
          <span style="color:#10b981">__SHARPE_COPY__</span>
        </div>
        <div class="sub">Vol diaria / Sharpe anualizado</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Win Rate Global</h4>
        <div class="val" style="color:#fbbf24">__WIN_RATE_COPY__%</div>
        <div class="sub">__TOTAL_GANADAS_COPY__W · __TOTAL_PERDIDAS_COPY__L</div>
      </div>
      <div class="card-m" style="--accent: #10b981; --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.2)">
        <h4>Win Rate Estratégico (TP/SL)</h4>
        <div class="val" style="color:#10b981">__WR_ESTRAT_COPY__%</div>
        <div class="sub">__N_TP_COPY__ TP vs __N_SL_COPY__ SL (Ratio __TP_SL_RATIO_COPY__)</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Profit Factor</h4>
        <div class="val __PF_CLASE_COPY__">__PROFIT_FACTOR_COPY__</div>
        <div class="sub">Ratio Ganancias / Pérdidas</div>
      </div>
      <div class="card-m" style="--accent: #ef4444; --accent-hover: #f87171; --accent-glow: rgba(239, 68, 68, 0.2)">
        <h4>Drawdown Máximo</h4>
        <div class="val negative">__MAX_DRAWDOWN_COPY__%</div>
        <div class="sub">Actual: __CURRENT_DRAWDOWN_COPY__% (0.0% ATH)</div>
      </div>
      <div class="card-m" style="--accent: var(--green); --accent-hover: #34d399; --accent-glow: rgba(16, 185, 129, 0.2)">
        <h4>Avg Win / Loss</h4>
        <div class="val" style="font-size:1.15rem; display:flex; align-items:center; gap:0.4rem; height:2.7rem">
          <span class="positive">+__AVG_WIN_COPY__</span>
          <span style="color:var(--muted); font-weight:400">/</span>
          <span class="negative">__AVG_LOSS_COPY__</span>
        </div>
        <div class="sub">Promedio ganadores/perdedores</div>
      </div>
      <div class="card-m" style="--accent: #8b5cf6; --accent-hover: #c084fc; --accent-glow: rgba(139, 92, 246, 0.2)">
        <h4>Duración Promedio</h4>
        <div class="val" style="color:#c084fc">__DUR_GLOBAL_COPY__h</div>
        <div class="sub">__DUR_WIN_COPY__h Win / __DUR_LOSS_COPY__h Loss</div>
      </div>
    </div>

    <!-- Tabla Interactiva de Whales Seguidos -->
    <div class="panel" style="margin-bottom:2rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
        <h3 style="margin-bottom:0; display:flex; align-items:center; gap:0.5rem;">
          🐳 Monitoreo y Rendimiento por Whale Seguido
        </h3>
        <div class="search-box" style="min-width:280px;">
          <input type="text" id="searchWhales" placeholder="🔍 Buscar whale, nombre o wallet..." onkeyup="filterWhalesTable()">
        </div>
      </div>
      <div class="whale-table-container" style="max-height:420px; overflow-y:auto; border:1px solid var(--border); border-radius:12px;">
        <table class="whale-table" style="width:100%; border-collapse:collapse;">
          <thead style="position:sticky; top:0; background:rgba(8, 12, 28, 0.95); backdrop-filter:blur(8px); z-index:10;">
            <tr>
              <th style="text-align:left;">Whale / Wallet</th>
              <th style="text-align:center;">Activas</th>
              <th style="text-align:center;">Cerradas</th>
              <th style="text-align:center;">Total</th>
              <th style="text-align:center;">Win Rate</th>
              <th style="text-align:right;">P&L Realizado</th>
              <th style="text-align:right;">P&L Flotante</th>
              <th style="text-align:right;">P&L Total</th>
              <th style="text-align:center;">Avg / Op</th>
            </tr>
          </thead>
          <tbody id="tablaWhalesBody">
            __WHALES_TABLE_HTML__
          </tbody>
        </table>
      </div>
    </div>

    <!-- Gráficos Row 1: PnL Acumulado (Día + Hora) y Evolución Diaria de Retornos -->
    <div class="row-2">
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem; flex-wrap:wrap; gap:0.5rem;">
          <h3 style="margin-bottom:0;">🎯 Curva P&L Acumulado Copy-Trader</h3>
          <span style="font-size:0.72rem; color:var(--muted); font-family:var(--font-mono);"><span style="color:#38bdf8;">●</span> Paso regular 1h (Escala Lineal)</span>
        </div>
        <div style="height:320px; position:relative">
          <canvas id="chartCopyPnl"></canvas>
        </div>
      </div>
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem; flex-wrap:wrap; gap:0.5rem;">
          <h3 style="margin-bottom:0;">📅 Evolución del Retorno Diario</h3>
          <div class="metric-toggle-group">
            <button class="metric-toggle-btn active" id="btnToggleUsd" onclick="setDailyView('usd')">$ USD</button>
            <button class="metric-toggle-btn" id="btnToggleRoi" onclick="setDailyView('roi')">% ROI</button>
          </div>
        </div>
        <div style="height:320px; position:relative">
          <canvas id="chartCopyDaily"></canvas>
        </div>
      </div>
    </div>

    <!-- Gráficos Row 2: Drawdown Histórico y Rolling Win Rate -->
    <div class="row-2" style="margin-top:1.5rem;">
      <div class="panel">
        <h3>📉 Curva de Drawdown Histórico (% Caída desde ATH)</h3>
        <div style="height:260px; position:relative">
          <canvas id="chartCopyDrawdown"></canvas>
        </div>
      </div>
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem; flex-wrap:wrap; gap:0.5rem;">
          <h3 style="margin-bottom:0;">🎯 Evolución Dinámica del Win Rate (Ventana Móvil 20 Ops)</h3>
          <span style="font-size:0.72rem; color:var(--muted); font-family:var(--font-mono);"><span style="color:rgba(239, 68, 68, 0.9); font-weight:700;">---</span> Umbral 50%</span>
        </div>
        <div style="height:260px; position:relative">
          <canvas id="chartCopyRollingWr"></canvas>
        </div>
      </div>
    </div>

    <!-- Gráficos Row 3: Distribución de Salidas y Señales -->
    <div class="panel" style="margin-top:1.5rem; margin-bottom:2rem;">
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1.5rem;">
        <div>
          <h3>🎯 Distribución de Salidas Copy</h3>
          <div style="height:190px; position:relative; margin-bottom:1rem">
            <canvas id="chartCopyDonut"></canvas>
          </div>
          <div class="breakdown-grid">
            <div class="bk-item"><div class="bk-dot" style="background:#06b6d4"></div><div><div class="bk-label">Whale Sell</div><div class="bk-count" style="color:#06b6d4">__N_TARGET_SELL_COPY__</div></div></div>
            <div class="bk-item"><div class="bk-dot" style="background:#10b981"></div><div><div class="bk-label">Resolved</div><div class="bk-count" style="color:#10b981">__N_RESOLVED_COPY__</div></div></div>
            <div class="bk-item"><div class="bk-dot" style="background:#f59e0b"></div><div><div class="bk-label">Failsafe Exit</div><div class="bk-count" style="color:#f59e0b">__N_FAILSAFE_COPY__</div></div></div>
          </div>
        </div>
        <div>
          <h3>⚖️ Distribución de Señales</h3>
          <div style="margin-top:2rem;">
            <div class="yes-no-bar-container">
              <div class="yes-no-bar-yes" style="width: __PCT_YES_COPY__%;"></div>
            </div>
            <div class="yes-no-labels" style="margin-top:0.75rem;">
              <span class="positive" style="color:#38bdf8">YES: __YES_COUNT_COPY__ (__PCT_YES_COPY_STR__%)</span>
              <span class="negative">NO: __NO_COUNT_COPY__ (__PCT_NO_COPY_STR__%)</span>
            </div>
            <div style="margin-top:2rem; padding:1rem; background:rgba(8, 12, 20, 0.45); border-radius:10px; border:1px solid var(--border);">
              <div style="font-size:0.75rem; color:var(--muted); font-family:var(--font-mono);">
                💡 <strong>Ratio de Convicción:</strong> Mayoría en <strong>__SEÑAL_DOMINANTE_COPY__</strong> con gestión asimétrica de riesgo.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Panel de Distribución de Sizing Dinámico -->
    <div class="panel" style="margin-bottom:2rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem; flex-wrap:wrap; gap:0.5rem;">
        <h3 style="margin-bottom:0; display:flex; align-items:center; gap:0.5rem;">
          ⚖️ Distribución de Sizing Dinámico (Gestión de Riesgo)
        </h3>
        <div style="display:flex; gap:0.8rem; font-family:var(--font-mono); font-size:0.75rem;">
          <span style="color:var(--muted)">Mín: <strong style="color:#fff">${min_sizing_copy:.2f}</strong></span>
          <span style="color:var(--muted)">Mediana: <strong style="color:#fff">${median_sizing_copy:.2f}</strong></span>
          <span style="color:var(--muted)">Promedio: <strong style="color:#38bdf8">${avg_sizing_copy:.2f}</strong></span>
          <span style="color:var(--muted)">Máx: <strong style="color:#fff">${max_sizing_copy:.2f}</strong></span>
        </div>
      </div>
      
      <div style="height:16px; width:100%; background:rgba(255,255,255,0.04); border-radius:8px; overflow:hidden; display:flex; margin-bottom:1rem; border:1px solid rgba(255,255,255,0.06);">
        <div style="width:__PCT_DEF__%; background:#38bdf8; transition:width 0.5s;" title="Defensivo ($8-$12): __CNT_DEF__ ops (__PCT_DEF__%)"></div>
        <div style="width:__PCT_BAL__%; background:#818cf8; transition:width 0.5s;" title="Equilibrado ($12-$18): __CNT_BAL__ ops (__PCT_BAL__%)"></div>
        <div style="width:__PCT_ASYM__%; background:#c084fc; transition:width 0.5s;" title="Asimétrico ($18-$25): __CNT_ASYM__ ops (__PCT_ASYM__%)"></div>
      </div>
      
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:1rem;">
        <div style="background:rgba(56, 189, 248, 0.05); border:1px solid rgba(56, 189, 248, 0.15); border-radius:10px; padding:0.85rem;">
          <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.75rem; color:#38bdf8; font-weight:600; font-family:var(--font-mono);">
            <span style="width:8px; height:8px; border-radius:50%; background:#38bdf8; display:inline-block;"></span> DEFENSIVO ($8 – $12)
          </div>
          <div style="font-size:1.35rem; font-weight:700; font-family:var(--font-mono); color:#fff; margin-top:0.3rem;">
            __PCT_DEF__% <span style="font-size:0.75rem; color:var(--muted); font-weight:400;">(__CNT_DEF__ ops)</span>
          </div>
          <div style="font-size:0.7rem; color:var(--muted); margin-top:0.2rem;">Protección de capital en mercados volátiles</div>
        </div>
        <div style="background:rgba(129, 140, 248, 0.05); border:1px solid rgba(129, 140, 248, 0.15); border-radius:10px; padding:0.85rem;">
          <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.75rem; color:#818cf8; font-weight:600; font-family:var(--font-mono);">
            <span style="width:8px; height:8px; border-radius:50%; background:#818cf8; display:inline-block;"></span> EQUILIBRADO ($12 – $18)
          </div>
          <div style="font-size:1.35rem; font-weight:700; font-family:var(--font-mono); color:#fff; margin-top:0.3rem;">
            __PCT_BAL__% <span style="font-size:0.75rem; color:var(--muted); font-weight:400;">(__CNT_BAL__ ops)</span>
          </div>
          <div style="font-size:0.7rem; color:var(--muted); margin-top:0.2rem;">Tamaño estándar para operaciones con edge confirmado</div>
        </div>
        <div style="background:rgba(192, 132, 252, 0.05); border:1px solid rgba(192, 132, 252, 0.15); border-radius:10px; padding:0.85rem;">
          <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.75rem; color:#c084fc; font-weight:600; font-family:var(--font-mono);">
            <span style="width:8px; height:8px; border-radius:50%; background:#c084fc; display:inline-block;"></span> ASIMÉTRICO ($18 – $25)
          </div>
          <div style="font-size:1.35rem; font-weight:700; font-family:var(--font-mono); color:#fff; margin-top:0.3rem;">
            __PCT_ASYM__% <span style="font-size:0.75rem; color:var(--muted); font-weight:400;">(__CNT_ASYM__ ops)</span>
          </div>
          <div style="font-size:0.7rem; color:var(--muted); margin-top:0.2rem;">Alta convicción / Máxima recompensa por unidad de riesgo</div>
        </div>
      </div>
    </div>

    <!-- Rendimiento por Categoría de Mercado -->
    <div class="panel" style="margin-bottom:2rem;">
      <h3 style="margin-bottom:1rem; display:flex; align-items:center; gap:0.5rem;">
        🌐 Rendimiento por Categoría de Mercado
      </h3>
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:1rem;">
        __CATEGORIAS_HTML__
      </div>
    </div>

    <!-- Active Grid Copy -->
    <div class="panel">
      <h3>🎯 Posiciones Abiertas Copy-Trader (__ACTIVE_COUNT_COPY__)</h3>
      <div class="abiertas-wrapper">
        __OPS_ABIERTAS_COPY_HTML__
      </div>
    </div>

    <!-- Historial Copy detailed -->
    <div class="panel">
      <h3>🎯 Historial Detallado de Operaciones Copy-Trader</h3>
      <div class="filter-bar" style="flex-wrap:wrap; gap:0.75rem;">
        <div class="search-box" style="flex:1; min-width:240px;">
          <input type="text" id="buscarTablaCopy" placeholder="🔍 Buscar mercado, wallet o resultado..." onkeyup="filtrarTabla('Copy')">
        </div>
        <div class="filter-tabs">
          <button class="filter-tab filter-tab-copy active" onclick="setFiltro('todos', 'Copy')">Todos</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('ganancias', 'Copy')">Ganados</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('perdidas', 'Copy')">Perdidos</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('target_sell', 'Copy')">Whale Sell</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('resolved', 'Copy')">Resolved</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('failsafe', 'Copy')">Failsafe Sync</button>
        </div>
        <div style="display:flex; align-items:center; gap:0.6rem;">
          <select id="limitCopySelect" onchange="cambiarLimiteCopy(this.value)" class="custom-select" title="Límite de filas">
            <option value="25">Ver 25 ops</option>
            <option value="50">Ver 50 ops</option>
            <option value="100">Ver 100 ops</option>
            <option value="all" selected>Ver Todas</option>
          </select>
          <button class="btn-csv-export" onclick="exportarCsvCopy()">📥 Exportar CSV</button>
        </div>
      </div>
      <div class="tabla-contenedor">
        <table>
          <thead>
            <tr>
              <th>Fecha Cierre</th><th>Mercado</th><th>Resultado</th>
              <th>Monto</th><th>P&L</th><th>Salida</th><th>Detalle</th>
            </tr>
          </thead>
          <tbody id="tablaCopyBody">
            __OPS_CERRADAS_COPY_HTML__
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>

<!-- Modal Overlay Unificado -->
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
      <div class="spec-item"><span class="spec-label">Confianza</span><span id="modalConfianza" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Edge Neto</span><span id="modalEdge" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Entrada</span><span id="modalPrecioEnt" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Cierre/Actual</span><span id="modalPrecioAct" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Resultado / P&L</span><span id="modalPnl" class="spec-value"></span></div>
      <div class="spec-item"><span class="spec-label">Tipo Salida</span><span id="modalSalida" class="spec-value"></span></div>
    </div>
    <div class="modal-reasoning-section">
      <h4 id="modalReasoningTitle">🧠 Razonamiento CoT Completo</h4>
      <p id="modalRazonamientoText"></p>
    </div>
  </div>
</div>

<script>
// Main Tab Switching Logic
function switchMainTab(tabId) {
  document.querySelectorAll('.tab-view').forEach(view => {
    view.classList.add('hidden-tab-view');
    view.classList.remove('active');
  });
  document.querySelectorAll('.main-nav-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  const selectedView = document.getElementById('view-' + tabId);
  if (selectedView) {
    selectedView.classList.remove('hidden-tab-view');
    selectedView.classList.add('active');
  }
  
  const selectedBtn = document.getElementById('nav-btn-' + tabId);
  if (selectedBtn) {
    selectedBtn.classList.add('active');
  }
  localStorage.setItem('activeMainTab', tabId);
}

// Side-by-side Historial Switcher (Tab 1 Comparativa)
function switchCompTab(agent) {
  if (agent === 'hib') {
    document.getElementById('comp-btn-hib').classList.add('active');
    document.getElementById('comp-btn-copy').classList.remove('active');
    document.getElementById('comp-tab-hib-content').style.display = 'block';
    document.getElementById('comp-tab-copy-content').style.display = 'none';
  } else {
    document.getElementById('comp-btn-hib').classList.remove('active');
    document.getElementById('comp-btn-copy').classList.add('active');
    document.getElementById('comp-tab-hib-content').style.display = 'none';
    document.getElementById('comp-tab-copy-content').style.display = 'block';
  }
}

// Modal Functions
function abrirModal(datos) {
  const modal = document.getElementById('modalDetalle');
  document.getElementById('modalTitulo').innerHTML = datos.pregunta;
  
  const badge = document.getElementById('modalBadge');
  badge.textContent = datos.senal;
  badge.className = 'badge-senal ' + (datos.senal.includes('NO') ? 'no-signal' : 'yes-signal');
  
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
  
  const reasoningTitle = document.getElementById('modalReasoningTitle');
  if (datos.senal.includes('COPIAR')) {
    reasoningTitle.innerHTML = '🐳 Ejecución de Copy-Trading';
  } else {
    reasoningTitle.innerHTML = '🧠 Razonamiento CoT Completo';
  }
  
  document.getElementById('modalRazonamientoText').innerHTML = datos.razonamiento || 'Sin detalles registrados.';
  modal.classList.add('open');
}

function abrirModalDesdeBtn(btn) {
  const datos = JSON.parse(btn.getAttribute('data-info'));
  abrirModal(datos);
}

function cerrarModal() {
  document.getElementById('modalDetalle').classList.remove('open');
}

document.getElementById('modalDetalle').addEventListener('click', function(e) {
  if (e.target === this) cerrarModal();
});

// Filtering and Search Functions (Independent per Tab)
const filtros = { Hib: 'todos', Copy: 'todos' };

function filterWhalesTable() {
  const query = document.getElementById('searchWhales').value.toLowerCase();
  const rows = document.querySelectorAll('#tablaWhalesBody tr');
  rows.forEach(row => {
    const searchData = row.getAttribute('data-search') || '';
    row.style.display = searchData.includes(query) ? '' : 'none';
  });
}

function cambiarLimiteCopy(val) {
  const rows = document.querySelectorAll('#tablaCopyBody tr');
  const limit = val === 'all' ? rows.length : parseInt(val);
  let visibleCount = 0;
  rows.forEach((row) => {
    // Si ya está filtrada por búsqueda o pestaña, respetarla
    if (row.getAttribute('data-hidden-by-filter') === 'true') {
      row.style.display = 'none';
      return;
    }
    if (visibleCount < limit) {
      row.style.display = '';
      visibleCount++;
    } else {
      row.style.display = 'none';
    }
  });
}

function exportarCsvCopy() {
  const rows = document.querySelectorAll('#tablaCopyBody tr');
  let csv = 'Fecha,Mercado,Resultado,Monto_USDC,PnL_USDC,Salida\\n';
  for (let i = 0; i < rows.length; i++) {
    const cols = rows[i].querySelectorAll('td');
    if (cols.length >= 6) {
      const fecha = cols[0].textContent.trim();
      const mercado = cols[1].textContent.trim().replace(/"/g, '');
      const res = cols[2].textContent.trim();
      const monto = cols[3].textContent.trim().replace('$', '').replace(/,/g, '');
      const pnl = cols[4].textContent.trim().replace('$', '').replace('+', '').replace(/,/g, '');
      const salida = cols[5].textContent.trim();
      csv += [fecha, '"' + mercado + '"', res, monto, pnl, salida].join(',') + '\\n';
    }
  }
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'polymarket_copy_trades.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function setFiltro(tipo, agent) {
  filtros[agent] = tipo;
  document.querySelectorAll('.filter-tab-' + agent.toLowerCase()).forEach(tab => tab.classList.remove('active'));
  event.target.classList.add('active');
  filtrarTabla(agent);
}

function filtrarTabla(agent) {
  const query = document.getElementById('buscarTabla' + agent).value.toLowerCase();
  const rows = document.querySelectorAll('#tabla' + agent + 'Body tr');
  const filtro = filtros[agent];
  
  rows.forEach(row => {
    const nameCell = row.querySelector('.txt-truncate');
    if (!nameCell) return;
    
    const text = nameCell.textContent.toLowerCase();
    const badgeEl = row.querySelector('.badge-razon');
    const razon = badgeEl ? badgeEl.textContent.trim().toUpperCase() : 'EXIT';
    
    const pnlEl = row.querySelector('.bold-pnl');
    const pnl = pnlEl ? parseFloat(pnlEl.textContent.replace('$', '').replace('+', '').replace(/,/g, '')) : 0.0;
    
    let matchesQuery = text.includes(query);
    let matchesFiltro = false;
    
    if (filtro === 'todos') {
      matchesFiltro = true;
    } else if (filtro === 'ganancias') {
      matchesFiltro = pnl >= 0;
    } else if (filtro === 'perdidas') {
      matchesFiltro = pnl < 0;
    } else if (agent === 'Hib') {
      if (filtro === 'tp') matchesFiltro = (razon === 'TAKE_PROFIT' || razon === 'EARLY_EXIT');
      else if (filtro === 'sl') matchesFiltro = razon === 'STOP_LOSS';
      else if (filtro === 'time') matchesFiltro = razon === 'TIME_EXIT';
      else if (filtro === 'inactiva') matchesFiltro = razon === 'INACTIVA';
    } else if (agent === 'Copy') {
      if (filtro === 'target_sell') matchesFiltro = razon === 'TARGET_SELL';
      else if (filtro === 'resolved') matchesFiltro = razon === 'RESOLVED_EXIT';
      else if (filtro === 'failsafe') matchesFiltro = razon === 'FAILSAFE_SYNC_EXIT';
    }
    
    const show = (matchesQuery && matchesFiltro);
    row.setAttribute('data-hidden-by-filter', show ? 'false' : 'true');
    row.style.display = show ? '' : 'none';
  });
  if (agent === 'Copy') {
    const lim = document.getElementById('limitCopySelect');
    if (lim && lim.value !== 'all') {
      cambiarLimiteCopy(lim.value);
    }
  }
}

// Restore active main tab on load
document.addEventListener('DOMContentLoaded', () => {
  const activeTab = localStorage.getItem('activeMainTab') || 'comparativo';
  switchMainTab(activeTab);
});

// Chart.js Configuration
// Chart 1: Comparativa VS
const ctxComp = document.getElementById('chartCompPnl').getContext('2d');
new Chart(ctxComp, {
  type: 'line',
  data: {
    labels: __FECHAS_RENDIMIENTO_COMP__,
    datasets: [
      {
        label: 'Agente Híbrido',
        data: __VALORES_RENDIMIENTO_HIB_COMP__,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.04)',
        fill: true,
        tension: 0.25,
        borderWidth: 2.5,
        pointRadius: 3,
        pointBackgroundColor: '#8b5cf6'
      },
      {
        label: 'Agente Copy-Trader',
        data: __VALORES_RENDIMIENTO_COPY_COMP__,
        borderColor: '#0284c7',
        backgroundColor: 'rgba(2, 132, 199, 0.04)',
        fill: true,
        tension: 0.25,
        borderWidth: 2.5,
        pointRadius: 3,
        pointBackgroundColor: '#0284c7'
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: '#f8fafc', font: { family: 'Inter', size: 12, weight: '500' } }
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleFont: { family: 'Outfit', size: 13, weight: '700' },
        bodyFont: { family: 'Inter', size: 12 },
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(255,255,255,0.03)' },
        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } }
      },
      y: {
        grid: { color: 'rgba(255,255,255,0.03)' },
        ticks: { 
          color: '#94a3b8', 
          font: { family: 'JetBrains Mono', size: 10 },
          callback: function(value) { return '$' + value; }
        }
      }
    }
  }
});

// Chart 2: Híbrido P&L
const ctxHib = document.getElementById('chartHibPnl').getContext('2d');
const gradHib = ctxHib.createLinearGradient(0, 0, 0, 320);
gradHib.addColorStop(0, 'rgba(139, 92, 246, 0.35)');
gradHib.addColorStop(1, 'rgba(139, 92, 246, 0.0)');
new Chart(ctxHib, {
  type: 'line',
  data: {
    labels: __FECHAS_RENDIMIENTO_HIB__,
    datasets: [{
      data: __VALORES_RENDIMIENTO_HIB__,
      borderColor: '#8b5cf6',
      backgroundColor: gradHib,
      borderWidth: 3,
      fill: true,
      tension: 0.35,
      pointBackgroundColor: '#a78bfa',
      pointHoverBackgroundColor: '#ffffff',
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBorderColor: 'transparent'
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: 'JetBrains Mono' } } },
      y: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: 'JetBrains Mono' } } }
    }
  }
});

// Chart 3: Híbrido Donut
new Chart(document.getElementById('chartHibDonut').getContext('2d'), {
  type: 'doughnut',
  data: {
    labels: __DONUT_LABELS_HIB__,
    datasets: [{
      data: __DONUT_DATA_HIB__,
      backgroundColor: __DONUT_COLORS_HIB__,
      borderWidth: 0,
      hoverOffset: 6
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '75%',
    plugins: { legend: { display: false } }
  }
});

// Chart 4: Copy P&L
const ctxCopy = document.getElementById('chartCopyPnl').getContext('2d');
const gradCopy = ctxCopy.createLinearGradient(0, 0, 0, 320);
gradCopy.addColorStop(0, 'rgba(2, 132, 199, 0.35)');
gradCopy.addColorStop(1, 'rgba(2, 132, 199, 0.0)');
new Chart(ctxCopy, {
  type: 'line',
  data: {
    labels: __FECHAS_RENDIMIENTO_COPY__,
    datasets: [{
      data: __VALORES_RENDIMIENTO_COPY__,
      borderColor: '#0284c7',
      backgroundColor: gradCopy,
      borderWidth: 3,
      fill: true,
      tension: 0.35,
      pointBackgroundColor: '#38bdf8',
      pointHoverBackgroundColor: '#ffffff',
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBorderColor: 'transparent'
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: 'JetBrains Mono' } } },
      y: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: 'JetBrains Mono' } } }
    }
  }
});

// Chart 5: Copy Donut
new Chart(document.getElementById('chartCopyDonut').getContext('2d'), {
  type: 'doughnut',
  data: {
    labels: __DONUT_LABELS_COPY__,
    datasets: [{
      data: __DONUT_DATA_COPY__,
      backgroundColor: __DONUT_COLORS_COPY__,
      borderWidth: 0,
      hoverOffset: 6
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '75%',
    plugins: { legend: { display: false } }
  }
});

// Chart 6: Copy Daily P&L (Bar Chart with USD / ROI toggle)
let currentDailyMetric = 'usd';
const dailyLabelsCopy = __DAILY_LABELS_COPY__;
const dailyPnlDataCopy = __DAILY_PNL_COPY__;
const dailyRoiDataCopy = __DAILY_ROI_COPY__;
const dailyColorsCopy = __DAILY_COLORS_COPY__;

const chartCopyDailyInst = new Chart(document.getElementById('chartCopyDaily').getContext('2d'), {
  type: 'bar',
  data: {
    labels: dailyLabelsCopy,
    datasets: [{
      label: 'P&L Diario (USD)',
      data: dailyPnlDataCopy,
      backgroundColor: dailyColorsCopy,
      borderRadius: 6,
      borderWidth: 0
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(ctx) {
            const idx = ctx.dataIndex;
            const pnl = dailyPnlDataCopy[idx];
            const roi = dailyRoiDataCopy[idx];
            return [
              ' P&L: ' + (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2) + ' USD',
              ' Retorno: ' + (roi >= 0 ? '+' : '') + roi.toFixed(2) + '% ROI'
            ];
          }
        }
      }
    },
    scales: {
      x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#94a3b8', font: { size: 10, family: 'JetBrains Mono' } } },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: {
          color: '#94a3b8',
          font: { size: 10, family: 'JetBrains Mono' },
          callback: function(v) { return (currentDailyMetric === 'usd' ? '$' : '') + v + (currentDailyMetric === 'roi' ? '%' : ''); }
        }
      }
    }
  }
});

function setDailyView(metric) {
  currentDailyMetric = metric;
  const btnUsd = document.getElementById('btnToggleUsd');
  const btnRoi = document.getElementById('btnToggleRoi');
  if (btnUsd) btnUsd.classList.toggle('active', metric === 'usd');
  if (btnRoi) btnRoi.classList.toggle('active', metric === 'roi');

  if (metric === 'usd') {
    chartCopyDailyInst.data.datasets[0].label = 'P&L Diario (USD)';
    chartCopyDailyInst.data.datasets[0].data = dailyPnlDataCopy;
  } else {
    chartCopyDailyInst.data.datasets[0].label = 'Retorno Diario (% ROI)';
    chartCopyDailyInst.data.datasets[0].data = dailyRoiDataCopy;
  }
  chartCopyDailyInst.update();
}

// Chart 7: Copy Drawdown (% from Peak)
const ctxDd = document.getElementById('chartCopyDrawdown').getContext('2d');
const gradDd = ctxDd.createLinearGradient(0, 0, 0, 260);
gradDd.addColorStop(0, 'rgba(239, 68, 68, 0.0)');
gradDd.addColorStop(1, 'rgba(239, 68, 68, 0.35)');
new Chart(ctxDd, {
  type: 'line',
  data: {
    labels: __FECHAS_RENDIMIENTO_COPY__,
    datasets: [{
      data: __DRAWDOWN_SERIES_COPY__,
      borderColor: '#ef4444',
      backgroundColor: gradDd,
      borderWidth: 2,
      fill: true,
      tension: 0.25,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointBackgroundColor: '#ef4444'
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(ctx) { return ' Drawdown: ' + ctx.raw.toFixed(2) + '%'; }
        }
      }
    },
    scales: {
      x: { display: false },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: {
          color: '#94a3b8',
          font: { size: 10, family: 'JetBrains Mono' },
          callback: function(v) { return v + '%'; }
        }
      }
    }
  }
});

// Chart 8: Copy Rolling Win Rate (20 ops moving avg with 50% Benchmark)
const rollingWrDataCopy = __ROLLING_WR_SERIES_COPY__;
new Chart(document.getElementById('chartCopyRollingWr').getContext('2d'), {
  type: 'line',
  data: {
    labels: __FECHAS_RENDIMIENTO_COPY__,
    datasets: [
      {
        label: 'Win Rate Móvil (20 ops)',
        data: rollingWrDataCopy,
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.08)',
        borderWidth: 2.5,
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointBackgroundColor: '#10b981'
      },
      {
        label: 'Umbral 50%',
        data: Array(rollingWrDataCopy.length).fill(50),
        borderColor: 'rgba(239, 68, 68, 0.75)',
        borderWidth: 1.5,
        borderDash: [5, 5],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(ctx) {
            if (ctx.datasetIndex === 1) return ' Umbral Base: 50.0%';
            return ' Win Rate (últimas 20): ' + ctx.raw.toFixed(1) + '%';
          }
        }
      }
    },
    scales: {
      x: { display: false },
      y: {
        min: 0,
        max: 100,
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: {
          color: '#94a3b8',
          font: { size: 10, family: 'JetBrains Mono' },
          callback: function(v) { return v + '%'; }
        }
      }
    }
  }
});

</script>
</body>
</html>"""

    # ──────────────────────────────────────────────────────────────
    # 7. INYECTAR DATOS EN EL TEMPLATE
    # ──────────────────────────────────────────────────────────────
    # Reemplazos de metadatos generales
    html_content = html_template.replace("__ULTIMA_ACTUALIZACION__", now_str)
    html_content = html_content.replace("__CICLOS_HIB__", str(n_ciclos_hib))
    html_content = html_content.replace("__CICLOS_COPY__", str(n_ciclos_copy))

    # Reemplazos Híbrido
    html_content = html_content.replace("__CAPITAL_INITIAL_HIB__", f"{capital_inicial_hib:,.0f}")
    html_content = html_content.replace("__CAPITAL_ACTUAL_HIB__", f"${capital_actual_hib:,.2f}")
    html_content = html_content.replace("__NET_EQUITY_HIB_VAL__", f"${equity_hib:,.2f}")
    html_content = html_content.replace("__CAPITAL_EN_RIESGO_HIB__", f"${capital_en_riesgo_hib:,.2f}")
    html_content = html_content.replace("__PNL_REALIZADO_HIB__", f"{'+' if pnl_total_hib>=0 else ''}${pnl_total_hib:,.2f}")
    html_content = html_content.replace("__PNL_FLOTANTE_HIB__", f"{'+' if pnl_flotante_hib>=0 else ''}${pnl_flotante_hib:,.2f}")
    html_content = html_content.replace("__WIN_RATE_HIB__", f"{win_rate_hib * 100:.1f}")
    html_content = html_content.replace("__PROFIT_FACTOR_HIB__", profit_factor_str_hib)
    html_content = html_content.replace("__AVG_WIN_HIB__", f"${avg_win_hib:.2f}")
    html_content = html_content.replace("__AVG_LOSS_HIB__", f"${abs(avg_loss_hib):.2f}")
    html_content = html_content.replace("__TOTAL_GANADAS_HIB__", str(total_ganadas_hib))
    html_content = html_content.replace("__TOTAL_PERDIDAS_HIB__", str(total_perdidas_hib))
    html_content = html_content.replace("__TOTAL_CERRADAS_HIB__", str(total_cerradas_hib))
    html_content = html_content.replace("__ACTIVE_COUNT_HIB__", str(n_abiertas_hib))
    html_content = html_content.replace("__N_TP_HIB__", str(n_tp_calc))
    html_content = html_content.replace("__N_SL_HIB__", str(n_sl_calc))
    html_content = html_content.replace("__N_TIME_HIB__", str(n_time_calc))
    html_content = html_content.replace("__N_INACTIVA_HIB__", str(n_inactiva_calc))
    html_content = html_content.replace("__PCT_YES_HIB__", f"{pct_yes_hib:.1f}")
    html_content = html_content.replace("__PCT_NO_HIB__", f"{pct_no_hib:.1f}")
    html_content = html_content.replace("__PCT_YES_HIB_STR__", f"{pct_yes_hib:.0f}")
    html_content = html_content.replace("__PCT_NO_HIB_STR__", f"{pct_no_hib:.0f}")
    html_content = html_content.replace("__YES_COUNT_HIB__", str(yes_count_hib))
    html_content = html_content.replace("__NO_COUNT_HIB__", str(no_count_hib))

    pnl_clase_hib = "positive" if pnl_total_hib >= 0 else "negative"
    flot_clase_hib = "positive" if pnl_flotante_hib >= 0 else "negative"
    html_content = html_content.replace("__PNL_CLASE_HIB__", pnl_clase_hib)
    html_content = html_content.replace("__FLOT_CLASE_HIB__", flot_clase_hib)
    html_content = html_content.replace("__PF_CLASE_HIB__", profit_factor_clase_hib)
    html_content = html_content.replace("__EQUITY_CLASE_HIB__", "positive" if equity_hib >= capital_inicial_hib else "negative")
    html_content = html_content.replace("__PNL_NET_PCT_HIB__", f"{pnl_net_pct_hib:+.2f}")
    html_content = html_content.replace("__PNL_7D_HIB__", f"{'+' if pnl_7d_hib>=0 else ''}${pnl_7d_hib:,.2f}")
    html_content = html_content.replace("__ROI_7D_HIB__", f"{roi_7d_hib:+.1f}")
    html_content = html_content.replace("__OPS_7D_HIB__", str(ops_7d_hib))
    html_content = html_content.replace("__PNL_7D_CLASE_HIB__", "positive" if pnl_7d_hib >= 0 else "negative")

    html_content = html_content.replace("__PNL_COLOR_HIB__", "var(--green)" if pnl_total_hib>=0 else "var(--red)")
    html_content = html_content.replace("__PNL_COLOR_HOVER_HIB__", "#34d399" if pnl_total_hib>=0 else "#f87171")
    html_content = html_content.replace("__PNL_GLOW_HIB__", "rgba(16, 185, 129, 0.25)" if pnl_total_hib>=0 else "rgba(239, 68, 68, 0.25)")
    html_content = html_content.replace("__FLOT_COLOR_HIB__", "var(--green)" if pnl_flotante_hib>=0 else "var(--red)")
    html_content = html_content.replace("__FLOT_COLOR_HOVER_HIB__", "#34d399" if pnl_flotante_hib>=0 else "#f87171")
    html_content = html_content.replace("__FLOT_GLOW_HIB__", "rgba(16, 185, 129, 0.25)" if pnl_flotante_hib>=0 else "rgba(239, 68, 68, 0.25)")

    html_content = html_content.replace("__OPS_ABIERTAS_HIB_HTML__", ops_abiertas_hib_html)
    html_content = html_content.replace("__OPS_CERRADAS_HIB_HTML__", ops_cerradas_hib_html)

    # Reemplazos Copy-Trader
    html_content = html_content.replace("__CAPITAL_INITIAL_COPY__", f"{capital_inicial_copy:,.0f}")
    html_content = html_content.replace("__CAPITAL_ACTUAL_COPY__", f"${capital_actual_copy:,.2f}")
    html_content = html_content.replace("__NET_EQUITY_COPY_VAL__", f"${equity_copy:,.2f}")
    html_content = html_content.replace("__CAPITAL_EN_RIESGO_COPY__", f"${capital_en_riesgo_copy:,.2f}")
    html_content = html_content.replace("__PNL_REALIZADO_COPY__", f"{'+' if pnl_total_copy>=0 else ''}${pnl_total_copy:,.2f}")
    html_content = html_content.replace("__PNL_FLOTANTE_COPY__", f"{'+' if pnl_flotante_copy>=0 else ''}${pnl_flotante_copy:,.2f}")
    html_content = html_content.replace("__WIN_RATE_COPY__", f"{win_rate_copy * 100:.1f}")
    html_content = html_content.replace("__PROFIT_FACTOR_COPY__", profit_factor_str_copy)
    html_content = html_content.replace("__AVG_WIN_COPY__", f"${avg_win_copy:.2f}")
    html_content = html_content.replace("__AVG_LOSS_COPY__", f"${abs(avg_loss_copy):.2f}")
    html_content = html_content.replace("__TOTAL_GANADAS_COPY__", str(total_ganadas_copy))
    html_content = html_content.replace("__TOTAL_PERDIDAS_COPY__", str(total_perdidas_copy))
    html_content = html_content.replace("__TOTAL_CERRADAS_COPY__", str(total_cerradas_copy))
    html_content = html_content.replace("__ACTIVE_COUNT_COPY__", str(n_abiertas_copy))
    html_content = html_content.replace("__N_TARGET_SELL_COPY__", str(n_target_sell_copy))
    html_content = html_content.replace("__N_RESOLVED_COPY__", str(n_resolved_copy))
    html_content = html_content.replace("__N_FAILSAFE_COPY__", str(n_failsafe_copy))
    html_content = html_content.replace("__PCT_YES_COPY__", f"{pct_yes_copy:.1f}")
    html_content = html_content.replace("__PCT_NO_COPY__", f"{pct_no_copy:.1f}")
    html_content = html_content.replace("__PCT_YES_COPY_STR__", f"{pct_yes_copy:.0f}")
    html_content = html_content.replace("__PCT_NO_COPY_STR__", f"{pct_no_copy:.0f}")
    html_content = html_content.replace("__YES_COUNT_COPY__", str(yes_count_copy))
    html_content = html_content.replace("__NO_COUNT_COPY__", str(no_count_copy))

    pnl_clase_copy = "positive" if pnl_total_copy >= 0 else "negative"
    flot_clase_copy = "positive" if pnl_flotante_copy >= 0 else "negative"
    html_content = html_content.replace("__PNL_CLASE_COPY__", pnl_clase_copy)
    html_content = html_content.replace("__FLOT_CLASE_COPY__", flot_clase_copy)
    html_content = html_content.replace("__PF_CLASE_COPY__", profit_factor_clase_copy)
    html_content = html_content.replace("__EQUITY_CLASE_COPY__", "positive" if equity_copy >= capital_inicial_copy else "negative")
    html_content = html_content.replace("__PNL_NET_PCT_COPY__", f"{pnl_net_pct_copy:+.2f}")

    html_content = html_content.replace("__PNL_COLOR_COPY__", "var(--green)" if pnl_total_copy>=0 else "var(--red)")
    html_content = html_content.replace("__PNL_COLOR_HOVER_COPY__", "#34d399" if pnl_total_copy>=0 else "#f87171")
    html_content = html_content.replace("__PNL_GLOW_COPY__", "rgba(16, 185, 129, 0.25)" if pnl_total_copy>=0 else "rgba(239, 68, 68, 0.25)")
    html_content = html_content.replace("__FLOT_COLOR_COPY__", "var(--green)" if pnl_flotante_copy>=0 else "var(--red)")
    html_content = html_content.replace("__FLOT_COLOR_HOVER_COPY__", "#34d399" if pnl_flotante_copy>=0 else "#f87171")
    html_content = html_content.replace("__FLOT_GLOW_COPY__", "rgba(16, 185, 129, 0.25)" if pnl_flotante_copy>=0 else "rgba(239, 68, 68, 0.25)")

    # Nuevas variables de terminal institucional
    tp_sl_ratio_copy = f"{(n_tp_copy / n_sl_copy):.2f}" if n_sl_copy > 0 else "∞"
    senal_dom = "YES" if pct_yes_copy >= 50 else "NO"
    html_content = html_content.replace("__DIA_NOMBRE_HOY__", dia_nombre_hoy)
    html_content = html_content.replace("__PNL_HOY_COPY__", f"{'+' if pnl_hoy_copy>=0 else ''}${pnl_hoy_copy:,.2f}")
    html_content = html_content.replace("__ROI_HOY_COPY__", f"{roi_hoy_pct_copy:+.1f}")
    html_content = html_content.replace("__OPS_HOY_COPY__", str(ops_hoy_copy))
    html_content = html_content.replace("__WR_HOY_COPY__", f"{wr_hoy_copy:.1f}")

    # Semanal y Mensual Copy
    html_content = html_content.replace("__PNL_7D_COPY__", f"{'+' if pnl_7d_copy>=0 else ''}${pnl_7d_copy:,.2f}")
    html_content = html_content.replace("__ROI_7D_COPY__", f"{roi_7d_copy:+.1f}")
    html_content = html_content.replace("__OPS_7D_COPY__", str(ops_7d_copy))
    html_content = html_content.replace("__WR_7D_COPY__", f"{wr_7d_copy:.1f}")

    html_content = html_content.replace("__PNL_30D_COPY__", f"{'+' if pnl_30d_copy>=0 else ''}${pnl_30d_copy:,.2f}")
    html_content = html_content.replace("__ROI_30D_COPY__", f"{roi_30d_copy:+.1f}")
    html_content = html_content.replace("__OPS_30D_COPY__", str(ops_30d_copy))
    html_content = html_content.replace("__WR_30D_COPY__", f"{wr_30d_copy:.1f}")

    # Promedio Diario, Expectativa, Volatilidad y Sharpe
    html_content = html_content.replace("__AVG_DAILY_PNL_COPY__", f"{'+' if avg_daily_pnl_copy>=0 else ''}${avg_daily_pnl_copy:,.2f}")
    html_content = html_content.replace("__AVG_DAILY_ROI_COPY__", f"{avg_daily_roi_copy:+.2f}")
    html_content = html_content.replace("__EXPECTANCY_COPY__", f"{'+' if expectancy_copy>=0 else ''}${expectancy_copy:,.2f}")
    html_content = html_content.replace("__EXPECTANCY_PCT_COPY__", f"{expectancy_pct_copy:+.1f}")
    html_content = html_content.replace("__VOLATILIDAD_COPY__", f"{volatilidad_copy:.1f}")
    html_content = html_content.replace("__SHARPE_COPY__", f"{sharpe_copy:.2f}")

    html_content = html_content.replace("__WR_ESTRAT_COPY__", f"{win_rate_estrat_copy:.1f}")
    html_content = html_content.replace("__N_TP_COPY__", str(n_tp_copy))
    html_content = html_content.replace("__N_SL_COPY__", str(n_sl_copy))
    html_content = html_content.replace("__TP_SL_RATIO_COPY__", tp_sl_ratio_copy)
    html_content = html_content.replace("__MAX_DRAWDOWN_COPY__", f"{max_drawdown_copy:.1f}")
    html_content = html_content.replace("__CURRENT_DRAWDOWN_COPY__", f"{current_drawdown_copy:.1f}")
    html_content = html_content.replace("__DUR_GLOBAL_COPY__", f"{avg_dur_global_h:.1f}")
    html_content = html_content.replace("__DUR_WIN_COPY__", f"{avg_dur_win_h:.1f}")
    html_content = html_content.replace("__DUR_LOSS_COPY__", f"{avg_dur_loss_h:.1f}")
    html_content = html_content.replace("__SEÑAL_DOMINANTE_COPY__", senal_dom)

    # Dynamic sizing replacements
    html_content = html_content.replace("__PCT_DEF__", f"{pct_def:.1f}")
    html_content = html_content.replace("__PCT_BAL__", f"{pct_bal:.1f}")
    html_content = html_content.replace("__PCT_ASYM__", f"{pct_asym:.1f}")
    html_content = html_content.replace("__CNT_DEF__", str(cnt_def))
    html_content = html_content.replace("__CNT_BAL__", str(cnt_bal))
    html_content = html_content.replace("__CNT_ASYM__", str(cnt_asym))

    # Tablas y Categorías
    html_content = html_content.replace("__WHALES_TABLE_HTML__", whales_table_html)
    html_content = html_content.replace("__CATEGORIAS_HTML__", categorias_html)
    html_content = html_content.replace("__WHALES_GRID_HTML__", whales_html)

    # Gráficos adicionales
    html_content = html_content.replace("__DAILY_LABELS_COPY__", json.dumps(daily_labels_copy))
    html_content = html_content.replace("__DAILY_PNL_COPY__", json.dumps(daily_pnl_copy))
    html_content = html_content.replace("__DAILY_ROI_COPY__", json.dumps(daily_roi_copy))
    html_content = html_content.replace("__DAILY_COLORS_COPY__", json.dumps(daily_colors_copy))
    html_content = html_content.replace("__DRAWDOWN_SERIES_COPY__", json.dumps(drawdown_series_copy if 'drawdown_series_copy' in locals() else []))
    html_content = html_content.replace("__ROLLING_WR_SERIES_COPY__", json.dumps(rolling_wr_series_copy if 'rolling_wr_series_copy' in locals() else []))
    html_content = html_content.replace("__OPS_ABIERTAS_COPY_HTML__", ops_abiertas_copy_html)
    html_content = html_content.replace("__OPS_CERRADAS_COPY_HTML__", ops_cerradas_copy_html)

    # Reemplazos Gráficos y JS Arrays
    html_content = html_content.replace("__FECHAS_RENDIMIENTO_COMP__", json.dumps(chart_labels_comp))
    html_content = html_content.replace("__VALORES_RENDIMIENTO_HIB_COMP__", json.dumps(chart_data_hib_comp))
    html_content = html_content.replace("__VALORES_RENDIMIENTO_COPY_COMP__", json.dumps(chart_data_copy_comp))

    html_content = html_content.replace("__FECHAS_RENDIMIENTO_HIB__", json.dumps(fechas_hib))
    html_content = html_content.replace("__VALORES_RENDIMIENTO_HIB__", json.dumps(valores_hib))

    html_content = html_content.replace("__DONUT_LABELS_HIB__", json.dumps(donut_labels_hib))
    html_content = html_content.replace("__DONUT_DATA_HIB__", json.dumps(donut_data_hib))
    html_content = html_content.replace("__DONUT_COLORS_HIB__", json.dumps(donut_colors_hib))

    html_content = html_content.replace("__FECHAS_RENDIMIENTO_COPY__", json.dumps(fechas_copy))
    html_content = html_content.replace("__VALORES_RENDIMIENTO_COPY__", json.dumps(valores_copy))

    html_content = html_content.replace("__DONUT_LABELS_COPY__", json.dumps(donut_labels_copy))
    html_content = html_content.replace("__DONUT_DATA_COPY__", json.dumps(donut_data_copy))
    html_content = html_content.replace("__DONUT_COLORS_COPY__", json.dumps(donut_colors_copy))

    # Guardar en las tres ubicaciones para compatibilidad y no romper enlaces
    for path in [FILE_OUTPUT_COMPARATIVO, FILE_OUTPUT_HIBRIDO, FILE_INDEX]:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Dashboard guardado con éxito en: {path}")

if __name__ == "__main__":
    generar_dashboard()
