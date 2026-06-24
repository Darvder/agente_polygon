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
            for _, p in cerradas_hib.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                historia_pnl_hib.append({"fecha": fecha, "pnl": round(pnl_acum, 2)})
                
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

                ops_cerradas_hib_html += f"""
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
            for _, p in cerradas_copy.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                pnl_acum += pnl_op
                fecha = str(p.get('fecha_cierre_real', '—'))[:16]
                historia_pnl_copy.append({"fecha": fecha, "pnl": round(pnl_acum, 2)})

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

                ops_cerradas_copy_html += f"""
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
    # 5. PREPARAR DATOS DEL GRÁFICO COMBINADO (VS)
    # ──────────────────────────────────────────────────────────────
    datas_dict = {}
    for h in historia_pnl_hib:
        f = h["fecha"][:10]
        datas_dict.setdefault(f, {})["hib"] = h["pnl"]
    for c in historia_pnl_copy:
        f = c["fecha"][:10]
        datas_dict.setdefault(f, {})["copy"] = c["pnl"]

    fechas_ordenadas = sorted(datas_dict.keys())
    chart_labels_comp = []
    chart_data_hib_comp = []
    chart_data_copy_comp = []
    p_last_hib = 0.0
    p_last_copy = 0.0
    
    for f in fechas_ordenadas:
        val = datas_dict[f]
        if "hib" in val: p_last_hib = val["hib"]
        if "copy" in val: p_last_copy = val["copy"]
        chart_labels_comp.append(f)
        chart_data_hib_comp.append(p_last_hib)
        chart_data_copy_comp.append(p_last_copy)

    if not chart_labels_comp:
        chart_labels_comp = [datetime.now().strftime("%Y-%m-%d")]
        chart_data_hib_comp = [0.0]
        chart_data_copy_comp = [0.0]

    # Individual charts
    fechas_hib = [h["fecha"][:10] for h in historia_pnl_hib] if historia_pnl_hib else [datetime.now().strftime("%Y-%m-%d")]
    valores_hib = [h["pnl"] for h in historia_pnl_hib] if historia_pnl_hib else [0.0]

    fechas_copy = [c["fecha"][:10] for c in historia_pnl_copy] if historia_pnl_copy else [datetime.now().strftime("%Y-%m-%d")]
    valores_copy = [c["pnl"] for c in historia_pnl_copy] if historia_pnl_copy else [0.0]

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
  overflow-x: auto; 
  margin-top: 0.5rem; 
  border-radius: 12px;
  border: 1px solid var(--border);
}

table { 
  width: 100%; 
  border-collapse: collapse; 
  font-size: 0.85rem; 
  font-family: var(--font-mono); 
}

th { 
  background: rgba(8, 12, 20, 0.7); 
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
        <div class="grid-metricas" style="margin-bottom:0;">
          <div class="card-m" style="--accent: var(--primary-hib); --accent-hover: #c084fc; --accent-glow: var(--primary-hib-glow)">
            <h4>Capital Total</h4>
            <div class="val">__NET_EQUITY_HIB_VAL__</div>
            <div class="sub __EQUITY_CLASE_HIB__">__PNL_NET_PCT_HIB__%</div>
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
        <div class="grid-metricas" style="margin-bottom:0;">
          <div class="card-m" style="--accent: var(--primary-copy); --accent-hover: #7dd3fc; --accent-glow: var(--primary-copy-glow)">
            <h4>Capital Total</h4>
            <div class="val">__NET_EQUITY_COPY_VAL__</div>
            <div class="sub __EQUITY_CLASE_COPY__">__PNL_NET_PCT_COPY__%</div>
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
        <h4>P&L Realizado</h4>
        <div class="val __PNL_CLASE_COPY__">__PNL_REALIZADO_COPY__</div>
        <div class="sub">__TOTAL_CERRADAS_COPY__ ops cerradas</div>
      </div>
      <div class="card-m" style="--accent: __FLOT_COLOR_COPY__; --accent-hover: __FLOT_COLOR_HOVER_COPY__; --accent-glow: __FLOT_GLOW_COPY__">
        <h4>P&L Temp Flotante</h4>
        <div class="val __FLOT_CLASE_COPY__">__PNL_FLOTANTE_COPY__</div>
        <div class="sub">De posiciones activas</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Win Rate</h4>
        <div class="val" style="color:#fbbf24">__WIN_RATE_COPY__%</div>
        <div class="sub">__TOTAL_GANADAS_COPY__W · __TOTAL_PERDIDAS_COPY__L</div>
      </div>
      <div class="card-m" style="--accent: #fbbf24; --accent-hover: #fbbf24; --accent-glow: rgba(245, 158, 11, 0.2)">
        <h4>Profit Factor</h4>
        <div class="val __PF_CLASE_COPY__">__PROFIT_FACTOR_COPY__</div>
        <div class="sub">Retorno ganancias/pérdidas</div>
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
    </div>

    <!-- Whales monitored section -->
    <h3 style="font-family:var(--font-mono); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); margin-bottom:1rem; display:flex; align-items:center; gap:0.5rem;">
      🐳 Traders Líderes Seguidos
    </h3>
    <div class="grid-whales">
      __WHALES_GRID_HTML__
    </div>

    <!-- Gráficos Row Copy -->
    <div class="row-2">
      <div class="panel">
        <h3>🎯 Curva P&L Acumulado Copy-Trader</h3>
        <div style="height:320px; position:relative">
          <canvas id="chartCopyPnl"></canvas>
        </div>
      </div>
      <div class="panel">
        <h3>🎯 Distribución de Salidas Copy</h3>
        <div style="height:190px; position:relative; margin-bottom:1.25rem">
          <canvas id="chartCopyDonut"></canvas>
        </div>
        <div class="breakdown-grid" style="margin-bottom: 1.25rem;">
          <div class="bk-item"><div class="bk-dot" style="background:#06b6d4"></div><div><div class="bk-label">Whale Sell</div><div class="bk-count" style="color:#06b6d4">__N_TARGET_SELL_COPY__</div></div></div>
          <div class="bk-item"><div class="bk-dot" style="background:#10b981"></div><div><div class="bk-label">Resolved</div><div class="bk-count" style="color:#10b981">__N_RESOLVED_COPY__</div></div></div>
          <div class="bk-item"><div class="bk-dot" style="background:#f59e0b"></div><div><div class="bk-label">Failsafe Exit</div><div class="bk-count" style="color:#f59e0b">__N_FAILSAFE_COPY__</div></div></div>
        </div>
        <div class="panel-distribucion">
          <h3>Distribución de Señales</h3>
          <div class="yes-no-bar-container">
            <div class="yes-no-bar-yes" style="width: __PCT_YES_COPY__%;"></div>
          </div>
          <div class="yes-no-labels">
            <span class="positive" style="color:#38bdf8">YES: __YES_COUNT_COPY__ (__PCT_YES_COPY_STR__%)</span>
            <span class="negative">NO: __NO_COUNT_COPY__ (__PCT_NO_COPY_STR__%)</span>
          </div>
        </div>
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
      <div class="filter-bar">
        <div class="search-box">
          <input type="text" id="buscarTablaCopy" placeholder="Buscar mercado..." onkeyup="filtrarTabla('Copy')">
        </div>
        <div class="filter-tabs">
          <button class="filter-tab filter-tab-copy active" onclick="setFiltro('todos', 'Copy')">Todos</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('ganancias', 'Copy')">Ganados</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('perdidas', 'Copy')">Perdidos</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('target_sell', 'Copy')">Whale Sell</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('resolved', 'Copy')">Resolved</button>
          <button class="filter-tab filter-tab-copy" onclick="setFiltro('failsafe', 'Copy')">Failsafe Sync</button>
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
    
    row.style.display = (matchesQuery && matchesFiltro) ? '' : 'none';
  });
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

    html_content = html_content.replace("__WHALES_GRID_HTML__", whales_html)
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
