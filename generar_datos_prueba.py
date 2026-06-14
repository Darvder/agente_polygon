# generar_datos_prueba.py
import os
import json
import pandas as pd
from datetime import datetime, timedelta

DIR_DATOS = "datos_polymarket/paper_trading"
ARCHIVO_LIBRO = os.path.join(DIR_DATOS, "libro_hibrido.csv")
ARCHIVO_ESTADO = os.path.join(DIR_DATOS, "estado_hibrido.json")

def generar_datos():
    os.makedirs(DIR_DATOS, exist_ok=True)
    
    # 1. Generar estado_hibrido.json
    estado = {
        "capital_inicial": 1000.0,
        "capital_actual": 978.50,
        "capital_en_riesgo": 40.00,
        "n_ciclos": 127,
        "ultima_corrida": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_tp": 18,
        "n_sl": 6,
        "n_time": 3
    }
    with open(ARCHIVO_ESTADO, "w") as f:
        json.dump(estado, f, indent=2)
    print(f"✅ Generado: {ARCHIVO_ESTADO}")

    # 2. Generar libro_hibrido.csv
    ahora = datetime.now()
    
    # Lista de columnas requeridas por el libro
    columnas = [
        'fecha_entrada', 'fecha_entrada_dt', 'market_id', 'pregunta', 'señal', 
        'precio_entrada', 'precio_token_entrada', 'precio_actual', 'precio_cierre', 
        'pct_cambio', 'llm_estimacion', 'llm_confianza', 'llm_edge', 'hay_noticia', 
        'n_noticias', 'monto_usdc', 'dias_mercado', 'fecha_cierre_mercado', 
        'fecha_cierre_real', 'pnl_realizado', 'estado', 'razon_cierre', 
        'razonamiento', 'tp_dinamico', 'sl_dinamico', 'horas_max', 'vol_1d', 'momentum_1h'
    ]
    
    trades = [
        # --- POSICIONES ABIERTAS ---
        {
            'fecha_entrada': (ahora - timedelta(hours=4)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'm1',
            'pregunta': 'Will Bitcoin reach $110,000 in June 2026?',
            'señal': 'COMPRAR YES',
            'precio_entrada': 0.450,
            'precio_token_entrada': 0.450,
            'precio_actual': 0.520,  # floating profit
            'precio_cierre': None,
            'pct_cambio': None,
            'llm_estimacion': 0.65,
            'llm_confianza': 0.85,
            'llm_edge': 0.20,
            'hay_noticia': True,
            'n_noticias': 4,
            'monto_usdc': 20.00,
            'dias_mercado': 14,
            'fecha_cierre_mercado': (ahora + timedelta(days=14)).strftime("%Y-%m-%d"),
            'fecha_cierre_real': None,
            'pnl_realizado': None,
            'estado': 'ABIERTA',
            'razon_cierre': None,
            'razonamiento': 'Strong institutional inflows and bullish momentum indicators support positive breakout probabilities above market pricing.',
            'tp_dinamico': 0.12,
            'sl_dinamico': -0.06,
            'horas_max': 24,
            'vol_1d': 0.0042,
            'momentum_1h': 0.012
        },
        {
            'fecha_entrada': (ahora - timedelta(hours=8)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'm2',
            'pregunta': 'Will OpenAI announce GPT-5 before July?',
            'señal': 'COMPRAR NO',
            'precio_entrada': 0.600,
            'precio_token_entrada': 0.600,
            'precio_actual': 0.550,  # floating loss (buying NO means our token value is 1 - price_yes. Entry at 1-0.60 = 0.40. Actual price_yes = 0.65 -> token is 0.35)
            'precio_cierre': None,
            'pct_cambio': None,
            'llm_estimacion': 0.35,
            'llm_confianza': 0.72,
            'llm_edge': 0.25,
            'hay_noticia': False,
            'n_noticias': 1,
            'monto_usdc': 20.00,
            'dias_mercado': 20,
            'fecha_cierre_mercado': (ahora + timedelta(days=20)).strftime("%Y-%m-%d"),
            'fecha_cierre_real': None,
            'pnl_realizado': None,
            'estado': 'ABIERTA',
            'razon_cierre': None,
            'razonamiento': 'Internal leaks and development cycle constraints suggest a delayed release timeline, making the YES contract overpriced.',
            'tp_dinamico': 0.10,
            'sl_dinamico': -0.05,
            'horas_max': 48,
            'vol_1d': 0.0028,
            'momentum_1h': -0.005
        },
        # --- POSICIONES CERRADAS ---
        {
            'fecha_entrada': (ahora - timedelta(days=4)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(days=4)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'c1',
            'pregunta': 'Will Apple release a folding phone in 2026?',
            'señal': 'COMPRAR NO',
            'precio_entrada': 0.750,
            'precio_token_entrada': 0.250, # 1 - 0.75
            'precio_actual': 0.280,
            'precio_cierre': 0.280,
            'pct_cambio': 0.12,
            'llm_estimacion': 0.10,
            'llm_confianza': 0.90,
            'llm_edge': 0.15,
            'hay_noticia': True,
            'n_noticias': 5,
            'monto_usdc': 20.00,
            'dias_mercado': 120,
            'fecha_cierre_mercado': '2026-10-31',
            'fecha_cierre_real': (ahora - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
            'pnl_realizado': 2.40,
            'estado': 'CERRADA',
            'razon_cierre': 'TAKE_PROFIT',
            'razonamiento': 'Supply chain bottlenecks and lack of prototype leaks confirm Apple foldables are pushed to at least 2027.',
            'tp_dinamico': 0.10,
            'sl_dinamico': -0.05,
            'horas_max': 72,
            'vol_1d': 0.0015,
            'momentum_1h': 0.001
        },
        {
            'fecha_entrada': (ahora - timedelta(days=3)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'c2',
            'pregunta': 'Will NASA launch Artemis II in September?',
            'señal': 'COMPRAR YES',
            'precio_entrada': 0.500,
            'precio_token_entrada': 0.500,
            'precio_actual': 0.460,
            'precio_cierre': 0.460,
            'pct_cambio': -0.08,
            'llm_estimacion': 0.62,
            'llm_confianza': 0.75,
            'llm_edge': 0.12,
            'hay_noticia': True,
            'n_noticias': 3,
            'monto_usdc': 20.00,
            'dias_mercado': 90,
            'fecha_cierre_mercado': '2026-09-30',
            'fecha_cierre_real': (ahora - timedelta(days=2, hours=12)).strftime("%Y-%m-%d %H:%M"),
            'pnl_realizado': -1.60,
            'estado': 'CERRADA',
            'razon_cierre': 'STOP_LOSS',
            'razonamiento': 'Test results for hardware safety thresholds triggered a temporary pause, dropping immediate launch probability.',
            'tp_dinamico': 0.10,
            'sl_dinamico': -0.07,
            'horas_max': 96,
            'vol_1d': 0.0035,
            'momentum_1h': -0.015
        },
        {
            'fecha_entrada': (ahora - timedelta(days=2)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'c3',
            'pregunta': 'Will SpaceX fly Starship Flight 5 this week?',
            'señal': 'COMPRAR YES',
            'precio_entrada': 0.650,
            'precio_token_entrada': 0.650,
            'precio_actual': 0.650,
            'precio_cierre': 0.650,
            'pct_cambio': 0.00,
            'llm_estimacion': 0.75,
            'llm_confianza': 0.88,
            'llm_edge': 0.10,
            'hay_noticia': False,
            'n_noticias': 2,
            'monto_usdc': 20.00,
            'dias_mercado': 5,
            'fecha_cierre_mercado': '2026-06-20',
            'fecha_cierre_real': (ahora - timedelta(days=1, hours=20)).strftime("%Y-%m-%d %H:%M"),
            'pnl_realizado': 0.00,
            'estado': 'CERRADA',
            'razon_cierre': 'INACTIVA',
            'razonamiento': 'No regulatory launch approval changes occurred, leading to price stagnation and capital preservation exit.',
            'tp_dinamico': 0.12,
            'sl_dinamico': -0.06,
            'horas_max': 24,
            'vol_1d': 0.0002,
            'momentum_1h': 0.000
        },
        {
            'fecha_entrada': (ahora - timedelta(days=1)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'c4',
            'pregunta': 'Will the FED cut interest rates in June?',
            'señal': 'COMPRAR YES',
            'precio_entrada': 0.400,
            'precio_token_entrada': 0.400,
            'precio_actual': 0.448,
            'precio_cierre': 0.448,
            'pct_cambio': 0.12,
            'llm_estimacion': 0.55,
            'llm_confianza': 0.80,
            'llm_edge': 0.15,
            'hay_noticia': True,
            'n_noticias': 6,
            'monto_usdc': 20.00,
            'dias_mercado': 12,
            'fecha_cierre_mercado': '2026-06-30',
            'fecha_cierre_real': (ahora - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M"),
            'pnl_realizado': 2.40,
            'estado': 'CERRADA',
            'razon_cierre': 'EARLY_EXIT',
            'razonamiento': 'CPI inflation cooling down released positive momentum. Hit 80% of TP target in less than 20% of maximum time.',
            'tp_dinamico': 0.15,
            'sl_dinamico': -0.08,
            'horas_max': 72,
            'vol_1d': 0.0055,
            'momentum_1h': 0.024
        },
        {
            'fecha_entrada': (ahora - timedelta(days=2)).strftime("%Y-%m-%d"),
            'fecha_entrada_dt': (ahora - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            'market_id': 'c5',
            'pregunta': 'Will Google DeepMind release AlphaFold 4 today?',
            'señal': 'COMPRAR YES',
            'precio_entrada': 0.200,
            'precio_token_entrada': 0.200,
            'precio_actual': 0.120,
            'precio_cierre': 0.120,
            'pct_cambio': -0.40,
            'llm_estimacion': 0.35,
            'llm_confianza': 0.65,
            'llm_edge': 0.15,
            'hay_noticia': False,
            'n_noticias': 0,
            'monto_usdc': 20.00,
            'dias_mercado': 1,
            'fecha_cierre_mercado': '2026-06-13',
            'fecha_cierre_real': (ahora - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
            'pnl_realizado': -8.00,
            'estado': 'CERRADA',
            'razon_cierre': 'TIME_EXIT',
            'razonamiento': 'Max retention time reached without release announcements. Stated probability decayed to baseline.',
            'tp_dinamico': 0.25,
            'sl_dinamico': -0.15,
            'horas_max': 48,
            'vol_1d': 0.0018,
            'momentum_1h': -0.002
        }
    ]
    
    df = pd.DataFrame(trades, columns=columnas)
    df.to_csv(ARCHIVO_LIBRO, index=False)
    print(f"✅ Generado: {ARCHIVO_LIBRO}")

if __name__ == "__main__":
    generar_datos()
