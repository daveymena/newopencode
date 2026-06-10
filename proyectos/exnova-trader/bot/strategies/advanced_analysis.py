"""
Análisis Avanzado de Trading
Implementa múltiples estrategias profesionales
"""
import pandas as pd
import numpy as np

class AdvancedMarketAnalysis:
    """
    Análisis avanzado del mercado con múltiples estrategias
    """
    def __init__(self):
        self.min_candles_for_analysis = 100  # Mínimo para análisis serio
        
    def full_market_analysis(self, df):
        """
        Análisis COMPLETO del mercado antes de operar
        
        Returns:
            dict: {
                'can_trade': bool,
                'recommendation': str,
                'confidence': float,
                'reasons': list,
                'warnings': list,
                'strategies': dict
            }
        """
        result = {
            'can_trade': False,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'reasons': [],
            'warnings': [],
            'strategies': {}
        }
        
        # Verificar datos suficientes
        if len(df) < self.min_candles_for_analysis:
            result['warnings'].append(f"⚠️ Pocas velas ({len(df)}), se necesitan {self.min_candles_for_analysis}")
            return result
        
        # 1. ANÁLISIS DE SOPORTES Y RESISTENCIAS
        support_resistance = self.analyze_support_resistance(df)
        result['strategies']['support_resistance'] = support_resistance
        
        # 2. ANÁLISIS DE REVERSIONES
        reversal = self.analyze_reversal_patterns(df)
        result['strategies']['reversal'] = reversal
        
        # 3. ANÁLISIS DE MOMENTUM
        momentum = self.analyze_momentum(df)
        result['strategies']['momentum'] = momentum
        
        # 4. ANÁLISIS DE ACUMULACIÓN/DISTRIBUCIÓN
        accumulation = self.analyze_accumulation_distribution(df)
        result['strategies']['accumulation'] = accumulation
        
        # 5. DETECCIÓN DE TRAMPAS DEL MERCADO
        traps = self.detect_market_traps(df)
        result['strategies']['traps'] = traps
        
        # 6. ANÁLISIS DE VOLUMEN
        volume_analysis = self.analyze_volume(df)
        result['strategies']['volume'] = volume_analysis
        
        # 7. ANÁLISIS DE TENDENCIA
        trend = self.analyze_trend(df)
        result['strategies']['trend'] = trend
        
        # CONSOLIDAR ANÁLISIS
        return self.consolidate_analysis(result)
    
    def analyze_support_resistance(self, df):
        """Identifica soportes y resistencias"""
        analysis = {
            'signal': 'NEUTRAL',
            'strength': 0,
            'reason': '',
            'levels': {}
        }
        
        if len(df) < 50:
            return analysis
        
        # Calcular niveles de soporte y resistencia
        highs = df['high'].rolling(window=20).max()
        lows = df['low'].rolling(window=20).min()
        
        current_price = df.iloc[-1]['close']
        recent_high = highs.iloc[-1]
        recent_low = lows.iloc[-1]
        
        # Calcular distancia a niveles
        distance_to_resistance = (recent_high - current_price) / current_price
        distance_to_support = (current_price - recent_low) / current_price
        
        analysis['levels'] = {
            'resistance': recent_high,
            'support': recent_low,
            'current': current_price
        }
        
        # Determinar señal
        if distance_to_support < 0.001:  # Muy cerca del soporte
            analysis['signal'] = 'CALL'
            analysis['strength'] = 0.8
            analysis['reason'] = f"Precio cerca del soporte ({recent_low:.5f})"
        elif distance_to_resistance < 0.001:  # Muy cerca de resistencia
            analysis['signal'] = 'PUT'
            analysis['strength'] = 0.8
            analysis['reason'] = f"Precio cerca de resistencia ({recent_high:.5f})"
        else:
            analysis['signal'] = 'NEUTRAL'
            analysis['strength'] = 0.3
            analysis['reason'] = "Precio en zona neutral"
        
        return analysis
    
    def analyze_reversal_patterns(self, df):
        """Detecta patrones de reversión"""
        analysis = {
            'signal': 'NEUTRAL',
            'strength': 0,
            'reason': '',
            'patterns': []
        }
        
        if len(df) < 10:
            return analysis
        
        last_candles = df.tail(5)
        
        # Patrón de Martillo (Hammer) - Reversión alcista
        last = last_candles.iloc[-1]
        body = abs(last['close'] - last['open'])
        lower_shadow = min(last['close'], last['open']) - last['low']
        upper_shadow = last['high'] - max(last['close'], last['open'])
        
        if lower_shadow > 2 * body and upper_shadow < 0.3 * body:
            analysis['patterns'].append('Hammer')
            analysis['signal'] = 'CALL'
            analysis['strength'] = 0.7
            analysis['reason'] = "Patrón Hammer detectado (reversión alcista)"
        
        # Patrón de Estrella Fugaz (Shooting Star) - Reversión bajista
        if upper_shadow > 2 * body and lower_shadow < 0.3 * body:
            analysis['patterns'].append('Shooting Star')
            analysis['signal'] = 'PUT'
            analysis['strength'] = 0.7
            analysis['reason'] = "Patrón Shooting Star detectado (reversión bajista)"
        
        # Divergencia con RSI
        if 'rsi' in df.columns and len(df) >= 20:
            price_trend = df['close'].tail(20).diff().sum()
            rsi_trend = df['rsi'].tail(20).diff().sum()
            
            # Divergencia bajista: precio sube pero RSI baja
            if price_trend > 0 and rsi_trend < 0:
                analysis['patterns'].append('Divergencia Bajista')
                if analysis['signal'] == 'NEUTRAL':
                    analysis['signal'] = 'PUT'
                    analysis['strength'] = 0.6
                    analysis['reason'] = "Divergencia bajista detectada"
            
            # Divergencia alcista: precio baja pero RSI sube
            elif price_trend < 0 and rsi_trend > 0:
                analysis['patterns'].append('Divergencia Alcista')
                if analysis['signal'] == 'NEUTRAL':
                    analysis['signal'] = 'CALL'
                    analysis['strength'] = 0.6
                    analysis['reason'] = "Divergencia alcista detectada"
        
        return analysis
    
    def analyze_momentum(self, df):
        """Analiza el momentum del mercado"""
        analysis = {
            'signal': 'NEUTRAL',
            'strength': 0,
            'reason': '',
            'momentum_score': 0
        }
        
        if 'rsi' not in df.columns or 'macd' not in df.columns:
            return analysis
        
        last = df.iloc[-1]
        rsi = last['rsi']
        macd = last['macd']
        
        # Calcular momentum score
        momentum_score = 0
        
        # RSI momentum
        if rsi > 60:
            momentum_score += 1
        elif rsi < 40:
            momentum_score -= 1
        
        # MACD momentum
        if macd > 0:
            momentum_score += 1
        else:
            momentum_score -= 1
        
        # Momentum de precio
        if len(df) >= 10:
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]
            if price_change > 0.001:
                momentum_score += 1
            elif price_change < -0.001:
                momentum_score -= 1
        
        analysis['momentum_score'] = momentum_score
        
        # Determinar señal
        if momentum_score >= 2:
            analysis['signal'] = 'CALL'
            analysis['strength'] = min(momentum_score / 3, 1.0)
            analysis['reason'] = f"Momentum alcista fuerte (score: {momentum_score})"
        elif momentum_score <= -2:
            analysis['signal'] = 'PUT'
            analysis['strength'] = min(abs(momentum_score) / 3, 1.0)
            analysis['reason'] = f"Momentum bajista fuerte (score: {momentum_score})"
        else:
            analysis['signal'] = 'NEUTRAL'
            analysis['strength'] = 0.3
            analysis['reason'] = f"Momentum débil (score: {momentum_score})"
        
        return analysis
    
    def analyze_accumulation_distribution(self, df):
        """Analiza acumulación/distribución"""
        analysis = {
            'signal': 'NEUTRAL',
            'strength': 0,
            'reason': '',
            'phase': 'NEUTRAL'
        }
        
        if 'volume' not in df.columns or len(df) < 20:
            return analysis
        
        # Calcular A/D Line
        clv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        clv = clv.fillna(0)
        ad_line = (clv * df['volume']).cumsum()
        
        # Analizar tendencia de A/D
        ad_trend = ad_line.tail(10).diff().sum()
        price_trend = df['close'].tail(10).diff().sum()
        
        if ad_trend > 0 and price_trend > 0:
            analysis['phase'] = 'ACUMULACIÓN'
            analysis['signal'] = 'CALL'
            analysis['strength'] = 0.7
            analysis['reason'] = "Fase de acumulación detectada"
        elif ad_trend < 0 and price_trend < 0:
            analysis['phase'] = 'DISTRIBUCIÓN'
            analysis['signal'] = 'PUT'
            analysis['strength'] = 0.7
            analysis['reason'] = "Fase de distribución detectada"
        elif ad_trend > 0 and price_trend < 0:
            analysis['phase'] = 'ACUMULACIÓN OCULTA'
            analysis['signal'] = 'CALL'
            analysis['strength'] = 0.8
            analysis['reason'] = "Acumulación oculta (precio baja pero volumen comprador)"
        elif ad_trend < 0 and price_trend > 0:
            analysis['phase'] = 'DISTRIBUCIÓN OCULTA'
            analysis['signal'] = 'PUT'
            analysis['strength'] = 0.8
            analysis['reason'] = "Distribución oculta (precio sube pero volumen vendedor)"
        
        return analysis
    
    def detect_market_traps(self, df):
        """Detecta trampas del mercado (bull/bear traps)"""
        analysis = {
            'trap_detected': False,
            'trap_type': None,
            'warning': '',
            'avoid_trade': False
        }
        
        if len(df) < 20:
            return analysis
        
        recent = df.tail(10)
        
        # Bull Trap: Precio rompe resistencia pero vuelve a caer
        if len(recent) >= 5:
            max_price = recent['high'].max()
            current_price = recent.iloc[-1]['close']
            
            # Si el precio subió mucho y ahora está cayendo
            if max_price > recent.iloc[0]['high'] * 1.002:  # Subió 0.2%
                if current_price < max_price * 0.998:  # Cayó 0.2% desde el máximo
                    analysis['trap_detected'] = True
                    analysis['trap_type'] = 'BULL_TRAP'
                    analysis['warning'] = "⚠️ Posible Bull Trap detectado"
                    analysis['avoid_trade'] = True
        
        # Bear Trap: Precio rompe soporte pero vuelve a subir
        if len(recent) >= 5:
            min_price = recent['low'].min()
            current_price = recent.iloc[-1]['close']
            
            # Si el precio bajó mucho y ahora está subiendo
            if min_price < recent.iloc[0]['low'] * 0.998:  # Bajó 0.2%
                if current_price > min_price * 1.002:  # Subió 0.2% desde el mínimo
                    analysis['trap_detected'] = True
                    analysis['trap_type'] = 'BEAR_TRAP'
                    analysis['warning'] = "⚠️ Posible Bear Trap detectado"
                    analysis['avoid_trade'] = True
        
        return analysis
    
    def analyze_volume(self, df):
        """Analiza el volumen de trading"""
        analysis = {
            'signal': 'NEUTRAL',
            'strength': 0,
            'reason': '',
            'volume_trend': 'NORMAL'
        }
        
        if 'volume' not in df.columns or len(df) < 20:
            return analysis
        
        current_volume = df.iloc[-1]['volume']
        avg_volume = df['volume'].tail(20).mean()
        
        # Volumen anormalmente alto
        if current_volume > avg_volume * 1.5:
            analysis['volume_trend'] = 'ALTO'
            analysis['strength'] = 0.6
            analysis['reason'] = "Volumen alto detectado (posible movimiento fuerte)"
        
        # Volumen anormalmente bajo
        elif current_volume < avg_volume * 0.5:
            analysis['volume_trend'] = 'BAJO'
            analysis['strength'] = 0.3
            analysis['reason'] = "Volumen bajo (evitar operar)"
        
        return analysis
    
    def analyze_trend(self, df):
        """Analiza la tendencia del mercado"""
        analysis = {
            'trend': 'NEUTRAL',
            'strength': 0,
            'reason': ''
        }
        
        if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
            return analysis
        
        last = df.iloc[-1]
        sma_20 = last['sma_20']
        sma_50 = last['sma_50']
        price = last['close']
        
        # Tendencia alcista fuerte
        if sma_20 > sma_50 and price > sma_20:
            analysis['trend'] = 'ALCISTA'
            analysis['strength'] = 0.8
            analysis['reason'] = "Tendencia alcista confirmada (precio > SMA20 > SMA50)"
        
        # Tendencia bajista fuerte
        elif sma_20 < sma_50 and price < sma_20:
            analysis['trend'] = 'BAJISTA'
            analysis['strength'] = 0.8
            analysis['reason'] = "Tendencia bajista confirmada (precio < SMA20 < SMA50)"
        
        # Cruce de medias (cambio de tendencia)
        elif len(df) >= 2:
            prev_sma_20 = df.iloc[-2]['sma_20']
            prev_sma_50 = df.iloc[-2]['sma_50']
            
            # Cruce alcista
            if sma_20 > sma_50 and prev_sma_20 <= prev_sma_50:
                analysis['trend'] = 'CRUCE_ALCISTA'
                analysis['strength'] = 0.9
                analysis['reason'] = "Cruce alcista de medias detectado"
            
            # Cruce bajista
            elif sma_20 < sma_50 and prev_sma_20 >= prev_sma_50:
                analysis['trend'] = 'CRUCE_BAJISTA'
                analysis['strength'] = 0.9
                analysis['reason'] = "Cruce bajista de medias detectado"
        
        return analysis
    
    def consolidate_analysis(self, result):
        """Consolida todos los análisis en una decisión final"""
        strategies = result['strategies']
        
        # Verificar trampas del mercado
        if strategies.get('traps', {}).get('avoid_trade', False):
            result['can_trade'] = False
            result['recommendation'] = 'HOLD'
            result['warnings'].append(strategies['traps']['warning'])
            result['reasons'].append("🚫 Trampa del mercado detectada - NO OPERAR")
            return result
        
        # PRIORIDAD: Si soporte/resistencia da señal FUERTE, darle más peso
        sr_analysis = strategies.get('support_resistance', {})
        if sr_analysis.get('strength', 0) >= 0.8:
            # Señal muy fuerte de soporte/resistencia
            result['reasons'].append(f"⭐ SEÑAL FUERTE: {sr_analysis.get('reason', '')}")
            result['recommendation'] = sr_analysis['signal']
            result['confidence'] = sr_analysis['strength']
            result['can_trade'] = True
            return result
        
        # Recolectar señales
        signals = []
        weights = []
        
        for strategy_name, strategy_data in strategies.items():
            if strategy_name == 'traps':
                continue
            
            signal = strategy_data.get('signal', 'NEUTRAL')
            strength = strategy_data.get('strength', 0)
            reason = strategy_data.get('reason', '')
            
            # Dar más peso a soportes/resistencias
            if strategy_name == 'support_resistance' and strength > 0.5:
                strength = strength * 1.5  # 50% más peso
            
            if signal != 'NEUTRAL' and strength > 0.5:
                signals.append(signal)
                weights.append(strength)
                result['reasons'].append(f"✅ {strategy_name.upper()}: {reason}")
        
        # Calcular consenso
        if not signals:
            result['can_trade'] = False
            result['recommendation'] = 'HOLD'
            result['warnings'].append("⚠️ No hay señales claras de ninguna estrategia")
            return result
        
        # Contar votos
        call_votes = sum(w for s, w in zip(signals, weights) if s == 'CALL')
        put_votes = sum(w for s, w in zip(signals, weights) if s == 'PUT')
        total_weight = sum(weights)
        
        # Determinar recomendación
        if call_votes > put_votes and call_votes / total_weight > 0.6:
            result['recommendation'] = 'CALL'
            result['confidence'] = call_votes / total_weight
            result['can_trade'] = True
        elif put_votes > call_votes and put_votes / total_weight > 0.6:
            result['recommendation'] = 'PUT'
            result['confidence'] = put_votes / total_weight
            result['can_trade'] = True
        else:
            result['recommendation'] = 'HOLD'
            result['confidence'] = max(call_votes, put_votes) / total_weight if total_weight > 0 else 0
            result['can_trade'] = False
            result['warnings'].append(f"⚠️ Señales contradictorias (CALL: {call_votes:.1f}, PUT: {put_votes:.1f})")
        
        return result
