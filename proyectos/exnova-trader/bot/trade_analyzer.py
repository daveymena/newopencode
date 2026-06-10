import pandas as pd
import numpy as np

class TradeAnalyzer:
    def __init__(self):
        pass

    def analyze_loss(self, entry_candle, exit_candle, trade_direction, subsequent_candles):
        """
        Analiza una operación perdedora para determinar si vale la pena aplicar Martingala.
        
        Args:
            entry_candle: Vela de entrada.
            exit_candle: Vela de salida (resultado).
            trade_direction: "call" o "put".
            subsequent_candles: DataFrame con velas posteriores al cierre (para ver si fue timing).
            
        Returns:
            dict: {
                "should_martingale": bool,
                "reason": str,
                "suggested_action": str
            }
        """
        entry_price = entry_candle['close']
        exit_price = exit_candle['close']
        
        # 1. Análisis de Dirección (¿Cambio de tendencia?)
        # Si la operación fue CALL y el precio se desplomó fuertemente, es un cambio de tendencia.
        # Definimos "fuerte" como más de 2 veces el tamaño promedio del cuerpo de las velas recientes (aprox).
        
        price_diff = exit_price - entry_price
        is_trend_reversal = False
        
        if trade_direction == "call" and price_diff < -0.0005: # Valor hardcoded por ahora, idealmente dinámico (ATR)
            is_trend_reversal = True
        elif trade_direction == "put" and price_diff > 0.0005:
            is_trend_reversal = True
            
        if is_trend_reversal:
            return {
                "should_martingale": False,
                "reason": "Cambio de tendencia fuerte en contra.",
                "suggested_action": "reset"
            }

        # 2. Análisis de Timing (¿Ruido?)
        # Si en las siguientes velas el precio se movió a favor, fue solo un problema de timing.
        if not subsequent_candles.empty:
            max_favorable = 0
            if trade_direction == "call":
                max_favorable = subsequent_candles['high'].max() - entry_price
            else:
                max_favorable = entry_price - subsequent_candles['low'].min()
            
            if max_favorable > 0:
                return {
                    "should_martingale": True,
                    "reason": "Error de timing. El precio se movió a favor poco después.",
                    "suggested_action": "martingale_same_direction"
                }

        # 3. Análisis de Volatilidad (Ruido normal)
        # Si la pérdida fue pequeña, asumimos ruido de mercado.
        return {
            "should_martingale": True,
            "reason": "Pérdida pequeña (ruido de mercado).",
            "suggested_action": "martingale_same_direction"
        }
