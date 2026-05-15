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
    
    # Manejo seguro del archivo de estado
    balance_actual = 0
    if os.path.exists(PATH_ESTADO):
        with open(PATH_ESTADO, 'r') as f:
            try:
                estado = json.load(f)
                balance_actual = estado.get("balance_total", 0)
            except json.JSONDecodeError:
                pass

    # 2. Calcular métricas clave
    # Usamos .str.upper() para asegurar que atrape 'CERRADA' sin importar mayúsculas/minúsculas
    ops_cerradas = df[df['estado'].astype(str).str.upper() == 'CERRADA']
    
    # Usamos 'pnl_realizado' tal cual está en el CSV del híbrido
    win_rate = (ops_cerradas['pnl_realizado'] > 0).mean() * 100 if not ops_cerradas.empty else 0
    pnl_total = ops_cerradas['pnl_realizado'].sum()

    # 3. Gráficos
    if not ops_cerradas.empty:
        # Gráfico de evolución del Balance (usamos 'fecha_cierre_real')
        fig_balance = px.line(ops_cerradas, x='fecha_cierre_real', y='pnl_realizado', 
                              title="Rendimiento Acumulado (Híbrido)",
                              template="plotly_dark")

        # Gráfico de distribución de beneficios
        fig_dist = px.histogram(ops_cerradas, x="pnl_realizado", 
                                title="Distribución de Ganancias/Pérdidas",
                                color_discrete_sequence=['#00cc96'],
                                template="plotly_dark")
    else:
        # Gráficos vacíos por si aún no hay operaciones cerradas
        fig_balance = px.line(title="Esperando operaciones cerradas...")
        fig_dist = px.histogram(title="Esperando operaciones cerradas...")

    # 4. Generar HTML
    with open(PATH_SALIDA, 'w') as f:
        f.write(f"<html><head><title>Dashboard Agente Híbrido</title></head><body style='background-color:#111111; color:white; font-family:sans-serif; padding: 20px;'>")
        f.write(f"<h1>Resumen Agente Híbrido</h1>")
        f.write(f"<h2>Balance Actual: ${balance_actual:.2f} | Win Rate: {win_rate:.1f}% | PNL Total: ${pnl_total:.2f}</h2>")
        f.write(fig_balance.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(fig_dist.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write("</body></html>")
    
    print(f"Dashboard actualizado exitosamente en: {PATH_SALIDA}")

if __name__ == "__main__":
    generar_dashboard()
