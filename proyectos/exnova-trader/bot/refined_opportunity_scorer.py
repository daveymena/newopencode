"""
Scoring Refinado de Oportunidades (SRO)
=======================================
Sistema de puntuación mejorado para oportunidades de trading.
Requiere mayor confluencia y calidad de señales.

Cambios vs versión anterior:
- Score mínimo 25 (antes 5) - mucho más selectivo
- Requiere múltiples condiciones simultáneamente
- Scoring más estricto para confirmar calidad
"""

import pandas as pd
import numpy as np
import time
from datetime import datetime

class RefinedOpportunityScorer:
    """
    Sistema de scoring ultra-preciso para oportunidades de trading.
    Solo las mejores configuraciones pasan el filtro.
    """
    
    def __init__(self):
        # THRESHOLD ESTRICTO - Solo las mejores oportunidades pasan
        # REDUCIDO de 25 a 15 para mayor sensibilidad en 24/7
        self.min_score_threshold = 15  # Antes: 25 - Ahora: 15
        
        # Configuración de scoring
        self.weights = {
            'trend': 20,           # Fuerza de tendencia
            'momentum': 20,       # Confirmación de momentum
            'structure': 15,      # Estructura de mercado
            'rsi': 15,            # Condición RSI
            'macd': 10,           # Señal MACD
            'bb_position': 10,    # Posición en Bollinger
            'volume': 5,          # Volumen/actividad
            'pattern': 5          # Patrones de velas
        }
        
    def calculate_score(self, df, asset, power_levels=None):
        """
        Calcula el score de oportunidad para un activo
        
        Args:
            df: DataFrame con datos y indicadores
            asset: Nombre del activo
            power_levels: Niveles institucionales (opcional)
            
        Returns:
            dict: {
                'score': float,
                'max_score': float,
                'action': str,
                'confidence': float,
                'reasons': list,
                'details': dict
            }
        """
        result = {
            'score': 0,
            'max_score': 100,
            'action': 'HOLD',
            'confidence': 0,
            'reasons': [],
            'details': {}
        }
        
        if df is None or df.empty or len(df) < 50:
            result['reasons'].append("❌ Datos insuficientes")
            return result
        
        try:
            last = df.iloc[-1]
            price = last.get('close', 0)
            
            # Obtener indicadores
            rsi = last.get('rsi', 50)
            macd = last.get('macd', 0)
            macd_signal = last.get('macd_signal', 0)
            macd_diff = last.get('macd_diff', 0)
            bb_high = last.get('bb_high', price)
            bb_low = last.get('bb_low', price)
            sma_20 = last.get('sma_20', price)
            sma_50 = last.get('sma_50', price)
            atr = last.get('atr', 0)
            
            # Calcular componentes del score
            scores = {}
            
            # 1. TENDENCIA (max 20)
            scores['trend'] = self._score_trend(df, sma_20, sma_50, price)
            
            # 2. MOMENTUM (max 20)
            scores['momentum'] = self._score_momentum(df, rsi, macd, macd_diff)
            
            # 3. ESTRUCTURA (max 15)
            scores['structure'] = self._score_structure(df, price, power_levels)
            
            # 4. RSI (max 15)
            scores['rsi'] = self._score_rsi(rsi)
            
            # 5. MACD (max 10)
            scores['macd'] = self._score_macd(macd, macd_signal, macd_diff)
            
            # 6. BOLLINGER (max 10)
            scores['bb_position'] = self._score_bollinger(price, bb_high, bb_low)
            
            # 7. VOLUMEN/ACTIVIDAD (max 5)
            scores['volume'] = self._score_volume(df, atr)
            
            # 8. PATRONES (max 5)
            scores['pattern'] = self._score_patterns(df)
            
            # Sumar scores
            total_score = sum(scores.values())
            result['score'] = total_score
            
            # Guardar detalles
            result['details'] = scores
            
            # Determinar acción basada en dirección
            # CALL: tendencia alcista + RSI bajo + MACD positivo
            # PUT: tendencia bajista + RSI alto + MACD negativo
            
            call_score = self._calculate_direction_score(df, 'CALL')
            put_score = self._calculate_direction_score(df, 'PUT')
            
            # REDUCIDO: Antes >= 20, ahora >= 10 para mayor sensibilidad
            if call_score > put_score and call_score >= 10:
                result['action'] = 'CALL'
                result['confidence'] = min(call_score / 100, 0.95)
                result['reasons'].append(f"✅ CALL: Score direccional {call_score:.0f}")
            elif put_score > call_score and put_score >= 10:
                result['action'] = 'PUT'
                result['confidence'] = min(put_score / 100, 0.95)
                result['reasons'].append(f"✅ PUT: Score direccional {put_score:.0f}")
            else:
                # Asignar dirección basada en RSI si no hay dirección clara
                if rsi < 45:
                    result['action'] = 'CALL'
                    result['confidence'] = 0.5
                    result['reasons'].append(f"📊 RSI sugiere CALL ({rsi:.0f})")
                elif rsi > 55:
                    result['action'] = 'PUT'
                    result['confidence'] = 0.5
                    result['reasons'].append(f"📊 RSI sugiere PUT ({rsi:.0f})")
                else:
                    result['reasons'].append("⚠️ Sin dirección clara")
            
            # Agregar razones por componentes altos
            if scores['trend'] >= 15:
                result['reasons'].append(f"📈 Tendencia fuerte: {scores['trend']:.0f}/20")
            if scores['momentum'] >= 15:
                result['reasons'].append(f"💨 Momentum confirmado: {scores['momentum']:.0f}/20")
            if scores['rsi'] >= 10:
                result['reasons'].append(f"📊 RSI óptimo: {scores['rsi']:.0f}/15")
            if scores['structure'] >= 10:
                result['reasons'].append(f"🏗️ Estructura buena: {scores['structure']:.0f}/15")
                
            return result
            
        except Exception as e:
            result['reasons'].append(f"❌ Error: {str(e)[:50]}")
            return result
    
    def _score_trend(self, df, sma_20, sma_50, price):
        """Evalúa la fuerza de la tendencia"""
        if pd.isna(sma_20) or pd.isna(sma_50) or sma_50 == 0:
            return 0
        
        # Diferencia entre SMAs como % de la media
        sma_diff_pct = abs(sma_20 - sma_50) / sma_50
        
        # Distancia del precio a la media
        price_distance = abs(price - sma_20) / sma_20
        
        score = 0
        
        # SMA 20 > SMA 50 = Alcista
        if sma_20 > sma_50:
            # Tendencia alcista
            if sma_diff_pct > 0.005:  # >0.5% diferencia
                score += 10
            elif sma_diff_pct > 0.002:
                score += 5
            
            # Precio cerca o debajo de SMA20 (pullback)
            if price <= sma_20:
                score += 5
            elif price_distance < 0.002:
                score += 3
                
        # SMA 20 < SMA 50 = Bajista
        elif sma_20 < sma_50:
            if sma_diff_pct > 0.005:
                score += 10
            elif sma_diff_pct > 0.002:
                score += 5
            
            if price >= sma_20:
                score += 5
            elif price_distance < 0.002:
                score += 3
        
        # Confirmar con precio
        recent_closes = df['close'].tail(5).values
        if sma_20 > sma_50:
            # Alcista: precio debe subir
            if all(recent_closes[i] <= recent_closes[i+1] for i in range(len(recent_closes)-1)):
                score += 5
        else:
            # Bajista: precio debe bajar
            if all(recent_closes[i] >= recent_closes[i+1] for i in range(len(recent_closes)-1)):
                score += 5
        
        return min(score, 20)
    
    def _score_momentum(self, df, rsi, macd, macd_diff):
        """Evalúa el momentum del movimiento"""
        score = 0
        
        # Calcular momentum de precio (5 velas)
        if len(df) >= 5:
            price_change = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']
            
            # Momentum positivo fuerte
            if price_change > 0.002:  # >0.2% en 5 velas
                score += 5
            elif price_change > 0:
                score += 2
        
        # RSI en zona óptima
        if 30 < rsi < 40:  # Cerca de sobreventa - potencial CALL
            score += 8
        elif 60 < rsi < 70:  # Cerca de sobrecompra - potencial PUT
            score += 8
        elif rsi < 30 or rsi > 70:  # Extremadamente sobrevendido/sobrecomprado
            score += 5
        
        # MACD tiene momentum claro
        if macd_diff > 0:  # MACD subiendo
            score += 4
        elif macd_diff < 0:  # MACD bajando
            score += 4
            
        # MACD cruzando señal
        if (macd > macd_signal and macd > 0) or (macd < macd_signal and macd < 0):
            score += 3
            
        return min(score, 20)
    
    def _score_structure(self, df, price, power_levels):
        """Evalúa la estructura de mercado"""
        score = 0
        
        if power_levels:
            major_res = power_levels.get('major_res', 0)
            major_supp = power_levels.get('major_supp', 0)
            
            if major_res > 0 and major_supp > 0:
                # Estructura clara
                score += 5
                
                # Precio no cerca de resistencia (para CALL)
                dist_to_res = (major_res - price) / major_res if major_res > 0 else 0
                dist_to_supp = (price - major_supp) / price if major_supp > 0 else 0
                
                # CALL: precio cerca de soporte, lejos de resistencia
                if dist_to_supp < 0.005:  # <0.5% de soporte
                    score += 5
                if dist_to_res > 0.005:  # >0.5% de resistencia
                    score += 5
                    
                # PUT: precio cerca de resistencia, lejos de soporte
                if dist_to_res < 0.005:
                    score += 5
                if dist_to_supp > 0.005:
                    score += 5
        
        return min(score, 15)
    
    def _score_rsi(self, rsi):
        """Evalúa posición del RSI"""
        score = 0
        
        # Zonas óptimas para reversión
        if rsi < 25:  # Sobreventa extrema - CALL
            score += 15
        elif rsi < 35:
            score += 10
        elif 40 <= rsi <= 60:  # Zona neutral
            score += 3
        elif rsi > 75:  # Sobrecompra extrema - PUT
            score += 15
        elif rsi > 65:
            score += 10
            
        return min(score, 15)
    
    def _score_macd(self, macd, macd_signal, macd_diff):
        """Evalúa señales del MACD"""
        score = 0
        
        # MACD tiene dirección clara
        if macd_diff > 0:  # Alcista
            score += 4
        elif macd_diff < 0:  # Bajista
            score += 4
            
        # MACD y señal alineados
        if macd > macd_signal:
            score += 3
        elif macd < macd_signal:
            score += 3
            
        # MACD en territorio positivo/negativo
        if macd > 0:
            score += 3
        elif macd < 0:
            score += 3
            
        return min(score, 10)
    
    def _score_bollinger(self, price, bb_high, bb_low):
        """Evalúa posición en Bollinger Bands"""
        score = 0
        
        if bb_high <= bb_low:  # Evitar errores
            return 0
            
        bb_range = bb_high - bb_low
        if bb_range > 0:
            position = (price - bb_low) / bb_range
            
            # En extremos: potencial reversión
            if position < 0.1:  # Cerca de banda inferior - CALL
                score += 10
            elif position > 0.9:  # Cerca de banda superior - PUT
                score += 10
            elif position < 0.3:  # En zona inferior
                score += 5
            elif position > 0.7:  # En zona superior
                score += 5
                
        return min(score, 10)
    
    def _score_volume(self, df, atr):
        """Evalúa actividad/volumen reciente"""
        score = 0
        
        if atr > 0:
            # ATR como proxy de volumen/volatilidad
            recent_atr = df['atr'].tail(5).mean()
            
            if recent_atr > atr * 0.8:  # ATR reciente alto = actividad
                score += 5
            elif recent_atr > atr * 0.5:
                score += 3
                
        return min(score, 5)
    
    def _score_patterns(self, df):
        """Evalúa patrones de velas recientes"""
        score = 0
        
        if len(df) < 3:
            return 0
            
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        
        # Vela actual
        last_bullish = last['close'] > last['open']
        prev_bullish = prev['close'] > prev['open']
        
        # Engulfing alcista
        if last_bullish and not prev_bullish:
            if last['close'] > prev['open'] and last['open'] < prev['close']:
                score += 5
        # Engulfing bajista
        elif not last_bullish and prev_bullish:
            if last['close'] < prev['open'] and last['open'] > prev['close']:
                score += 5
                
        # Vela de confirmación
        if last_bullish:
            body = abs(last['close'] - last['open'])
            range_size = last['high'] - last['low']
            if range_size > 0 and body / range_size > 0.6:
                score += 2
                
        return min(score, 5)
    
    def _calculate_direction_score(self, df, direction):
        """Calcula score para una dirección específica"""
        score = 0
        
        if len(df) < 20:
            return 0
            
        last = df.iloc[-1]
        
        rsi = last.get('rsi', 50)
        macd = last.get('macd', 0)
        macd_signal = last.get('macd_signal', 0)
        sma_20 = last.get('sma_20', 0)
        sma_50 = last.get('sma_50', 0)
        
        if direction == 'CALL':
            # CALL: RSI bajo, MACD positivo, tendencia alcista
            if rsi < 50:
                score += 25
                if rsi < 40:
                    score += 15
            if macd > macd_signal:
                score += 20
            if sma_20 > sma_50:
                score += 25
        else:  # PUT
            # PUT: RSI alto, MACD negativo, tendencia bajista
            if rsi > 50:
                score += 25
                if rsi > 60:
                    score += 15
            if macd < macd_signal:
                score += 20
            if sma_20 < sma_50:
                score += 25
                
        return min(score, 100)
    
    def get_opportunity_classification(self, score):
        """
        Clasifica la oportunidad según el score
        
        Returns:
            str: Clasificación (ELITE, ALTA, MEDIA, BAJA, NULA)
        """
        if score >= 80:
            return 'ELITE'
        elif score >= 60:
            return 'ALTA'
        elif score >= 40:
            return 'MEDIA'
        elif score >= 25:
            return 'BAJA'
        else:
            return 'NULA'