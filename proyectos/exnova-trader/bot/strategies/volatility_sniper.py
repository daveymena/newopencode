
"""
⚡ VOLATILITY SNIPER STRATEGY
Especializada en capturar reversiones rápidas cuando el precio se aleja demasiado de su media
basado en Z-Score, Desviación Estándar y Filtro de Tendencia.
"""
import pandas as pd
import numpy as np

class VolatilitySniperStrategy:
    def __init__(self, period=20, std_dev=2.5):
        self.period = period
        self.std_dev = std_dev
        self.name = "Volatility Sniper"

    def analyze(self, df):
        if len(df) < self.period + 5:
            return {'action': 'WAIT', 'confidence': 0, 'reason': 'Datos insuficientes'}

        df = df.copy()
        
        # 1. Calcular Media y Desviación Estándar
        df['sma'] = df['close'].rolling(window=self.period).mean()
        df['std'] = df['close'].rolling(window=self.period).std()
        
        # 2. Calcular Z-Score (Cuán lejos estamos de la media en términos de desv. estándar)
        # Z = (Precio - Media) / Desv. Estándar
        df['zscore'] = (df['close'] - df['sma']) / df['std']
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        action = 'WAIT'
        confidence = 0
        reasons = []
        
        # 3. Lógica de Reversión por Volatilidad
        # Si el Z-Score es extremo (> 2.5), el precio está en una zona de alta probabilidad de reversión
        
        # --- SEÑAL PUT (Venta / Reversión Bajista) ---
        if last['zscore'] > self.std_dev:
            # Confirmar que el precio está empezando a perder fuerza (vela roja o mecha superior)
            is_exhausting = last['close'] < last['open'] or (last['high'] - max(last['open'], last['close'])) > (abs(last['close'] - last['open']))
            
            if is_exhausting:
                action = 'PUT'
                # La confianza aumenta cuanto más extremo sea el Z-Score
                confidence = min(95, 60 + (last['zscore'] - self.std_dev) * 15)
                reasons.append(f"Z-Score Extremo ({last['zscore']:.2f}): Precio muy por encima de la media")
                if last['close'] < last['open']: reasons.append("Confirmación: Vela de giro detectada")
        
        # --- SEÑAL CALL (Compra / Reversión Alcista) ---
        elif last['zscore'] < -self.std_dev:
            is_exhausting = last['close'] > last['open'] or (min(last['open'], last['close']) - last['low']) > (abs(last['close'] - last['open']))
            
            if is_exhausting:
                action = 'CALL'
                confidence = min(95, 60 + (abs(last['zscore']) - self.std_dev) * 15)
                reasons.append(f"Z-Score Extremo ({last['zscore']:.2f}): Precio muy por debajo de la media")
                if last['close'] > last['open']: reasons.append("Confirmación: Vela de giro detectada")

        # 4. Filtro de Seguridad: No operar si el ADX es extremo (evitar tendencias imparables)
        # (Si el ADX ya está calculado en el DF por FeatureEngineer)
        if 'adx' in df.columns and last['adx'] > 45:
            confidence *= 0.5
            reasons.append("⚠️ ADX Muy Alto: Riesgo de continuación de tendencia")

        return {
            'action': action,
            'confidence': round(confidence, 1),
            'reason': " | ".join(reasons) if reasons else "Sin señal clara",
            'strategy': self.name,
            'indicators': {
                'zscore': round(last['zscore'], 2),
                'sma': round(last['sma'], 5)
            }
        }
