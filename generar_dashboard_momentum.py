def generar():
    e, df = cargar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- CÁLCULOS DE CAPITAL ---
    capital_inicial = e.get("capital_inicial", 1000)
    capital_actual = e.get("capital_actual", 1000)
    capital_en_riesgo = e.get("capital_en_riesgo", 0)
    
    # Patrimonio Neto (Equity): Lo que realmente tienes hoy
    patrimonio_neto = capital_actual + capital_en_riesgo
    # P&L Neto Absoluto: Ganancia/Pérdida real respecto al inicio
    pnl_neto_absoluto = patrimonio_neto - capital_inicial
    ret_neto = (pnl_neto_absoluto / capital_inicial) * 100

    ab = df[df["estado"]=="ABIERTA"] if not df.empty else pd.DataFrame()
    ce = df[df["estado"]=="CERRADA"] if not df.empty else pd.DataFrame()

    # P&L Realizado (solo de trades cerrados)
    pnl_realizado_total = ce["pnl_realizado"].sum() if not ce.empty else 0
    
    # --- GRÁFICO ---
    labels_s, labels_f, values = build_pnl_series(df)
    # El gráfico se pone rojo si el P&L acumulado actual es negativo
    chart_color = "#10b981" if (values[-1] if values else 0) >= 0 else "#ef4444"

    # --- MÉTRICAS EXTRA ---
    wins = (ce["pnl_realizado"] > 0).sum() if not ce.empty else 0
    wr = wins / len(ce) if not ce.empty else 0
    
    # Drawdown (Simplificado: caída desde el pico del gráfico)
    max_pico = max(values) if values else 0
    current_val = values[-1] if values else 0
    drawdown = current_val - max_pico

    # ... [Resto de las funciones de HTML] ...