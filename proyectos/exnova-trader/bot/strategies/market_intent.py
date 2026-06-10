"""
🎯 ANALIZADOR DE INTENCIÓN DEL MERCADO (Inertia & Force)
Determina si el mercado tiene 'fuerza' para continuar o si el rebote es real.
"""
import pandas as pd
import numpy as np

class MarketIntentAnalyzer:
    """
    Analiza la 'intencionalidad' del movimiento del precio.
    Evita que el bot entre en contra de una inercia institucional imparable.
    """
    
    def __init__(self):
        self.name = "Market Intent Analyzer"

    def analyze_intent(self, df):
        """
        Analiza si el mercado tiene 'ganas' de seguir en la dirección actual.
        
        Returns:
            dict: {
                'intent': 'BULLISH_FORCE' | 'BEARISH_FORCE' | 'NEUTRAL',
                'strength': 0.0 to 1.0,
                'is_unstoppable': bool,
                'reason': str
            }
        """
        if len(df) < 50:
            return {'intent': 'NEUTRAL', 'strength': 0, 'is_unstoppable': False, 'reason': 'Datos insuficientes'}

        last_candles = df.tail(20)
        
        # 1. Análisis de Inercia (Distancia recorrida vs Tiempo)
        # Si el precio se ha movido mucho en muy poco tiempo, hay inercia institucional.
        price_change_20 = (df.iloc[-1]['close'] - df.iloc[-20]['close']) / df.iloc[-20]['close']
        price_change_10 = (df.iloc[-1]['close'] - df.iloc[-10]['close']) / df.iloc[-10]['close']
        
        # 2. Análisis de 'Ganas' (Relación de Cuerpos)
        # Si las velas a favor de la tendencia son mucho más grandes que las de retroceso.
        recent = df.tail(10)
        bull_bodies = sum([row['close'] - row['open'] for _, row in recent.iterrows() if row['close'] > row['open']])
        bear_bodies = sum([row['open'] - row['close'] for _, row in recent.iterrows() if row['close'] < row['open']])
        
        # 3. Análisis de Retroceso (Pullback Depth)
        # Si el retroceso es superficial (< 30% del movimiento anterior), la fuerza es imparable.
        max_high = last_candles['high'].max()
        min_low = last_candles['low'].min()
        total_range = max_high - min_low
        current_price = df.iloc[-1]['close']
        
        if total_range == 0: return {'intent': 'NEUTRAL', 'strength': 0, 'is_unstoppable': False, 'reason': 'Rango cero'}

        # Calcular dónde estamos respecto al rango reciente
        position_pct = (current_price - min_low) / total_range
        
        # LÓGICA DE FUERZA ALCISTA (BULLISH FORCE)
        if position_pct > 0.8 and bull_bodies > abs(bear_bodies) * 2:
            strength = min(1.0, (bull_bodies / (abs(bear_bodies) + 0.0001)) / 5)
            is_unstoppable = strength > 0.8 or price_change_10 > 0.002
            return {
                'intent': 'BULLISH_FORCE',
                'strength': strength,
                'is_unstoppable': is_unstoppable,
                'reason': f"Fuerte inercia ALCISTA ({position_pct*100:.1f}% del rango). Retrocesos ignorados."
            }
            
        # LÓGICA DE FUERZA BAJISTA (BEARISH FORCE)
        if position_pct < 0.2 and abs(bear_bodies) > bull_bodies * 2:
            strength = min(1.0, (abs(bear_bodies) / (bull_bodies + 0.0001)) / 5)
            is_unstoppable = strength > 0.8 or price_change_10 < -0.002
            return {
                'intent': 'BEARISH_FORCE',
                'strength': strength,
                'is_unstoppable': is_unstoppable,
                'reason': f"Fuerte inercia BAJISTA ({ (1-position_pct)*100:.1f}% del rango). Compradores sin fuerza."
            }

        # 4. Análisis de Aceleración (Velas creciendo en tamaño)
        recent_diffs = abs(recent['close'] - recent['open']).tail(3).tolist()
        is_accelerating = recent_diffs[2] > recent_diffs[1] > recent_diffs[0]
        
        # 5. Análisis de Volumen Clímax
        avg_vol = df['volume'].tail(50).mean()
        is_volume_climax = df['volume'].iloc[-1] > avg_vol * 2.5
        
        if is_accelerating and is_volume_climax:
             return {
                'intent': 'CLIMAX_ACCELERATION',
                'strength': 1.0,
                'is_unstoppable': True,
                'reason': "CLÍMAX DE ACELERACIÓN Y VOLUMEN: El mercado está barriendo niveles sin freno."
            }

        # 6. Análisis de ADX (Fuerza de Tendencia)
        # Si ADX > 35, la tendencia es MUY fuerte. Reversiones son peligrosas.
        adx = self.calculate_adx(df)
        if adx > 35:
            direction = 'BULLISH' if price_change_20 > 0 else 'BEARISH'
            return {
                'intent': f'{direction}_TREND_STRONG',
                'strength': adx / 100,
                'is_unstoppable': True if adx > 45 else False,
                'reason': f"Tendencia {direction} confirmada por ADX ({adx:.1f}). Peligro contra-tendencia."
            }

        return {
            'intent': 'NEUTRAL',
            'strength': 0.5,
            'is_unstoppable': False,
            'reason': "Mercado con intención equilibrada o en rango."
        }

    def calculate_adx(self, df, period=14):
        """Calcula el Average Directional Index (ADX)"""
        try:
            plus_dm = df['high'].diff()
            minus_dm = df['low'].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm > 0] = 0
            minus_dm = abs(minus_dm)

            tr1 = pd.DataFrame(df['high'] - df['low'])
            tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
            tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
            frames = [tr1, tr2, tr3]
            tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
            atr = tr.rolling(period).mean()

            plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
            dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
            adx = dx.rolling(period).mean()
            return adx.iloc[-1]
        except:
            return 20.0

    def get_market_sentiment_summary(self, df):
        """Retorna un resumen legible para el bot"""
        analysis = self.analyze_intent(df)
        
        if analysis['is_unstoppable']:
            icon = "🚀" if "BULL" in analysis['intent'] else "📉"
            return f"{icon} INERCIA IMPARABLE: {analysis['reason']}"
        
        if analysis['strength'] > 0.7:
            return f"⚠️ FUERZA DETECTADA: {analysis['reason']}"
            
        return f"⚖️ SENTIMIENTO: {analysis['reason']}"
