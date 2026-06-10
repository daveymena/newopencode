"""
Sistema de Validación de Entradas Refinado (SVER)
====================================================
Mejora el sistema de validación para entradas más precisas y consistentes.

Cambios principales:
- Requiere 80%+ confianza (antes 40%)
- Score mínimo de 80/100 (antes 60)
- Validación de confluencia de múltiples indicadores
- Confirmación de momentum obligatoria
- Timing óptimo requerido
- Detección de estructuras de mercado
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

class RefinedEntryValidator:
    """
    Validador de entradas de alta precisión
    Solo aprueba operaciones cuando hay confluencia PERFECTA
    """
    
    def __init__(self):
        # THRESHOLDS ESTRICTO (versus los anteriores)
        # AJUSTADOS para modo 24/7 - antes eran 0.80/80
        self.min_confidence = 0.50  # Antes: 0.80 - Ahora: 50%
        self.min_score = 50  # Antes: 80 - Ahora: 50
        
        # Validaciones obligatorias
        self.require_momentum_confirmation = True
        self.require_timing_optimization = True
        self.require_structure_confirmation = True
        self.require_multiple_indicator_agree = True
        
        # Parámetros de momentum
        self.momentum_lookback = 5
        self.min_momentum_strength = 0.40  # 40% mínimo (reducido de 60%)
        
        # Parámetros de timing
        self.min_candles_for_timing = 3
        
        # Parámetros de estructura
        self.min_structure_bars = 20
        
        # Conteo de rechazos para debug
        self.rejection_stats = {
            'low_confidence': 0,
            'low_score': 0,
            'no_momentum': 0,
            'bad_timing': 0,
            'no_structure': 0,
            'no_confluence': 0
        }
        
    def validate_entry(self, df, action, indicators_analysis, rl_prediction, market_context=None):
        """
        Validación COMPLETA y ESTRICTA de entrada
        
        Returns:
            dict: {
                'valid': bool,
                'confidence': float,
                'score': float,
                'reasons': list,
                'warnings': list,
                'rejection_reason': str o None
            }
        """
        result = {
            'valid': False,
            'confidence': 0.0,
            'score': 0.0,
            'reasons': [],
            'warnings': [],
            'rejection_reason': None,
            'details': {}
        }
        
        # ============= VALIDACIÓN 1: DATOS SUFICIENTES =============
        if df is None or df.empty:
            result['rejection_reason'] = 'NO_DATA'
            return result
        
        if len(df) < 50:
            result['warnings'].append(f"⚠️ Pocas velas: {len(df)}")
            result['rejection_reason'] = 'INSUFFICIENT_DATA'
            return result
        
        result['reasons'].append(f"✅ Datos OK ({len(df)} velas)")
        
        # ============= VALIDACIÓN 2: SCORE DE FILTROS =============
        from strategies.profitability_filters import ProfitabilityFilters
        pf = ProfitabilityFilters()
        profitability_check = pf.apply_all_filters(df, action)
        
        result['score'] = profitability_check['score']
        result['reasons'].extend(profitability_check['reasons'])
        
        # CHECK: Score mínimo
        if result['score'] < self.min_score:
            result['rejection_reason'] = 'LOW_SCORE'
            self.rejection_stats['low_score'] += 1
            result['warnings'].append(f"❌ SCORE BAJO: {result['score']:.0f}/100 (mínimo: {self.min_score})")
            return result
        
        result['reasons'].append(f"✅ Score APROBADO: {result['score']:.0f}/100")
        
        # ============= VALIDACIÓN 3: MOMENTUM CONFIRMATION =============
        momentum_valid, momentum_details = self._validate_momentum(df, action)
        result['details']['momentum'] = momentum_details
        
        if not momentum_valid:
            result['rejection_reason'] = 'NO_MOMENTUM'
            self.rejection_stats['no_momentum'] += 1
            result['warnings'].append(f"❌ MOMENTUM INSUFICIENTE: {momentum_details['reason']}")
            return result
        
        result['reasons'].append(f"✅ Momentum CONFIRMADO: {momentum_details['strength']:.0%}")
        
        # ============= VALIDACIÓN 4: TIMING ÓPTIMO =============
        if self.require_timing_optimization:
            timing_valid, timing_details = self._validate_timing(df, action)
            result['details']['timing'] = timing_details
            
            if not timing_valid:
                result['rejection_reason'] = 'BAD_TIMING'
                self.rejection_stats['bad_timing'] += 1
                result['warnings'].append(f"❌ TIMING NO ÓPTIMO: {timing_details['reason']}")
                return result
            
            result['reasons'].append(f"✅ Timing ÓPTIMO: {timing_details['reason']}")
        
        # ============= VALIDACIÓN 5: ESTRUCTURA DE MERCADO =============
        if self.require_structure_confirmation:
            structure_valid, structure_details = self._validate_structure(df)
            result['details']['structure'] = structure_details
            
            if not structure_valid:
                result['rejection_reason'] = 'NO_STRUCTURE'
                self.rejection_stats['no_structure'] += 1
                result['warnings'].append(f"❌ ESTRUCTURA DÉBIL: {structure_details['reason']}")
                return result
            
            result['reasons'].append(f"✅ Estructura CONFIRMADA: {structure_details['type']}")
        
        # ============= VALIDACIÓN 6: CONFLUENCIA MULTI-INDICADOR =============
        if self.require_multiple_indicator_agree:
            confluence_valid, confluence_details = self._validate_confluence(df, action)
            result['details']['confluence'] = confluence_details
            
            if not confluence_valid:
                result['rejection_reason'] = 'NO_CONFLUENCE'
                self.rejection_stats['no_confluence'] += 1
                result['warnings'].append(f"❌ SIN CONFLUENCIA: {confluence_details['reason']}")
                return result
            
            result['reasons'].append(f"✅ CONFLUENCIA: {confluence_details['agreement']:.0%} de indicadores de acuerdo")
        
        # ============= VALIDACIÓN 7: ANÁLISIS AVANZADO =============
        from strategies.advanced_analysis import AdvancedMarketAnalysis
        advanced = AdvancedMarketAnalysis().full_market_analysis(df)
        
        result['details']['advanced'] = advanced
        
        # El análisis avanzado debe dar al menos 70% confianza
        if advanced['confidence'] < 0.70:
            result['rejection_reason'] = 'LOW_ADVANCED_CONFIDENCE'
            result['warnings'].append(f"❌ Análisis avanzado bajo: {advanced['confidence']*100:.0f}%")
            return result
        
        result['confidence'] = min(advanced['confidence'], 0.95)
        result['reasons'].append(f"✅ Análisis avanzado: {advanced['confidence']*100:.0f}%")
        
        # ============= VALIDACIÓN 8: CONFIANZA MÍNIMA =============
        if result['confidence'] < self.min_confidence:
            result['rejection_reason'] = 'LOW_CONFIDENCE'
            self.rejection_stats['low_confidence'] += 1
            result['warnings'].append(f"❌ CONFIANZA BAJA: {result['confidence']*100:.0f}% (mínimo: {self.min_confidence*100:.0f}%)")
            return result
        
        # ============= TODAS LAS VALIDACIONES PASARON =============
        result['valid'] = True
        direction = 'CALL' if action == 1 else 'PUT'
        result['reasons'].append(f"🎯 ENTRADA APROBADA: {direction}")
        result['reasons'].append(f"⭐ CONFIANZA FINAL: {result['confidence']*100:.0f}% | SCORE: {result['score']:.0f}/100")
        
        return result
    
    def _validate_momentum(self, df, action):
        """
        Valida que haya momentum suficiente en la dirección de la operación
        """
        details = {
            'strength': 0.0,
            'direction': 'NEUTRAL',
            'reason': ''
        }
        
        if 'rsi' not in df.columns or 'macd' not in df.columns:
            details['reason'] = 'Indicadores no disponibles'
            return False, details
        
        last = df.iloc[-1]
        rsi = last['rsi']
        macd = last['macd']
        macd_signal = last.get('macd_signal', 0)
        
        # Calcular fuerza de momentum
        momentum_score = 0
        max_score = 3
        
        # RSI confirmation
        if action == 1:  # CALL
            if rsi < 35:  # Sobreventa
                momentum_score += 1
            elif rsi < 45:
                momentum_score += 0.5
        else:  # PUT
            if rsi > 65:  # Sobrecompra
                momentum_score += 1
            elif rsi > 55:
                momentum_score += 0.5
        
        # MACD confirmation
        if action == 1:  # CALL
            if macd > macd_signal and macd > 0:
                momentum_score += 1
            elif macd > macd_signal:
                momentum_score += 0.5
        else:  # PUT
            if macd < macd_signal and macd < 0:
                momentum_score += 1
            elif macd < macd_signal:
                momentum_score += 0.5
        
        # Price momentum (últimas 5 velas)
        if len(df) >= 5:
            recent_change = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']
            
            if action == 1:  # CALL
                if recent_change > 0:
                    momentum_score += 1
                elif recent_change > -0.001:
                    momentum_score += 0.5
            else:  # PUT
                if recent_change < 0:
                    momentum_score += 1
                elif recent_change < 0.001:
                    momentum_score += 0.5
        
        strength = momentum_score / max_score
        details['strength'] = strength
        
        if strength >= self.min_momentum_strength:
            direction = 'CALL' if action == 1 else 'PUT'
            details['direction'] = direction
            details['reason'] = f"Momentum {direction}: {strength*100:.0f}%"
            return True, details
        else:
            details['reason'] = f"Momentum débil: {strength*100:.0f}% (mínimo {self.min_momentum_strength*100:.0f}%)"
            return False, details
    
    def _validate_timing(self, df, action):
        """
        Valida que el timing sea óptimo para entrar
        """
        details = {
            'type': 'UNKNOWN',
            'reason': ''
        }
        
        if len(df) < 5:
            details['reason'] = 'Datos insuficientes para timing'
            return False, details
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Tipo de vela actual
        current_bullish = last['close'] > last['open']
        
        if action == 1:  # CALL - esperar vela bullish
            if current_bullish:
                # Verificar que no sea demasiado tarde (vela muy grande puede indicar fin de movimiento)
                body = abs(last['close'] - last['open'])
                range_size = last['high'] - last['low']
                
                if range_size > 0:
                    body_ratio = body / range_size
                    
                    if 0.3 <= body_ratio <= 0.8:  # Cuerpo medio, no muy extendido
                        details['type'] = 'PULLBACK_ENTRY'
                        details['reason'] = 'Entrada en pullback confirmada'
                        return True, details
                    elif body_ratio > 0.8:
                        details['type'] = 'LATE_ENTRY'
                        details['reason'] = 'Movimiento可能 demasiado avanzado'
                        return False, details
            else:
                details['reason'] = 'Esperando vela bullish para CALL'
                return False, details
        
        else:  # PUT - esperar vela bearish
            if not current_bullish:
                body = abs(last['close'] - last['open'])
                range_size = last['high'] - last['low']
                
                if range_size > 0:
                    body_ratio = body / range_size
                    
                    if 0.3 <= body_ratio <= 0.8:
                        details['type'] = 'PULLBACK_ENTRY'
                        details['reason'] = 'Entrada en pullback confirmada'
                        return True, details
                    elif body_ratio > 0.8:
                        details['type'] = 'LATE_ENTRY'
                        details['reason'] = 'Movimiento posiblemente demasiado avanzado'
                        return False, details
            else:
                details['reason'] = 'Esperando vela bearish para PUT'
                return False, details
        
        details['reason'] = 'Timing no óptimo'
        return False, details
    
    def _validate_structure(self, df):
        """
        Valida la estructura de mercado (tendencia, soporte/resistencia)
        """
        details = {
            'type': 'UNKNOWN',
            'strength': 0.0,
            'reason': ''
        }
        
        if len(df) < 20:
            details['reason'] = 'Datos insuficientes para análisis de estructura'
            return False, details
        
        # Analizar estructura de tendencia con SMAs
        if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
            details['reason'] = 'SMAs no disponibles'
            return True, details  # No bloquear si no hay SMAs
        
        last = df.iloc[-1]
        sma_20 = last['sma_20']
        sma_50 = last['sma_50']
        price = last['close']
        
        # Estructura alcista
        if sma_20 > sma_50 and price > sma_20:
            details['type'] = 'UPTREND'
            details['strength'] = 0.8
            details['reason'] = 'Estructura alcista confirmada'
            return True, details
        
        # Estructura bajista
        elif sma_20 < sma_50 and price < sma_20:
            details['type'] = 'DOWNTREND'
            details['strength'] = 0.8
            details['reason'] = 'Estructura bajista confirmada'
            return True, details
        
        # Estructura lateral - solo aprobar si hay otros indicadores fuertes
        else:
            # Buscar estructura de rango
            highs = df['high'].tail(20).max()
            lows = df['low'].tail(20).min()
            range_size = highs - lows
            
            if range_size > 0:
                current_position = (price - lows) / range_size
                
                if current_position < 0.3:  # Cerca del soporte del rango
                    details['type'] = 'RANGE_SUPPORT'
                    details['strength'] = 0.5
                    details['reason'] = 'Precio en soporte de rango'
                    return True, details
                elif current_position > 0.7:  # Cerca de la resistencia del rango
                    details['type'] = 'RANGE_RESISTANCE'
                    details['strength'] = 0.5
                    details['reason'] = 'Precio en resistencia de rango'
                    return True, details
        
        details['reason'] = 'Sin estructura clara'
        return False, details
    
    def _validate_confluence(self, df, action):
        """
        Valida que múltiples indicadores estén de acuerdo
        """
        details = {
            'indicators': {},
            'agreement': 0.0,
            'reason': ''
        }
        
        indicators_agreeing = 0
        total_indicators = 0
        
        # RSI
        if 'rsi' in df.columns:
            total_indicators += 1
            rsi = df.iloc[-1]['rsi']
            
            if action == 1:  # CALL
                if rsi < 40:  # Sobreventa
                    indicators_agreeing += 1
                    details['indicators']['rsi'] = 'BUY'
                else:
                    details['indicators']['rsi'] = 'NEUTRAL'
            else:  # PUT
                if rsi > 60:  # Sobrecompra
                    indicators_agreeing += 1
                    details['indicators']['rsi'] = 'SELL'
                else:
                    details['indicators']['rsi'] = 'NEUTRAL'
        
        # MACD
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            total_indicators += 1
            macd = df.iloc[-1]['macd']
            macd_signal = df.iloc[-1]['macd_signal']
            
            if action == 1:  # CALL
                if macd > macd_signal and macd > 0:
                    indicators_agreeing += 1
                    details['indicators']['macd'] = 'BUY'
                else:
                    details['indicators']['macd'] = 'NEUTRAL'
            else:  # PUT
                if macd < macd_signal and macd < 0:
                    indicators_agreeing += 1
                    details['indicators']['macd'] = 'SELL'
                else:
                    details['indicators']['macd'] = 'NEUTRAL'
        
        # Bollinger Bands
        if all(col in df.columns for col in ['bb_high', 'bb_low', 'close']):
            total_indicators += 1
            last = df.iloc[-1]
            
            if action == 1:  # CALL
                if last['close'] < last['bb_low']:
                    indicators_agreeing += 1
                    details['indicators']['bb'] = 'BUY'
                else:
                    details['indicators']['bb'] = 'NEUTRAL'
            else:  # PUT
                if last['close'] > last['bb_high']:
                    indicators_agreeing += 1
                    details['indicators']['bb'] = 'SELL'
                else:
                    details['indicators']['bb'] = 'NEUTRAL'
        
        # Tendencia SMAs
        if 'sma_20' in df.columns and 'sma_50' in df.columns:
            total_indicators += 1
            sma_20 = df.iloc[-1]['sma_20']
            sma_50 = df.iloc[-1]['sma_50']
            
            if action == 1:  # CALL
                if sma_20 > sma_50:
                    indicators_agreeing += 1
                    details['indicators']['sma'] = 'BUY'
                else:
                    details['indicators']['sma'] = 'NEUTRAL'
            else:  # PUT
                if sma_20 < sma_50:
                    indicators_agreeing += 1
                    details['indicators']['sma'] = 'SELL'
                else:
                    details['indicators']['sma'] = 'NEUTRAL'
        
        # Calcular acuerdo
        if total_indicators > 0:
            agreement = indicators_agreeing / total_indicators
            details['agreement'] = agreement
            
            # Require al menos 50% de acuerdo (antes 60%)
            min_agreement = 0.50
            
            if agreement >= min_agreement:
                details['reason'] = f'{agreement*100:.0f}% de indicadores de acuerdo ({indicators_agreeing}/{total_indicators})'
                return True, details
            else:
                details['reason'] = f'Solo {agreement*100:.0f}% de acuerdo ({indicators_agreeing}/{total_indicators})'
                return False, details
        
        details['reason'] = 'Sin indicadores suficientes'
        return True, details  # No bloquear si no hay suficientes indicadores
    
    def get_stats(self):
        """Retorna estadísticas de rechazos"""
        return self.rejection_stats
    
    def reset_stats(self):
        """Resetea las estadísticas"""
        for key in self.rejection_stats:
            self.rejection_stats[key] = 0


class EntryRefiner:
    """
    Refina las decisiones del trader antes de ejecutar
    Añade capa adicional de validación
    """
    
    def __init__(self):
        self.validator = RefinedEntryValidator()
        self.approval_rate = []  # Track de tasa de aprobación
        
    def refine_decision(self, df, action, indicators_analysis=None, rl_prediction=None, market_context=None):
        """
        Refina una decisión antes de ejecutarla
        
        Returns:
            dict con 'approved' y detalles de validación
        """
        result = {
            'approved': False,
            'original_action': action,
            'validation': None,
            'message': ''
        }
        
        if action == 0:  # HOLD - no validar
            result['message'] = 'Acción original es HOLD'
            return result
        
        # Ejecutar validación estricta
        validation = self.validator.validate_entry(
            df=df,
            action=action,
            indicators_analysis=indicators_analysis,
            rl_prediction=rl_prediction,
            market_context=market_context
        )
        
        result['validation'] = validation
        
        if validation['valid']:
            result['approved'] = True
            result['message'] = f"✅ APROBADA - Confianza: {validation['confidence']*100:.0f}% | Score: {validation['score']:.0f}"
        else:
            result['approved'] = False
            result['message'] = f"❌ RECHAZADA - Razón: {validation['rejection_reason']}"
        
        # Track approval rate
        self.approval_rate.append(1 if result['approved'] else 0)
        
        return result
    
    def get_approval_rate(self):
        """Retorna la tasa de aprobación histórica"""
        if not self.approval_rate:
            return 0
        return sum(self.approval_rate) / len(self.approval_rate)
    
    def get_rejection_stats(self):
        """Retorna estadísticas de rechazos"""
        return self.validator.get_stats()