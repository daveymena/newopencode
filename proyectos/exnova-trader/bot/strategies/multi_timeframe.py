"""
🎯 ANÁLISIS MULTI-TIMEFRAME
Identifica niveles clave en temporalidades mayores (M15, M30)
y confirma entradas en temporalidad menor (M1)
"""
import pandas as pd
import numpy as np
from datetime import datetime

class MultiTimeframeAnalyzer:
    """
    Analiza múltiples temporalidades para encontrar niveles clave
    y confirmar puntos de entrada óptimos
    """
    
    def __init__(self, market_data):
        self.market_data = market_data
        
    def analyze_asset(self, asset):
        """
        Analiza un activo en múltiples temporalidades (H1, M30, M15, M5, M1)
        
        Returns:
            dict: {
                'key_levels': {'support': [], 'resistance': []},
                'current_context': str,
                'entry_signal': dict or None
            }
        """
        import time
        current_time = time.time()
        
        # 1. Obtener datos de TODAS las temporalidades (H1 → M30 → M15 → M5 → M1)
        df_h1  = self.market_data.get_candles(asset, 3600, 50, current_time)   # 1 hora
        df_m30 = self.market_data.get_candles(asset, 60*30, 50, current_time)  # 30 min
        df_m15 = self.market_data.get_candles(asset, 60*15, 50, current_time)  # 15 min
        df_m5  = self.market_data.get_candles(asset, 60*5, 80, current_time)   # 5 min (NUEVO)
        df_m1  = self.market_data.get_candles(asset, 60, 100, current_time)    # 1 min
        
        if df_m15 is None or df_m30 is None or df_h1 is None or df_m5 is None or df_m1 is None:
            return None
        
        # 2. Identificar niveles clave en HTF (M15, M30, H1)
        key_levels = self._find_key_levels(df_m15, df_m30, df_h1)
        
        # 3. Analizar contexto actual (incluyendo M5)
        current_price = df_m1.iloc[-1]['close']
        context = self._analyze_context(df_m15, df_m30, df_h1, df_m5, current_price, key_levels)
        
        # 4. Buscar señal de entrada en M5 y M1 (confirmación en 2 temporalidades)
        entry_signal = self._find_entry_signal(df_m5, df_m1, key_levels, context)
        
        return {
            'asset': asset,
            'key_levels': key_levels,
            'current_context': context,
            'entry_signal': entry_signal,
            'current_price': current_price
        }
    
    def _find_key_levels(self, df_m15, df_m30, df_h1):
        """
        Identifica soportes y resistencias FUERTES en M15, M30 y H1
        """
        levels = {
            'support': [],
            'resistance': [],
            'pivot_points': []
        }
        
        # Combinar datos de todas las temporalidades HTF
        all_highs = list(df_m15['high'].values) + list(df_m30['high'].values) + list(df_h1['high'].values)
        all_lows = list(df_m15['low'].values) + list(df_m30['low'].values) + list(df_h1['low'].values)
        
        # Encontrar resistencias (máximos que se repiten)
        resistance_candidates = []
        for i in range(5, len(df_m30) - 5):
            high = df_m30.iloc[i]['high']
            # Es resistencia si es el máximo local
            if high == df_m30['high'].iloc[i-5:i+5].max():
                resistance_candidates.append(high)
        
        # Encontrar soportes (mínimos que se repiten)
        support_candidates = []
        for i in range(5, len(df_m30) - 5):
            low = df_m30.iloc[i]['low']
            # Es soporte si es el mínimo local
            if low == df_m30['low'].iloc[i-5:i+5].min():
                support_candidates.append(low)
        
        # Agrupar niveles cercanos (tolerancia 0.1%)
        levels['resistance'] = self._cluster_levels(resistance_candidates)
        levels['support'] = self._cluster_levels(support_candidates)
        
        # Calcular puntos pivote
        recent_high = df_m30['high'].tail(20).max()
        recent_low = df_m30['low'].tail(20).min()
        recent_close = df_m30['close'].iloc[-1]
        
        pivot = (recent_high + recent_low + recent_close) / 3
        levels['pivot_points'] = [pivot]
        
        return levels
    
    def _cluster_levels(self, levels, tolerance=0.001):
        """
        Agrupa niveles cercanos en clusters
        """
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            # Si está dentro del 0.1% del cluster actual
            if abs(level - current_cluster[0]) / current_cluster[0] < tolerance:
                current_cluster.append(level)
            else:
                # Guardar promedio del cluster
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        # Último cluster
        if current_cluster:
            clusters.append(np.mean(current_cluster))
        
        # Retornar solo los 5 niveles más relevantes
        return sorted(clusters)[:5]
    
    def _analyze_context(self, df_m15, df_m30, df_h1, df_m5, current_price, key_levels):
        """
        Analiza el contexto del mercado en temporalidades mayores (H1, M30, M15, M5)
        Detecta la 'fuerza real' y dirección del precio
        """
        # --- TENDENCIA H1 (La Verdadera Dirección) ---
        sma_20_h1 = df_h1['close'].rolling(20).mean().iloc[-1]
        sma_50_h1 = df_h1['close'].rolling(50).mean().iloc[-1] if len(df_h1) >= 50 else sma_20_h1
        
        if sma_20_h1 > sma_50_h1 and current_price > sma_20_h1:
            trend_h1 = "UPTREND"
        elif sma_20_h1 < sma_50_h1 and current_price < sma_20_h1:
            trend_h1 = "DOWNTREND"
        else:
            trend_h1 = "SIDEWAYS"

        # --- TENDENCIA M30 ---
        sma_20_m30 = df_m30['close'].rolling(20).mean().iloc[-1]
        sma_50_m30 = df_m30['close'].rolling(50).mean().iloc[-1] if len(df_m30) >= 50 else sma_20_m30
        
        # ADX M30 para ver fuerza
        def get_adx(df):
            plus_dm = df['high'].diff().where(lambda x: (x > 0) & (x > df['low'].diff().abs()), 0).rolling(14).mean()
            minus_dm = df['low'].diff().abs().where(lambda x: (x > 0) & (x > df['high'].diff()), 0).rolling(14).mean()
            tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1).rolling(14).mean()
            plus_di = 100 * (plus_dm / tr)
            minus_di = 100 * (minus_dm / tr)
            dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
            return dx.rolling(14).mean().iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]
            
        adx_m30, di_plus_m30, di_minus_m30 = get_adx(df_m30)
        
        if sma_20_m30 > sma_50_m30 and current_price > sma_20_m30:
            trend_m30 = "UPTREND"
        elif sma_20_m30 < sma_50_m30 and current_price < sma_20_m30:
            trend_m30 = "DOWNTREND"
        else:
            trend_m30 = "SIDEWAYS"

        # --- TENDENCIA M15 ---
        sma_20_m15 = df_m15['close'].rolling(20).mean().iloc[-1]
        if current_price > sma_20_m15:
            trend_m15 = "UPTREND"
        elif current_price < sma_20_m15:
            trend_m15 = "DOWNTREND"
        else:
            trend_m15 = "SIDEWAYS"
        
        # --- TENDENCIA M5 (MICRO-ESTRUCTURA) ---
        sma_10_m5 = df_m5['close'].rolling(10).mean().iloc[-1]
        if current_price > sma_10_m5:
            trend_m5 = "UPTREND"
        elif current_price < sma_10_m5:
            trend_m5 = "DOWNTREND"
        else:
            trend_m5 = "SIDEWAYS"
        
        # Encontrar nivel más cercano
        all_levels = key_levels['support'] + key_levels['resistance']
        distance = 1.0 # Valor por defecto
        if all_levels:
            nearest_level = min(all_levels, key=lambda x: abs(x - current_price))
            distance = abs(current_price - nearest_level) / current_price
            
            # ¿Está en soporte o resistencia?
            level_type = "SUPPORT" if nearest_level in key_levels['support'] else "RESISTANCE"
            
            # ¿Está cerca del nivel? (dentro del 0.2%)
            position = f"AT_{level_type}" if distance < 0.002 else "BETWEEN_LEVELS"
        else:
            position = "NO_CLEAR_LEVEL"
            nearest_level = None
        
        return {
            'trend_h1': trend_h1,
            'trend_m30': trend_m30,
            'trend_m15': trend_m15,
            'trend_m5': trend_m5,
            'adx_m30': adx_m30,
            'trend_strength': "STRONG" if adx_m30 > 25 else "WEAK",
            'position': position,
            'nearest_level': nearest_level,
            'distance_to_level': distance if nearest_level else None,
            'is_aligned': (trend_m30 == trend_m15 == trend_m5)
        }
    
    def _find_entry_signal(self, df_m5, df_m1, key_levels, context):
        """
        Busca señal de entrada en M5 y M1 SOLO si estamos cerca de un nivel clave
        Requiere CONFIRMACIÓN en AMBAS temporalidades (M5 + M1)
        """
        position = context['position']
        
        # Solo buscar entrada si estamos en un nivel clave
        if position not in ['AT_SUPPORT', 'AT_RESISTANCE']:
            return None
        
        # Análisis en M5 (micro-estructura)
        last_m5 = df_m5.iloc[-1]
        prev_m5 = df_m5.iloc[-2]
        
        # Análisis en M1 (confirmación)
        last_m1 = df_m1.iloc[-1]
        prev_m1 = df_m1.iloc[-2]
        current_price = last_m1['close']
        
        # RSI en M5 y M1
        def calc_rsi(df):
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        rsi_m5 = calc_rsi(df_m5).iloc[-1]
        rsi_m1 = calc_rsi(df_m1).iloc[-1]
        
        # --- SEÑAL DE COMPRA (CALL) en SOPORTE ---
        if position == 'AT_SUPPORT':
            # Validación en M5
            m5_bullish = last_m5['close'] > last_m5['open']
            m5_prev_bearish = prev_m5['close'] < prev_m5['open']
            m5_lower_wick = min(last_m5['open'], last_m5['close']) - last_m5['low']
            m5_range = last_m5['high'] - last_m5['low']
            m5_rejection = m5_range > 0 and m5_lower_wick / m5_range > 0.25
            
            # Validación en M1
            m1_bullish = last_m1['close'] > last_m1['open']
            m1_lower_wick = min(last_m1['open'], last_m1['close']) - last_m1['low']
            m1_range = last_m1['high'] - last_m1['low']
            m1_rejection = m1_range > 0 and m1_lower_wick / m1_range > 0.25
            
            # M5 debe alinearse con tendencia micro
            m5_aligned_with_trend = (context['trend_m5'] == 'UPTREND' or context['trend_m5'] == 'SIDEWAYS')
            
            # CONDICIONES PARA ENTRAR:
            # 1. M5 muestra rebote (vela alcista + mecha)
            # 2. M1 confirma (vela alcista)
            # 3. RSI M5 < 40 (sobreventa)
            # 4. M5 alineado con tendencia micro
            
            if m5_bullish and m5_rejection and m1_bullish and rsi_m5 < 40 and m5_aligned_with_trend:
                confidence = 70
                if rsi_m5 < 30: confidence += 10
                if m5_rejection and m1_rejection: confidence += 10
                if context['trend_m5'] == context['trend_m15']: confidence += 5
                
                return {
                    'action': 'CALL',
                    'confidence': min(confidence, 95),
                    'reason': f'Rebote confirmado M5+M1 en SOPORTE ({context["nearest_level"]:.5f})',
                    'entry_price': current_price,
                    'rsi': rsi_m5,
                    'timeframe': 'M30->M5->M1',
                    'expiration': 180  # 3 minutos
                }
        
        # --- SEÑAL DE VENTA (PUT) en RESISTENCIA ---
        elif position == 'AT_RESISTANCE':
            # Validación en M5
            m5_bearish = last_m5['close'] < last_m5['open']
            m5_prev_bullish = prev_m5['close'] > prev_m5['open']
            m5_upper_wick = last_m5['high'] - max(last_m5['open'], last_m5['close'])
            m5_range = last_m5['high'] - last_m5['low']
            m5_rejection = m5_range > 0 and m5_upper_wick / m5_range > 0.25
            
            # Validación en M1
            m1_bearish = last_m1['close'] < last_m1['open']
            m1_upper_wick = last_m1['high'] - max(last_m1['open'], last_m1['close'])
            m1_range = last_m1['high'] - last_m1['low']
            m1_rejection = m1_range > 0 and m1_upper_wick / m1_range > 0.25
            
            # M5 debe alinearse con tendencia micro
            m5_aligned_with_trend = (context['trend_m5'] == 'DOWNTREND' or context['trend_m5'] == 'SIDEWAYS')
            
            # CONDICIONES PARA ENTRAR:
            # 1. M5 muestra rechazo (vela bajista + mecha)
            # 2. M1 confirma (vela bajista)
            # 3. RSI M5 > 60 (sobrecompra)
            # 4. M5 alineado con tendencia micro
            
            if m5_bearish and m5_rejection and m1_bearish and rsi_m5 > 60 and m5_aligned_with_trend:
                confidence = 70
                if rsi_m5 > 70: confidence += 10
                if m5_rejection and m1_rejection: confidence += 10
                if context['trend_m5'] == context['trend_m15']: confidence += 5
                
                return {
                    'action': 'PUT',
                    'confidence': min(confidence, 95),
                    'reason': f'Rechazo confirmado M5+M1 en RESISTENCIA ({context["nearest_level"]:.5f})',
                    'entry_price': current_price,
                    'rsi': rsi_m5,
                    'timeframe': 'M30->M5->M1',
                    'expiration': 180  # 3 minutos
                }
        
        return None
