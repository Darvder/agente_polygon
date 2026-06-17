#!/usr/bin/env python3
"""
agente_copytrader.py
Copia las operaciones de los traders más exitosos de Polymarket de forma automatizada (Paper Trading).
Implementa filtros de slippage y sincronización por posiciones abiertas (failsafe).
"""

import os
import json
import time
import logging
import requests
import pandas as pd
from datetime import datetime

# TZ setup
os.environ['TZ'] = 'America/Guayaquil'

# Logger setup
os.makedirs("datos_polymarket/logs", exist_ok=True)
os.makedirs("datos_polymarket/copy_trading", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("datos_polymarket/logs/agente_copytrader.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("copytrader")

# Rutas de archivos
DIR_COPY = "datos_polymarket/copy_trading"
FILE_CONFIG = os.path.join(DIR_COPY, "config_copy.json")
FILE_ESTADO = os.path.join(DIR_COPY, "estado_copy.json")
FILE_LIBRO = os.path.join(DIR_COPY, "libro_copy.csv")
FILE_CACHE = os.path.join(DIR_COPY, "trades_cache.json")

# Columnas oficiales para el libro de copy-trading
COLUMNAS_LIBRO = [
    'fecha_entrada', 'fecha_entrada_dt', 'target_wallet', 'market_id', 'condition_id', 
    'token_id', 'pregunta', 'outcome', 'precio_token_entrada', 'precio_actual', 
    'precio_cierre', 'pct_cambio', 'monto_usdc', 'estado', 'fecha_cierre_real', 
    'pnl_realizado', 'razon_cierre', 'tx_hash'
]

# Configuración por defecto
DEFAULT_CONFIG = {
    "wallets_to_copy": [
        "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb", # mintblade
        "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2", # endlessFate
        "0x26437896ed9dfeb2f69765edcafe8fdceaab39ae"  # Latina
    ],
    "max_positions": 15,
    "capital_per_trade": 20.0,
    "max_slippage": 0.03
}

DEFAULT_ESTADO = {
    "capital_inicial": 1000.0,
    "capital_actual": 1000.0,
    "capital_en_riesgo": 0.0,
    "n_ciclos": 0,
    "ultima_corrida": "—",
    "n_tp": 0,
    "n_sl": 0,
    "n_time": 0
}

# ── Inicializadores de archivos ────────────────────────────────────

def cargar_config():
    if os.path.exists(FILE_CONFIG):
        with open(FILE_CONFIG) as f:
            return json.load(f)
    # Crear por defecto
    with open(FILE_CONFIG, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return DEFAULT_CONFIG

def cargar_estado():
    if os.path.exists(FILE_ESTADO):
        with open(FILE_ESTADO) as f:
            return json.load(f)
    with open(FILE_ESTADO, "w") as f:
        json.dump(DEFAULT_ESTADO, f, indent=2)
    return DEFAULT_ESTADO

def guardar_estado(e):
    with open(FILE_ESTADO, "w") as f:
        json.dump(e, f, indent=2)

def cargar_libro():
    if os.path.exists(FILE_LIBRO):
        try:
            return pd.read_csv(FILE_LIBRO)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=COLUMNAS_LIBRO)
    return pd.DataFrame(columns=COLUMNAS_LIBRO)

def guardar_libro(df):
    df.to_csv(FILE_LIBRO, index=False)

def cargar_cache():
    if os.path.exists(FILE_CACHE):
        with open(FILE_CACHE) as f:
            return set(json.load(f))
    return set()

def guardar_cache(c):
    with open(FILE_CACHE, "w") as f:
        json.dump(list(c), f)

# ── Conectores de API ──────────────────────────────────────────────

def obtener_datos_mercado(condition_id):
    """Consulta la Gamma API para obtener metadatos y precios del mercado."""
    time.sleep(1.0)
    url = "https://gamma-api.polymarket.com/markets"
    try:
        r = requests.get(url, params={"condition_ids": condition_id}, timeout=12)
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception as e:
        log.warning(f"Error consultando Gamma API para condition_id {condition_id[:10]}: {e}")
    return None

def obtener_transacciones_usuario(wallet):
    """Consulta las transacciones de un usuario en la data-api."""
    time.sleep(1.0)
    url = f"https://data-api.polymarket.com/trades"
    try:
        r = requests.get(url, params={"user": wallet}, timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning(f"Error consultando trades para wallet {wallet[:10]}: {e}")
    return []

def obtener_posiciones_usuario(wallet):
    """Consulta la cartera abierta de posiciones del usuario."""
    time.sleep(1.0)
    url = f"https://data-api.polymarket.com/positions"
    try:
        r = requests.get(url, params={"user": wallet}, timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning(f"Error consultando posiciones para wallet {wallet[:10]}: {e}")
    return []

# ── Lógica Principal de Copy-Trading ────────────────────────────────

async def procesar_copy_trading():
    log.info("="*55)
    log.info("🚀 INICIANDO CICLO DE COPY-TRADING v1")
    log.info("="*55)

    config = cargar_config()
    estado = cargar_estado()
    df = cargar_libro()
    cache = cargar_cache()

    wallets = config.get("wallets_to_copy", [])
    capital_por_op = config.get("capital_per_trade", 20.0)
    max_slippage = config.get("max_slippage", 0.03)
    max_posiciones = config.get("max_positions", 15)

    # 1. Auditoría contable defensiva
    if not df.empty:
        df['estado'] = df['estado'].astype(str).str.strip().str.upper()
        monto_riesgo_real = float(df[df['estado'] == 'ABIERTA']['monto_usdc'].sum())
        if float(estado.get("capital_en_riesgo", 0)) != monto_riesgo_real:
            desfase = float(estado.get("capital_en_riesgo", 0)) - monto_riesgo_real
            estado["capital_en_riesgo"] = monto_riesgo_real
            estado["capital_actual"] = round(float(estado.get("capital_actual", 1000.0) + desfase), 2)
            log.info(f"⚖️ [AUDITORÍA] Contabilidad unificada: Riesgo ajustado a ${monto_riesgo_real} USDC.")
            guardar_estado(estado)

    # Contar cupo
    n_abiertas = len(df[df["estado"] == "ABIERTA"]) if not df.empty else 0
    cupo = max_posiciones - n_abiertas
    log.info(f"Cartera Copy-Trading: {n_abiertas}/{max_posiciones} posiciones ocupadas. Cupo restante: {cupo}")

    # 2. Procesar transacciones recientes de cada billetera objetivo
    nuevas_posiciones = []
    
    for wallet in wallets:
        log.info(f"Scouting wallet: {wallet[:15]}...")
        trades = obtener_transacciones_usuario(wallet)
        if not trades:
            continue
            
        # Procesar cronológicamente (antiguas primero)
        trades_ordenados = sorted(trades, key=lambda x: x.get("timestamp", 0))

        for t in trades_ordenados:
            tx_hash = t.get("transactionHash")
            if not tx_hash or tx_hash in cache:
                continue

            side = str(t.get("side")).upper()
            condition_id = t.get("conditionId")
            asset_id = str(t.get("asset"))
            target_price = float(t.get("price", 0))
            pregunta = t.get("title", "")
            outcome_trader = t.get("outcome", "")

            # A. COMPRAR (BUY)
            if side == "BUY":
                if cupo <= 0:
                    # Cartera llena, pero registramos la tx en caché para no evaluarla de nuevo
                    cache.add(tx_hash)
                    continue

                # Comprobar si ya tenemos esta posición abierta para evitar duplicar
                ya_abierta = False
                if not df.empty:
                    ya_abierta = not df[(df["estado"] == "ABIERTA") & (df["token_id"] == asset_id)].empty
                if ya_abierta:
                    cache.add(tx_hash)
                    continue

                # Consultar metadatos en Gamma API
                market = obtener_datos_mercado(condition_id)
                if not market:
                    cache.add(tx_hash)
                    continue

                # Verificar estado del mercado
                if not market.get("active") or market.get("closed"):
                    cache.add(tx_hash)
                    continue

                # Identificar el índice del resultado
                token_ids = json.loads(market.get("clobTokenIds", "[]"))
                try:
                    outcome_idx = token_ids.index(asset_id)
                except ValueError:
                    log.warning(f"No se encontró el token {asset_id[:10]} en la lista del mercado {pregunta[:30]}")
                    cache.add(tx_hash)
                    continue

                # Obtener precios en vivo
                outcome_prices = market.get("outcomePrices")
                if not outcome_prices or outcome_idx >= len(outcome_prices):
                    cache.add(tx_hash)
                    continue

                precio_token_actual = float(outcome_prices[outcome_idx])

                # Comprobar el slippage
                desfase_precio = abs(precio_token_actual - target_price)
                if desfase_precio > max_slippage:
                    log.info(f"⏭️ [{pregunta[:30]}] Slippage excedido: trader={target_price:.3f} | actual={precio_token_actual:.3f} (diff={desfase_precio:.3f} > {max_slippage})")
                    cache.add(tx_hash)
                    continue

                # Validar saldo disponible
                if estado["capital_actual"] < capital_por_op:
                    log.warning("❌ Saldo insuficiente en la cuenta de Copy-Trading para abrir posiciones.")
                    cache.add(tx_hash)
                    continue

                # Abrir posición
                log.info(f"🎯 COPIANDO COMPRA: {pregunta[:40]} | Outcome: {outcome_trader} | Precio: {precio_token_actual:.3f} | Wallet: {wallet[:10]}")
                
                nueva_op = {
                    "fecha_entrada": datetime.now().strftime("%Y-%m-%d"),
                    "fecha_entrada_dt": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "target_wallet": wallet,
                    "market_id": market.get("id"),
                    "condition_id": condition_id,
                    "token_id": asset_id,
                    "pregunta": pregunta[:70],
                    "outcome": outcome_trader,
                    "precio_token_entrada": precio_token_actual,
                    "precio_actual": precio_token_actual,
                    "precio_cierre": "",
                    "pct_cambio": 0.0,
                    "monto_usdc": capital_por_op,
                    "estado": "ABIERTA",
                    "fecha_cierre_real": "",
                    "pnl_realizado": 0.0,
                    "razon_cierre": "",
                    "tx_hash": tx_hash
                }
                
                nuevas_posiciones.append(nueva_op)
                estado["capital_actual"] = round(estado["capital_actual"] - capital_por_op, 2)
                estado["capital_en_riesgo"] = round(estado["capital_en_riesgo"] + capital_por_op, 2)
                cupo -= 1
                cache.add(tx_hash)

            # B. VENDER (SELL)
            elif side == "SELL":
                # Buscar si tenemos esta posición abierta
                if not df.empty:
                    posiciones_a_cerrar = df[(df["estado"] == "ABIERTA") & (df["token_id"] == asset_id)]
                    for idx, pos in posiciones_a_cerrar.iterrows():
                        market = obtener_datos_mercado(condition_id)
                        if market:
                            token_ids = json.loads(market.get("clobTokenIds", "[]"))
                            outcome_prices = market.get("outcomePrices")
                            try:
                                outcome_idx = token_ids.index(asset_id)
                                precio_cierre = float(outcome_prices[outcome_idx])
                            except:
                                precio_cierre = target_price # Fallback al precio del target
                        else:
                            precio_cierre = target_price

                        # Cerrar posición
                        pte = float(pos["precio_token_entrada"])
                        pct = (precio_cierre - pte) / pte
                        pnl = round(float(pos["monto_usdc"]) * pct, 2)

                        df.loc[idx, "estado"] = "CERRADA"
                        df.loc[idx, "precio_cierre"] = precio_cierre
                        df.loc[idx, "pct_cambio"] = round(pct, 4)
                        df.loc[idx, "pnl_realizado"] = pnl
                        df.loc[idx, "razon_cierre"] = "TARGET_SELL"
                        df.loc[idx, "fecha_cierre_real"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                        estado["capital_actual"] = round(estado["capital_actual"] + float(pos["monto_usdc"]) + pnl, 2)
                        estado["capital_en_riesgo"] = round(max(0.0, estado["capital_en_riesgo"] - float(pos["monto_usdc"])), 2)
                        
                        if pnl >= 0: estado["n_tp"] += 1
                        else: estado["n_sl"] += 1

                        log.info(f"🔒 COPIANDO VENTA: {pos['pregunta'][:40]} | Outcome: {pos['outcome']} | Cierre: {precio_cierre:.3f} (PnL: ${pnl:+.2f})")
                
                cache.add(tx_hash)

    # 3. Guardar las nuevas posiciones abiertas
    if nuevas_posiciones:
        df_n = pd.DataFrame(nuevas_posiciones)
        df = pd.concat([df, df_n], ignore_index=True) if not df.empty else df_n
        
    # 4. Actualizar precios de posiciones abiertas y sincronización Failsafe
    if not df.empty:
        abiertas = df[df["estado"] == "ABIERTA"]
        for idx, pos in abiertas.iterrows():
            asset_id = str(pos["token_id"])
            wallet_objetivo = str(pos["target_wallet"])
            cond_id = str(pos["condition_id"])
            m_id = str(pos["market_id"])

            # A. Obtener precio actual del mercado
            market = obtener_datos_mercado(cond_id)
            if not market:
                continue

            token_ids = json.loads(market.get("clobTokenIds", "[]"))
            outcome_prices = market.get("outcomePrices")
            try:
                outcome_idx = token_ids.index(asset_id)
                precio_actual = float(outcome_prices[outcome_idx])
            except:
                precio_actual = float(pos["precio_actual"])

            df.loc[idx, "precio_actual"] = precio_actual

            # B. VALIDACIÓN FAILSAFE: Comprobar si el trader aún mantiene la posición
            positions_trader = obtener_posiciones_usuario(wallet_objetivo)
            mantiene_posicion = False
            for p_obj in positions_trader:
                if str(p_obj.get("asset")) == asset_id and float(p_obj.get("size", 0)) > 0:
                    mantiene_posicion = True
                    break

            # Si el mercado está cerrado o resuelto
            mercado_resuelto = market.get("closed") or not market.get("active")

            if mercado_resuelto or not mantiene_posicion:
                # El trader ya no tiene la posición o el mercado resolvió -> Salida forzada
                pte = float(pos["precio_token_entrada"])
                
                if mercado_resuelto:
                    # Comprobar precio de resolución final (1.0 si ganó, 0.0 si perdió)
                    # En paper trading, si el mercado cerró, vemos cuál es el precio actual
                    # Si Gamma API lo tiene cerrado, el precio reflejará 1 o 0.
                    precio_cierre = precio_actual
                    razon = "RESOLVED_EXIT"
                else:
                    precio_cierre = precio_actual
                    razon = "FAILSAFE_SYNC_EXIT"

                pct = (precio_cierre - pte) / pte
                pnl = round(float(pos["monto_usdc"]) * pct, 2)

                df.loc[idx, "estado"] = "CERRADA"
                df.loc[idx, "precio_cierre"] = precio_cierre
                df.loc[idx, "pct_cambio"] = round(pct, 4)
                df.loc[idx, "pnl_realizado"] = pnl
                df.loc[idx, "razon_cierre"] = razon
                df.loc[idx, "fecha_cierre_real"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                estado["capital_actual"] = round(estado["capital_actual"] + float(pos["monto_usdc"]) + pnl, 2)
                estado["capital_en_riesgo"] = round(max(0.0, estado["capital_en_riesgo"] - float(pos["monto_usdc"])), 2)

                if pnl >= 0: estado["n_tp"] += 1
                else: estado["n_sl"] += 1

                log.info(f"🔒 [FAILSAFE] Salida sincronizada: {pos['pregunta'][:40]} | Motivo: {razon} | Cierre: {precio_cierre:.3f} (PnL: ${pnl:+.2f})")

    # 5. Guardar estado general
    estado["n_ciclos"] += 1
    estado["ultima_corrida"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    guardar_estado(estado)
    guardar_libro(df)
    guardar_cache(cache)

    log.info(f"🏁 FIN DEL CICLO DE COPY-TRADING #{estado['n_ciclos']} | Nuevas: {len(nuevas_posiciones)}")
    log.info("="*55)

if __name__ == "__main__":
    import asyncio
    asyncio.run(procesar_copy_trading())
