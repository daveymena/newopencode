"""
Fibonacci Analyzer - Detecta niveles óptimos de entrada basados en Fibonacci
"""
import pandas as pd
import numpy as np
from datetime import datetime

class FibonacciAnalyzer:
    """
    Analiza niveles de Fibonacci para encontrar puntos de entrada óptimos
    """
    
    def __init__(self):
        # Niveles de retroceso (más importantes para entradas)
        self.retracement_levels = {
            0.236: 'débil',
            0.382: 'moderado',
            0.5: 'equilibrio',
            0.618: 'golden',  # ⭐ MÁS IMPORTANTE
            0.786: 'profundo'
        }
        
        # Niveles de extensión (para targets)
        self.extension_levels = {
            1.272: 'objetivo_1',
            1.618: 'golden_extension',  # ⭐ TARGET PRINCIPAL
            2.0: 'objetivo_2',
            2.618: 'objetivo_3'
        }
        
        # Tolerancia para considerar que el precio está en un nivel
        self.tolerance = 0.0015  # 0.15% de tolerancia
    
    def find_swing_points(self, df, lookback=20):
        """
        Encuentra swing high y swing low para calcular Fibonacci
        """
        if len(df) < lookback * 2:
            return None
        
        # Encontrar swing high (máximo local)
        swing_high_idx = df['high'].rolling(window=lookback, center=True).apply(
            lambda x: x.argmax() == lookback // 2, raw=True
        )
        swing_highs = df[swing_high_idx == 1.0]
        
        # Encontrar swing low (mínimo local)
        swing_low_idx = df['low'].rolling(window=lookback, center=True).apply(
            lambda x: x.argmin() == lookback // 2, raw=True
        )
        swing_lows = df[swing_low_idx == 1.0]
        
        if len(swing_highs) == 0 or len(swing_lows) == 0:
            return None
        
        # Obtener el último swing high y swing low
        last_swing_high = swing_highs.iloc[-1]
        last_swing_low = swing_lows.iloc[-1]
        
        return {
            'swing_high': {
                'price': last_swing_high['high'],
                'time': last_swing_high.name,
                'index': swing_highs.index[-1]
            },
            'swing_low': {
                'price': last_swing_low['low'],
                'time': last_swing_low.name,
                'index': swing_lows.index[-1]
            }
        }
    
    def calculate_fibonacci_levels(self, swing_high, swing_low, direction='uptrend'):
        """
        Calcula niveles de Fibonacci basados en swing points
        
        Args:
            swing_high: Precio del swing high
            swing_low: Precio del swing low
            direction: 'uptrend' o 'downtrend'
        """
        if direction == 'uptrend':
            # Para tendencia alcista: retroceso desde high hacia low
            diff = swing_high - swing_low
            levels = {}
            
            for level, name in self.retracement_levels.items():
                price = swing_high - (diff * level)
                levels[name] = {
                    'level': level,
                    'price': price,
                    'type': 'retracement'
                }
            
            # Niveles de extensión (targets alcistas)
            for level, name in self.extension_levels.items():
                price = swing_high + (diff * (level - 1))
                levels[name] = {
                    'level': level,
                    'price': price,
                    'type': 'extension'
                }
        
        else:  # downtrend
            # Para tendencia bajista: retroceso desde low hacia high
            diff = swing_high - swing_low
            levels = {}
            
            for level, name in self.retracement_levels.items():
                price = swing_low + (diff * level)
                levels[name] = {
                    'level': level,
                    'price': price,
                    'type': 'retracement'
                }
            
            # Niveles de extensión (targets bajistas)
            for level, name in self.extension_levels.items():
                price = swing_low - (diff * (level - 1))
                levels[name] = {
                    'level': level,
                    'price': price,
                    'type': 'extension'
                }
        
        return levels
    
    def analyze_current_position(self, df, current_price=None):
        """
        Analiza la posición actual del precio respecto a niveles de Fibonacci
        """
        if df.empty or len(df) < 50:
            return {
                'valid': False,
                'reason': 'Datos insuficientes'
            }
        
        # Usar último precio si no se especifica
        if current_price is None:
            current_price = df.iloc[-1]['close']
        
        # Encontrar swing points
        swings = self.find_swing_points(df, lookback=20)
        
        if not swings:
            return {
                'valid': False,
                'reason': 'No se encontraron swing points'
            }
        
        swing_high_price = swings['swing_high']['price']
        swing_low_price = swings['swing_low']['price']
        swing_high_idx = swings['swing_high']['index']
        swing_low_idx = swings['swing_low']['index']
        
        # Determinar dirección de la tendencia
        if swing_high_idx > swing_low_idx:
            # Último swing fue high → tendencia alcista, esperamos retroceso para CALL
            direction = 'uptrend'
            trend_bias = 'CALL'
        else:
            # Último swing fue low → tendencia bajista, esperamos retroceso para PUT
            direction = 'downtrend'
            trend_bias = 'PUT'
        
        # Calcular niveles de Fibonacci
        fib_levels = self.calculate_fibonacci_levels(
            swing_high_price,
            swing_low_price,
            direction
        )
        
        # Verificar en qué nivel está el precio actual
        current_level = None
        closest_level = None
        min_distance = float('inf')
        
        for level_name, level_data in fib_levels.items():
            if level_data['type'] != 'retracement':
                continue
            
            level_price = level_data['price']
            distance = abs(current_price - level_price) / current_price
            
            # Verificar si está en el nivel (dentro de tolerancia)
            if distance <= self.tolerance:
                current_level = {
                    'name': level_name,
                    'level': level_data['level'],
                    'price': level_price,
                    'distance_pct': distance * 100
                }
            
            # Guardar el nivel más cercano
            if distance < min_distance:
                min_distance = distance
                closest_level = {
                    'name': level_name,
                    'level': level_data['level'],
                    'price': level_price,
                    'distance_pct': distance * 100
                }
        
        # Evaluar calidad de la entrada
        entry_quality = self._evaluate_entry_quality(
            current_level,
            closest_level,
            direction,
            current_price,
            swing_high_price,
            swing_low_price
        )
        
        return {
            'valid': True,
            'direction': direction,
            'trend_bias': trend_bias,
            'swing_high': swing_high_price,
            'swing_low': swing_low_price,
            'current_price': current_price,
            'fibonacci_levels': fib_levels,
            'current_level': current_level,
            'closest_level': closest_level,
            'entry_quality': entry_quality,
            'should_enter': entry_quality['score'] >= 70,
            'recommendation': entry_quality['recommendation']
        }
    
    def _evaluate_entry_quality(self, current_level, closest_level, direction, 
                                current_price, swing_high, swing_low):
        """
        Evalúa la calidad del punto de entrada basado en Fibonacci
        """
        score = 0
        reasons = []
        recommendation = None
        
        if not current_level and not closest_level:
            return {
                'score': 0,
                'reasons': ['Precio no está cerca de ningún nivel de Fibonacci'],
                'recommendation': 'WAIT'
            }
        
        # Usar current_level si existe, sino usar closest_level
        level = current_level if current_level else closest_level
        level_name = level['name']
        level_value = level['level']
        distance = level['distance_pct']
        
        # SCORING BASADO EN NIVEL DE FIBONACCI
        
        # 1. GOLDEN RATIO (0.618) - MEJOR ENTRADA
        if level_name == 'golden':
            score += 40
            reasons.append(f"⭐ GOLDEN RATIO (0.618) - Nivel óptimo de entrada")
            if current_level:
                score += 10
                reasons.append(f"✅ Precio EXACTO en Golden Ratio (±{distance:.2f}%)")
        
        # 2. NIVEL 0.5 (50%) - BUENA ENTRADA
        elif level_name == 'equilibrio':
            score += 30
            reasons.append(f"✅ Nivel 0.5 (50%) - Zona de equilibrio")
            if current_level:
                score += 10
                reasons.append(f"✅ Precio en nivel 0.5 (±{distance:.2f}%)")
        
        # 3. NIVEL 0.786 - ENTRADA PROFUNDA
        elif level_name == 'profundo':
            score += 25
            reasons.append(f"⚠️ Nivel 0.786 - Retroceso profundo (última oportunidad)")
            if current_level:
                score += 10
                reasons.append(f"✅ Precio en nivel 0.786 (±{distance:.2f}%)")
        
        # 4. NIVEL 0.382 - ENTRADA TEMPRANA
        elif level_name == 'moderado':
            score += 20
            reasons.append(f"⚠️ Nivel 0.382 - Retroceso débil (entrada temprana)")
            if current_level:
                score += 5
                reasons.append(f"Precio en nivel 0.382 (±{distance:.2f}%)")
        
        # 5. NIVEL 0.236 - ENTRADA MUY TEMPRANA
        elif level_name == 'débil':
            score += 10
            reasons.append(f"⚠️ Nivel 0.236 - Retroceso muy débil (riesgoso)")
        
        # BONUS: Proximidad al nivel
        if current_level:
            # Está exactamente en el nivel
            score += 15
        elif distance < 0.5:  # Muy cerca (< 0.5%)
            score += 10
            reasons.append(f"Cerca del nivel {level_name} ({distance:.2f}%)")
        elif distance < 1.0:  # Cerca (< 1%)
            score += 5
            reasons.append(f"Aproximándose al nivel {level_name} ({distance:.2f}%)")
        
        # DETERMINAR RECOMENDACIÓN
        if score >= 70:
            recommendation = direction.upper().replace('TREND', '')  # 'UP' o 'DOWN'
            if direction == 'uptrend':
                recommendation = 'CALL'
            else:
                recommendation = 'PUT'
            reasons.append(f"🎯 ENTRADA ÓPTIMA para {recommendation}")
        elif score >= 50:
            recommendation = 'WAIT_CONFIRMATION'
            reasons.append(f"⏳ Esperar confirmación adicional")
        else:
            recommendation = 'WAIT'
            reasons.append(f"⏸️ No es momento óptimo de entrada")
        
        return {
            'score': score,
            'level_name': level_name,
            'level_value': level_value,
            'distance_pct': distance,
            'reasons': reasons,
            'recommendation': recommendation
        }
    
    def get_targets(self, entry_price, direction, swing_high, swing_low):
        """
        Calcula targets basados en extensiones de Fibonacci
        """
        fib_levels = self.calculate_fibonacci_levels(swing_high, swing_low, direction)
        
        targets = []
        for level_name, level_data in fib_levels.items():
            if level_data['type'] == 'extension':
                targets.append({
                    'name': level_name,
                    'price': level_data['price'],
                    'level': level_data['level'],
                    'distance_pips': abs(level_data['price'] - entry_price)
                })
        
        # Ordenar por distancia
        targets.sort(key=lambda x: x['distance_pips'])
        
        return targets
    
    def get_human_readable_analysis(self, analysis):
        """
        Genera análisis legible para humanos
        """
        if not analysis['valid']:
            return f"❌ {analysis['reason']}"
        
        lines = []
        lines.append(f"📊 ANÁLISIS DE FIBONACCI")
        lines.append(f"   Tendencia: {analysis['direction'].upper()}")
        lines.append(f"   Bias: {analysis['trend_bias']}")
        lines.append(f"   Swing High: {analysis['swing_high']:.5f}")
        lines.append(f"   Swing Low: {analysis['swing_low']:.5f}")
        lines.append(f"   Precio Actual: {analysis['current_price']:.5f}")
        
        if analysis['current_level']:
            level = analysis['current_level']
            lines.append(f"\n✅ PRECIO EN NIVEL: {level['name'].upper()} ({level['level']*100:.1f}%)")
            lines.append(f"   Precio del nivel: {level['price']:.5f}")
            lines.append(f"   Distancia: {level['distance_pct']:.2f}%")
        elif analysis['closest_level']:
            level = analysis['closest_level']
            lines.append(f"\n📍 NIVEL MÁS CERCANO: {level['name'].upper()} ({level['level']*100:.1f}%)")
            lines.append(f"   Precio del nivel: {level['price']:.5f}")
            lines.append(f"   Distancia: {level['distance_pct']:.2f}%")
        
        entry = analysis['entry_quality']
        lines.append(f"\n🎯 CALIDAD DE ENTRADA: {entry['score']}/100")
        for reason in entry['reasons']:
            lines.append(f"   {reason}")
        
        lines.append(f"\n💡 RECOMENDACIÓN: {entry['recommendation']}")
        
        if analysis['should_enter']:
            lines.append(f"✅ ENTRADA APROBADA")
        else:
            lines.append(f"⏸️ NO ENTRAR - Esperar mejor nivel")
        
        return '\n'.join(lines)
