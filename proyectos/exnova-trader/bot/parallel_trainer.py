"""
Sistema de Entrenamiento en Paralelo
Mientras el bot opera en REAL, entrena en PRACTICE simulando operaciones
"""
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from database.db_manager import db
import json

class ParallelTrainer:
    """
    Entrena en paralelo mientras el bot opera en REAL
    Analiza TODAS las oportunidades (reversiones y continuaciones)
    """
    
    def __init__(self, market_data, feature_engineer, agent, llm_client=None):
        self.market_data = market_data
        self.feature_engineer = feature_engineer
        self.agent = agent
        self.llm_client = llm_client
        
        # Operaciones simuladas en seguimiento
        self.simulated_trades = []
        
        # Estadísticas de entrenamiento
        self.training_stats = {
            'total_simulated': 0,
            'reversions_tested': 0,
            'continuations_tested': 0,
            'wins': 0,
            'losses': 0,
            'lessons_learned': []
        }
        
        self.enabled = True
        self.last_analysis_time = 0
        self.analysis_interval = 60  # Analizar cada 60 segundos
        
        # 🧠 MEMORIA DE CORTO PLAZO (Últimas 20 simulaciones por estrategia)
        self.strategy_performance = {
            'reversion': [],    # [True, False, True...]
            'continuation': []
        }

    def get_best_current_strategy(self):
        """Retorna la estrategia con mejor rendimiento actual (>60% WR)"""
        strategies = {}
        for stra, results in self.strategy_performance.items():
            if len(results) >= 5: # Mínimo 5 muestras
                recent = results[-10:] # Últimas 10
                win_rate = sum(recent) / len(recent)
                strategies[stra] = win_rate
        
        if not strategies:
            return None, 0.0
            
        best_strat = max(strategies.items(), key=lambda x: x[1])
        return best_strat[0], best_strat[1] # (nombre, win_rate)
        
    def analyze_opportunity(self, asset: str, df: pd.DataFrame, 
                           real_decision: Optional[str] = None) -> Dict:
        """
        Analiza una oportunidad en paralelo
        
        Args:
            asset: Activo a analizar
            df: DataFrame con velas e indicadores
            real_decision: Decisión que tomó el bot real (CALL/PUT/HOLD)
        
        Returns:
            Análisis completo con reversiones y continuaciones
        """
        if not self.enabled or df.empty:
            return {}
        
        current_time = time.time()
        if current_time - self.last_analysis_time < self.analysis_interval:
            return {}
        
        self.last_analysis_time = current_time
        
        try:
            last_candle = df.iloc[-1]
            
            # 1. ANALIZAR TENDENCIA ACTUAL
            trend_analysis = self._analyze_trend(df)
            
            # 2. ANALIZAR REVERSIÓN (operar contra la tendencia)
            reversion_analysis = self._analyze_reversion(df, trend_analysis)
            
            # 3. ANALIZAR CONTINUACIÓN (operar a favor de la tendencia)
            continuation_analysis = self._analyze_continuation(df, trend_analysis)
            
            # 4. COMPARAR CON DECISIÓN REAL
            comparison = self._compare_with_real_decision(
                real_decision,
                reversion_analysis,
                continuation_analysis
            )
            
            # 5. SIMULAR OPERACIONES PROMETEDORAS
            if reversion_analysis['confidence'] > 0.7:
                self._simulate_trade(
                    asset=asset,
                    direction=reversion_analysis['direction'],
                    entry_price=float(last_candle['close']),
                    strategy='reversion',
                    analysis=reversion_analysis,
                    df=df
                )
                self.training_stats['reversions_tested'] += 1
            
            if continuation_analysis['confidence'] > 0.7:
                self._simulate_trade(
                    asset=asset,
                    direction=continuation_analysis['direction'],
                    entry_price=float(last_candle['close']),
                    strategy='continuation',
                    analysis=continuation_analysis,
                    df=df
                )
                self.training_stats['continuations_tested'] += 1
            
            return {
                'trend': trend_analysis,
                'reversion': reversion_analysis,
                'continuation': continuation_analysis,
                'comparison': comparison,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"[ERROR] Error en análisis paralelo: {e}")
            return {}
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """Analiza la tendencia actual del mercado"""
        try:
            # Usar últimas 20 velas
            recent = df.tail(20)
            
            # Calcular tendencia con SMAs
            sma_20 = recent['sma_20'].iloc[-1] if 'sma_20' in recent.columns else 0
            sma_50 = recent['sma_50'].iloc[-1] if 'sma_50' in recent.columns else 0
            current_price = recent['close'].iloc[-1]
            
            # Determinar tendencia
            if sma_20 > sma_50 and current_price > sma_20:
                trend = 'bullish'
                strength = min((sma_20 - sma_50) / sma_50 * 100, 100)
            elif sma_20 < sma_50 and current_price < sma_20:
                trend = 'bearish'
                strength = min((sma_50 - sma_20) / sma_50 * 100, 100)
            else:
                trend = 'neutral'
                strength = 0
            
            # Detectar momentum
            rsi = recent['rsi'].iloc[-1] if 'rsi' in recent.columns else 50
            macd = recent['macd'].iloc[-1] if 'macd' in recent.columns else 0
            
            return {
                'direction': trend,
                'strength': abs(strength),
                'rsi': float(rsi),
                'macd': float(macd),
                'price_vs_sma20': 'above' if current_price > sma_20 else 'below',
                'momentum': 'strong' if abs(macd) > 0.001 else 'weak'
            }
            
        except Exception as e:
            print(f"[ERROR] Error analizando tendencia: {e}")
            return {'direction': 'neutral', 'strength': 0}
    
    def _analyze_reversion(self, df: pd.DataFrame, trend: Dict) -> Dict:
        """
        Analiza oportunidades de REVERSIÓN (operar contra la tendencia)
        Busca señales de agotamiento y cambio de dirección
        """
        try:
            last_candle = df.iloc[-1]
            rsi = trend['rsi']
            macd = trend['macd']
            
            # Señales de reversión alcista (comprar en tendencia bajista)
            bullish_reversion_signals = []
            if rsi < 30:
                bullish_reversion_signals.append('RSI sobreventa extrema')
            if trend['direction'] == 'bearish' and macd > 0:
                bullish_reversion_signals.append('MACD cruzó al alza')
            if 'bb_lower' in df.columns and last_candle['close'] < last_candle['bb_lower']:
                bullish_reversion_signals.append('Precio bajo Bollinger inferior')
            
            # Señales de reversión bajista (vender en tendencia alcista)
            bearish_reversion_signals = []
            if rsi > 70:
                bearish_reversion_signals.append('RSI sobrecompra extrema')
            if trend['direction'] == 'bullish' and macd < 0:
                bearish_reversion_signals.append('MACD cruzó a la baja')
            if 'bb_upper' in df.columns and last_candle['close'] > last_candle['bb_upper']:
                bearish_reversion_signals.append('Precio sobre Bollinger superior')
            
            # Determinar mejor reversión
            if len(bullish_reversion_signals) >= 2:
                return {
                    'direction': 'call',
                    'confidence': min(len(bullish_reversion_signals) / 3, 1.0),
                    'signals': bullish_reversion_signals,
                    'reason': 'Reversión alcista detectada',
                    'risk_level': 'medium'
                }
            elif len(bearish_reversion_signals) >= 2:
                return {
                    'direction': 'put',
                    'confidence': min(len(bearish_reversion_signals) / 3, 1.0),
                    'signals': bearish_reversion_signals,
                    'reason': 'Reversión bajista detectada',
                    'risk_level': 'medium'
                }
            else:
                return {
                    'direction': 'hold',
                    'confidence': 0.0,
                    'signals': [],
                    'reason': 'No hay señales claras de reversión',
                    'risk_level': 'high'
                }
                
        except Exception as e:
            print(f"[ERROR] Error analizando reversión: {e}")
            return {'direction': 'hold', 'confidence': 0.0}
    
    def _analyze_continuation(self, df: pd.DataFrame, trend: Dict) -> Dict:
        """
        Analiza oportunidades de CONTINUACIÓN (operar a favor de la tendencia)
        Busca confirmación de que la tendencia continuará
        """
        try:
            last_candle = df.iloc[-1]
            rsi = trend['rsi']
            
            # Continuación alcista (comprar en tendencia alcista)
            bullish_continuation_signals = []
            if trend['direction'] == 'bullish':
                bullish_continuation_signals.append('Tendencia alcista confirmada')
            if 40 < rsi < 60:
                bullish_continuation_signals.append('RSI en zona neutral (momentum sostenible)')
            if trend['price_vs_sma20'] == 'above':
                bullish_continuation_signals.append('Precio sobre SMA20')
            if trend['momentum'] == 'strong' and trend['macd'] > 0:
                bullish_continuation_signals.append('Momentum alcista fuerte')
            
            # Continuación bajista (vender en tendencia bajista)
            bearish_continuation_signals = []
            if trend['direction'] == 'bearish':
                bearish_continuation_signals.append('Tendencia bajista confirmada')
            if 40 < rsi < 60:
                bearish_continuation_signals.append('RSI en zona neutral (momentum sostenible)')
            if trend['price_vs_sma20'] == 'below':
                bearish_continuation_signals.append('Precio bajo SMA20')
            if trend['momentum'] == 'strong' and trend['macd'] < 0:
                bearish_continuation_signals.append('Momentum bajista fuerte')
            
            # Determinar mejor continuación
            if len(bullish_continuation_signals) >= 3:
                return {
                    'direction': 'call',
                    'confidence': min(len(bullish_continuation_signals) / 4, 1.0),
                    'signals': bullish_continuation_signals,
                    'reason': 'Continuación alcista probable',
                    'risk_level': 'low'
                }
            elif len(bearish_continuation_signals) >= 3:
                return {
                    'direction': 'put',
                    'confidence': min(len(bearish_continuation_signals) / 4, 1.0),
                    'signals': bearish_continuation_signals,
                    'reason': 'Continuación bajista probable',
                    'risk_level': 'low'
                }
            else:
                return {
                    'direction': 'hold',
                    'confidence': 0.0,
                    'signals': [],
                    'reason': 'No hay señales claras de continuación',
                    'risk_level': 'high'
                }
                
        except Exception as e:
            print(f"[ERROR] Error analizando continuación: {e}")
            return {'direction': 'hold', 'confidence': 0.0}
    
    def _compare_with_real_decision(self, real_decision: Optional[str],
                                    reversion: Dict, continuation: Dict) -> Dict:
        """Compara las estrategias simuladas con la decisión real"""
        if not real_decision or real_decision == 'HOLD':
            return {'match': 'none', 'alternative_strategies': []}
        
        real_dir = 'call' if real_decision == 'CALL' else 'put'
        alternatives = []
        
        # Verificar si reversión sugiere algo diferente
        if reversion['direction'] != 'hold' and reversion['direction'] != real_dir:
            alternatives.append({
                'strategy': 'reversion',
                'direction': reversion['direction'],
                'confidence': reversion['confidence'],
                'reason': reversion['reason']
            })
        
        # Verificar si continuación sugiere algo diferente
        if continuation['direction'] != 'hold' and continuation['direction'] != real_dir:
            alternatives.append({
                'strategy': 'continuation',
                'direction': continuation['direction'],
                'confidence': continuation['confidence'],
                'reason': continuation['reason']
            })
        
        return {
            'real_decision': real_decision,
            'alternatives': alternatives,
            'should_explore': len(alternatives) > 0
        }
    
    def _simulate_trade(self, asset: str, direction: str, entry_price: float,
                       strategy: str, analysis: Dict, df: pd.DataFrame):
        """Simula una operación para aprendizaje"""
        try:
            trade = {
                'id': f"SIM_{int(time.time())}_{asset}",
                'asset': asset,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': time.time(),
                'strategy': strategy,
                'analysis': analysis,
                'duration': 60,  # 1 minuto
                'state_before': df.tail(10).copy() if len(df) >= 10 else df.copy()
            }
            
            self.simulated_trades.append(trade)
            self.training_stats['total_simulated'] += 1
            
            print(f"[TRAINING] Simulando {strategy.upper()}: {direction.upper()} en {asset}")
            
        except Exception as e:
            print(f"[ERROR] Error simulando trade: {e}")
    
    def check_simulated_trades(self):
        """Verifica resultados de operaciones simuladas"""
        completed = []
        
        for trade in self.simulated_trades:
            # Verificar si ya pasó el tiempo
            if time.time() - trade['entry_time'] >= trade['duration'] + 10:
                completed.append(trade)
        
        for trade in completed:
            self.simulated_trades.remove(trade)
            self._process_simulated_result(trade)
    
    def _process_simulated_result(self, trade: Dict):
        """Procesa el resultado de una operación simulada"""
        try:
            # Obtener precio de salida
            df = self.market_data.get_candles(trade['asset'], 60, 5)
            if df.empty:
                return
            
            exit_price = float(df.iloc[-1]['close'])
            entry_price = trade['entry_price']
            
            # Determinar si ganó
            if trade['direction'] == 'call':
                won = exit_price > entry_price
            else:  # put
                won = exit_price < entry_price
            
            # Actualizar estadísticas
            if won:
                self.training_stats['wins'] += 1
            else:
                self.training_stats['losses'] += 1
            
            # Calcular lección aprendida
            lesson = self._extract_lesson(trade, won, exit_price)
            self.training_stats['lessons_learned'].append(lesson)
            
            # 💾 GUARDAR EN BASE DE DATOS
            try:
                # Guardar como experiencia de aprendizaje
                experience_data = {
                    'trade_id': None,  # No es trade real
                    'state': json.dumps({
                        'entry_price': entry_price,
                        'strategy': trade['strategy'],
                        'signals': trade['analysis'].get('signals', [])
                    }),
                    'action': trade['direction'],
                    'action_confidence': trade['analysis'].get('confidence', 0),
                    'reward': 1.0 if won else -1.0,
                    'next_state': json.dumps({'exit_price': exit_price}),
                    'was_correct': won,
                    'error_type': None if won else f"{trade['strategy']}_failed",
                    'lesson': lesson,
                    'should_avoid': not won,
                    'model_version': 'parallel_training_v1'
                }
                db.save_experience(experience_data)
                
                print(f"[TRAINING] {'✅ GANÓ' if won else '❌ PERDIÓ'}: {trade['strategy']} {trade['direction']} en {trade['asset']}")
                print(f"[TRAINING] Lección: {lesson}")
                
            except Exception as e:
                print(f"[WARNING] Error guardando experiencia simulada: {e}")
                
        except Exception as e:
            print(f"[ERROR] Error procesando resultado simulado: {e}")
    
    def _extract_lesson(self, trade: Dict, won: bool, exit_price: float) -> str:
        """Extrae lección aprendida de la operación simulada"""
        strategy = trade['strategy']
        direction = trade['direction']
        asset = trade['asset']
        
        if won:
            return f"✅ {strategy.capitalize()} {direction.upper()} en {asset} fue exitosa. Señales: {', '.join(trade['analysis']['signals'][:2])}"
        else:
            return f"❌ {strategy.capitalize()} {direction.upper()} en {asset} falló. Evitar cuando: {trade['analysis'].get('reason', 'condiciones similares')}"
    
    def get_training_summary(self) -> Dict:
        """Obtiene resumen del entrenamiento paralelo"""
        total = self.training_stats['total_simulated']
        wins = self.training_stats['wins']
        losses = self.training_stats['losses']
        
        win_rate = (wins / total * 100) if total > 0 else 0
        
        return {
            'total_simulated': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'reversions_tested': self.training_stats['reversions_tested'],
            'continuations_tested': self.training_stats['continuations_tested'],
            'recent_lessons': self.training_stats['lessons_learned'][-5:],
            'active_simulations': len(self.simulated_trades)
        }
