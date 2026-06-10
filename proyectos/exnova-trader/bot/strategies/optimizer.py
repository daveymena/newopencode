import pandas as pd

class StrategyOptimizer:
    """
    Clase para mejorar la asertividad de las señales de trading
    mediante confluencia de indicadores.
    """
    
    @staticmethod
    def get_confluence_signal(df):
        """
        Analiza el DataFrame y devuelve una señal basada en confluencia de factores.
        Retorna: 0 (Hold), 1 (Call), 2 (Put)
        """
        if df.empty or len(df) < 2:
            return 0
            
        last_row = df.iloc[-1]
        
        # Factores de confluencia
        score_call = 0
        score_put = 0
        
        # 1. RSI (Sobrevendido/Sobrecomprado)
        if last_row['rsi'] < 30:
            score_call += 2 # Fuerte señal de rebote alcista
        elif last_row['rsi'] > 70:
            score_put += 2 # Fuerte señal de rebote bajista
            
        # 2. Bandas de Bollinger (Rebote en bandas)
        if last_row['close'] < last_row['bb_low']:
            score_call += 2
        elif last_row['close'] > last_row['bb_high']:
            score_put += 2
            
        # 3. Patrones de Velas
        if last_row.get('pattern_hammer', 0) == 1:
            score_call += 1
        if last_row.get('pattern_bullish_engulfing', 0) == 1:
            score_call += 2
            
        # 4. Tendencia (SMA)
        if last_row['close'] > last_row['sma_50']:
            score_call += 1 # Tendencia alcista
        elif last_row['close'] < last_row['sma_50']:
            score_put += 1 # Tendencia bajista
            
        # Umbral de decisión (ajustable)
        THRESHOLD = 3  # Reducido para más operaciones de aprendizaje
        
        if score_call >= THRESHOLD and score_call > score_put:
            return 1 # CALL
        elif score_put >= THRESHOLD and score_put > score_call:
            return 2 # PUT
            
        return 0 # HOLD
