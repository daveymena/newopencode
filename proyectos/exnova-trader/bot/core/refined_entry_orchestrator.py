"""
Orquestador de Entradas Refinadas (OER)
========================================
Integra todos los sistemas de validación refinada antes de ejecutar operaciones.

Este módulo se asegura de que cada operación pase por:
1. Scoring de oportunidad refinado
2. Validación de entrada refinada
3. Verificación de confluencia multi-indicador
4. Confirmación de timing óptimo
"""

from core.refined_entry_validator import RefinedEntryValidator, EntryRefiner
from core.refined_opportunity_scorer import RefinedOpportunityScorer

class EntryOrchestrator:
    """
    Orquestador que coordina todos los sistemas de validación antes de operar.
    Agrega una capa adicional de protección y calidad.
    """
    
    def __init__(self):
        # Sistemas de validación
        self.entry_validator = RefinedEntryValidator()
        self.entry_refiner = EntryRefiner()
        self.opportunity_scorer = RefinedOpportunityScorer()
        
        # Configuración
        self.use_refined_validation = True
        self.min_refined_score = 15  # Score mínimo del scorer (reducido para 24/7)
        self.min_confidence = 0.65   # 65% confianza mínima (reducido de 80% para 24/7)
        
        # Estadísticas
        self.stats = {
            'total_opportunities': 0,
            'approved': 0,
            'rejected': 0,
            'rejections_by_reason': {}
        }
        
    def evaluate_opportunity(self, df, action, asset, indicators_analysis=None, 
                            rl_prediction=None, market_context=None, power_levels=None):
        """
        Evalúa una oportunidad con TODOS los sistemas de validación refinada.
        
        Args:
            df: DataFrame con datos del activo
            action: Acción propuesta (1=CALL, 2=PUT)
            asset: Nombre del activo
            indicators_analysis: Análisis de indicadores (opcional)
            rl_prediction: Predicción RL (opcional)
            market_context: Contexto de mercado (opcional)
            power_levels: Niveles institucionales (opcional)
            
        Returns:
            dict: {
                'approved': bool,
                'confidence': float,
                'score': float,
                'message': str,
                'details': dict
            }
        """
        result = {
            'approved': False,
            'confidence': 0.0,
            'score': 0.0,
            'message': '',
            'details': {},
            'rejection_reason': None
        }
        
        self.stats['total_opportunities'] += 1
        
        # ============= ETAPA 1: SCORING DE OPORTUNIDAD =============
        scoring_result = self.opportunity_scorer.calculate_score(df, asset, power_levels)
        result['score'] = scoring_result['score']
        result['details']['scoring'] = scoring_result
        
        # Verificar score mínimo
        if scoring_result['score'] < self.min_refined_score:
            reason = f'Score bajo: {scoring_result["score"]:.0f} < {self.min_refined_score}'
            result['rejection_reason'] = 'LOW_SCORE'
            self._record_rejection(reason)
            result['message'] = f"❌ {reason}"
            self.stats['rejected'] += 1
            return result
        
        # Usar la dirección del scoring si es diferente
        if scoring_result['action'] != 'HOLD':
            action = 1 if scoring_result['action'] == 'CALL' else 2
        
        # ============= ETAPA 2: VALIDACIÓN REFINADA =============
        if self.use_refined_validation:
            refinement = self.entry_refiner.refine_decision(
                df=df,
                action=action,
                indicators_analysis=indicators_analysis,
                rl_prediction=rl_prediction,
                market_context=market_context
            )
            
            result['details']['refinement'] = refinement
            
            if not refinement['approved']:
                result['rejection_reason'] = refinement['validation'].get('rejection_reason', 'UNKNOWN')
                result['message'] = f"❌ Validación refinada: {refinement['message']}"
                self._record_rejection(result['rejection_reason'])
                self.stats['rejected'] += 1
                return result
        
        # ============= ETAPA 3: CONFIANZA MÍNIMA =============
        # Combinar confianzas
        scoring_confidence = scoring_result.get('confidence', 0)
        
        if self.use_refined_validation:
            refinement_confidence = refinement['validation'].get('confidence', 0)
            combined_confidence = (scoring_confidence + refinement_confidence) / 2
        else:
            combined_confidence = scoring_confidence
            
        result['confidence'] = combined_confidence
        
        if combined_confidence < self.min_confidence:
            reason = f'Confianza baja: {combined_confidence*100:.0f}% < {self.min_confidence*100:.0f}%'
            result['rejection_reason'] = 'LOW_CONFIDENCE'
            result['message'] = f"❌ {reason}"
            self._record_rejection(reason)
            self.stats['rejected'] += 1
            return result
        
        # ============= TODAS LAS VALIDACIONES PASARON =============
        result['approved'] = True
        result['message'] = f"✅ APROBADA - Score: {result['score']:.0f} | Confianza: {result['confidence']*100:.0f}%"
        
        self.stats['approved'] += 1
        
        return result
    
    def _record_rejection(self, reason):
        """Registra una rechazo por razón"""
        if reason not in self.stats['rejections_by_reason']:
            self.stats['rejections_by_reason'][reason] = 0
        self.stats['rejections_by_reason'][reason] += 1
    
    def get_stats(self):
        """Retorna estadísticas del orquestador"""
        return self.stats
    
    def get_approval_rate(self):
        """Retorna tasa de aprobación"""
        if self.stats['total_opportunities'] == 0:
            return 0
        return self.stats['approved'] / self.stats['total_opportunities']
    
    def reset_stats(self):
        """Resetea estadísticas"""
        self.stats = {
            'total_opportunities': 0,
            'approved': 0,
            'rejected': 0,
            'rejections_by_reason': {}
        }


def integrate_refined_validation(trader):
    """
    Integra el orquestador de entradas refinadas en el trader.
    Llama esta función después de crear el LiveTrader.
    """
    from core.refined_entry_orchestrator import EntryOrchestrator
    
    # Crear orquestador
    orchestrator = EntryOrchestrator()
    
    # Guardar referencia en el trader
    trader.entry_orchestrator = orchestrator
    
    # Guardar el método original de validación
    trader._original_validate_decision = trader.decision_validator.validate_decision
    
    # Sobrescribir método de validación para usar el orquestador
    def refined_validate_decision(df, action, indicators_analysis=None, rl_prediction=None, llm_advice=None):
        """Método de validación mejorado"""
        # Usar el orquestador si está disponible
        if hasattr(trader, 'entry_orchestrator') and trader.entry_orchestrator:
            # Obtener power_levels si es posible
            power_levels = None
            if hasattr(trader.asset_manager, '_get_power_levels'):
                try:
                    power_levels = trader.asset_manager._get_power_levels(trader.current_asset)
                except:
                    pass
            
            # Evaluar con el orquestador
            result = trader.entry_orchestrator.evaluate_opportunity(
                df=df,
                action=action,
                asset=trader.current_asset,
                indicators_analysis=indicators_analysis,
                rl_prediction=rl_prediction,
                market_context=None,
                power_levels=power_levels
            )
            
            if result['approved']:
                return {
                    'valid': True,
                    'confidence': result['confidence'],
                    'recommendation': 'CALL' if action == 1 else 'PUT',
                    'reasons': [result['message']],
                    'warnings': []
                }
            else:
                return {
                    'valid': False,
                    'confidence': 0,
                    'recommendation': 'HOLD',
                    'reasons': [],
                    'warnings': [result['message']]
                }
        else:
            # Fallback al método original
            return trader._original_validate_decision(df, action, indicators_analysis, rl_prediction, llm_advice)
    
    # Reemplazar método
    trader.decision_validator.validate_decision = refined_validate_decision
    
    return trader