"""
Analizador de Operaciones con IA - Aprendizaje Detallado
Analiza cada operación perdida/ganada para mejorar precisión
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class AITradeAnalyzer:
    """Analiza operaciones con IA para identificar patrones de pérdida/ganancia"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.trades_history = []
        self.patterns = {
            'winning_patterns': [],
            'losing_patterns': [],
            'precision_factors': []
        }
        
    def analyze_trade(self, trade_data: Dict) -> Dict:
        """
        Analiza una operación individual
        
        Args:
            trade_data: {
                'id': str,
                'asset': str,
                'action': str (CALL/PUT),
                'entry_price': float,
                'exit_price': float,
                'result': str (WIN/LOSS),
                'profit': float,
                'rsi': float,
                'macd': float,
                'pullback_distance': float,
                'confidence': float,
                'timestamp': str,
                'reason': str
            }
        """
        analysis = {
            'trade_id': trade_data.get('id'),
            'result': trade_data.get('result'),
            'profit': trade_data.get('profit'),
            'indicators_quality': self._analyze_indicators(trade_data),
            'entry_quality': self._analyze_entry(trade_data),
            'timing_quality': self._analyze_timing(trade_data),
            'confluence_score': self._calculate_confluence(trade_data),
            'precision_factors': self._identify_precision_factors(trade_data),
            'improvement_areas': self._identify_improvements(trade_data),
            'ai_insights': None
        }
        
        # Agregar análisis de IA si está disponible
        if self.llm_client:
            analysis['ai_insights'] = self._get_ai_insights(trade_data, analysis)
        
        self.trades_history.append(analysis)
        return analysis
    
    def _analyze_indicators(self, trade_data: Dict) -> Dict:
        """Analiza la calidad de los indicadores en la entrada"""
        rsi = trade_data.get('rsi', 50)
        macd = trade_data.get('macd', 0)
        
        quality = {
            'rsi_quality': self._rate_rsi(rsi),
            'macd_quality': self._rate_macd(macd),
            'overall_score': 0
        }
        
        # Calcular score general
        rsi_score = quality['rsi_quality']['score']
        macd_score = quality['macd_quality']['score']
        quality['overall_score'] = (rsi_score + macd_score) / 2
        
        return quality
    
    def _rate_rsi(self, rsi: float) -> Dict:
        """Califica la calidad del RSI"""
        if rsi < 20:
            return {'level': 'EXCELLENT', 'score': 100, 'reason': 'Sobreventa extrema'}
        elif rsi < 30:
            return {'level': 'VERY_GOOD', 'score': 90, 'reason': 'Sobreventa clara'}
        elif rsi < 40:
            return {'level': 'GOOD', 'score': 70, 'reason': 'Sobreventa moderada'}
        elif rsi > 80:
            return {'level': 'EXCELLENT', 'score': 100, 'reason': 'Sobrecompra extrema'}
        elif rsi > 70:
            return {'level': 'VERY_GOOD', 'score': 90, 'reason': 'Sobrecompra clara'}
        elif rsi > 60:
            return {'level': 'GOOD', 'score': 70, 'reason': 'Sobrecompra moderada'}
        else:
            return {'level': 'POOR', 'score': 30, 'reason': 'RSI neutral (45-55)'}
    
    def _rate_macd(self, macd: float) -> Dict:
        """Califica la calidad del MACD"""
        abs_macd = abs(macd)
        
        if abs_macd > 0.0005:
            return {'level': 'EXCELLENT', 'score': 100, 'reason': 'Divergencia muy fuerte'}
        elif abs_macd > 0.0002:
            return {'level': 'VERY_GOOD', 'score': 90, 'reason': 'Divergencia fuerte'}
        elif abs_macd > 0.0001:
            return {'level': 'GOOD', 'score': 70, 'reason': 'Divergencia clara'}
        elif abs_macd > 0.00001:
            return {'level': 'FAIR', 'score': 50, 'reason': 'Divergencia débil'}
        else:
            return {'level': 'POOR', 'score': 20, 'reason': 'MACD casi cero'}
    
    def _analyze_entry(self, trade_data: Dict) -> Dict:
        """Analiza la calidad del punto de entrada"""
        pullback = trade_data.get('pullback_distance', 0)
        confidence = trade_data.get('confidence', 0)
        
        return {
            'pullback_quality': self._rate_pullback(pullback),
            'confidence_level': self._rate_confidence(confidence),
            'entry_score': (self._rate_pullback(pullback)['score'] + 
                          self._rate_confidence(confidence)['score']) / 2
        }
    
    def _rate_pullback(self, pullback: float) -> Dict:
        """Califica la calidad del pullback"""
        if 0.1 <= pullback <= 0.3:
            return {'level': 'OPTIMAL', 'score': 100, 'reason': 'Pullback óptimo'}
        elif 0.05 <= pullback < 0.1:
            return {'level': 'GOOD', 'score': 80, 'reason': 'Pullback aceptable'}
        elif 0.3 < pullback <= 0.5:
            return {'level': 'FAIR', 'score': 60, 'reason': 'Pullback moderado'}
        else:
            return {'level': 'POOR', 'score': 20, 'reason': 'Pullback débil o excesivo'}
    
    def _rate_confidence(self, confidence: float) -> Dict:
        """Califica el nivel de confianza"""
        conf_pct = confidence * 100
        
        if conf_pct >= 80:
            return {'level': 'EXCELLENT', 'score': 100, 'reason': f'Confianza muy alta ({conf_pct:.0f}%)'}
        elif conf_pct >= 70:
            return {'level': 'VERY_GOOD', 'score': 90, 'reason': f'Confianza alta ({conf_pct:.0f}%)'}
        elif conf_pct >= 60:
            return {'level': 'GOOD', 'score': 75, 'reason': f'Confianza aceptable ({conf_pct:.0f}%)'}
        elif conf_pct >= 50:
            return {'level': 'FAIR', 'score': 50, 'reason': f'Confianza moderada ({conf_pct:.0f}%)'}
        else:
            return {'level': 'POOR', 'score': 20, 'reason': f'Confianza baja ({conf_pct:.0f}%)'}
    
    def _analyze_timing(self, trade_data: Dict) -> Dict:
        """Analiza la calidad del timing"""
        return {
            'time_of_day': self._analyze_time_of_day(trade_data.get('timestamp')),
            'market_condition': trade_data.get('market_condition', 'UNKNOWN'),
            'timing_score': 0
        }
    
    def _analyze_time_of_day(self, timestamp: str) -> Dict:
        """Analiza si la hora es óptima para trading"""
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            
            # Horas óptimas: 8-12 y 14-18 (horario de mercado)
            if 8 <= hour <= 12 or 14 <= hour <= 18:
                return {'period': 'OPTIMAL', 'score': 100, 'reason': 'Horario de mercado activo'}
            elif 6 <= hour <= 20:
                return {'period': 'GOOD', 'score': 80, 'reason': 'Horario aceptable'}
            else:
                return {'period': 'POOR', 'score': 40, 'reason': 'Horario de baja volatilidad'}
        except:
            return {'period': 'UNKNOWN', 'score': 50, 'reason': 'No se pudo analizar'}
    
    def _calculate_confluence(self, trade_data: Dict) -> float:
        """Calcula el score de confluencia de señales"""
        signals = 0
        total = 0
        
        # RSI
        rsi = trade_data.get('rsi', 50)
        if rsi < 30 or rsi > 70:
            signals += 1
        total += 1
        
        # MACD
        macd = trade_data.get('macd', 0)
        if abs(macd) > 0.0001:
            signals += 1
        total += 1
        
        # Pullback
        pullback = trade_data.get('pullback_distance', 0)
        if 0.05 <= pullback <= 0.5:
            signals += 1
        total += 1
        
        # Confianza
        confidence = trade_data.get('confidence', 0)
        if confidence >= 0.65:
            signals += 1
        total += 1
        
        return (signals / total) * 100 if total > 0 else 0
    
    def _identify_precision_factors(self, trade_data: Dict) -> List[str]:
        """Identifica factores que mejoran la precisión"""
        factors = []
        
        rsi = trade_data.get('rsi', 50)
        if rsi < 25 or rsi > 75:
            factors.append('RSI_EXTREMO')
        
        macd = trade_data.get('macd', 0)
        if abs(macd) > 0.0002:
            factors.append('MACD_FUERTE')
        
        pullback = trade_data.get('pullback_distance', 0)
        if 0.1 <= pullback <= 0.3:
            factors.append('PULLBACK_OPTIMO')
        
        confidence = trade_data.get('confidence', 0)
        if confidence >= 0.75:
            factors.append('CONFIANZA_ALTA')
        
        return factors
    
    def _identify_improvements(self, trade_data: Dict) -> List[str]:
        """Identifica áreas de mejora"""
        improvements = []
        
        rsi = trade_data.get('rsi', 50)
        if 40 <= rsi <= 60:
            improvements.append('RSI_NEUTRAL_EVITAR')
        
        macd = trade_data.get('macd', 0)
        if abs(macd) < 0.00005:
            improvements.append('MACD_DEBIL_ESPERAR')
        
        pullback = trade_data.get('pullback_distance', 0)
        if pullback < 0.05 or pullback > 0.5:
            improvements.append('PULLBACK_FUERA_RANGO')
        
        confidence = trade_data.get('confidence', 0)
        if confidence < 0.65:
            improvements.append('CONFIANZA_BAJA_RECHAZAR')
        
        return improvements
    
    def _get_ai_insights(self, trade_data: Dict, analysis: Dict) -> str:
        """Obtiene insights de IA sobre la operación"""
        try:
            prompt = f"""
Analiza esta operación de trading y proporciona insights:

OPERACIÓN:
- Activo: {trade_data.get('asset')}
- Acción: {trade_data.get('action')}
- Resultado: {trade_data.get('result')}
- Ganancia: ${trade_data.get('profit')}

INDICADORES:
- RSI: {trade_data.get('rsi'):.1f}
- MACD: {trade_data.get('macd'):.6f}
- Pullback: {trade_data.get('pullback_distance'):.3f}%
- Confianza: {trade_data.get('confidence')*100:.0f}%

ANÁLISIS:
- Calidad de indicadores: {analysis['indicators_quality']['overall_score']:.0f}/100
- Calidad de entrada: {analysis['entry_quality']['entry_score']:.0f}/100
- Score de confluencia: {analysis['confluence_score']:.0f}/100

Proporciona:
1. Por qué ganó/perdió
2. Qué hizo bien
3. Qué mejorar
4. Patrón identificado
"""
            
            if self.llm_client:
                response = self.llm_client.analyze(prompt)
                return response
            return None
        except Exception as e:
            logger.error(f"Error obteniendo insights de IA: {e}")
            return None
    
    def get_winning_patterns(self) -> Dict:
        """Extrae patrones de operaciones ganadoras"""
        winning_trades = [t for t in self.trades_history if t['result'] == 'WIN']
        
        if not winning_trades:
            return {}
        
        patterns = {
            'avg_rsi': np.mean([t.get('rsi', 50) for t in winning_trades]),
            'avg_macd': np.mean([t.get('macd', 0) for t in winning_trades]),
            'avg_pullback': np.mean([t.get('pullback_distance', 0) for t in winning_trades]),
            'avg_confidence': np.mean([t.get('confidence', 0) for t in winning_trades]),
            'common_factors': self._get_common_factors([t['precision_factors'] for t in winning_trades]),
            'count': len(winning_trades)
        }
        
        return patterns
    
    def get_losing_patterns(self) -> Dict:
        """Extrae patrones de operaciones perdedoras"""
        losing_trades = [t for t in self.trades_history if t['result'] == 'LOSS']
        
        if not losing_trades:
            return {}
        
        patterns = {
            'avg_rsi': np.mean([t.get('rsi', 50) for t in losing_trades]),
            'avg_macd': np.mean([t.get('macd', 0) for t in losing_trades]),
            'avg_pullback': np.mean([t.get('pullback_distance', 0) for t in losing_trades]),
            'avg_confidence': np.mean([t.get('confidence', 0) for t in losing_trades]),
            'common_issues': self._get_common_factors([t['improvement_areas'] for t in losing_trades]),
            'count': len(losing_trades)
        }
        
        return patterns
    
    def _get_common_factors(self, factors_list: List[List[str]]) -> Dict:
        """Extrae factores comunes de una lista de listas"""
        from collections import Counter
        
        all_factors = [f for sublist in factors_list for f in sublist]
        counter = Counter(all_factors)
        
        return dict(counter.most_common(5))
    
    def generate_improvement_report(self) -> Dict:
        """Genera reporte de mejoras basado en análisis"""
        winning = self.get_winning_patterns()
        losing = self.get_losing_patterns()
        
        report = {
            'total_trades': len(self.trades_history),
            'winning_trades': winning.get('count', 0),
            'losing_trades': losing.get('count', 0),
            'win_rate': (winning.get('count', 0) / len(self.trades_history) * 100) if self.trades_history else 0,
            'winning_patterns': winning,
            'losing_patterns': losing,
            'recommendations': self._generate_recommendations(winning, losing),
            'precision_improvements': self._calculate_precision_improvements()
        }
        
        return report
    
    def _generate_recommendations(self, winning: Dict, losing: Dict) -> List[str]:
        """Genera recomendaciones basadas en patrones"""
        recommendations = []
        
        if winning and losing:
            # Comparar RSI
            if winning.get('avg_rsi', 50) < losing.get('avg_rsi', 50):
                recommendations.append('Preferir RSI más bajo (< 30)')
            
            # Comparar MACD
            if abs(winning.get('avg_macd', 0)) > abs(losing.get('avg_macd', 0)):
                recommendations.append('Esperar MACD más fuerte (> 0.0002)')
            
            # Comparar Pullback
            if 0.1 <= winning.get('avg_pullback', 0) <= 0.3:
                recommendations.append('Mantener pullback en rango óptimo (0.1-0.3%)')
            
            # Comparar Confianza
            if winning.get('avg_confidence', 0) > losing.get('avg_confidence', 0):
                recommendations.append(f"Aumentar umbral de confianza a {winning.get('avg_confidence', 0)*100:.0f}%")
        
        return recommendations
    
    def _calculate_precision_improvements(self) -> Dict:
        """Calcula mejoras potenciales de precisión"""
        if not self.trades_history:
            return {}
        
        current_win_rate = sum(1 for t in self.trades_history if t['result'] == 'WIN') / len(self.trades_history)
        
        # Simular mejoras
        improvements = {
            'current_win_rate': current_win_rate * 100,
            'if_only_high_confidence': self._simulate_filter('confidence') * 100,
            'if_only_strong_rsi': self._simulate_filter('rsi_extreme') * 100,
            'if_only_strong_macd': self._simulate_filter('macd_strong') * 100,
            'if_all_filters': self._simulate_all_filters() * 100
        }
        
        return improvements
    
    def _simulate_filter(self, filter_type: str) -> float:
        """Simula aplicar un filtro y calcula win rate resultante"""
        if filter_type == 'confidence':
            filtered = [t for t in self.trades_history if t.get('confidence', 0) >= 0.75]
        elif filter_type == 'rsi_extreme':
            filtered = [t for t in self.trades_history if t.get('rsi', 50) < 25 or t.get('rsi', 50) > 75]
        elif filter_type == 'macd_strong':
            filtered = [t for t in self.trades_history if abs(t.get('macd', 0)) > 0.0002]
        else:
            return 0
        
        if not filtered:
            return 0
        
        return sum(1 for t in filtered if t['result'] == 'WIN') / len(filtered)
    
    def _simulate_all_filters(self) -> float:
        """Simula aplicar todos los filtros"""
        filtered = [
            t for t in self.trades_history
            if (t.get('confidence', 0) >= 0.75 and
                (t.get('rsi', 50) < 25 or t.get('rsi', 50) > 75) and
                abs(t.get('macd', 0)) > 0.0002)
        ]
        
        if not filtered:
            return 0
        
        return sum(1 for t in filtered if t['result'] == 'WIN') / len(filtered)
