"""
Sistema de Corrección Automática - Ajusta parámetros basado en resultados
"""

import logging
from typing import Dict, List
import json

logger = logging.getLogger(__name__)


class AutoCorrection:
    """Corrige automáticamente parámetros basado en análisis de operaciones"""
    
    def __init__(self):
        self.current_params = {
            'confidence_threshold': 0.65,
            'rsi_min_oversold': 25,
            'rsi_max_overbought': 75,
            'macd_min_divergence': 0.0001,
            'pullback_min': 0.05,
            'pullback_max': 0.5,
            'cooldown_seconds': 180,
            'max_trades_per_hour': 20
        }
        
        self.adjustment_history = []
    
    def analyze_and_correct(self, analysis_report: Dict) -> Dict:
        """
        Analiza el reporte y sugiere correcciones
        
        Args:
            analysis_report: Reporte de AITradeAnalyzer.generate_improvement_report()
        
        Returns:
            Dict con cambios sugeridos y razones
        """
        corrections = {
            'timestamp': str(datetime.now()),
            'current_params': self.current_params.copy(),
            'suggested_changes': [],
            'reasoning': [],
            'expected_improvement': 0
        }
        
        win_rate = analysis_report.get('win_rate', 0)
        winning_patterns = analysis_report.get('winning_patterns', {})
        losing_patterns = analysis_report.get('losing_patterns', {})
        
        # CORRECCIÓN 1: Confianza
        if win_rate < 50:
            # Win rate muy bajo, aumentar selectividad
            new_confidence = min(0.80, self.current_params['confidence_threshold'] + 0.05)
            corrections['suggested_changes'].append({
                'parameter': 'confidence_threshold',
                'current': self.current_params['confidence_threshold'],
                'suggested': new_confidence,
                'reason': f'Win rate bajo ({win_rate:.0f}%), aumentar selectividad'
            })
            corrections['reasoning'].append(f'Confianza: {self.current_params["confidence_threshold"]:.0%} → {new_confidence:.0%}')
        
        elif win_rate > 70:
            # Win rate muy alto, podemos ser menos selectivos
            new_confidence = max(0.55, self.current_params['confidence_threshold'] - 0.05)
            corrections['suggested_changes'].append({
                'parameter': 'confidence_threshold',
                'current': self.current_params['confidence_threshold'],
                'suggested': new_confidence,
                'reason': f'Win rate alto ({win_rate:.0f}%), podemos operar más'
            })
            corrections['reasoning'].append(f'Confianza: {self.current_params["confidence_threshold"]:.0%} → {new_confidence:.0%}')
        
        # CORRECCIÓN 2: RSI
        if winning_patterns.get('avg_rsi'):
            avg_winning_rsi = winning_patterns['avg_rsi']
            if avg_winning_rsi < 20:
                new_min = max(15, self.current_params['rsi_min_oversold'] - 5)
                corrections['suggested_changes'].append({
                    'parameter': 'rsi_min_oversold',
                    'current': self.current_params['rsi_min_oversold'],
                    'suggested': new_min,
                    'reason': f'Operaciones ganadoras tienen RSI promedio {avg_winning_rsi:.0f}'
                })
                corrections['reasoning'].append(f'RSI mínimo: {self.current_params["rsi_min_oversold"]} → {new_min}')
        
        # CORRECCIÓN 3: MACD
        if winning_patterns.get('avg_macd'):
            avg_winning_macd = abs(winning_patterns['avg_macd'])
            if avg_winning_macd > 0.0003:
                new_macd = min(0.0002, self.current_params['macd_min_divergence'] + 0.00005)
                corrections['suggested_changes'].append({
                    'parameter': 'macd_min_divergence',
                    'current': self.current_params['macd_min_divergence'],
                    'suggested': new_macd,
                    'reason': f'Operaciones ganadoras tienen MACD promedio {avg_winning_macd:.6f}'
                })
                corrections['reasoning'].append(f'MACD mínimo: {self.current_params["macd_min_divergence"]:.6f} → {new_macd:.6f}')
        
        # CORRECCIÓN 4: Pullback
        if winning_patterns.get('avg_pullback'):
            avg_winning_pb = winning_patterns['avg_pullback']
            if 0.08 <= avg_winning_pb <= 0.25:
                new_min = max(0.05, avg_winning_pb - 0.05)
                new_max = min(0.5, avg_winning_pb + 0.05)
                corrections['suggested_changes'].append({
                    'parameter': 'pullback_range',
                    'current': f"{self.current_params['pullback_min']:.3f}-{self.current_params['pullback_max']:.3f}",
                    'suggested': f"{new_min:.3f}-{new_max:.3f}",
                    'reason': f'Pullback óptimo identificado: {avg_winning_pb:.3f}%'
                })
                corrections['reasoning'].append(f'Pullback: {self.current_params["pullback_min"]:.3f}-{self.current_params["pullback_max"]:.3f} → {new_min:.3f}-{new_max:.3f}')
        
        # CORRECCIÓN 5: Cooldown
        if analysis_report.get('total_trades', 0) > 0:
            trades_per_hour = analysis_report['total_trades'] / (analysis_report.get('duration_hours', 1))
            if trades_per_hour > 30:
                new_cooldown = min(300, self.current_params['cooldown_seconds'] + 30)
                corrections['suggested_changes'].append({
                    'parameter': 'cooldown_seconds',
                    'current': self.current_params['cooldown_seconds'],
                    'suggested': new_cooldown,
                    'reason': f'Demasiadas operaciones ({trades_per_hour:.0f}/hr), aumentar cooldown'
                })
                corrections['reasoning'].append(f'Cooldown: {self.current_params["cooldown_seconds"]}s → {new_cooldown}s')
        
        # Calcular mejora esperada
        corrections['expected_improvement'] = self._calculate_expected_improvement(corrections)
        
        self.adjustment_history.append(corrections)
        return corrections
    
    def _calculate_expected_improvement(self, corrections: Dict) -> float:
        """Calcula la mejora esperada en win rate"""
        improvement = 0
        
        for change in corrections['suggested_changes']:
            if change['parameter'] == 'confidence_threshold':
                # Aumentar confianza = +5-10% win rate
                if change['suggested'] > change['current']:
                    improvement += 7
                else:
                    improvement -= 3
            
            elif change['parameter'] == 'rsi_min_oversold':
                # RSI más estricto = +3-5% win rate
                if change['suggested'] < change['current']:
                    improvement += 4
            
            elif change['parameter'] == 'macd_min_divergence':
                # MACD más fuerte = +2-4% win rate
                if change['suggested'] > change['current']:
                    improvement += 3
            
            elif change['parameter'] == 'pullback_range':
                # Pullback óptimo = +5-8% win rate
                improvement += 6
            
            elif change['parameter'] == 'cooldown_seconds':
                # Cooldown más largo = +2-3% win rate (menos operaciones malas)
                if change['suggested'] > change['current']:
                    improvement += 2
        
        return min(improvement, 20)  # Máximo 20% de mejora esperada
    
    def apply_corrections(self, corrections: Dict) -> bool:
        """Aplica las correcciones sugeridas"""
        try:
            for change in corrections['suggested_changes']:
                param = change['parameter']
                
                if param == 'pullback_range':
                    # Caso especial para rango
                    range_str = change['suggested']
                    min_val, max_val = map(float, range_str.split('-'))
                    self.current_params['pullback_min'] = min_val
                    self.current_params['pullback_max'] = max_val
                else:
                    self.current_params[param] = change['suggested']
            
            logger.info(f"✅ Correcciones aplicadas: {corrections}")
            return True
        except Exception as e:
            logger.error(f"❌ Error aplicando correcciones: {e}")
            return False
    
    def get_current_params(self) -> Dict:
        """Retorna parámetros actuales"""
        return self.current_params.copy()
    
    def get_adjustment_history(self) -> List[Dict]:
        """Retorna historial de ajustes"""
        return self.adjustment_history.copy()
    
    def export_params_to_config(self) -> str:
        """Exporta parámetros en formato para config.py"""
        config_str = """
# Parámetros Optimizados por Auto-Correction
CONFIDENCE_THRESHOLD = {:.2f}
RSI_MIN_OVERSOLD = {:.0f}
RSI_MAX_OVERBOUGHT = {:.0f}
MACD_MIN_DIVERGENCE = {:.6f}
PULLBACK_MIN = {:.3f}
PULLBACK_MAX = {:.3f}
COOLDOWN_SECONDS = {:.0f}
MAX_TRADES_PER_HOUR = {:.0f}
""".format(
            self.current_params['confidence_threshold'],
            self.current_params['rsi_min_oversold'],
            self.current_params['rsi_max_overbought'],
            self.current_params['macd_min_divergence'],
            self.current_params['pullback_min'],
            self.current_params['pullback_max'],
            self.current_params['cooldown_seconds'],
            self.current_params['max_trades_per_hour']
        )
        return config_str


from datetime import datetime
