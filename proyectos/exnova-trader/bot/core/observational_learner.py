"""
Observational Learner - Aprende observando el mercado sin operar
Analiza oportunidades que NO se ejecutaron y aprende de ellas
"""
import time
import pandas as pd
from datetime import datetime

class ObservationalLearner:
    """
    Sistema que aprende observando el mercado
    - Registra oportunidades detectadas pero no ejecutadas
    - Simula qué habría pasado
    - Aprende de los resultados
    """
    
    def __init__(self, continuous_learner, market_data, feature_engineer):
        self.continuous_learner = continuous_learner
        self.market_data = market_data
        self.feature_engineer = feature_engineer
        
        # Registro de oportunidades observadas
        self.observed_opportunities = []
        
        # Configuración
        self.max_observations = 100  # Máximo de observaciones a guardar
        self.observation_duration = 60  # Segundos para verificar resultado
        
    def observe_opportunity(self, opportunity_data, reason_not_executed):
        """
        Registra una oportunidad que NO se ejecutó
        
        Args:
            opportunity_data: dict con datos de la oportunidad
            reason_not_executed: str razón por la que no se ejecutó
        """
        observation = {
            'timestamp': time.time(),
            'asset': opportunity_data.get('asset'),
            'action': opportunity_data.get('action'),
            'score': opportunity_data.get('score'),
            'confidence': opportunity_data.get('confidence'),
            'entry_price': opportunity_data.get('entry_price'),
            'reason_not_executed': reason_not_executed,
            'state_before': opportunity_data.get('state_before'),
            'checked': False
        }
        
        self.observed_opportunities.append(observation)
        
        # Limitar tamaño
        if len(self.observed_opportunities) > self.max_observations:
            self.observed_opportunities = self.observed_opportunities[-self.max_observations:]
        
        print(f"👁️ Oportunidad observada: {observation['action']} en {observation['asset']}")
        print(f"   Razón no ejecutada: {reason_not_executed}")
    
    def check_observations(self):
        """
        Verifica resultados de oportunidades observadas
        y aprende de ellas
        """
        current_time = time.time()
        learned_count = 0
        
        for obs in self.observed_opportunities:
            # Solo verificar observaciones no checadas y con tiempo suficiente
            if not obs['checked'] and (current_time - obs['timestamp']) >= self.observation_duration:
                result = self._check_observation_result(obs)
                
                if result:
                    # Agregar como experiencia de aprendizaje
                    self._add_observation_experience(obs, result)
                    obs['checked'] = True
                    learned_count += 1
        
        if learned_count > 0:
            print(f"📚 Aprendidas {learned_count} observaciones")
        
        return learned_count
    
    def _check_observation_result(self, observation):
        """
        Verifica qué habría pasado si se hubiera ejecutado la operación
        
        Returns:
            dict con resultado o None si no se puede verificar
        """
        try:
            # Obtener precio actual
            df = self.market_data.get_candles(
                observation['asset'],
                60,
                2  # Solo necesitamos 2 velas
            )
            
            if df.empty or len(df) < 2:
                return None
            
            current_price = df.iloc[-1]['close']
            entry_price = observation['entry_price']
            
            # Determinar si habría ganado
            if observation['action'] == 'CALL':
                won = current_price > entry_price
            else:  # PUT
                won = current_price < entry_price
            
            # Calcular profit simulado
            profit = 0.85 if won else -1.0  # 85% payout o pérdida total
            
            return {
                'won': won,
                'profit': profit,
                'exit_price': current_price,
                'price_change': current_price - entry_price
            }
        
        except Exception as e:
            print(f"⚠️ Error verificando observación: {e}")
            return None
    
    def _add_observation_experience(self, observation, result):
        """
        Agrega la observación como experiencia de aprendizaje
        """
        try:
            # Obtener estado después
            df_after = self.market_data.get_candles(
                observation['asset'],
                60,
                200
            )
            
            if df_after.empty:
                return
            
            df_after = self.feature_engineer.prepare_for_rl(df_after)
            
            if df_after.empty or len(df_after) < 10:
                return
            
            state_after = df_after.iloc[-10:]
            
            # Convertir acción
            action = 1 if observation['action'] == 'CALL' else 2
            
            # Agregar experiencia
            self.continuous_learner.add_real_trade_experience(
                state_before=observation['state_before'],
                action=action,
                profit=result['profit'],
                state_after=state_after,
                metadata={
                    'asset': observation['asset'],
                    'entry_price': observation['entry_price'],
                    'exit_price': result['exit_price'],
                    'won': result['won'],
                    'timestamp': observation['timestamp'],
                    'type': 'OBSERVATIONAL',  # Marca como aprendizaje observacional
                    'reason_not_executed': observation['reason_not_executed']
                }
            )
            
            # Mostrar resultado
            emoji = "✅" if result['won'] else "❌"
            print(f"{emoji} Observación: {observation['action']} habría {'GANADO' if result['won'] else 'PERDIDO'}")
            print(f"   Entrada: {observation['entry_price']:.5f}")
            print(f"   Salida: {result['exit_price']:.5f}")
            print(f"   Cambio: {result['price_change']:.5f}")
            print(f"   Profit simulado: ${result['profit']:.2f}")
        
        except Exception as e:
            print(f"⚠️ Error agregando experiencia observacional: {e}")
    
    def get_statistics(self):
        """
        Obtiene estadísticas de aprendizaje observacional
        """
        total = len(self.observed_opportunities)
        checked = sum(1 for obs in self.observed_opportunities if obs['checked'])
        pending = total - checked
        
        return {
            'total_observations': total,
            'checked': checked,
            'pending': pending
        }
