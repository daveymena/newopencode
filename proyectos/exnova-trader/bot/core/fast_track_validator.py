"""
Fast-Track Validator - Ejecuta inmediatamente señales ELITE sin esperar a Ollama
Captura las mejores oportunidades antes de que se pierdan
"""

class FastTrackValidator:
    """
    Valida si una señal es tan fuerte que puede ejecutarse inmediatamente
    sin esperar análisis de Ollama (que tarda 15 segundos)
    """
    
    def __init__(self):
        # Criterios para Fast-Track
        self.technical_score_threshold = 85  # Score técnico mínimo
        self.multi_tf_score_threshold = 75   # Score multi-timeframe mínimo
        self.min_criteria_passed = 4         # Mínimo 4 de 5 criterios
        
        # Estadísticas
        self.fast_track_count = 0
        self.fast_track_wins = 0
        self.fast_track_losses = 0
    
    def should_fast_track(self, opportunity_data):
        """
        Determina si la señal es ELITE y puede ejecutarse inmediatamente
        
        Args:
            opportunity_data: dict con datos de la oportunidad
            
        Returns:
            dict: {
                'fast_track': bool,
                'reason': str,
                'criteria_passed': int,
                'criteria_details': dict
            }
        """
        criteria = {}
        
        # 1. SCORE TÉCNICO MUY ALTO
        technical_score = opportunity_data.get('technical_score', 0)
        criteria['technical_elite'] = technical_score >= self.technical_score_threshold
        
        # 2. MULTI-TIMEFRAME FUERTEMENTE ALINEADO
        multi_tf_score = opportunity_data.get('multi_tf_score', 0)
        multi_tf_aligned = opportunity_data.get('multi_tf_aligned', False)
        criteria['multi_tf_strong'] = multi_tf_aligned and multi_tf_score >= self.multi_tf_score_threshold
        
        # 3. FIBONACCI EN GOLDEN RATIO
        fibonacci_level = opportunity_data.get('fibonacci_level', '')
        criteria['fibonacci_golden'] = fibonacci_level == 'golden'
        
        # 4. SMART MONEY CONFIRMADO (Order Block o FVG)
        order_block = opportunity_data.get('order_block_detected', False)
        fvg_detected = opportunity_data.get('fvg_detected', False)
        criteria['smart_money_confirmed'] = order_block or fvg_detected
        
        # 5. SIN PÉRDIDAS RECIENTES
        consecutive_losses = opportunity_data.get('consecutive_losses', 0)
        criteria['no_recent_losses'] = consecutive_losses == 0
        
        # Contar criterios pasados
        criteria_passed = sum(criteria.values())
        
        # Decisión
        should_fast_track = criteria_passed >= self.min_criteria_passed
        
        if should_fast_track:
            reason = f"Señal ELITE detectada ({criteria_passed}/5 criterios) - Fast-Track activado"
        else:
            reason = f"Señal normal ({criteria_passed}/5 criterios) - Requiere validación completa"
        
        return {
            'fast_track': should_fast_track,
            'reason': reason,
            'criteria_passed': criteria_passed,
            'criteria_details': criteria,
            'confidence_boost': 0.10 if should_fast_track else 0.00  # +10% confianza
        }
    
    def record_result(self, won):
        """Registra resultado de operación Fast-Track"""
        self.fast_track_count += 1
        if won:
            self.fast_track_wins += 1
        else:
            self.fast_track_losses += 1
    
    def get_stats(self):
        """Obtiene estadísticas de Fast-Track"""
        if self.fast_track_count == 0:
            return {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0
            }
        
        return {
            'total': self.fast_track_count,
            'wins': self.fast_track_wins,
            'losses': self.fast_track_losses,
            'win_rate': (self.fast_track_wins / self.fast_track_count) * 100
        }
    
    def get_human_readable_criteria(self, criteria_details):
        """Genera descripción legible de criterios"""
        descriptions = []
        
        if criteria_details.get('technical_elite'):
            descriptions.append("✅ Score técnico ELITE (≥85)")
        else:
            descriptions.append("❌ Score técnico normal (<85)")
        
        if criteria_details.get('multi_tf_strong'):
            descriptions.append("✅ Multi-timeframe FUERTE (≥75)")
        else:
            descriptions.append("❌ Multi-timeframe débil (<75)")
        
        if criteria_details.get('fibonacci_golden'):
            descriptions.append("✅ Fibonacci GOLDEN RATIO")
        else:
            descriptions.append("❌ Fibonacci no en Golden Ratio")
        
        if criteria_details.get('smart_money_confirmed'):
            descriptions.append("✅ Smart Money CONFIRMADO")
        else:
            descriptions.append("❌ Smart Money no confirmado")
        
        if criteria_details.get('no_recent_losses'):
            descriptions.append("✅ Sin pérdidas recientes")
        else:
            descriptions.append("❌ Tiene pérdidas recientes")
        
        return descriptions
