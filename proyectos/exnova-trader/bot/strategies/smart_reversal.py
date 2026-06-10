"""
🔄 ESTRATEGIA SMART REVERSAL
Ideal para mercados laterales o canales de tendencia.
Identifica agotamiento en niveles de soporte/resistencia y opera la reversión.
"""
import pandas as pd
import numpy as np

class SmartReversalStrategy:
    def __init__(self):
        pass

    def calculate_indicators(self, df):
        """Asegura que los indicadores necesarios estén presentes"""
        # RSI ya viene del FeatureEngineer, pero por si acaso:
        if 'rsi' not in df.columns:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bandas de Bollinger para volatilidad y límites
        if 'bb_high' not in df.columns:
            sma = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            df['bb_high'] = sma + (std * 2)
            df['bb_low'] = sma - (std * 2)
        
        return df

    def find_levels(self, df, window=20):
        """Identifica niveles locales de soporte y resistencia"""
        recent = df.tail(window)
        resistance = recent['high'].max()
        support = recent['low'].min()
        return support, resistance

    def analyze(self, df):
        """Analiza el mercado para buscar reversiones"""
        if len(df) < 50:
            return {'action': 'WAIT', 'confidence': 0, 'reason': 'Datos insuficientes'}

        df = self.calculate_indicators(df)
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        current_price = last_candle['close']
        rsi = last_candle['rsi']
        support, resistance = self.find_levels(df)
        
        # --- LÓGICA PARA CALL (Reversión al Alza) ---
        # REGLA: Solo comprar si el precio YA REBOTÓ del soporte
        # NO comprar mientras está cayendo hacia el soporte
        
        # 1. Precio cerca del soporte o banda inferior
        at_bottom = current_price <= support * 1.0005 or current_price <= last_candle['bb_low'] * 1.0005
        
        # 2. RSI en sobreventa
        oversold = rsi < 35
        
        # 3. 🚨 CONFIRMACIÓN DE REBOTE (CRÍTICO)
        # La vela actual debe ser ALCISTA (close > open) = ya está rebotando
        candle_is_bullish = last_candle['close'] > last_candle['open']
        
        # 4. Vela anterior era BAJISTA (estaba cayendo)
        prev_was_bearish = prev_candle['close'] < prev_candle['open']
        
        # 5. Mecha inferior larga = rechazo del soporte
        lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
        candle_range = last_candle['high'] - last_candle['low']
        strong_rejection = candle_range > 0 and lower_wick / candle_range > 0.3
        
        # ✅ SOLO OPERAR SI HAY CONFIRMACIÓN DE REBOTE
        if at_bottom and oversold and candle_is_bullish and (prev_was_bearish or strong_rejection):
            confidence = 55
            if strong_rejection: confidence += 20
            if rsi < 30: confidence += 10
            if prev_was_bearish: confidence += 10  # Cambio de tendencia confirmado
            
            return {
                'action': 'CALL',
                'confidence': min(confidence, 95),
                'strategy': 'Smart Reversal (Alcista)',
                'reason': f'Rebote confirmado en soporte {support:.5f} con RSI {rsi:.1f}',
                'details': {
                    'price': current_price,
                    'support': support,
                    'rsi': rsi,
                    'bb_low': last_candle['bb_low'],
                    'rejection_confirmed': strong_rejection
                },
                'expiration': 120 # 2 minutos para el rebote
            }

        # --- LÓGICA PARA PUT (Reversión a la Baja) ---
        # REGLA: Solo vender si el precio YA RECHAZÓ la resistencia
        # NO vender mientras está subiendo hacia la resistencia
        
        # 1. Precio cerca de la resistencia o banda superior
        at_top = current_price >= resistance * 0.9995 or current_price >= last_candle['bb_high'] * 0.9995
        
        # 2. RSI en sobrecompra
        overbought = rsi > 65
        
        # 3. 🚨 CONFIRMACIÓN DE RECHAZO (CRÍTICO)
        # La vela actual debe ser BAJISTA (close < open) = ya está cayendo
        candle_is_bearish = last_candle['close'] < last_candle['open']
        
        # 4. Vela anterior era ALCISTA (estaba subiendo)
        prev_was_bullish = prev_candle['close'] > prev_candle['open']
        
        # 5. Mecha superior larga = rechazo de la resistencia
        upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        candle_range = last_candle['high'] - last_candle['low']
        strong_rejection = candle_range > 0 and upper_wick / candle_range > 0.3
        
        # ✅ SOLO OPERAR SI HAY CONFIRMACIÓN DE RECHAZO
        if at_top and overbought and candle_is_bearish and (prev_was_bullish or strong_rejection):
            confidence = 55
            if strong_rejection: confidence += 20
            if rsi > 70: confidence += 10
            if prev_was_bullish: confidence += 10  # Cambio de tendencia confirmado
            
            return {
                'action': 'PUT',
                'confidence': min(confidence, 95),
                'strategy': 'Smart Reversal (Bajista)',
                'reason': f'Rechazo confirmado en resistencia {resistance:.5f} con RSI {rsi:.1f}',
                'details': {
                    'price': current_price,
                    'resistance': resistance,
                    'rsi': rsi,
                    'bb_high': last_candle['bb_high'],
                    'rejection_confirmed': strong_rejection
                },
                'expiration': 120 # 2 minutos
            }

        return {'action': 'WAIT', 'confidence': 0, 'reason': 'No hay condiciones de reversión'}
