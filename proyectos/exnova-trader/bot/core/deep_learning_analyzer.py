"""
Deep Learning Analyzer - Aprende de cada pérdida para mejorar en tiempo real
Analiza: ¿Por qué perdió? ¿Cuándo debió entrar? ¿Qué variables fallaron?
"""
import pandas as pd
import numpy as np
from datetime import datetime
import json
from pathlib import Path

class DeepLearningAnalyzer:
    """
    Sistema de aprendizaje profundo que analiza cada operación perdida
    y aprende cómo mejorar para la próxima
    """
    
    def __init__(self):
        self.lessons_path = Path("data/deep_lessons.json")
        self.lessons = []
        self.improvements = {
            'entry_timing': [],      # Lecciones sobre timing de entrada
            'exit_timing': [],       # Lecciones sobre timing de salida
            'indicator_weights': {}, # Pesos de indicadores que funcionan
            'failed_patterns': [],   # Patrones que NO funcionan
            'successful_patterns': [], # Patrones que SÍ funcionan
            'optimal_conditions': {} # Condiciones óptimas por activo
        }
        self.load_lessons()
    
    def load_lessons(self):
        """Carga lecciones previas"""
        if self.lessons_path.exists():
            try:
                with open(self.lessons_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.lessons = data.get('lessons', [])
                    self.improvements = data.get('improvements', self.improvements)
                print(f"📚 {len(self.lessons)} lecciones cargadas")
            except Exception as e:
                print(f"⚠️ Error cargando lecciones: {e}")
    
    def save_lessons(self):
        """Guarda lecciones aprendidas"""
        try:
            self.lessons_path.parent.mkdir(exist_ok=True)
            data = {
                'lessons': self.lessons[-100:],  # Últimas 100 lecciones
                'improvements': self.improvements
            }
            with open(self.lessons_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error guardando lecciones: {e}")
    
    def analyze_loss(self, trade_data, market_data_before, market_data_after):
        """
        Analiza una operación perdida en profundidad
        
        Args:
            trade_data: Datos de la operación (asset, direction, entry_price, etc.)
            market_data_before: DataFrame con velas ANTES de la operación
            market_data_after: DataFrame con velas DESPUÉS de la operación
        
        Returns:
            dict: Análisis completo con lecciones aprendidas
        """
        print(f"\n🔬 ANÁLISIS PROFUNDO DE PÉRDIDA")
        print(f"   Activo: {trade_data['asset']}")
        print(f"   Dirección: {trade_data['direction']}")
        print(f"   Precio entrada: {trade_data['entry_price']}")
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'trade': trade_data,
            'result': 'loss',
            'why_lost': [],
            'when_should_enter': None,
            'what_failed': [],
            'how_to_improve': [],
            'lesson': None
        }
        
        # 1. ¿POR QUÉ PERDIÓ?
        why_lost = self._analyze_why_lost(trade_data, market_data_before, market_data_after)
        analysis['why_lost'] = why_lost
        
        # 2. ¿CUÁNDO DEBIÓ ENTRAR?
        optimal_entry = self._find_optimal_entry_time(trade_data, market_data_before, market_data_after)
        analysis['when_should_enter'] = optimal_entry
        
        # 3. ¿QUÉ VARIABLES FALLARON?
        failed_vars = self._identify_failed_variables(trade_data, market_data_before)
        analysis['what_failed'] = failed_vars
        
        # 4. ¿CÓMO MEJORAR?
        improvements = self._generate_improvements(why_lost, optimal_entry, failed_vars)
        analysis['how_to_improve'] = improvements
        
        # 5. CREAR LECCIÓN
        lesson = self._create_lesson(analysis)
        analysis['lesson'] = lesson
        
        # 6. GUARDAR Y APLICAR
        self.lessons.append(analysis)
        self._apply_improvements(improvements)
        self.save_lessons()
        
        return analysis
    
    def analyze_win(self, trade_data, market_data_before, market_data_after):
        """
        Analiza una operación GANADA para encontrar puntos de entrada aún mejores
        
        Args:
            trade_data: Datos de la operación (asset, direction, entry_price, etc.)
            market_data_before: DataFrame con velas ANTES de la operación
            market_data_after: DataFrame con velas DESPUÉS de la operación
        
        Returns:
            dict: Análisis completo con oportunidades de mejora
        """
        print(f"\n💎 ANÁLISIS DE OPTIMIZACIÓN (Operación Ganada)")
        print(f"   Activo: {trade_data['asset']}")
        print(f"   Dirección: {trade_data['direction']}")
        print(f"   Precio entrada: {trade_data['entry_price']}")
        print(f"   Ganancia: ${trade_data.get('profit', 0):.2f}")
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'trade': trade_data,
            'result': 'win',
            'why_won': [],
            'could_improve': None,
            'what_worked': [],
            'how_to_maximize': [],
            'lesson': None
        }
        
        # 1. ¿POR QUÉ GANÓ?
        why_won = self._analyze_why_won(trade_data, market_data_before, market_data_after)
        analysis['why_won'] = why_won
        
        # 2. ¿PUDO GANAR MÁS?
        better_entry = self._find_better_entry_for_win(trade_data, market_data_before, market_data_after)
        analysis['could_improve'] = better_entry
        
        # 3. ¿QUÉ VARIABLES FUNCIONARON?
        working_vars = self._identify_working_variables(trade_data, market_data_before)
        analysis['what_worked'] = working_vars
        
        # 4. ¿CÓMO MAXIMIZAR?
        maximizations = self._generate_maximizations(why_won, better_entry, working_vars)
        analysis['how_to_maximize'] = maximizations
        
        # 5. CREAR LECCIÓN POSITIVA
        lesson = self._create_positive_lesson(analysis)
        analysis['lesson'] = lesson
        
        # 6. GUARDAR Y APLICAR
        self.lessons.append(analysis)
        self._apply_maximizations(maximizations)
        self.save_lessons()
        
        return analysis
    
    def _analyze_why_lost(self, trade_data, df_before, df_after):
        """Analiza por qué perdió la operación"""
        reasons = []
        
        if df_before.empty or df_after.empty:
            return ["Sin datos suficientes para análisis"]
        
        entry_price = trade_data['entry_price']
        direction = trade_data['direction'].lower()
        
        # Obtener precio después de la operación
        if len(df_after) > 0:
            exit_price = df_after.iloc[-1]['close']
            price_movement = ((exit_price - entry_price) / entry_price) * 100
            
            # 1. ANÁLISIS DE MOVIMIENTO
            if direction == 'call' and price_movement < 0:
                reasons.append(f"Precio bajó {abs(price_movement):.3f}% en vez de subir")
                
                # ¿Había señales de que bajaría?
                last_candle = df_before.iloc[-1]
                if last_candle.get('rsi', 50) > 70:
                    reasons.append("RSI estaba sobrecomprado (>70) - señal de caída inminente")
                if last_candle.get('macd', 0) < 0:
                    reasons.append("MACD negativo - momentum bajista")
                
            elif direction == 'put' and price_movement > 0:
                reasons.append(f"Precio subió {price_movement:.3f}% en vez de bajar")
                
                # ¿Había señales de que subiría?
                last_candle = df_before.iloc[-1]
                if last_candle.get('rsi', 50) < 30:
                    reasons.append("RSI estaba sobrevendido (<30) - señal de rebote inminente")
                if last_candle.get('macd', 0) > 0:
                    reasons.append("MACD positivo - momentum alcista")
        
        # 2. ANÁLISIS DE TENDENCIA
        if len(df_before) >= 20:
            sma_20 = df_before['close'].rolling(20).mean().iloc[-1]
            price = df_before.iloc[-1]['close']
            
            if direction == 'call' and price < sma_20:
                reasons.append("Compró por debajo de SMA20 - contra tendencia")
            elif direction == 'put' and price > sma_20:
                reasons.append("Vendió por encima de SMA20 - contra tendencia")
        
        # 3. ANÁLISIS DE VOLATILIDAD
        if 'atr' in df_before.columns:
            atr = df_before.iloc[-1]['atr']
            if atr > df_before['atr'].mean() * 1.5:
                reasons.append("Volatilidad muy alta - mercado impredecible")
        
        return reasons if reasons else ["Razón desconocida - mercado aleatorio"]
    
    def _find_optimal_entry_time(self, trade_data, df_before, df_after):
        """
        Encuentra el momento óptimo de entrada
        Analiza: ¿Debió entrar antes? ¿Después? ¿Cuánto tiempo?
        """
        if df_before.empty or df_after.empty:
            return None
        
        entry_price = trade_data['entry_price']
        direction = trade_data['direction'].lower()
        
        optimal = {
            'should_wait': False,
            'wait_time': 0,
            'reason': '',
            'better_entry_price': entry_price,
            'improvement': 0
        }
        
        # Analizar velas DESPUÉS de la entrada
        if len(df_after) >= 5:
            # Buscar mejor punto de entrada en las siguientes 5 velas
            for i, row in df_after.head(5).iterrows():
                if direction == 'call':
                    # Para CALL, buscar precio más bajo (mejor entrada)
                    if row['low'] < entry_price:
                        better_price = row['low']
                        improvement = ((entry_price - better_price) / entry_price) * 100
                        
                        if improvement > optimal['improvement']:
                            optimal['should_wait'] = True
                            optimal['wait_time'] = i + 1  # Número de vela
                            optimal['better_entry_price'] = better_price
                            optimal['improvement'] = improvement
                            optimal['reason'] = f"Precio bajó a {better_price:.5f} en vela {i+1}"
                
                elif direction == 'put':
                    # Para PUT, buscar precio más alto (mejor entrada)
                    if row['high'] > entry_price:
                        better_price = row['high']
                        improvement = ((better_price - entry_price) / entry_price) * 100
                        
                        if improvement > optimal['improvement']:
                            optimal['should_wait'] = True
                            optimal['wait_time'] = i + 1
                            optimal['better_entry_price'] = better_price
                            optimal['improvement'] = improvement
                            optimal['reason'] = f"Precio subió a {better_price:.5f} en vela {i+1}"
        
        # Si encontró mejor entrada
        if optimal['should_wait']:
            optimal['lesson'] = f"Esperar {optimal['wait_time']} vela(s) hubiera mejorado {optimal['improvement']:.2f}%"
        else:
            optimal['lesson'] = "El timing de entrada fue correcto"
        
        return optimal
    
    def _identify_failed_variables(self, trade_data, df_before):
        """Identifica qué variables/indicadores fallaron"""
        failed = []
        
        if df_before.empty:
            return failed
        
        last_candle = df_before.iloc[-1]
        direction = trade_data['direction'].lower()
        
        # 1. RSI
        rsi = last_candle.get('rsi', 50)
        if direction == 'call' and rsi > 60:
            failed.append({
                'variable': 'RSI',
                'value': rsi,
                'problem': 'RSI alto para CALL',
                'recommendation': 'Solo CALL si RSI < 40'
            })
        elif direction == 'put' and rsi < 40:
            failed.append({
                'variable': 'RSI',
                'value': rsi,
                'problem': 'RSI bajo para PUT',
                'recommendation': 'Solo PUT si RSI > 60'
            })
        
        # 2. MACD
        macd = last_candle.get('macd', 0)
        if direction == 'call' and macd < 0:
            failed.append({
                'variable': 'MACD',
                'value': macd,
                'problem': 'MACD negativo para CALL',
                'recommendation': 'Solo CALL si MACD > 0'
            })
        elif direction == 'put' and macd > 0:
            failed.append({
                'variable': 'MACD',
                'value': macd,
                'problem': 'MACD positivo para PUT',
                'recommendation': 'Solo PUT si MACD < 0'
            })
        
        # 3. TENDENCIA
        if len(df_before) >= 20:
            sma_20 = df_before['close'].rolling(20).mean().iloc[-1]
            price = last_candle['close']
            
            if direction == 'call' and price < sma_20:
                failed.append({
                    'variable': 'Tendencia',
                    'value': f'Precio {((price - sma_20) / sma_20 * 100):.2f}% bajo SMA20',
                    'problem': 'Compró contra tendencia',
                    'recommendation': 'Solo CALL si precio > SMA20'
                })
            elif direction == 'put' and price > sma_20:
                failed.append({
                    'variable': 'Tendencia',
                    'value': f'Precio {((price - sma_20) / sma_20 * 100):.2f}% sobre SMA20',
                    'problem': 'Vendió contra tendencia',
                    'recommendation': 'Solo PUT si precio < SMA20'
                })
        
        return failed
    
    def _generate_improvements(self, why_lost, optimal_entry, failed_vars):
        """Genera mejoras concretas basadas en el análisis"""
        improvements = []
        
        # 1. MEJORAS DE TIMING
        if optimal_entry and optimal_entry['should_wait']:
            improvements.append({
                'type': 'timing',
                'action': f"Esperar {optimal_entry['wait_time']} vela(s) más",
                'impact': f"+{optimal_entry['improvement']:.2f}% mejor entrada",
                'priority': 'HIGH'
            })
        
        # 2. MEJORAS DE VARIABLES
        for failed in failed_vars:
            improvements.append({
                'type': 'variable_filter',
                'variable': failed['variable'],
                'action': failed['recommendation'],
                'priority': 'HIGH'
            })
        
        # 3. MEJORAS DE CONDICIONES
        for reason in why_lost:
            if 'RSI' in reason and 'sobrecomprado' in reason:
                improvements.append({
                    'type': 'condition',
                    'action': 'Evitar CALL cuando RSI > 70',
                    'priority': 'CRITICAL'
                })
            elif 'RSI' in reason and 'sobrevendido' in reason:
                improvements.append({
                    'type': 'condition',
                    'action': 'Evitar PUT cuando RSI < 30',
                    'priority': 'CRITICAL'
                })
            elif 'contra tendencia' in reason:
                improvements.append({
                    'type': 'condition',
                    'action': 'Verificar tendencia antes de entrar',
                    'priority': 'CRITICAL'
                })
        
        return improvements
    
    def _create_lesson(self, analysis):
        """Crea una lección resumida del análisis"""
        lesson = {
            'asset': analysis['trade']['asset'],
            'direction': analysis['trade']['direction'],
            'main_problem': analysis['why_lost'][0] if analysis['why_lost'] else 'Desconocido',
            'solution': analysis['how_to_improve'][0]['action'] if analysis['how_to_improve'] else 'Ninguna',
            'priority': 'HIGH',
            'applied': False
        }
        
        return lesson
    
    def _apply_improvements(self, improvements):
        """Aplica mejoras al sistema en tiempo real"""
        for improvement in improvements:
            if improvement['type'] == 'timing':
                # Agregar a lecciones de timing
                self.improvements['entry_timing'].append(improvement)
                
            elif improvement['type'] == 'variable_filter':
                # Ajustar pesos de variables
                var = improvement['variable']
                if var not in self.improvements['indicator_weights']:
                    self.improvements['indicator_weights'][var] = 1.0
                
                # Reducir peso de variable que falló
                self.improvements['indicator_weights'][var] *= 0.9
                
            elif improvement['type'] == 'condition':
                # Agregar a patrones fallidos
                self.improvements['failed_patterns'].append(improvement['action'])
        
        # Limitar tamaño de listas
        if len(self.improvements['entry_timing']) > 50:
            self.improvements['entry_timing'] = self.improvements['entry_timing'][-50:]
        if len(self.improvements['failed_patterns']) > 50:
            self.improvements['failed_patterns'] = self.improvements['failed_patterns'][-50:]
    
    def get_recommendations_for_trade(self, asset, direction, indicators):
        """
        Obtiene recomendaciones basadas en lecciones aprendidas
        
        Returns:
            dict: {
                'should_trade': bool,
                'confidence_adjustment': float,
                'warnings': list,
                'recommendations': list,
                'success_patterns': list
            }
        """
        recommendations = {
            'should_trade': True,
            'confidence_adjustment': 0.0,
            'warnings': [],
            'recommendations': [],
            'success_patterns': []
        }
        
        # Verificar contra patrones fallidos
        for pattern in self.improvements['failed_patterns']:
            if direction.upper() in pattern:
                # Verificar si las condiciones del patrón fallido se cumplen
                if 'RSI > 70' in pattern and indicators.get('rsi', 50) > 70:
                    recommendations['should_trade'] = False
                    recommendations['warnings'].append(f"⚠️ Patrón fallido detectado: {pattern}")
                elif 'RSI < 30' in pattern and indicators.get('rsi', 50) < 30:
                    recommendations['should_trade'] = False
                    recommendations['warnings'].append(f"⚠️ Patrón fallido detectado: {pattern}")
        
        # Verificar patrones exitosos (NUEVO)
        for pattern in self.improvements['successful_patterns']:
            if direction.upper() in pattern:
                # Verificar si las condiciones del patrón exitoso se cumplen
                if 'RSI < 40' in pattern and indicators.get('rsi', 50) < 40:
                    recommendations['confidence_adjustment'] += 0.10
                    recommendations['success_patterns'].append(f"✅ Patrón exitoso detectado: {pattern}")
                elif 'RSI > 60' in pattern and indicators.get('rsi', 50) > 60:
                    recommendations['confidence_adjustment'] += 0.10
                    recommendations['success_patterns'].append(f"✅ Patrón exitoso detectado: {pattern}")
                elif 'tendencia' in pattern.lower():
                    # Verificar tendencia
                    if 'sma_20' in indicators and 'price' in indicators:
                        if direction.upper() == 'CALL' and indicators['price'] > indicators['sma_20']:
                            recommendations['confidence_adjustment'] += 0.15
                            recommendations['success_patterns'].append(f"✅ {pattern}")
                        elif direction.upper() == 'PUT' and indicators['price'] < indicators['sma_20']:
                            recommendations['confidence_adjustment'] += 0.15
                            recommendations['success_patterns'].append(f"✅ {pattern}")
        
        # Ajustar confianza según pesos de indicadores
        for var, weight in self.improvements['indicator_weights'].items():
            if weight < 0.8:  # Variable poco confiable
                recommendations['confidence_adjustment'] -= 0.05
                recommendations['warnings'].append(f"⚠️ {var} tiene bajo rendimiento histórico")
            elif weight > 1.2:  # Variable muy confiable
                recommendations['confidence_adjustment'] += 0.05
                recommendations['recommendations'].append(f"💡 {var} tiene alto rendimiento histórico")
        
        # Recomendaciones de timing
        if self.improvements['entry_timing']:
            avg_wait = np.mean([t.get('wait_time', 0) for t in self.improvements['entry_timing'][-10:]])
            if avg_wait > 0:
                recommendations['recommendations'].append(
                    f"💡 Históricamente, esperar {avg_wait:.0f} vela(s) mejora entrada"
                )
            elif avg_wait < 0:
                recommendations['recommendations'].append(
                    f"💡 Históricamente, entrar {abs(avg_wait):.0f} vela(s) antes mejora entrada"
                )
        
        return recommendations
    
    def get_learning_summary(self):
        """Obtiene resumen del aprendizaje"""
        return {
            'total_lessons': len(self.lessons),
            'entry_timing_lessons': len(self.improvements['entry_timing']),
            'failed_patterns': len(self.improvements['failed_patterns']),
            'indicator_weights': self.improvements['indicator_weights'],
            'recent_lessons': self.lessons[-5:] if self.lessons else []
        }

    
    def _analyze_why_won(self, trade_data, df_before, df_after):
        """Analiza por qué ganó la operación"""
        reasons = []
        
        if df_before.empty or df_after.empty:
            return ["Datos insuficientes para análisis"]
        
        entry_price = trade_data['entry_price']
        direction = trade_data['direction'].lower()
        
        # Obtener precio después de la operación
        if len(df_after) > 0:
            exit_price = df_after.iloc[-1]['close']
            price_movement = ((exit_price - entry_price) / entry_price) * 100
            
            # 1. ANÁLISIS DE MOVIMIENTO FAVORABLE
            if direction == 'call' and price_movement > 0:
                reasons.append(f"Precio subió {price_movement:.3f}% como esperado")
                
                # ¿Qué indicadores lo predijeron correctamente?
                last_candle = df_before.iloc[-1]
                if last_candle.get('rsi', 50) < 40:
                    reasons.append("RSI estaba sobrevendido (<40) - señal alcista correcta")
                if last_candle.get('macd', 0) > 0:
                    reasons.append("MACD positivo - momentum alcista confirmado")
                
            elif direction == 'put' and price_movement < 0:
                reasons.append(f"Precio bajó {abs(price_movement):.3f}% como esperado")
                
                # ¿Qué indicadores lo predijeron correctamente?
                last_candle = df_before.iloc[-1]
                if last_candle.get('rsi', 50) > 60:
                    reasons.append("RSI estaba sobrecomprado (>60) - señal bajista correcta")
                if last_candle.get('macd', 0) < 0:
                    reasons.append("MACD negativo - momentum bajista confirmado")
        
        # 2. ANÁLISIS DE TENDENCIA
        if len(df_before) >= 20:
            sma_20 = df_before['close'].rolling(20).mean().iloc[-1]
            price = df_before.iloc[-1]['close']
            
            if direction == 'call' and price > sma_20:
                reasons.append("Compró a favor de tendencia (precio > SMA20)")
            elif direction == 'put' and price < sma_20:
                reasons.append("Vendió a favor de tendencia (precio < SMA20)")
        
        # 3. ANÁLISIS DE VOLATILIDAD
        if 'atr' in df_before.columns:
            atr = df_before.iloc[-1]['atr']
            if atr < df_before['atr'].mean():
                reasons.append("Volatilidad baja - mercado predecible")
        
        return reasons if reasons else ["Ganó por condiciones favorables del mercado"]
    
    def _find_better_entry_for_win(self, trade_data, df_before, df_after):
        """
        Encuentra si pudo haber entrado en un punto mejor para ganar MÁS
        """
        if df_before.empty or df_after.empty:
            return None
        
        entry_price = trade_data['entry_price']
        direction = trade_data['direction'].lower()
        
        better = {
            'could_improve': False,
            'wait_time': 0,
            'reason': '',
            'better_entry_price': entry_price,
            'additional_profit': 0
        }
        
        # Analizar velas ANTES de la entrada (¿debió esperar?)
        if len(df_before) >= 10:
            recent_candles = df_before.tail(10)
            
            for i in range(len(recent_candles) - 1, 0, -1):
                row = recent_candles.iloc[i]
                
                if direction == 'call':
                    # Para CALL, buscar precio más bajo ANTES (mejor entrada)
                    if row['low'] < entry_price:
                        better_price = row['low']
                        additional_profit = ((entry_price - better_price) / better_price) * 100
                        
                        if additional_profit > better['additional_profit']:
                            better['could_improve'] = True
                            better['wait_time'] = -(len(recent_candles) - i)  # Negativo = antes
                            better['better_entry_price'] = better_price
                            better['additional_profit'] = additional_profit
                            better['reason'] = f"Esperar {abs(better['wait_time'])} vela(s) antes hubiera dado +{additional_profit:.2f}% más ganancia"
                
                elif direction == 'put':
                    # Para PUT, buscar precio más alto ANTES (mejor entrada)
                    if row['high'] > entry_price:
                        better_price = row['high']
                        additional_profit = ((better_price - entry_price) / entry_price) * 100
                        
                        if additional_profit > better['additional_profit']:
                            better['could_improve'] = True
                            better['wait_time'] = -(len(recent_candles) - i)
                            better['better_entry_price'] = better_price
                            better['additional_profit'] = additional_profit
                            better['reason'] = f"Esperar {abs(better['wait_time'])} vela(s) antes hubiera dado +{additional_profit:.2f}% más ganancia"
        
        # Si no encontró mejor entrada antes, el timing fue perfecto
        if not better['could_improve']:
            better['reason'] = "Timing de entrada fue ÓPTIMO - no pudo mejorar"
        
        return better
    
    def _identify_working_variables(self, trade_data, df_before):
        """Identifica qué variables/indicadores funcionaron bien"""
        working = []
        
        if df_before.empty:
            return working
        
        last_candle = df_before.iloc[-1]
        direction = trade_data['direction'].lower()
        
        # 1. RSI
        rsi = last_candle.get('rsi', 50)
        if direction == 'call' and rsi < 40:
            working.append({
                'variable': 'RSI',
                'value': rsi,
                'success': 'RSI bajo para CALL - señal correcta',
                'recommendation': 'Aumentar peso de RSI para CALL cuando < 40'
            })
        elif direction == 'put' and rsi > 60:
            working.append({
                'variable': 'RSI',
                'value': rsi,
                'success': 'RSI alto para PUT - señal correcta',
                'recommendation': 'Aumentar peso de RSI para PUT cuando > 60'
            })
        
        # 2. MACD
        macd = last_candle.get('macd', 0)
        if direction == 'call' and macd > 0:
            working.append({
                'variable': 'MACD',
                'value': macd,
                'success': 'MACD positivo para CALL - momentum correcto',
                'recommendation': 'Aumentar peso de MACD para CALL cuando > 0'
            })
        elif direction == 'put' and macd < 0:
            working.append({
                'variable': 'MACD',
                'value': macd,
                'success': 'MACD negativo para PUT - momentum correcto',
                'recommendation': 'Aumentar peso de MACD para PUT cuando < 0'
            })
        
        # 3. TENDENCIA
        if len(df_before) >= 20:
            sma_20 = df_before['close'].rolling(20).mean().iloc[-1]
            price = last_candle['close']
            
            if direction == 'call' and price > sma_20:
                working.append({
                    'variable': 'Tendencia',
                    'value': f'Precio {((price - sma_20) / sma_20 * 100):.2f}% sobre SMA20',
                    'success': 'Compró a favor de tendencia',
                    'recommendation': 'Priorizar CALL cuando precio > SMA20'
                })
            elif direction == 'put' and price < sma_20:
                working.append({
                    'variable': 'Tendencia',
                    'value': f'Precio {((price - sma_20) / sma_20 * 100):.2f}% bajo SMA20',
                    'success': 'Vendió a favor de tendencia',
                    'recommendation': 'Priorizar PUT cuando precio < SMA20'
                })
        
        return working
    
    def _generate_maximizations(self, why_won, better_entry, working_vars):
        """Genera mejoras para maximizar ganancias futuras"""
        maximizations = []
        
        # 1. MEJORAS DE TIMING
        if better_entry and better_entry['could_improve']:
            maximizations.append({
                'type': 'timing_optimization',
                'action': f"Buscar entrada {abs(better_entry['wait_time'])} vela(s) antes",
                'impact': f"+{better_entry['additional_profit']:.2f}% más ganancia",
                'priority': 'MEDIUM'
            })
        else:
            # Timing fue perfecto, reforzar este patrón
            maximizations.append({
                'type': 'timing_reinforcement',
                'action': 'Timing fue óptimo - reforzar este patrón',
                'impact': 'Mantener estrategia actual',
                'priority': 'LOW'
            })
        
        # 2. REFORZAR VARIABLES QUE FUNCIONARON
        for working in working_vars:
            maximizations.append({
                'type': 'variable_reinforcement',
                'variable': working['variable'],
                'action': working['recommendation'],
                'priority': 'HIGH'
            })
        
        # 3. REFORZAR CONDICIONES GANADORAS
        for reason in why_won:
            if 'RSI' in reason and 'sobrevendido' in reason:
                maximizations.append({
                    'type': 'condition_reinforcement',
                    'action': 'Priorizar CALL cuando RSI < 40',
                    'priority': 'HIGH'
                })
            elif 'RSI' in reason and 'sobrecomprado' in reason:
                maximizations.append({
                    'type': 'condition_reinforcement',
                    'action': 'Priorizar PUT cuando RSI > 60',
                    'priority': 'HIGH'
                })
            elif 'tendencia' in reason.lower():
                maximizations.append({
                    'type': 'condition_reinforcement',
                    'action': 'Priorizar operaciones a favor de tendencia',
                    'priority': 'CRITICAL'
                })
        
        return maximizations
    
    def _create_positive_lesson(self, analysis):
        """Crea una lección positiva del análisis de operación ganada"""
        lesson = {
            'asset': analysis['trade']['asset'],
            'direction': analysis['trade']['direction'],
            'main_success': analysis['why_won'][0] if analysis['why_won'] else 'Condiciones favorables',
            'optimization': analysis['could_improve']['reason'] if analysis['could_improve'] else 'Timing óptimo',
            'priority': 'MEDIUM',
            'applied': False,
            'type': 'success_pattern'
        }
        
        return lesson
    
    def _apply_maximizations(self, maximizations):
        """Aplica maximizaciones al sistema en tiempo real"""
        for maximization in maximizations:
            if maximization['type'] == 'timing_optimization':
                # Agregar a lecciones de timing
                self.improvements['entry_timing'].append(maximization)
                
            elif maximization['type'] == 'variable_reinforcement':
                # Aumentar peso de variable que funcionó
                var = maximization['variable']
                if var not in self.improvements['indicator_weights']:
                    self.improvements['indicator_weights'][var] = 1.0
                
                # Aumentar peso de variable que funcionó
                self.improvements['indicator_weights'][var] = min(1.5, self.improvements['indicator_weights'][var] * 1.1)
                
            elif maximization['type'] == 'condition_reinforcement':
                # Agregar a patrones exitosos
                self.improvements['successful_patterns'].append(maximization['action'])
            
            elif maximization['type'] == 'timing_reinforcement':
                # Reforzar timing actual
                pass  # Ya está funcionando bien
        
        # Limitar tamaño de listas
        if len(self.improvements['successful_patterns']) > 50:
            self.improvements['successful_patterns'] = self.improvements['successful_patterns'][-50:]
