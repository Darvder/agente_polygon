import pandas as pd
import json
import os
import math
from datetime import datetime

# 📁 CONFIGURACIÓN DE RUTAS DEL AGENTE HÍBRIDO
ARCHIVO_LIBRO   = "datos_polymarket/paper_trading/libro_hibrido.csv"
ARCHIVO_ESTADO  = "datos_polymarket/paper_trading/estado_hibrido.json"
ARCHIVO_OUTPUT  = "datos_polymarket/dashboard_hibrido.html"

def calcular_posicion_barra(precio_entrada, precio_actual, tp, sl):
    """
    Calcula matemáticamente el porcentaje de posición del precio actual
    dentro del rango delimitado por el Stop Loss y el Take Profit dinámicos.
    """
    try:
        precio_entrada = float(precio_entrada)
        precio_actual = float(precio_actual)
        tp = float(tp)
        sl = float(sl)
        
        # Calcular los precios objetivos exactos en base a los límites porcentuales
        precio_sl = precio_entrada * (1.0 + sl)  # sl suele ser negativo, ej: -0.03
        precio_tp = precio_entrada * (1.0 + tp)  # tp suele ser positivo, ej: 0.05
        
        rango = precio_tp - precio_sl
        if rango == 0:
            return 50.0
            
        pct = ((precio_actual - precio_sl) / rango) * 100.0
        return max(0.0, min(100.0, pct))  # Clamping entre 0 y 100
    except:
        return 50.0

def generar_dashboard():
    print(f"⏳ Iniciando generación de dashboard híbrido profesional...")
    
    # 1. Valores por defecto para el Estado de la Cartera
    capital_inicial = 1000.0
    capital_actual = 1000.0
    capital_en_riesgo = 0.0
    n_ciclos = 0
    ultima_corrida = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO, "r") as f:
                est = json.load(f)
                capital_actual = float(est.get("capital_actual", capital_actual))
                capital_en_riesgo = float(est.get("capital_en_riesgo", capital_en_riesgo))
                n_ciclos = est.get("n_ciclos", n_ciclos)
                ultima_corrida = est.get("ultima_corrida", ultima_corrida)
        except Exception as e:
            print(f"⚠️ Aviso al cargar estado_hibrido.json: {e}")

    # 2. Lectura y procesamiento robusto del Libro de Órdenes
    ops_abiertas_html = ""
    ops_cerradas_html = ""
    pnl_total = 0.0
    win_rate = 0.0
    total_ganadas = 0
    total_perdidas = 0
    total_cerradas = 0
    
    # Listas para el gráfico histórico de rendimiento
    fechas_rendimiento = []
    valores_rendimiento = []
    pnl_acumulado = 0.0

    if os.path.exists(ARCHIVO_LIBRO):
        try:
            df = pd.read_csv(ARCHIVO_LIBRO)
        except Exception as e:
            print(f"❌ Error crítico leyendo el CSV: {e}")
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    if not df.empty:
        # Estandarizar strings de estado para evitar fallos de formato
        df['estado'] = df['estado'].astype(str).str.strip().str.upper()
        
        # --- PROCESAR POSICIONES ABIERTAS ---
        abiertas = df[df['estado'] == 'ABIERTA']
        if abiertas.empty:
            ops_abiertas_html = '<div class="no-data">No hay posiciones abiertas actualmente. Buscando ineficiencias...</div>'
        else:
            for _, p in abiertas.iterrows():
                # Extraer parámetros dinámicos calculados por el VolatilityEngine
                tp_real = float(p.get('tp_dinamico', 0.05))
                sl_real = float(p.get('sl_dinamico', -0.04))
                
                # Extraer metadatos fundamentales de la señal e IA
                confianza = float(p.get('llm_confianza', 0.50))
                edge = float(p.get('llm_edge', 0.03))
                senal = str(p.get('señal', 'COMPRAR YES'))
                monto = float(p.get('monto_usdc', 0.0))
                
                precio_ent = float(p.get('precio_token_entrada', p.get('precio_entrada', 0.5)))
                precio_act = float(p.get('precio_actual', precio_ent))
                
                # Calcular el rendimiento flotante actual de la posición
                if "YES" in senal.upper():
                    pnl_flotante = (precio_act - precio_ent) * (monto / precio_ent)
                else:
                    pnl_flotante = ((1.0 - precio_act) - precio_ent) * (monto / precio_ent)
                
                pnl_clase = "positive" if pnl_flotante >= 0 else "negative"
                signo_pnl = "+" if pnl_flotante >= 0 else ""
                
                # Calcular dinámicamente el punto móvil de la burbuja
                pct_burbuja = calcular_posicion_barra(precio_ent, precio_act, tp_real, sl_real)
                
                ops_abiertas_html += f"""
                <div class="card-orden animated-fade-in">
                    <div class="card-orden-header">
                        <span class="badge-senal {senal.lower().replace(' ', '-')}">{senal}</span>
                        <span class="monto-orden">${monto:,.2f} USDC</span>
                    </div>
                    <div class="pregunta-titulo">{p['pregunta']}</div>
                    
                    <div class="metadatos-grid">
                        <div class="meta-item">
                            <span class="meta-label">🤖 Confianza IA</span>
                            <span class="meta-value">{confianza:.0%}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">📈 Edge Neto</span>
                            <span class="meta-value">+{edge:.1%}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">⏱️ Tiempo Máx</span>
                            <span class="meta-value">{p.get('horas_max', 24)}h</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">📊 P&L Flotante</span>
                            <span class="meta-value {pnl_clase}">{signo_pnl}${pnl_flotante:+.2f}</span>
                        </div>
                    </div>

                    <div class="riesgo-container">
                        <div class="riesgo-labels">
                            <span class="label-sl">SL: {sl_real:.1%}</span>
                            <span class="label-entry">Entrada: {precio_ent:.2f}</span>
                            <span class="label-tp">TP: {tp_real:.1%}</span>
                        </div>
                        <div class="riesgo-barra-bg">
                            <div class="riesgo-burbuja" style="left: {pct_burbuja}%;" title="Precio Actual: {precio_act:.2f}"></div>
                        </div>
                        <div class="riesgo-precios">
                            <span>${precio_ent * (1.0 + sl_real):.2f}</span>
                            <span style="font-weight: bold; color: #a78bfa;">Actual: ${precio_act:.2f}</span>
                            <span>${precio_ent * (1.0 + tp_real):.2f}</span>
                        </div>
                    </div>
                </div>
                """

        # --- PROCESAR HISTORIAL CERRADO ---
        cerradas = df[df['estado'] == 'CERRADA'].copy()
        if not cerradas.empty:
            # Asegurar orden cronológico para el gráfico histórico
            if 'fecha_cierre_real' in cerradas.columns:
                cerradas['fecha_sort'] = pd.to_datetime(cerradas['fecha_cierre_real'], errors='coerce')
                cerradas = cerradas.sort_values(by='fecha_sort', ascending=True)
            
            total_cerradas = len(cerradas)
            pnl_total = float(df['pnl_realizado'].fillna(0.0).sum())
            
            for _, p in cerradas.iterrows():
                pnl_op = float(p.get('pnl_realizado', 0.0))
                fecha_cierre = str(p.get('fecha_cierre_real', p.get('fecha_entrada', '---')))
                razon = str(p.get('razon_cierre', p.get('razonamiento', 'EXIT'))).upper()
                
                if pnl_op > 0:
                    total_ganadas += 1
                elif pnl_op < 0:
                    total_perdidas += 1
                    
                pnl_acumulado += pnl_op
                fechas_rendimiento.append(fecha_cierre[:10])
                valores_rendimiento.append(round(pnl_acumulado, 2))
                
                clase_row = "row-ganancia" if pnl_op >= 0 else "row-perdida"
                signo_row = "+" if pnl_op >= 0 else ""
                
                ops_cerradas_html += f"""
                <tr class="{clase_row}">
                    <td>{fecha_cierre[:16]}</td>
                    <td class="txt-truncate" title="{p['pregunta']}">{p['pregunta'][:50]}...</td>
                    <td><span class="badge-tabla">{p.get('señal', 'S/S')}</span></td>
                    <td>${float(p.get('monto_usdc', 0.0)):,.2f}</td>
                    <td class="bold-pnl">{signo_row}${pnl_op:,.2f}</td>
                    <td><span class="badge-razon {razon.lower()}">{razon}</span></td>
                </tr>
                """
            win_rate = (total_ganadas / total_cerradas) if total_cerradas > 0 else 0.0
    
    if not ops_cerradas_html:
        ops_cerradas_html = '<tr><td colspan="6" class="no-data">No se registran operaciones cerradas en este ciclo híbrido.</td></tr>'

    # Fallback para gráfico si no hay datos históricos
    if not fechas_rendimiento:
        fechas_rendimiento = [datetime.now().strftime("%Y-%m-%d")]
        valores_rendimiento = [0.0]

    # 3. CONSTRUCCIÓN DE LA PLANTILLA HTML INYECTANDO DATOS DINÁMICOS
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - Agente Híbrido IA</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-principal: #0b0f19;
            --bg-tarjetas: #151f32;
            --bg-lineas: #24344d;
            --accent-purple: #8b5cf6;
            --accent-purple-hover: #a78bfa;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --green-profit: #10b981;
            --red-loss: #ef4444;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }}

        body {{
            background-color: var(--bg-principal);
            color: var(--text-main);
            padding: 2rem;
            line-height: 1.5;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--bg-lineas);
            padding-bottom: 1.5rem;
        }}

        .brand h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .brand h1 span {{
            color: var(--accent-purple);
        }}

        .brand p {{
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }}

        .cron {{
            text-align: right;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .cron strong {{
            color: var(--accent-purple-hover);
        }}

        /* METRICAS GRID */
        .grid-metricas {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .card-metrica {{
            background-color: var(--bg-tarjetas);
            border: 1px solid var(--bg-lineas);
            border-radius: 12px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
        }}

        .card-metrica::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--bg-lineas);
        }}

        .card-metrica.destacada::before {{
            background-color: var(--accent-purple);
        }}

        .card-metrica.profit::before {{
            background-color: var(--green-profit);
        }}

        .card-metrica h4 {{
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.05em;
        }}

        .card-metrica .valor {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-top: 0.5rem;
        }}

        .positive {{ color: var(--green-profit); }}
        .negative {{ color: var(--red-loss); }}

        /* CONTENIDO PRINCIPAL */
        .main-layout {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}

        @media (max-width: 1024px) {{
            .main-layout {{ grid-template-columns: 1fr; }}
        }}

        .panel-bloque {{
            background-color: var(--bg-tarjetas);
            border: 1px solid var(--bg-lineas);
            border-radius: 16px;
            padding: 1.5rem;
        }}

        .panel-bloque h3 {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            color: var(--text-main);
            border-left: 3px solid var(--accent-purple);
            padding-left: 0.5rem;
        }}

        /* TARJETAS DE POSICIONES ABIERTAS */
        .abiertas-wrapper {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .card-orden {{
            background-color: #1c2a42;
            border: 1px solid var(--bg-lineas);
            border-radius: 12px;
            padding: 1.25rem;
            transition: transform 0.2s ease;
        }}

        .card-orden:hover {{
            transform: translateY(-2px);
            border-color: #3b5278;
        }}

        .card-orden-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}

        .badge-senal {{
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            text-transform: uppercase;
        }}

        .badge-senal.comprar-yes {{ background-color: rgba(16, 185, 129, 0.2); color: var(--green-profit); }}
        .badge-senal.comprar-no {{ background-color: rgba(239, 68, 68, 0.2); color: var(--red-loss); }}

        .monto-orden {{
            font-weight: 600;
            color: #e5e7eb;
            font-size: 0.95rem;
        }}

        .pregunta-titulo {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 1rem;
        }}

        .metadatos-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            background-color: rgba(11, 15, 25, 0.4);
            padding: 0.75rem;
            border-radius: 8px;
            margin-bottom: 1.25rem;
        }}

        @media (max-width: 480px) {{
            .metadatos-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}

        .meta-item {{
            display: flex;
            flex-direction: column;
        }}

        .meta-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .meta-value {{
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 0.15rem;
        }}

        /* BARRA DE RIESGO ADAPTATIVA DINÁMICA */
        .riesgo-container {{
            margin-top: 1rem;
            padding-top: 0.5rem;
        }}

        .riesgo-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }}

        .label-sl {{ color: var(--red-loss); font-weight: 600; }}
        .label-tp {{ color: var(--green-profit); font-weight: 600; }}
        .label-entry {{ color: var(--text-muted); }}

        .riesgo-barra-bg {{
            height: 8px;
            background: linear-gradient(to right, var(--red-loss) 0%, #4b5563 35%, #4b5563 65%, var(--green-profit) 100%);
            border-radius: 4px;
            position: relative;
            margin-bottom: 0.4rem;
        }}

        .riesgo-burbuja {{
            width: 14px;
            height: 14px;
            background-color: #ffffff;
            border: 3px solid var(--accent-purple);
            border-radius: 50%;
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 8px rgba(139, 92, 246, 0.8);
            transition: left 0.3s ease;
        }}

        .riesgo-precios {{
            display: flex;
            justify-content: space-between;
            font-size: 0.7rem;
            color: var(--text-muted);
        }}

        /* TABLA HISTORIAL */
        .tabla-contenedor {{
            width: 100%;
            overflow-x: auto;
            margin-top: 1.5rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}

        th {{
            background-color: rgba(11, 15, 25, 0.6);
            color: var(--text-muted);
            font-weight: 600;
            padding: 0.75rem 1rem;
            border-bottom: 2px solid var(--bg-lineas);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--bg-lineas);
            color: #d1d5db;
        }}

        tr:hover td {{
            background-color: rgba(36, 52, 77, 0.3);
        }}

        .row-ganancia .bold-pnl {{ color: var(--green-profit); font-weight: 600; }}
        .row-perdida .bold-pnl {{ color: var(--red-loss); font-weight: 600; }}

        .badge-tabla {{
            background-color: #24344d;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge-razon {{
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
        }}
        .badge-razon.tp_exit {{ background-color: rgba(16, 185, 129, 0.15); color: var(--green-profit); }}
        .badge-razon.sl_exit {{ background-color: rgba(239, 68, 68, 0.15); color: var(--red-loss); }}
        .badge-razon.time_exit {{ background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; }}

        .txt-truncate {{
            max-width: 280px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .no-data {{
            text-align: center;
            color: var(--text-muted);
            padding: 2rem;
            font-size: 0.9rem;
            font-style: italic;
        }}

        /* ANIMACIONES */
        .animated-fade-in {{
            animation: fadeIn 0.4s ease-out forwards;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <h1>🤖 Agente Híbrido <span>v2</span></h1>
            <p>Análisis fundamental de noticias procesado por IA integrado con Momentum & Volatilidad Cuántica</p>
        </div>
        <div class="cron">
            <p>Ciclos Ejecutados: <strong>#{n_ciclos}</strong></p>
            <p>Última actualización: <strong>{ultima_corrida}</strong></p>
        </div>
    </header>

    <div class="grid-metricas">
        <div class="card-metrica destacada">
            <h4>Capital Disponible</h4>
            <div class="valor">${capital_actual:,.2f} USDC</div>
        </div>
        <div class="card-metrica">
            <h4>Capital en Riesgo</h4>
            <div class="valor" style="color: #a78bfa;">${capital_en_riesgo:,.2f} USDC</div>
        </div>
        <div class="card-metrica profit">
            <h4>Rendimiento Neto (P&L)</h4>
            <div class="valor {"positive" if pnl_total >= 0 else "negative"}">
                {"Tiny" if pnl_total == 0 else "+" if pnl_total > 0 else ""}${pnl_total:,.2f}
            </div>
        </div>
        <div class="card-metrica">
            <h4>Efectividad (Win Rate)</h4>
            <div class="valor" style="color: #38bdf8;">{win_rate:.1%}</div>
        </div>
    </div>

    <div class="main-layout">
        <div class="panel-bloque">
            <h3>Curva de Rendimiento Histórico</h3>
            <div style="width: 100%; height: 320px; position: relative; margin-top: 1rem;">
                <canvas id="graficoRendimiento"></canvas>
            </div>
        </div>

        <div class="panel-bloque">
            <h3>Posiciones Activas</h3>
            <div class="abiertas-wrapper">
                {ops_abiertas_html}
            </div>
        </div>
    </div>

    <div class="panel-bloque" style="margin-top: 2rem;">
        <h3>Historial Completo de Operaciones</h3>
        <div class="tabla-contenedor">
            <table>
                <thead>
                    <tr>
                        <th>Fecha Ejecución</th>
                        <th>Mercado / Pregunta Predictiva</th>
                        <th>Señal</th>
                        <th>Monto</th>
                        <th>Resultado Realizado</th>
                        <th>Gatillo Salida</th>
                    </tr>
                </thead>
                <tbody>
                    {ops_cerradas_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('graficoRendimiento').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(fechas_rendimiento)},
                datasets: [{{
                    label: 'P&L Acumulado (USDC)',
                    data: {json.dumps(valores_rendimiento)},
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.08)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.25,
                    pointBackgroundColor: '#a78bfa',
                    pointRadius: 4
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
                        grid: {{ color: '#1f293d' }},
                        ticks: {{ color: '#9ca3af', font: {{ size: 10 }} }}
                    }},
                    y: {{
                        grid: {{ color: '#1f293d' }},
                        ticks: {{ color: '#9ca3af', font: {{ size: 11 }} }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    # Guardar el archivo final renderizado en disco
    try:
        with open(ARCHIVO_OUTPUT, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"✅ Dashboard generado exitosamente en: '{ARCHIVO_OUTPUT}'")
    except Exception as e:
        print(f"❌ Error fatal escribiendo el archivo HTML de salida: {e}")

if __name__ == "__main__":
    generar_dashboard()
