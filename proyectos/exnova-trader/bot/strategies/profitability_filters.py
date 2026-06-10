"""
Profitability Filters - Filtros avanzados para maximizar rentabilidad
Solo opera cuando las condiciones son ÓPTIMAS
"""
import pandas as pd
import numpy as np
from datetime import datetime, time
from optimize_knowledge import KnowledgeOptimizer

class ProfitabilityFilters:
    """
    Filtros profesionales para aumentar win rate y rentabilidad
    Basados en principios de trading institucional y aprendizaje histórico
    """
    
    def __init__(self):
        # Configuración de filtros
        self.min_trend_strength = 0.7  # Tendencia debe ser fuerte
        self.max_volatility_ratio = 2.5  # No operar en volatilidad extrema
        self.min_volatility_ratio = 0.5  # No operar en mercado muerto
        self.min_volume_ratio = 0.8  # Volumen debe ser significativo
        
        # Conectar con la base de conocimiento para filtros históricos
        self.optimizer = KnowledgeOptimizer()
        self.optimizer.analyze_patterns()  # Actualizar patrones al iniciar
        
        # Horarios óptimos (UTC) - Sesiones de mayor liquidez (más flexible)
        self.optimal_hours = [
            (7, 12),   # Sesión Londres
            (12, 18),  # Overlap Londres-NY + NY
            (19, 23),  # Sesión Asia
        ]
        
        # Zonas de soporte/resistencia (se actualizan dinámicamente)
        self.support_zones = []
        self.resistance_zones = []
        
    def apply_all_filters(self, df, proposed_action, asset="UNKNOWN"):
        """
        Aplica TODOS los filtros de rentabilidad
        
        Returns:
            dict: {
                'pass': bool,
                'score': float (0-100),
                'reasons': list,
                'warnings': list
            }
        """
        result = {
            'pass': False,
            'score': 0,
            'reasons': [],
            'warnings': []
        }
        
        if df is None or df.empty or len(df) < 100:
            result['warnings'].append("❌ Datos insuficientes para filtros")
            return result
        
        # Aplicar cada filtro y acumular score
        filters = [
            self._filter_trend_strength(df, proposed_action),
            self._filter_volatility(df),
            self._filter_momentum_confirmation(df, proposed_action),
            self._filter_support_resistance(df, proposed_action),
            self._filter_time_of_day(),
            self._filter_confluence(df, proposed_action),
            self._filter_risk_reward(df, proposed_action),
            self._filter_historical_performance(df, asset, proposed_action)  # 🆕 Nuevo filtro de aprendizaje
        ]
        
        # Calcular score total
        total_score = 0
        max_score = 0
        
        for filter_result in filters:
            total_score += filter_result['score']
            max_score += filter_result['max_score']
            result['reasons'].extend(filter_result['reasons'])
            result['warnings'].extend(filter_result['warnings'])
        
        # Score normalizado (0-100)
        result['score'] = (total_score / max_score * 100) if max_score > 0 else 0
        
        # Pasar solo si score >= 60 (más flexible)
        result['pass'] = result['score'] >= 60
        
        if result['pass']:
            if result['score'] >= 75:
                result['reasons'].append(f"✅ Score total: {result['score']:.0f}/100 - EXCELENTE")
            else:
                result['reasons'].append(f"✅ Score total: {result['score']:.0f}/100 - ACEPTABLE")
        else:
            result['warnings'].append(f"⚠️ Score total: {result['score']:.0f}/100 - Insuficiente (mínimo 60)")
        
        return result
    
    def _filter_trend_strength(self, df, action):
        """
        Filtro 1: Tendencia debe ser FUERTE y CLARA
        """
        result = {
            'score': 0,
            'max_score': 20,
            'reasons': [],
            'warnings': []
        }
        
        if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
            result['warnings'].append("⚠️ SMAs no disponibles")
            return result
        
        last = df.iloc[-1]
        sma_20 = last['sma_20']
        sma_50 = last['sma_50']
        price = last['close']
        
        # Calcular fuerza de tendencia
        sma_diff = abs(sma_20 - sma_50) / sma_50
        price_vs_sma20 = abs(price - sma_20) / sma_20
        
        # Determinar dirección de tendencia
        if sma_20 > sma_50 and price > sma_20:
            trend = 'UPTREND'
            trend_strength = min(sma_diff * 100, 1.0)  # Normalizar
        elif sma_20 < sma_50 and price < sma_20:
            trend = 'DOWNTREND'
            trend_strength = min(sma_diff * 100, 1.0)
        else:
            trend = 'SIDEWAYS'
            trend_strength = 0
        
        # Validar que la acción esté alineada con la tendencia
        if trend == 'UPTREND' and action == 1:  # CALL
            if trend_strength >= self.min_trend_strength:
                result['score'] = 20
                result['reasons'].append(f"✅ Tendencia alcista FUERTE ({trend_strength*100:.0f}%) + CALL")
            else:
                result['score'] = 10
                result['reasons'].append(f"⚠️ Tendencia alcista DÉBIL ({trend_strength*100:.0f}%)")
        
        elif trend == 'DOWNTREND' and action == 2:  # PUT
            if trend_strength >= self.min_trend_strength:
                result['score'] = 20
                result['reasons'].append(f"✅ Tendencia bajista FUERTE ({trend_strength*100:.0f}%) + PUT")
            else:
                result['score'] = 10
                result['reasons'].append(f"⚠️ Tendencia bajista DÉBIL ({trend_strength*100:.0f}%)")
        
        elif trend == 'SIDEWAYS':
            result['score'] = 8  # Permitir en lateral si otros indicadores son buenos
            result['reasons'].append("⚠️ Mercado LATERAL - Requiere señales fuertes")
        
        else:
            result['score'] = 10  # Permitir contra-tendencia si hay reversión
            result['reasons'].append(f"⚠️ Operación contra tendencia ({trend}) - Posible reversión")
        
        return result
    
    def _filter_volatility(self, df):
        """
        Filtro 2: Volatilidad debe estar en rango óptimo
        """
        result = {
            'score': 0,
            'max_score': 15,
            'reasons': [],
            'warnings': []
        }
        
        if 'atr' not in df.columns:
            result['warnings'].append("⚠️ ATR no disponible")
            return result
        
        current_atr = df.iloc[-1]['atr']
        avg_atr = df['atr'].mean()
        volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1
        
        # Volatilidad óptima: entre 0.5x y 2.5x la media
        if self.min_volatility_ratio <= volatility_ratio <= self.max_volatility_ratio:
            result['score'] = 15
            result['reasons'].append(f"✅ Volatilidad ÓPTIMA ({volatility_ratio:.2f}x)")
        elif volatility_ratio < self.min_volatility_ratio:
            result['score'] = 5
            result['warnings'].append(f"⚠️ Volatilidad MUY BAJA ({volatility_ratio:.2f}x) - Poco movimiento")
        else:
            result['score'] = 0
            result['warnings'].append(f"❌ Volatilidad EXTREMA ({volatility_ratio:.2f}x) - Muy arriesgado")
        
        return result
    
    def _filter_momentum_confirmation(self, df, action):
        """
        Filtro 3: Momentum debe confirmar la dirección
        """
        result = {
            'score': 0,
            'max_score': 20,
            'reasons': [],
            'warnings': []
        }
        
        if 'rsi' not in df.columns or 'macd' not in df.columns:
            result['warnings'].append("⚠️ Indicadores de momentum no disponibles")
            return result
        
        last = df.iloc[-1]
        rsi = last['rsi']
        macd = last['macd']
        
        # Para CALL: RSI < 35 (sobreventa) y MACD positivo
        if action == 1:  # CALL
            if rsi < 35 and macd > 0:
                result['score'] = 20
                result['reasons'].append(f"✅ Momentum PERFECTO para CALL (RSI:{rsi:.0f}, MACD+)")
            elif rsi < 35:
                result['score'] = 15
                result['reasons'].append(f"✅ RSI sobreventa ({rsi:.0f}) - Buen momento para CALL")
            elif rsi < 45:
                result['score'] = 10
                result['reasons'].append(f"⚠️ RSI bajo ({rsi:.0f}) pero no extremo")
            else:
                result['score'] = 0
                result['warnings'].append(f"❌ RSI alto ({rsi:.0f}) - NO es momento para CALL")
        
        # Para PUT: RSI > 65 (sobrecompra) y MACD negativo
        elif action == 2:  # PUT
            if rsi > 65 and macd < 0:
                result['score'] = 20
                result['reasons'].append(f"✅ Momentum PERFECTO para PUT (RSI:{rsi:.0f}, MACD-)")
            elif rsi > 65:
                result['score'] = 15
                result['reasons'].append(f"✅ RSI sobrecompra ({rsi:.0f}) - Buen momento para PUT")
            elif rsi > 55:
                result['score'] = 10
                result['reasons'].append(f"⚠️ RSI alto ({rsi:.0f}) pero no extremo")
            else:
                result['score'] = 0
                result['warnings'].append(f"❌ RSI bajo ({rsi:.0f}) - NO es momento para PUT")
        
        return result
    
    def _filter_support_resistance(self, df, action):
        """
        Filtro 4: Operar cerca de zonas de soporte/resistencia
        """
        result = {
            'score': 0,
            'max_score': 15,
            'reasons': [],
            'warnings': []
        }
        
        # Identificar zonas de soporte/resistencia dinámicamente
        self._update_support_resistance_zones(df)
        
        current_price = df.iloc[-1]['close']
        
        # Para CALL: debe estar cerca de soporte
        if action == 1:  # CALL
            nearest_support = self._find_nearest_level(current_price, self.support_zones)
            if nearest_support:
                distance = abs(current_price - nearest_support) / current_price
                if distance < 0.002:  # Dentro del 0.2%
                    result['score'] = 15
                    result['reasons'].append(f"✅ Precio en SOPORTE ({nearest_support:.5f}) - Excelente para CALL")
                elif distance < 0.005:  # Dentro del 0.5%
                    result['score'] = 10
                    result['reasons'].append(f"✅ Cerca de SOPORTE ({nearest_support:.5f})")
                else:
                    result['score'] = 5
                    result['reasons'].append(f"⚠️ Lejos de soporte más cercano")
            else:
                result['score'] = 5
                result['reasons'].append("⚠️ No hay soporte claro identificado")
        
        # Para PUT: debe estar cerca de resistencia
        elif action == 2:  # PUT
            nearest_resistance = self._find_nearest_level(current_price, self.resistance_zones)
            if nearest_resistance:
                distance = abs(current_price - nearest_resistance) / current_price
                if distance < 0.002:  # Dentro del 0.2%
                    result['score'] = 15
                    result['reasons'].append(f"✅ Precio en RESISTENCIA ({nearest_resistance:.5f}) - Excelente para PUT")
                elif distance < 0.005:  # Dentro del 0.5%
                    result['score'] = 10
                    result['reasons'].append(f"✅ Cerca de RESISTENCIA ({nearest_resistance:.5f})")
                else:
                    result['score'] = 5
                    result['reasons'].append(f"⚠️ Lejos de resistencia más cercana")
            else:
                result['score'] = 5
                result['reasons'].append("⚠️ No hay resistencia clara identificada")
        
        return result
    
    def _filter_time_of_day(self):
        """
        Filtro 5: Operar solo en horarios de alta liquidez
        """
        result = {
            'score': 0,
            'max_score': 10,
            'reasons': [],
            'warnings': []
        }
        
        current_hour = datetime.utcnow().hour
        
        # Verificar si está en horario óptimo
        in_optimal_time = False
        for start, end in self.optimal_hours:
            if start <= current_hour < end:
                in_optimal_time = True
                break
        
        if in_optimal_time:
            result['score'] = 10
            result['reasons'].append(f"✅ Horario ÓPTIMO ({current_hour}:00 UTC) - Alta liquidez")
        else:
            result['score'] = 7  # Más flexible, no penaliza tanto
            result['reasons'].append(f"⚠️ Horario normal ({current_hour}:00 UTC)")
        
        return result
    
    def _filter_confluence(self, df, action):
        """
        Filtro 6: Múltiples indicadores deben confluir
        """
        result = {
            'score': 0,
            'max_score': 15,
            'reasons': [],
            'warnings': []
        }
        
        last = df.iloc[-1]
        confluence_count = 0
        
        # Verificar confluencia de señales
        if action == 1:  # CALL
            # RSI sobreventa
            if 'rsi' in df.columns and last['rsi'] < 35:
                confluence_count += 1
            
            # Precio en BB inferior
            if 'bb_low' in df.columns and last['close'] <= last['bb_low']:
                confluence_count += 1
            
            # MACD positivo
            if 'macd' in df.columns and last['macd'] > 0:
                confluence_count += 1
            
            # Precio por encima de SMA20
            if 'sma_20' in df.columns and last['close'] > last['sma_20']:
                confluence_count += 1
        
        elif action == 2:  # PUT
            # RSI sobrecompra
            if 'rsi' in df.columns and last['rsi'] > 65:
                confluence_count += 1
            
            # Precio en BB superior
            if 'bb_high' in df.columns and last['close'] >= last['bb_high']:
                confluence_count += 1
            
            # MACD negativo
            if 'macd' in df.columns and last['macd'] < 0:
                confluence_count += 1
            
            # Precio por debajo de SMA20
            if 'sma_20' in df.columns and last['close'] < last['sma_20']:
                confluence_count += 1
        
        # Score basado en confluencia
        if confluence_count >= 3:
            result['score'] = 15
            result['reasons'].append(f"✅ CONFLUENCIA FUERTE ({confluence_count}/4 señales)")
        elif confluence_count == 2:
            result['score'] = 10
            result['reasons'].append(f"✅ Confluencia moderada ({confluence_count}/4 señales)")
        elif confluence_count == 1:
            result['score'] = 5
            result['warnings'].append(f"⚠️ Confluencia débil ({confluence_count}/4 señales)")
        else:
            result['score'] = 0
            result['warnings'].append("❌ Sin confluencia de señales")
        
        return result
    
    def _filter_risk_reward(self, df, action):
        """
        Filtro 7: Ratio riesgo/recompensa debe ser favorable
        """
        result = {
            'score': 0,
            'max_score': 5,
            'reasons': [],
            'warnings': []
        }
        
        # Para opciones binarias, el R:R es fijo (aprox 1.8:1)
        # Pero podemos evaluar la probabilidad de éxito basada en distancia a objetivo
        
        if 'atr' not in df.columns:
            result['score'] = 3  # Score neutral
            return result
        
        current_price = df.iloc[-1]['close']
        atr = df.iloc[-1]['atr']
        
        # Calcular distancia esperada de movimiento
        expected_move = atr * 0.5  # Movimiento esperado en 1-5 minutos
        
        # Para CALL: verificar espacio al alza
        if action == 1:
            if 'bb_high' in df.columns:
                distance_to_target = df.iloc[-1]['bb_high'] - current_price
                if distance_to_target > expected_move:
                    result['score'] = 5
                    result['reasons'].append("✅ Espacio suficiente al alza")
                else:
                    result['score'] = 2
                    result['warnings'].append("⚠️ Poco espacio al alza")
            else:
                result['score'] = 3
        
        # Para PUT: verificar espacio a la baja
        elif action == 2:
            if 'bb_low' in df.columns:
                distance_to_target = current_price - df.iloc[-1]['bb_low']
                if distance_to_target > expected_move:
                    result['score'] = 5
                    result['reasons'].append("✅ Espacio suficiente a la baja")
                else:
                    result['score'] = 2
                    result['warnings'].append("⚠️ Poco espacio a la baja")
            else:
                result['score'] = 3
        
        return result
    
    def _update_support_resistance_zones(self, df):
        """
        Identifica zonas de soporte y resistencia dinámicamente
        """
        if len(df) < 50:
            return
        
        # Usar últimas 50 velas
        recent = df.tail(50)
        
        # Identificar máximos y mínimos locales
        highs = recent['high'].values
        lows = recent['low'].values
        
        # Encontrar niveles de resistencia (máximos locales)
        self.resistance_zones = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                self.resistance_zones.append(highs[i])
        
        # Encontrar niveles de soporte (mínimos locales)
        self.support_zones = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                self.support_zones.append(lows[i])
        
        # Mantener solo los 3 niveles más relevantes
        self.resistance_zones = sorted(self.resistance_zones, reverse=True)[:3]
        self.support_zones = sorted(self.support_zones)[:3]
    
    def _find_nearest_level(self, price, levels):
        """
        Encuentra el nivel más cercano al precio actual
        """
        if not levels:
            return None
        
        nearest = min(levels, key=lambda x: abs(x - price))
        return nearest

    def _filter_historical_performance(self, df, asset, action):
        """
        Filtro 8 (Aprendizaje): Rigurosidad basada en historial
        """
        result = {
            'score': 0,
            'max_score': 20,
            'reasons': [],
            'warnings': []
        }
        
        refinements = self.optimizer.get_refinements_for_asset(asset)
        
        # 1. Chequeo de Activo Tóxico
        if refinements['is_toxic']:
            result['warnings'].append(f"⚠️ ACTIVO TÓXICO ({asset}): Historial negativo. Se requiere extrema precaución.")
            # Penalización fuerte: solo pasa si todo lo demás es perfecto
            result['score'] = -50 
            return result
            
        # 2. Chequeo de Activo Estrella
        if refinements['is_star']:
            result['score'] += 10
            result['reasons'].append(f"✅ ACTIVO ESTRELLA ({asset}): Historial muy positivo (+10 pts)")
        
        # 3. Chequeo de Horario Peligroso
        current_hour = datetime.utcnow().hour
        dangerous_hours = self.optimizer.db.get('patterns_found', {}).get('dangerous_hours', [])
        if current_hour in dangerous_hours:
            result['warnings'].append(f"⚠️ HORARIO PELIGROSO ({current_hour}:00): Historial de pérdidas en esta hora.")
            result['score'] -= 10
        
        # 4. Chequeo de Umbral RSI Específico (Rigurosidad Adaptativa)
        rsi_thresholds = refinements.get('rsi_adjust', {})
        current_rsi = df.iloc[-1]['rsi'] if 'rsi' in df.columns else 50
        
        if action == 1:  # CALL
            min_rsi = rsi_thresholds.get('CALL')
            if min_rsi and current_rsi > min_rsi:
                result['warnings'].append(f"❌ RSI Insuficiente para CALL ({current_rsi:.1f} > {min_rsi:.1f}). Historial sugiere entrar más abajo.")
                result['score'] -= 20 # Penalización fuerte
            elif min_rsi:
                result['score'] += 5
                result['reasons'].append(f"✅ RSI cumple criterio estricto (<{min_rsi:.1f})")
                
        elif action == 2:  # PUT
            max_rsi = rsi_thresholds.get('PUT')
            if max_rsi and current_rsi < max_rsi:
                result['warnings'].append(f"❌ RSI Insuficiente para PUT ({current_rsi:.1f} < {max_rsi:.1f}). Historial sugiere entrar más arriba.")
                result['score'] -= 20
            elif max_rsi:
                result['score'] += 5
                result['reasons'].append(f"✅ RSI cumple criterio estricto (>{max_rsi:.1f})")
        
        # Si no cayó en ninguna trampa histórica
        if result['score'] >= 0:
            result['score'] += 5
            
        return result
