"""
Feature Engineer - Indicadores técnicos para el bot v3.0
"""
import pandas as pd
import numpy as np

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


class FeatureEngineer:
    def __init__(self):
        pass

    def add_technical_indicators(self, df):
        """Agrega indicadores técnicos al DataFrame."""
        if df.empty:
            return df
        
        df = df.copy()

        # 1. RSI (Relative Strength Index)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

        # 2. MACD (Moving Average Convergence Divergence)
        macd = ta.trend.MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()

        # 3. Bollinger Bands
        bollinger = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_high'] = bollinger.bollinger_hband()
        df['bb_low'] = bollinger.bollinger_lband()
        df['bb_width'] = (df['bb_high'] - df['bb_low']) / df['close']

        # 4. SMA (Simple Moving Averages)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()

        # 5. ATR (Average True Range) - Volatilidad
        df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

        # Limpiar NaNs solo en columnas críticas (no eliminar todo por SMA_50)
        # Rellenar NaN en SMA_50 con SMA_20 si no hay suficientes datos
        if 'sma_50' in df.columns:
            df['sma_50'] = df['sma_50'].fillna(df['sma_20'])
        
        # Fill NaN in sma_20 with close price if there are not enough data for SMA_20
        df['sma_20'] = df['sma_20'].fillna(df['close'])

        # Eliminar solo filas donde falten indicadores críticos
        critical_cols = ['rsi', 'macd', 'bb_high', 'bb_low', 'sma_20', 'atr']
        df = df.dropna(subset=critical_cols)
        
        return df

    def detect_patterns(self, df):
        """Detecta patrones de velas simples."""
        if df.empty:
            return df
        
        df = df.copy()
        
        # Definiciones básicas de velas
        body = np.abs(df['close'] - df['open'])
        upper_shadow = df['high'] - np.maximum(df['close'], df['open'])
        lower_shadow = np.minimum(df['close'], df['open']) - df['low']
        candle_range = df['high'] - df['low']

        # Patrón Martillo (Hammer) - Señal alcista
        # Cuerpo pequeño, sombra inferior larga, poca sombra superior
        df['pattern_hammer'] = (
            (lower_shadow > 2 * body) & 
            (upper_shadow < 0.1 * body)
        ).astype(int)

        # Patrón Envolvente Alcista (Bullish Engulfing)
        # Vela previa roja, vela actual verde y cubre el cuerpo previo
        prev_open = df['open'].shift(1)
        prev_close = df['close'].shift(1)
        
        is_bullish_engulfing = (
            (df['close'] > df['open']) & # Vela actual verde
            (prev_close < prev_open) &   # Vela previa roja
            (df['close'] > prev_open) &  # Cierre actual > Apertura previa
            (df['open'] < prev_close)    # Apertura actual < Cierre previo
        )
        df['pattern_bullish_engulfing'] = is_bullish_engulfing.astype(int)

        return df

    def prepare_for_rl(self, df):
        """Pipeline completo para preparar datos para el agente RL."""
        df = self.add_technical_indicators(df)
        df = self.detect_patterns(df)
        
        # Normalización simple (opcional, mejor dejar que el Env o StableBaselines lo maneje si se usa VecNormalize)
        # Por ahora devolvemos el DF con features
        return df
