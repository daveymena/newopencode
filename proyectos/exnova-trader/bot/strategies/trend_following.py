"""
📈 ESTRATEGIA TREND FOLLOWING (Seguimiento de Tendencia)
Ideal para mercados OTC con rachas largas de velas del mismo color.
Identifica fuerza en una dirección y busca la continuación.
"""
import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, min_streak=3):
        self.min_streak = min_streak

    def analyze(self, df):
        """Analiza si hay una racha de tendencia con fuerza para continuar"""
        if len(df) < 20:
            return {'action': 'WAIT', 'confidence': 0, 'reason': 'Datos insuficientes'}

        last_candles = df.tail(5)
        
        # 1. Identificar racha actual
        last_type = 'bullish' if last_candles.iloc[-1]['close'] > last_candles.iloc[-1]['open'] else 'bearish'
        streak_count = 0
        
        for i in range(len(last_candles)-1, -1, -1):
            curr_type = 'bullish' if last_candles.iloc[i]['close'] > last_candles.iloc[i]['open'] else 'bearish'
            if curr_type == last_type:
                streak_count += 1
            else:
                break
        
        # 2. Calcular fuerza (Body vs Shadow)
        last_candle = last_candles.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        candle_range = last_candle['high'] - last_candle['low']
        body_ratio = body / candle_range if candle_range > 0 else 0
        
        # 3. Lógica de continuación
        if streak_count >= self.min_streak and body_ratio > 0.5:
            confidence = 50 + (streak_count * 5) # 50, 55, 60...
            
            # Bono si está rompiendo el máximo/mínimo de la vela anterior
            if last_type == 'bullish' and last_candle['close'] > last_candles.iloc[-2]['high']:
                confidence += 10
            elif last_type == 'bearish' and last_candle['close'] < last_candles.iloc[-2]['low']:
                confidence += 10
                
            return {
                'action': 'CALL' if last_type == 'bullish' else 'PUT',
                'confidence': min(confidence, 90),
                'strategy': 'Trend Following',
                'reason': f'Tendencia {last_type} con racha de {streak_count} velas',
                'details': {
                    'streak': streak_count,
                    'body_ratio': body_ratio,
                    'last_type': last_type
                },
                'expiration': 60 # 1 minuto para continuación rápida
            }

        return {'action': 'WAIT', 'confidence': 0, 'reason': 'No hay tendencia clara de racha'}
