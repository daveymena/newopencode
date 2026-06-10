"""
🚀 BREAKOUT MOMENTUM STRATEGY
Estrategia validada con operación real ganadora en Exnova
Basada en rupturas de niveles clave con confirmación de momentum
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional

class BreakoutMomentumStrategy:
    """
    Estrategia de trading basada en rupturas de niveles con momentum
    
    Validada con operación real:
    - Par: USD/CAD (OTC)
    - Resultado: GANADORA (+84%)
    - Fecha: 2026-01-06
    """
    
    def __init__(self, 
                 min_adx: float = 18, # Bajamos de 25 a 18
                 min_body_ratio: float = 0.4, # Bajamos de 0.6 a 0.4
                 lookback_period: int = 40):
        """
        Args:
            min_adx: ADX mínimo para confirmar tendencia fuerte
            min_body_ratio: Ratio mínimo cuerpo/rango de vela
            lookback_period: Período para identificar niveles
        """
        self.min_adx = min_adx
        self.min_body_ratio = min_body_ratio
        self.lookback_period = lookback_period
        
        # Cache de niveles identificados
        self.resistance_levels = []
        self.support_levels = []
        
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calcula el Average Directional Index (ADX)
        """
        if len(df) < period + 1:
            return pd.Series([0] * len(df), index=df.index)
        
        # Calcular True Range
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Calcular +DM y -DM
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # Suavizar
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        minus_dm_smooth = minus_dm.rolling(window=period).mean()
        
        # Calcular +DI y -DI
        plus_di = 100 * (plus_dm_smooth / atr)
        minus_di = 100 * (minus_dm_smooth / atr)
        
        # Calcular DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # Calcular ADX
        adx = dx.rolling(window=period).mean()
        
        return adx.fillna(0)
    
    def calculate_di_plus(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula DI+ (Directional Indicator Plus)"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        
        plus_di = 100 * (plus_dm_smooth / atr)
        return plus_di.fillna(0)
    
    def calculate_di_minus(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula DI- (Directional Indicator Minus)"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        high_diff = high.diff()
        low_diff = -low.diff()
        
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        minus_dm_smooth = minus_dm.rolling(window=period).mean()
        
        minus_di = 100 * (minus_dm_smooth / atr)
        return minus_di.fillna(0)
    
    def identify_resistance_levels(self, df: pd.DataFrame) -> List[float]:
        """
        Identifica niveles de resistencia (máximos locales)
        """
        if len(df) < self.lookback_period:
            return []
        
        recent_data = df.tail(self.lookback_period)
        highs = recent_data['high'].values
        resistance_levels = []
        
        # Buscar máximos locales
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                resistance_levels.append(highs[i])
        
        # Eliminar niveles muy cercanos (clustering)
        if resistance_levels:
            resistance_levels = self._remove_close_levels(resistance_levels)
        
        self.resistance_levels = resistance_levels
        return resistance_levels
    
    def identify_support_levels(self, df: pd.DataFrame) -> List[float]:
        """
        Identifica niveles de soporte (mínimos locales)
        """
        if len(df) < self.lookback_period:
            return []
        
        recent_data = df.tail(self.lookback_period)
        lows = recent_data['low'].values
        support_levels = []
        
        # Buscar mínimos locales
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                support_levels.append(lows[i])
        
        # Eliminar niveles muy cercanos
        if support_levels:
            support_levels = self._remove_close_levels(support_levels)
        
        self.support_levels = support_levels
        return support_levels
    
    def _remove_close_levels(self, levels: List[float], threshold: float = 0.001) -> List[float]:
        """
        Elimina niveles que están muy cerca entre sí
        """
        if not levels:
            return []
        
        levels = sorted(levels)
        filtered = [levels[0]]
        
        for level in levels[1:]:
            if abs(level - filtered[-1]) / filtered[-1] > threshold:
                filtered.append(level)
        
        return filtered
    
    def is_valid_breakout_up(self, df: pd.DataFrame, resistance_level: float) -> Tuple[bool, str]:
        """
        Verifica si hay una ruptura válida al alza de resistencia
        """
        if len(df) < 3:
            return False, "Datos insuficientes"
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 1. Precio debe cerrar por encima de resistencia
        if last['close'] <= resistance_level:
            return False, f"Precio {last['close']:.5f} no rompió resistencia {resistance_level:.5f}"
        
        # 2. Vela debe tener cuerpo fuerte
        body = abs(last['close'] - last['open'])
        candle_range = last['high'] - last['low']
        
        if candle_range == 0:
            return False, "Rango de vela es cero"
        
        body_ratio = body / candle_range
        if body_ratio < self.min_body_ratio:
            return False, f"Cuerpo débil ({body_ratio:.2f} < {self.min_body_ratio})"
        
        # 3. Vela debe ser alcista
        if last['close'] <= last['open']:
            return False, "Vela bajista"
        
        # 4. Verificar ADX si está disponible
        if 'adx' in df.columns:
            adx = last['adx']
            if adx < self.min_adx:
                return False, f"ADX débil ({adx:.1f} < {self.min_adx})"
        
        # 5. Verificar DI+ > DI- si están disponibles
        if 'di_plus' in df.columns and 'di_minus' in df.columns:
            if last['di_plus'] <= last['di_minus']:
                return False, "DI+ no supera DI-"
        
        return True, f"Breakout válido en {resistance_level:.5f}"
    
    def is_valid_breakout_down(self, df: pd.DataFrame, support_level: float) -> Tuple[bool, str]:
        """
        Verifica si hay una ruptura válida a la baja de soporte
        """
        if len(df) < 3:
            return False, "Datos insuficientes"
        
        last = df.iloc[-1]
        
        # 1. Precio debe cerrar por debajo de soporte
        if last['close'] >= support_level:
            return False, f"Precio {last['close']:.5f} no rompió soporte {support_level:.5f}"
        
        # 2. Vela debe tener cuerpo fuerte
        body = abs(last['close'] - last['open'])
        candle_range = last['high'] - last['low']
        
        if candle_range == 0:
            return False, "Rango de vela es cero"
        
        body_ratio = body / candle_range
        if body_ratio < self.min_body_ratio:
            return False, f"Cuerpo débil ({body_ratio:.2f} < {self.min_body_ratio})"
        
        # 3. Vela debe ser bajista
        if last['close'] >= last['open']:
            return False, "Vela alcista"
        
        # 4. Verificar ADX
        if 'adx' in df.columns:
            adx = last['adx']
            if adx < self.min_adx:
                return False, f"ADX débil ({adx:.1f} < {self.min_adx})"
        
        # 5. Verificar DI- > DI+
        if 'di_plus' in df.columns and 'di_minus' in df.columns:
            if last['di_minus'] <= last['di_plus']:
                return False, "DI- no supera DI+"
        
        return True, f"Breakout válido en {support_level:.5f}"
    
    def check_ma_alignment(self, df: pd.DataFrame, direction: str = "bullish") -> Tuple[bool, str]:
        """
        Verifica alineación de medias móviles
        """
        if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
            return True, "MAs no disponibles (omitir verificación)"
        
        last = df.iloc[-1]
        sma_20 = last['sma_20']
        sma_50 = last['sma_50']
        
        if direction == "bullish":
            if sma_20 > sma_50:
                return True, "MAs alineadas alcista"
            else:
                return False, f"MAs no alineadas (SMA20: {sma_20:.5f}, SMA50: {sma_50:.5f})"
        
        else:  # bearish
            if sma_20 < sma_50:
                return True, "MAs alineadas bajista"
            else:
                return False, f"MAs no alineadas (SMA20: {sma_20:.5f}, SMA50: {sma_50:.5f})"
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Analiza el mercado y determina si hay oportunidad de breakout
        
        Returns:
            dict con análisis completo
        """
        if len(df) < self.lookback_period:
            return {
                'action': 'WAIT',
                'confidence': 0,
                'reason': 'Datos insuficientes',
                'details': {}
            }
        
        # Agregar indicadores si no existen
        if 'adx' not in df.columns:
            df['adx'] = self.calculate_adx(df)
        if 'di_plus' not in df.columns:
            df['di_plus'] = self.calculate_di_plus(df)
        if 'di_minus' not in df.columns:
            df['di_minus'] = self.calculate_di_minus(df)
        
        # Identificar niveles
        resistances = self.identify_resistance_levels(df)
        supports = self.identify_support_levels(df)
        
        current_price = df.iloc[-1]['close']
        
        # Buscar breakout alcista
        if resistances:
            nearest_resistance = min(resistances, key=lambda x: abs(x - current_price))
            
            # Solo considerar si estamos cerca del nivel
            distance_to_resistance = abs(current_price - nearest_resistance) / current_price
            
            if distance_to_resistance < 0.005:  # Subimos de 0.2% a 0.5% para ser más flexibles
                is_valid, reason = self.is_valid_breakout_up(df, nearest_resistance)
                
                if is_valid:
                    # Verificar alineación de MAs
                    ma_aligned, ma_reason = self.check_ma_alignment(df, "bullish")
                    
                    if ma_aligned:
                        return {
                            'action': 'CALL',
                            'confidence': 85,
                            'strategy': 'Breakout Momentum (Alcista)',
                            'reason': f"Ruptura de resistencia {nearest_resistance:.5f}",
                            'details': {
                                'resistance_level': nearest_resistance,
                                'current_price': current_price,
                                'adx': df.iloc[-1].get('adx', 0),
                                'di_plus': df.iloc[-1].get('di_plus', 0),
                                'di_minus': df.iloc[-1].get('di_minus', 0),
                                'ma_alignment': ma_reason
                            },
                            'expiration': 120  # 2 minutos
                        }
        
        # Buscar breakout bajista
        if supports:
            nearest_support = min(supports, key=lambda x: abs(x - current_price))
            
            distance_to_support = abs(current_price - nearest_support) / current_price
            
            if distance_to_support < 0.005: # Subimos a 0.5%
                is_valid, reason = self.is_valid_breakout_down(df, nearest_support)
                
                if is_valid:
                    ma_aligned, ma_reason = self.check_ma_alignment(df, "bearish")
                    
                    if ma_aligned:
                        return {
                            'action': 'PUT',
                            'confidence': 85,
                            'strategy': 'Breakout Momentum (Bajista)',
                            'reason': f"Ruptura de soporte {nearest_support:.5f}",
                            'details': {
                                'support_level': nearest_support,
                                'current_price': current_price,
                                'adx': df.iloc[-1].get('adx', 0),
                                'di_plus': df.iloc[-1].get('di_plus', 0),
                                'di_minus': df.iloc[-1].get('di_minus', 0),
                                'ma_alignment': ma_reason
                            },
                            'expiration': 120
                        }
        
        # No hay oportunidad
        return {
            'action': 'WAIT',
            'confidence': 0,
            'reason': 'No hay breakout válido',
            'details': {
                'resistances': resistances,
                'supports': supports,
                'current_price': current_price
            }
        }
