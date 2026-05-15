import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# Configuración de rutas para el Agente Híbrido
PATH_LIBRO = "datos_polymarket/paper_trading/libro_hibrido.csv"
PATH_ESTADO = "datos_polymarket/paper_trading/estado_hibrido.json"
PATH_SALIDA = "datos_polymarket/dashboard_hibrido.html"

def generar_dashboard():
    if not os.path.exists(PATH_LIBRO):
        print("No se encontró el libro de órdenes del agente híbrido.")
        return

    # 1. Cargar datos
    df = pd.read_csv(PATH_LIBRO)
    with open(PATH_ESTADO, 'r') as f:
        estado = json.load(f)

    # 2. Calcular métricas clave
    balance_actual = estado.get("balance_total", 0)
    ops_cerradas = df[df['estado'] == 'cerrado']
    win_rate = (ops_cerradas['pnl_final'] > 0).mean() * 100 if not ops_cerradas.empty else 0
    pnl_total = ops_cerradas['pnl_final'].sum()

    # 3. Gráfico de evolución del Balance
    # (Asumiendo que el libro tiene timestamps de cierre)
    fig_balance = px.line(ops_cerradas, x='fecha_cierre', y='pnl_final', 
                          title="Rendimiento Acumulado (Híbrido)",
                          template="plotly_dark")

    # 4. Gráfico de distribución de beneficios
    fig_dist = px.histogram(ops_cerradas, x="pnl_final", 
                            title="Distribución de Ganancias/Pérdidas",
                            color_discrete_sequence=['#00cc96'],
                            template="plotly_dark")

    # 5. Generar HTML
    with open(PATH_SALIDA, 'w') as f:
        f.write(f"<html><head><title>Dashboard Agente Híbrido</title></head><body>")
        f.write(f"<h1 style='font-family:sans-serif;'>Resumen Agente Híbrido</h1>")
        f.write(f"<p>Balance Actual: ${balance_actual:.2f} | Win Rate: {win_rate:.1f}% | PNL Total: ${pnl_total:.2f}</p>")
        f.write(fig_balance.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(fig_dist.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write("</body></html>")
    
    print(f"Dashboard actualizado en: {PATH_SALIDA}")

if __name__ == "__main__":
    generar_dashboard()
