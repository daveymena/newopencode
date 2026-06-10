"""
Precision Refiner - Sistema de refinamiento continuo para máxima precisión
Aprende de cada operación y ajusta parámetros en tiempo real
"""
import json
from pathlib import Path
from datetime import datetime
import numpy as np

class PrecisionRefiner:
    """
    Sistema que refina continuamente la precisión del bot
    Objetivo: Cada operación debe ser más precisa que la anterior
    """
    
    def __init__(self):
        self.db_path = Path("data/precision_database.json")
        self.history = []
        self.precision_metrics = {
            'rsi_optimal_ranges': {
                'call': {'min': 20, 'max': 40},  # Rango más amplio
                'put': {'min': 60, 'max': 80}    # Rango más amplio
            },
            'confidence_threshold': 70,  # Reducido de 80% a 70%
            'confidence_min': 60,        # Mínimo permitido
            'confidence_max': 85,        # Máximo permitido
            'win_rate_target': 65,       # Objetivo más realista
            'current_win_rate': 0,
            'total_operations': 0,
            'successful_patterns': [],
            'failed_patterns': [],
            'adjustments_history': []
        }
        self.load_precision_data()
    
    def load_precision_data(self):
        """Carga datos de precisión guardados"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.precision_metrics = data.get('metrics', self.precision_metrics)
                    self.history = data.get('history', [])
                    print(f"📊 Precisión cargada: {self.precision_metrics['current_win_rate']:.1f}% winrate")
            except Exception as e:
                print(f"⚠️ Error cargando precisión: {e}")
    
    def save_precision_data(self):
        """Guarda datos de precisión"""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            data = {
                'metrics': self.precision_metrics,
                'history': self.history[-100:]  # Últimas 100 operaciones
            }
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error guardando precisión: {e}")
    
    def analyze_opportunity(self, opportunity_data):
        """
        Analiza una oportunidad ANTES de ejecutar
        Retorna score de precisión (0-100)
        """
        score = 0
        reasons = []
        warnings = []
        
        asset = opportunity_data.get('asset', '')
        action = opportunity_data.get('action', '').lower()
        confidence = opportunity_data.get('confidence', 0)
        rsi = opportunity_data.get('rsi', 50)
        
        # 1. VALIDAR RSI EN RANGO ÓPTIMO
        optimal_range = self.precision_metrics['rsi_optimal_ranges'].get(action, {})
        if optimal_range:
            min_rsi = optimal_range.get('min', 0)
            max_rsi = optimal_range.get('max', 100)
            
            if min_rsi <= rsi <= max_rsi:
                score += 30
                reasons.append(f"✅ RSI {rsi:.1f} en rango óptimo ({min_rsi}-{max_rsi})")
            else:
                warnings.append(f"⚠️ RSI {rsi:.1f} fuera de rango óptimo ({min_rsi}-{max_rsi})")
        
        # 2. VALIDAR CONFIANZA
        threshold = self.precision_metrics['confidence_threshold']
        if confidence >= threshold:
            score += 25
            reasons.append(f"✅ Confianza {confidence}% >= umbral {threshold}%")
        else:
            score -= 10
            warnings.append(f"⚠️ Confianza {confidence}% < umbral {threshold}%")
        
        # 3. VALIDAR CONTRA PATRONES EXITOSOS
        similar_successful = self._find_similar_patterns(opportunity_data, self.precision_metrics['successful_patterns'])
        if similar_successful:
            score += 20
            reasons.append(f"✅ Patrón similar a {len(similar_successful)} operaciones exitosas")
        
        # 4. VALIDAR CONTRA PATRONES FALLIDOS
        similar_failed = self._find_similar_patterns(opportunity_data, self.precision_metrics['failed_patterns'])
        if similar_failed:
            score -= 15
            warnings.append(f"⚠️ Patrón similar a {len(similar_failed)} operaciones fallidas")
        
        # 5. BONUS POR WIN RATE ALTO
        if self.precision_metrics['current_win_rate'] >= 65:
            score += 15
            reasons.append(f"✅ Sistema en racha positiva ({self.precision_metrics['current_win_rate']:.1f}%)")
        
        # 6. PENALIZACIÓN POR WIN RATE BAJO
        if self.precision_metrics['current_win_rate'] < 50 and self.precision_metrics['total_operations'] >= 10:
            score -= 20
            warnings.append(f"⚠️ Sistema necesita calibración ({self.precision_metrics['current_win_rate']:.1f}% winrate)")
        
        # Normalizar score (0-100)
        score = max(0, min(100, score + 50))  # Base 50 + ajustes
        
        return {
            'precision_score': score,
            'should_execute': score >= 60,  # Solo ejecutar si score >= 60
            'reasons': reasons,
            'warnings': warnings,
            'optimal_rsi_range': optimal_range
        }
    
    def learn_from_result(self, opportunity_data, result):
        """
        Aprende del resultado y ajusta parámetros para mejorar precisión
        """
        won = result.get('won', False)
        profit = result.get('profit', 0)
        
        # Actualizar métricas generales
        self.precision_metrics['total_operations'] += 1
        total = self.precision_metrics['total_operations']
        
        # Calcular win rate actual
        if won:
            wins = len([h for h in self.history if h.get('won', False)]) + 1
        else:
            wins = len([h for h in self.history if h.get('won', False)])
        
        self.precision_metrics['current_win_rate'] = (wins / total) * 100 if total > 0 else 0
        
        # Guardar en historial
        operation = {
            'timestamp': datetime.now().isoformat(),
            'asset': opportunity_data.get('asset'),
            'action': opportunity_data.get('action'),
            'rsi': opportunity_data.get('rsi'),
            'confidence': opportunity_data.get('confidence'),
            'won': won,
            'profit': profit
        }
        self.history.append(operation)
        
        # Guardar patrón
        pattern = self._extract_pattern(opportunity_data)
        if won:
            self.precision_metrics['successful_patterns'].append(pattern)
            # Limitar a últimos 50 patrones exitosos
            if len(self.precision_metrics['successful_patterns']) > 50:
                self.precision_metrics['successful_patterns'] = self.precision_metrics['successful_patterns'][-50:]
        else:
            self.precision_metrics['failed_patterns'].append(pattern)
            # Limitar a últimos 30 patrones fallidos
            if len(self.precision_metrics['failed_patterns']) > 30:
                self.precision_metrics['failed_patterns'] = self.precision_metrics['failed_patterns'][-30:]
        
        # REFINAMIENTO AUTOMÁTICO cada 3 operaciones (antes 5)
        if total % 3 == 0:
            self._auto_refine()
        
        # Guardar datos
        self.save_precision_data()
        
        return {
            'current_win_rate': self.precision_metrics['current_win_rate'],
            'total_operations': total,
            'adjustments_made': len(self.precision_metrics['adjustments_history'])
        }
    
    def _auto_refine(self):
        """
        Refinamiento automático de parámetros basado en resultados
        MEJORADO: Ajustes más agresivos y frecuentes
        """
        adjustments = []
        
        # Solo refinar si hay suficientes datos
        if len(self.history) < 10:
            return
        
        recent = self.history[-15:]  # Últimas 15 operaciones (antes 20)
        
        # 1. REFINAR RANGOS DE RSI
        for action in ['call', 'put']:
            action_ops = [op for op in recent if op.get('action', '').lower() == action]
            if len(action_ops) >= 5:
                wins = [op for op in action_ops if op.get('won', False)]
                losses = [op for op in action_ops if not op.get('won', False)]
                
                if wins:
                    # Calcular rango óptimo de RSI para operaciones ganadoras
                    win_rsis = [op.get('rsi', 50) for op in wins]
                    optimal_min = np.percentile(win_rsis, 25)
                    optimal_max = np.percentile(win_rsis, 75)
                    
                    # Ajustar rango
                    old_range = self.precision_metrics['rsi_optimal_ranges'][action].copy()
                    self.precision_metrics['rsi_optimal_ranges'][action] = {
                        'min': int(optimal_min),
                        'max': int(optimal_max)
                    }
                    
                    adjustments.append({
                        'type': 'rsi_range',
                        'action': action,
                        'old': old_range,
                        'new': self.precision_metrics['rsi_optimal_ranges'][action],
                        'reason': f'Basado en {len(wins)} operaciones ganadoras'
                    })
        
        # 2. REFINAR UMBRAL DE CONFIANZA (MÁS AGRESIVO)
        win_rate = self.precision_metrics['current_win_rate']
        old_threshold = self.precision_metrics['confidence_threshold']
        
        if win_rate < 55 and len(recent) >= 12:  # Antes: 55% y 15 ops
            # Win rate bajo → Aumentar umbral FUERTE
            new_threshold = min(
                self.precision_metrics['confidence_max'],
                old_threshold + 10  # +10% (antes +5%)
            )
            if new_threshold != old_threshold:
                self.precision_metrics['confidence_threshold'] = new_threshold
                adjustments.append({
                    'type': 'confidence_threshold',
                    'old': old_threshold,
                    'new': new_threshold,
                    'reason': f'Win rate bajo ({win_rate:.1f}%) - Aumentando selectividad FUERTE'
                })
        elif win_rate > 70 and len(recent) >= 12:  # Antes: 70% y 15 ops
            # Win rate alto → Reducir umbral FUERTE
            new_threshold = max(
                self.precision_metrics['confidence_min'],
                old_threshold - 5  # -5% (antes -3%)
            )
            if new_threshold != old_threshold:
                self.precision_metrics['confidence_threshold'] = new_threshold
                adjustments.append({
                    'type': 'confidence_threshold',
                    'old': old_threshold,
                    'new': new_threshold,
                    'reason': f'Win rate alto ({win_rate:.1f}%) - Reduciendo selectividad FUERTE'
                })
        
        # Guardar ajustes
        if adjustments:
            self.precision_metrics['adjustments_history'].extend(adjustments)
            # Limitar historial de ajustes
            if len(self.precision_metrics['adjustments_history']) > 20:
                self.precision_metrics['adjustments_history'] = self.precision_metrics['adjustments_history'][-20:]
            
            print(f"\n🔧 REFINAMIENTO AUTOMÁTICO - {len(adjustments)} ajustes realizados")
            for adj in adjustments:
                print(f"   {adj['type']}: {adj['old']} → {adj['new']}")
                print(f"   Razón: {adj['reason']}")
    
    def _extract_pattern(self, opportunity_data):
        """Extrae patrón de la oportunidad"""
        return {
            'asset': opportunity_data.get('asset'),
            'action': opportunity_data.get('action'),
            'rsi': opportunity_data.get('rsi'),
            'rsi_range': self._get_rsi_range(opportunity_data.get('rsi', 50)),
            'confidence': opportunity_data.get('confidence'),
            'setup_type': opportunity_data.get('setup_type', 'unknown')
        }
    
    def _get_rsi_range(self, rsi):
        """Clasifica RSI en rangos"""
        if rsi < 30:
            return 'oversold'
        elif rsi < 40:
            return 'low'
        elif rsi < 60:
            return 'neutral'
        elif rsi < 70:
            return 'high'
        else:
            return 'overbought'
    
    def _find_similar_patterns(self, opportunity_data, pattern_list):
        """Encuentra patrones similares en la lista"""
        similar = []
        current_pattern = self._extract_pattern(opportunity_data)
        
        for pattern in pattern_list:
            # Comparar similitud
            similarity_score = 0
            
            # Mismo activo
            if pattern.get('asset') == current_pattern.get('asset'):
                similarity_score += 1
            
            # Misma acción
            if pattern.get('action') == current_pattern.get('action'):
                similarity_score += 1
            
            # RSI en mismo rango
            if pattern.get('rsi_range') == current_pattern.get('rsi_range'):
                similarity_score += 1
            
            # Mismo setup type
            if pattern.get('setup_type') == current_pattern.get('setup_type'):
                similarity_score += 1
            
            # Si tiene 3+ coincidencias, es similar
            if similarity_score >= 3:
                similar.append(pattern)
        
        return similar
    
    def get_precision_report(self):
        """Genera reporte de precisión actual"""
        return {
            'win_rate': self.precision_metrics['current_win_rate'],
            'total_operations': self.precision_metrics['total_operations'],
            'confidence_threshold': self.precision_metrics['confidence_threshold'],
            'rsi_optimal_ranges': self.precision_metrics['rsi_optimal_ranges'],
            'successful_patterns_count': len(self.precision_metrics['successful_patterns']),
            'failed_patterns_count': len(self.precision_metrics['failed_patterns']),
            'recent_adjustments': self.precision_metrics['adjustments_history'][-5:] if self.precision_metrics['adjustments_history'] else []
        }
