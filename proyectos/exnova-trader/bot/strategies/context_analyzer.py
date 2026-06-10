"""
🧠 CONTEXT ANALYZER - EL ANALISTA DE CONTEXTO PROFUNDO
Este módulo analiza el CONTEXTO REAL del mercado antes de permitir una entrada:
1. ¿El nivel tiene HISTORIA? (¿Se ha respetado antes?)
2. ¿Hay CONFIRMACIÓN física? (Mechas, rebotes)
3. ¿El movimiento tiene INERCIA excesiva?
4. ¿El contexto HTF permite esta operación?
"""
import pandas as pd
import numpy as np

class ContextAnalyzer:
    def __init__(self):
        self.min_level_touches = 2  # Mínimo de toques para que un nivel sea válido
        self.max_candle_momentum = 0.002  # 20 pips = movimiento excesivo
        self.min_wick_ratio = 0.3  # La mecha debe ser al menos 30% del rango

    def analyze_deep_context(self, df, proposed_action, proposed_price, mtf_context):
        """
        Análisis profundo del contexto antes de permitir la entrada.
        Retorna: dict con {is_safe: bool, score: float, reason: str}
        """
        if df is None or df.empty or len(df) < 50:
            return {'is_safe': False, 'score': 0, 'reason': 'Datos insuficientes'}

        result = {
            'is_safe': True,
            'score': 100.0,
            'reason': '',
            'warnings': []
        }

        # 1. VALIDAR HISTORIA DEL NIVEL
        level_strength = self._validate_level_history(df, proposed_price, proposed_action)
        if level_strength['touches'] < self.min_level_touches:
            result['warnings'].append(f"⚠️ NIVEL DÉBIL: Solo {level_strength['touches']} toques históricos (mín: {self.min_level_touches})")
            result['score'] *= 0.5
            if level_strength['touches'] == 0:
                result['is_safe'] = False
                result['reason'] = "Nivel nunca ha sido respetado (trampa probable)"
                return result
        else:
            result['warnings'].append(f"✅ NIVEL FUERTE: {level_strength['touches']} toques históricos")

        # 2. VALIDAR CONFIRMACIÓN FÍSICA (RECHAZO)
        rejection_check = self._validate_price_rejection(df, proposed_action)
        if not rejection_check['has_rejection']:
            result['warnings'].append("⚠️ SIN RECHAZO: No hay mecha de confirmación")
            result['score'] *= 0.6
            if rejection_check['is_marubozu']:
                result['is_safe'] = False
                result['reason'] = f"Vela Marubozu {rejection_check['direction']} - Fuerza contra nosotros"
                return result
        else:
            result['warnings'].append(f"✅ RECHAZO DETECTADO: Mecha de {rejection_check['wick_pct']:.1f}%")

        # 3. VALIDAR INERCIA EXCESIVA
        momentum_check = self._validate_momentum(df, proposed_action)
        if momentum_check['has_excessive_momentum']:
            result['warnings'].append(f"🚨 INERCIA EXCESIVA: {momentum_check['candles_in_direction']} velas seguidas {momentum_check['direction']}")
            result['score'] *= 0.4
            if momentum_check['candles_in_direction'] >= 5:
                result['is_safe'] = False
                result['reason'] = f"Precio en caída/subida libre ({momentum_check['candles_in_direction']} velas)"
                return result

        # 4. VALIDAR CONTEXTO HTF
        htf_check = self._validate_htf_context(mtf_context, proposed_action)
        if not htf_check['is_aligned']:
            result['warnings'].append(f"⚠️ HTF NO ALINEADO: {htf_check['reason']}")
            result['score'] *= 0.7
            if htf_check['is_critical']:
                result['is_safe'] = False
                result['reason'] = htf_check['reason']
                return result

        # 5. SCORE FINAL
        result['reason'] = ' | '.join(result['warnings'])
        return result

    def _validate_level_history(self, df, target_price, action):
        """
        Valida cuántas veces el precio ha respetado este nivel antes.
        Un nivel "fuerte" debe haber rebotado al menos 2-3 veces.
        """
        tolerance = target_price * 0.0005  # 5 pips de tolerancia
        touches = 0
        
        for i in range(len(df) - 10):  # No contar las últimas 10 velas (es el movimiento actual)
            candle = df.iloc[i]
            
            if action == 'CALL':
                # Buscar toques en el SOPORTE
                if abs(candle['low'] - target_price) < tolerance:
                    # Verificar que hubo rebote (la siguiente vela subió)
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        if next_candle['close'] > candle['low']:
                            touches += 1
            
            elif action == 'PUT':
                # Buscar toques en la RESISTENCIA
                if abs(candle['high'] - target_price) < tolerance:
                    # Verificar que hubo rechazo (la siguiente vela bajó)
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        if next_candle['close'] < candle['high']:
                            touches += 1
        
        return {'touches': touches, 'is_strong': touches >= self.min_level_touches}

    def _validate_price_rejection(self, df, action):
        """
        Valida si hay una mecha de rechazo en las últimas velas.
        Sin mecha = Sin confirmación = PELIGRO.
        """
        last_candle = df.iloc[-1]
        high, low = last_candle['high'], last_candle['low']
        open_p, close_p = last_candle['open'], last_candle['close']
        
        # Calcular mechas
        upper_wick = high - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low
        body = abs(close_p - open_p)
        total_range = high - low if high > low else 0.0001
        
        if action == 'CALL':
            # Necesitamos mecha INFERIOR (rechazo de vendedores)
            wick_ratio = lower_wick / total_range
            
            # Detectar Marubozu bajista (sin mecha, fuerza vendedora)
            if body > total_range * 0.8 and close_p < open_p:
                return {
                    'has_rejection': False,
                    'is_marubozu': True,
                    'direction': 'BAJISTA',
                    'wick_pct': wick_ratio * 100
                }
            
            return {
                'has_rejection': wick_ratio > self.min_wick_ratio,
                'is_marubozu': False,
                'direction': 'N/A',
                'wick_pct': wick_ratio * 100
            }
        
        elif action == 'PUT':
            # Necesitamos mecha SUPERIOR (rechazo de compradores)
            wick_ratio = upper_wick / total_range
            
            # Detectar Marubozu alcista
            if body > total_range * 0.8 and close_p > open_p:
                return {
                    'has_rejection': False,
                    'is_marubozu': True,
                    'direction': 'ALCISTA',
                    'wick_pct': wick_ratio * 100
                }
            
            return {
                'has_rejection': wick_ratio > self.min_wick_ratio,
                'is_marubozu': False,
                'direction': 'N/A',
                'wick_pct': wick_ratio * 100
            }
        
        return {'has_rejection': False, 'is_marubozu': False, 'direction': 'N/A', 'wick_pct': 0}

    def _validate_momentum(self, df, action):
        """
        Detecta si el precio viene con INERCIA EXCESIVA.
        Si hay 4-5 velas grandes en la misma dirección, NO entrar en contra.
        """
        last_5 = df.tail(5)
        
        if action == 'CALL':
            # Contar velas bajistas grandes consecutivas
            bearish_count = 0
            for i, candle in last_5.iterrows():
                if candle['close'] < candle['open']:
                    move_size = abs(candle['close'] - candle['open']) / candle['open']
                    if move_size > 0.0005:  # Vela de al menos 5 pips
                        bearish_count += 1
                else:
                    break  # Rompe la racha
            
            return {
                'has_excessive_momentum': bearish_count >= 3,
                'candles_in_direction': bearish_count,
                'direction': 'BAJISTA'
            }
        
        elif action == 'PUT':
            # Contar velas alcistas grandes consecutivas
            bullish_count = 0
            for i, candle in last_5.iterrows():
                if candle['close'] > candle['open']:
                    move_size = abs(candle['close'] - candle['open']) / candle['open']
                    if move_size > 0.0005:
                        bullish_count += 1
                else:
                    break
            
            return {
                'has_excessive_momentum': bullish_count >= 3,
                'candles_in_direction': bullish_count,
                'direction': 'ALCISTA'
            }
        
        return {'has_excessive_momentum': False, 'candles_in_direction': 0, 'direction': 'N/A'}

    def _validate_htf_context(self, mtf_context, action):
        """
        Valida si el contexto HTF permite esta operación.
        Contextos críticos:
        - Tendencia H1 fuerte en contra
        - ADX > 40 (tendencia imparable)
        - Lejos de niveles clave
        """
        if not mtf_context:
            return {'is_aligned': True, 'is_critical': False, 'reason': 'Sin contexto HTF'}
        
        trend_h1 = mtf_context.get('trend_h1', 'SIDEWAYS')
        trend_m30 = mtf_context.get('trend_m30', 'SIDEWAYS')
        adx = mtf_context.get('adx_m30', 0)
        distance_to_level = mtf_context.get('distance_to_level', 1.0)
        
        # CRÍTICO: Tendencia H1 fuerte en contra
        if trend_h1 != 'SIDEWAYS':
            if (action == 'CALL' and trend_h1 == 'DOWNTREND') or \
               (action == 'PUT' and trend_h1 == 'UPTREND'):
                if adx > 35:
                    return {
                        'is_aligned': False,
                        'is_critical': True,
                        'reason': f'Tendencia H1 {trend_h1} imparable (ADX: {adx:.1f})'
                    }
                return {
                    'is_aligned': False,
                    'is_critical': False,
                    'reason': f'Tendencia H1 {trend_h1} en contra (ADX: {adx:.1f})'
                }
        
        # CRÍTICO: Lejos de niveles clave
        if distance_to_level > 0.005:  # > 50 pips
            return {
                'is_aligned': False,
                'is_critical': True,
                'reason': f'Precio a {distance_to_level*100:.2f}% del nivel clave más cercano'
            }
        
        return {'is_aligned': True, 'is_critical': False, 'reason': 'Contexto HTF favorable'}
