"""
Professional Learning System - Sistema de Aprendizaje Profesional
Implementa conceptos avanzados de trading para que el bot aprenda como un trader profesional
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class MarketPhase(Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    RANGING = "ranging"

class TradingConcept(Enum):
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BREAK_OF_STRUCTURE = "break_of_structure"
    CHANGE_OF_CHARACTER = "change_of_character"
    INDUCEMENT = "inducement"
    MITIGATION = "mitigation"
    SMART_MONEY_REVERSAL = "smart_money_reversal"
    INSTITUTIONAL_CANDLE = "institutional_candle"

@dataclass
class TradingLesson:
    """Representa una lección aprendida del mercado"""
    concept: TradingConcept
    market_phase: MarketPhase
    setup_description: str
    entry_conditions: List[str]
    exit_conditions: List[str]
    success_rate: float
    risk_reward_ratio: float
    market_context: Dict
    timestamp: datetime
    confidence_level: float

class ProfessionalLearningSystem:
    """
    Sistema que aprende conceptos profesionales de trading:
    - Identifica patrones institucionales
    - Aprende timing de entrada y salida
    - Desarrolla intuición de mercado
    - Mejora la toma de decisiones
    """
    
    def __init__(self):
        self.lessons_learned: List[TradingLesson] = []
        self.concept_performance: Dict[TradingConcept, Dict] = {}
        self.market_phase_performance: Dict[MarketPhase, Dict] = {}
        self.pattern_library: Dict[str, Dict] = {}
        
        # Configuración de aprendizaje
        self.min_samples_for_lesson = 5
        self.confidence_threshold = 0.7
        self.max_lessons_per_concept = 20
        
        # Inicializar performance tracking
        self._initialize_performance_tracking()
    
    def _initialize_performance_tracking(self):
        """Inicializa el tracking de performance por concepto"""
        for concept in TradingConcept:
            self.concept_performance[concept] = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_profit': 0.0,
                'avg_risk_reward': 0.0,
                'best_conditions': [],
                'worst_conditions': [],
                'success_rate': 0.0
            }
        
        for phase in MarketPhase:
            self.market_phase_performance[phase] = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_profit': 0.0,
                'best_concepts': [],
                'success_rate': 0.0
            }
    
    def analyze_trade_for_learning(self, trade_data: Dict, market_analysis: Dict, 
                                 result: Dict) -> Optional[TradingLesson]:
        """
        Analiza una operación completada para extraer lecciones profesionales
        
        Args:
            trade_data: Datos de la operación
            market_analysis: Análisis de mercado al momento de la entrada
            result: Resultado de la operación
        
        Returns:
            TradingLesson si se puede extraer una lección válida
        """
        try:
            # 1. Identificar el concepto principal usado
            primary_concept = self._identify_primary_concept(market_analysis)
            
            # 2. Determinar la fase de mercado
            market_phase = self._determine_market_phase(market_analysis)
            
            # 3. Extraer condiciones de entrada
            entry_conditions = self._extract_entry_conditions(market_analysis, trade_data)
            
            # 4. Analizar el resultado
            was_successful = result.get('won', False)
            profit = result.get('profit', 0)
            
            # 5. Calcular métricas
            risk_reward = abs(profit / trade_data.get('amount', 1)) if trade_data.get('amount', 1) != 0 else 0
            
            # 6. Crear lección
            lesson = TradingLesson(
                concept=primary_concept,
                market_phase=market_phase,
                setup_description=self._generate_setup_description(market_analysis, trade_data),
                entry_conditions=entry_conditions,
                exit_conditions=self._extract_exit_conditions(result),
                success_rate=1.0 if was_successful else 0.0,
                risk_reward_ratio=risk_reward,
                market_context=self._extract_market_context(market_analysis),
                timestamp=datetime.now(),
                confidence_level=market_analysis.get('confidence', 0) / 100
            )
            
            # 7. Actualizar performance tracking
            self._update_performance_tracking(lesson, was_successful, profit)
            
            # 8. Agregar a lecciones aprendidas
            self.lessons_learned.append(lesson)
            
            # 9. Mantener solo las lecciones más recientes
            if len(self.lessons_learned) > 1000:
                self.lessons_learned = self.lessons_learned[-1000:]
            
            return lesson
            
        except Exception as e:
            logger.error(f"Error analizando trade para aprendizaje: {e}")
            return None
    
    def _identify_primary_concept(self, market_analysis: Dict) -> TradingConcept:
        """Identifica el concepto principal usado en el análisis"""
        
        # Verificar si hay análisis Smart Money
        if 'order_blocks' in market_analysis and market_analysis['order_blocks']:
            return TradingConcept.ORDER_BLOCK
        
        if 'fair_value_gaps' in market_analysis and market_analysis['fair_value_gaps']:
            return TradingConcept.FAIR_VALUE_GAP
        
        # Verificar estructura de mercado
        structure = market_analysis.get('market_structure', {})
        if structure.get('bos'):
            return TradingConcept.BREAK_OF_STRUCTURE
        
        if structure.get('choch'):
            return TradingConcept.CHANGE_OF_CHARACTER
        
        # Verificar inducement
        if 'inducement_signals' in market_analysis and market_analysis['inducement_signals']:
            return TradingConcept.INDUCEMENT
        
        # Verificar liquidez
        if 'liquidity_zones' in market_analysis and market_analysis['liquidity_zones']:
            return TradingConcept.LIQUIDITY_SWEEP
        
        # Default: Smart Money Reversal (patrón general)
        return TradingConcept.SMART_MONEY_REVERSAL
    
    def _determine_market_phase(self, market_analysis: Dict) -> MarketPhase:
        """Determina la fase de mercado basada en el análisis"""
        
        phase = market_analysis.get('market_phase', 'ranging')
        
        phase_mapping = {
            'accumulation': MarketPhase.ACCUMULATION,
            'markup': MarketPhase.MARKUP,
            'distribution': MarketPhase.DISTRIBUTION,
            'markdown': MarketPhase.MARKDOWN,
            'ranging': MarketPhase.RANGING
        }
        
        return phase_mapping.get(phase, MarketPhase.RANGING)
    
    def _extract_entry_conditions(self, market_analysis: Dict, trade_data: Dict) -> List[str]:
        """Extrae las condiciones específicas de entrada"""
        conditions = []
        
        # Condiciones de estructura
        structure = market_analysis.get('market_structure', {})
        if structure.get('trend'):
            conditions.append(f"Tendencia: {structure['trend']}")
        
        # Condiciones de momentum
        momentum = market_analysis.get('momentum', {})
        if momentum.get('state'):
            conditions.append(f"Momentum: {momentum['state']}")
        
        # Condiciones de Smart Money
        entry_signal = market_analysis.get('entry_signal', {})
        if entry_signal.get('reasons'):
            conditions.extend(entry_signal['reasons'])
        
        # Condiciones técnicas
        if 'rsi' in str(market_analysis):
            conditions.append("RSI en zona de interés")
        
        if 'macd' in str(market_analysis):
            conditions.append("MACD confirmando dirección")
        
        return conditions[:5]  # Máximo 5 condiciones principales
    
    def _extract_exit_conditions(self, result: Dict) -> List[str]:
        """Extrae las condiciones de salida"""
        conditions = []
        
        if result.get('won'):
            conditions.append("Objetivo alcanzado")
            conditions.append("Movimiento en dirección esperada")
        else:
            conditions.append("Stop loss activado")
            conditions.append("Movimiento contrario a expectativa")
        
        return conditions
    
    def _generate_setup_description(self, market_analysis: Dict, trade_data: Dict) -> str:
        """Genera una descripción del setup"""
        
        direction = trade_data.get('direction', 'unknown')
        asset = trade_data.get('asset', 'unknown')
        
        # Obtener contexto principal
        main_reason = "Setup general"
        entry_signal = market_analysis.get('entry_signal', {})
        if entry_signal.get('reasons'):
            main_reason = entry_signal['reasons'][0]
        
        return f"{direction.upper()} en {asset} basado en {main_reason}"
    
    def _extract_market_context(self, market_analysis: Dict) -> Dict:
        """Extrae el contexto de mercado relevante"""
        context = {}
        
        # Volatilidad
        if 'volatility' in market_analysis:
            context['volatility'] = market_analysis['volatility']
        
        # Fase de mercado
        if 'market_phase' in market_analysis:
            context['market_phase'] = market_analysis['market_phase']
        
        # Confianza del análisis
        if 'confidence' in market_analysis:
            context['analysis_confidence'] = market_analysis['confidence']
        
        # Número de confluencias
        entry_signal = market_analysis.get('entry_signal', {})
        if entry_signal.get('reasons'):
            context['confluences'] = len(entry_signal['reasons'])
        
        return context
    
    def _update_performance_tracking(self, lesson: TradingLesson, was_successful: bool, profit: float):
        """Actualiza el tracking de performance"""
        
        # Actualizar performance por concepto
        concept_perf = self.concept_performance[lesson.concept]
        concept_perf['total_trades'] += 1
        if was_successful:
            concept_perf['winning_trades'] += 1
        concept_perf['total_profit'] += profit
        concept_perf['success_rate'] = concept_perf['winning_trades'] / concept_perf['total_trades']
        
        # Actualizar performance por fase de mercado
        phase_perf = self.market_phase_performance[lesson.market_phase]
        phase_perf['total_trades'] += 1
        if was_successful:
            phase_perf['winning_trades'] += 1
        phase_perf['total_profit'] += profit
        phase_perf['success_rate'] = phase_perf['winning_trades'] / phase_perf['total_trades']
    
    def get_best_concepts_for_phase(self, market_phase: MarketPhase, min_trades: int = 5) -> List[Tuple[TradingConcept, float]]:
        """
        Obtiene los mejores conceptos para una fase de mercado específica
        
        Returns:
            Lista de (concepto, success_rate) ordenada por performance
        """
        concept_performance = []
        
        # Filtrar lecciones por fase de mercado
        phase_lessons = [l for l in self.lessons_learned if l.market_phase == market_phase]
        
        # Agrupar por concepto
        concept_groups = {}
        for lesson in phase_lessons:
            if lesson.concept not in concept_groups:
                concept_groups[lesson.concept] = []
            concept_groups[lesson.concept].append(lesson)
        
        # Calcular performance por concepto
        for concept, lessons in concept_groups.items():
            if len(lessons) >= min_trades:
                success_rate = sum(l.success_rate for l in lessons) / len(lessons)
                concept_performance.append((concept, success_rate))
        
        # Ordenar por success rate
        concept_performance.sort(key=lambda x: x[1], reverse=True)
        
        return concept_performance
    
    def get_optimal_entry_conditions(self, concept: TradingConcept, market_phase: MarketPhase) -> List[str]:
        """
        Obtiene las condiciones de entrada óptimas para un concepto y fase específicos
        """
        # Filtrar lecciones exitosas
        successful_lessons = [
            l for l in self.lessons_learned 
            if l.concept == concept and l.market_phase == market_phase and l.success_rate > 0.5
        ]
        
        if not successful_lessons:
            return []
        
        # Contar frecuencia de condiciones
        condition_frequency = {}
        for lesson in successful_lessons:
            for condition in lesson.entry_conditions:
                condition_frequency[condition] = condition_frequency.get(condition, 0) + 1
        
        # Ordenar por frecuencia
        sorted_conditions = sorted(condition_frequency.items(), key=lambda x: x[1], reverse=True)
        
        # Retornar las condiciones más comunes
        return [condition for condition, freq in sorted_conditions[:5]]
    
    def should_trade_concept(self, concept: TradingConcept, market_phase: MarketPhase, 
                           current_conditions: List[str]) -> Tuple[bool, float, List[str]]:
        """
        Determina si se debe operar un concepto específico basado en el aprendizaje
        
        Returns:
            (should_trade, confidence, reasons)
        """
        # Obtener lecciones relevantes
        relevant_lessons = [
            l for l in self.lessons_learned 
            if l.concept == concept and l.market_phase == market_phase
        ]
        
        if len(relevant_lessons) < self.min_samples_for_lesson:
            return False, 0.0, ["Insuficientes datos históricos"]
        
        # Calcular success rate histórico
        historical_success_rate = sum(l.success_rate for l in relevant_lessons) / len(relevant_lessons)
        
        if historical_success_rate < 0.6:
            return False, historical_success_rate, [f"Baja tasa de éxito histórica ({historical_success_rate:.1%})"]
        
        # Verificar coincidencia de condiciones
        optimal_conditions = self.get_optimal_entry_conditions(concept, market_phase)
        matching_conditions = [c for c in current_conditions if c in optimal_conditions]
        
        condition_match_ratio = len(matching_conditions) / max(len(optimal_conditions), 1)
        
        if condition_match_ratio < 0.4:
            return False, condition_match_ratio, ["Pocas condiciones óptimas presentes"]
        
        # Calcular confianza final
        confidence = (historical_success_rate * 0.6) + (condition_match_ratio * 0.4)
        
        reasons = [
            f"Tasa de éxito histórica: {historical_success_rate:.1%}",
            f"Condiciones coincidentes: {len(matching_conditions)}/{len(optimal_conditions)}",
            f"Concepto: {concept.value}",
            f"Fase de mercado: {market_phase.value}"
        ]
        
        should_trade = confidence >= self.confidence_threshold
        
        return should_trade, confidence, reasons
    
    def get_learning_insights(self) -> Dict:
        """Obtiene insights del aprendizaje acumulado"""
        
        if not self.lessons_learned:
            return {"error": "No hay lecciones aprendidas aún"}
        
        insights = {
            'total_lessons': len(self.lessons_learned),
            'concepts_learned': len(set(l.concept for l in self.lessons_learned)),
            'best_concepts': [],
            'best_market_phases': [],
            'recent_performance': {},
            'recommendations': []
        }
        
        # Mejores conceptos
        concept_success = {}
        for concept in TradingConcept:
            concept_lessons = [l for l in self.lessons_learned if l.concept == concept]
            if concept_lessons:
                success_rate = sum(l.success_rate for l in concept_lessons) / len(concept_lessons)
                concept_success[concept] = {
                    'success_rate': success_rate,
                    'total_lessons': len(concept_lessons)
                }
        
        # Ordenar por success rate
        sorted_concepts = sorted(concept_success.items(), key=lambda x: x[1]['success_rate'], reverse=True)
        insights['best_concepts'] = [
            {
                'concept': concept.value,
                'success_rate': data['success_rate'],
                'total_lessons': data['total_lessons']
            }
            for concept, data in sorted_concepts[:5]
        ]
        
        # Mejores fases de mercado
        phase_success = {}
        for phase in MarketPhase:
            phase_lessons = [l for l in self.lessons_learned if l.market_phase == phase]
            if phase_lessons:
                success_rate = sum(l.success_rate for l in phase_lessons) / len(phase_lessons)
                phase_success[phase] = {
                    'success_rate': success_rate,
                    'total_lessons': len(phase_lessons)
                }
        
        sorted_phases = sorted(phase_success.items(), key=lambda x: x[1]['success_rate'], reverse=True)
        insights['best_market_phases'] = [
            {
                'phase': phase.value,
                'success_rate': data['success_rate'],
                'total_lessons': data['total_lessons']
            }
            for phase, data in sorted_phases
        ]
        
        # Performance reciente (últimas 20 lecciones)
        recent_lessons = self.lessons_learned[-20:] if len(self.lessons_learned) >= 20 else self.lessons_learned
        if recent_lessons:
            recent_success_rate = sum(l.success_rate for l in recent_lessons) / len(recent_lessons)
            insights['recent_performance'] = {
                'success_rate': recent_success_rate,
                'total_trades': len(recent_lessons),
                'trend': 'improving' if recent_success_rate > 0.6 else 'declining'
            }
        
        # Generar recomendaciones
        insights['recommendations'] = self._generate_recommendations(insights)
        
        return insights
    
    def _generate_recommendations(self, insights: Dict) -> List[str]:
        """Genera recomendaciones basadas en los insights"""
        recommendations = []
        
        # Recomendaciones basadas en conceptos
        if insights['best_concepts']:
            best_concept = insights['best_concepts'][0]
            if best_concept['success_rate'] > 0.7:
                recommendations.append(f"Enfocarse en {best_concept['concept']} (éxito: {best_concept['success_rate']:.1%})")
        
        # Recomendaciones basadas en fases de mercado
        if insights['best_market_phases']:
            best_phase = insights['best_market_phases'][0]
            if best_phase['success_rate'] > 0.7:
                recommendations.append(f"Operar principalmente en fase {best_phase['phase']} (éxito: {best_phase['success_rate']:.1%})")
        
        # Recomendaciones basadas en performance reciente
        recent_perf = insights.get('recent_performance', {})
        if recent_perf.get('success_rate', 0) < 0.5:
            recommendations.append("Revisar estrategia - performance reciente por debajo del 50%")
        elif recent_perf.get('success_rate', 0) > 0.7:
            recommendations.append("Mantener estrategia actual - performance reciente excelente")
        
        # Recomendación de diversificación
        if len(insights['best_concepts']) > 3:
            recommendations.append("Diversificar entre múltiples conceptos para reducir riesgo")
        
        return recommendations
    
    def export_lessons(self) -> Dict:
        """Exporta las lecciones aprendidas para persistencia"""
        return {
            'lessons': [
                {
                    'concept': lesson.concept.value,
                    'market_phase': lesson.market_phase.value,
                    'setup_description': lesson.setup_description,
                    'entry_conditions': lesson.entry_conditions,
                    'exit_conditions': lesson.exit_conditions,
                    'success_rate': lesson.success_rate,
                    'risk_reward_ratio': lesson.risk_reward_ratio,
                    'market_context': lesson.market_context,
                    'timestamp': lesson.timestamp.isoformat(),
                    'confidence_level': lesson.confidence_level
                }
                for lesson in self.lessons_learned
            ],
            'concept_performance': {
                concept.value: perf for concept, perf in self.concept_performance.items()
            },
            'market_phase_performance': {
                phase.value: perf for phase, perf in self.market_phase_performance.items()
            }
        }
    
    def import_lessons(self, data: Dict):
        """Importa lecciones aprendidas desde persistencia"""
        try:
            # Importar lecciones
            for lesson_data in data.get('lessons', []):
                lesson = TradingLesson(
                    concept=TradingConcept(lesson_data['concept']),
                    market_phase=MarketPhase(lesson_data['market_phase']),
                    setup_description=lesson_data['setup_description'],
                    entry_conditions=lesson_data['entry_conditions'],
                    exit_conditions=lesson_data['exit_conditions'],
                    success_rate=lesson_data['success_rate'],
                    risk_reward_ratio=lesson_data['risk_reward_ratio'],
                    market_context=lesson_data['market_context'],
                    timestamp=datetime.fromisoformat(lesson_data['timestamp']),
                    confidence_level=lesson_data['confidence_level']
                )
                self.lessons_learned.append(lesson)
            
            # Importar performance tracking
            for concept_str, perf in data.get('concept_performance', {}).items():
                concept = TradingConcept(concept_str)
                self.concept_performance[concept] = perf
            
            for phase_str, perf in data.get('market_phase_performance', {}).items():
                phase = MarketPhase(phase_str)
                self.market_phase_performance[phase] = perf
            
            logger.info(f"Importadas {len(self.lessons_learned)} lecciones profesionales")
            
        except Exception as e:
            logger.error(f"Error importando lecciones: {e}")