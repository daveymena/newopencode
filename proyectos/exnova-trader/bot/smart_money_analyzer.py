"""
Smart Money Analyzer - Sistema básico para análisis Smart Money
"""
import pandas as pd
from typing import Dict, List
from datetime import datetime

from strategies.fvg_analyzer import FVGAnalyzer

class SmartMoneyAnalyzer:
    """Analizador avanzado de conceptos Smart Money con FVG y Estructura"""
    
    def __init__(self):
        self.min_candles = 50
        self.fvg_analyzer = FVGAnalyzer(min_gap_pct=0.005, min_body_ratio=1.3)
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """Método principal de análisis compatible con el bot"""
        return self.analyze_smart_money_structure(df)
        
    def analyze_smart_money_structure(self, candles: pd.DataFrame) -> Dict:
        """Análisis completo de estructura Smart Money e Imbalances"""
        if len(candles) < self.min_candles:
            return self._no_analysis("Insuficientes velas")
        
        try:
            # 1. Analizar FVGs (Fair Value Gaps)
            fvgs = self.fvg_analyzer.find_fvgs(candles)
            latest_fvg = self.fvg_analyzer.get_latest_fvg(candles)
            
            # 2. Determinar Bias y Tendencia
            recent_trend = self._get_simple_trend(candles)
            current_price = candles.iloc[-1]['close']
            
            # 3. Evaluar Proximidad a FVG
            fvg_hit = False
            fvg_type = None
            if latest_fvg:
                # Si el precio entró al gap
                if latest_fvg['bottom'] <= current_price <= latest_fvg['top']:
                    fvg_hit = True
                    fvg_type = latest_fvg['type']
            
            # 4. Generar señal basada en FVG + Tendencia (La estrategia del video)
            entry_signal = {
                'should_enter': False,
                'direction': None,
                'confidence': 50,
                'entry_reasons': [],
                'risk_factors': [],
                'is_valid': False
            }
            
            # Lógica: FVG Alcista + Precio en zona = CALL
            if fvg_hit and fvg_type == 'bullish' and recent_trend != 'bearish':
                entry_signal.update({
                    'should_enter': True,
                    'direction': 'CALL',
                    'confidence': 75,
                    'entry_reasons': ['Precio mitigando Bullish FVG', 'Alineación con tendencia'],
                    'is_valid': True
                })
            
            # Lógica: FVG Bajista + Precio en zona = PUT
            elif fvg_hit and fvg_type == 'bearish' and recent_trend != 'bullish':
                entry_signal.update({
                    'should_enter': True,
                    'direction': 'PUT',
                    'confidence': 75,
                    'entry_reasons': ['Precio mitigando Bearish FVG', 'Alineación con tendencia'],
                    'is_valid': True
                })
            
            return {
                'timestamp': datetime.now().isoformat(),
                'order_blocks': [], # TODO: Implementar Order Blocks más adelante
                'fair_value_gaps': fvgs,
                'latest_fvg': latest_fvg,
                'fvg_detected': latest_fvg is not None,
                'fvg_hit': fvg_hit,
                'liquidity_zones': [],
                'market_structure': {'trend': recent_trend, 'bos': None, 'choch': None, 'strength': 60},
                'inducement_signals': [],
                'mitigation_analysis': {
                    'mitigated_fvgs': [f for f in fvgs['bullish'] + fvgs['bearish'] if f['is_mitigated']],
                    'pending_fvg': latest_fvg if not latest_fvg or not latest_fvg['is_mitigated'] else None
                },
                'directional_bias': {'bias': recent_trend, 'confidence': 65, 'confidence_factors': [f'Tendencia {recent_trend}']},
                'entry_signal': entry_signal,
                'confidence': entry_signal['confidence'] if entry_signal['should_enter'] else 50,
                'is_valid': entry_signal['is_valid'],
                'order_block_hit': False, # Placeholder para UnifiedScoringEngine
                'liquidity_grab': False,
                'premium_discount': 0.5
            }
            
        except Exception as e:
            import traceback
            print(f"Error en SmartMoneyAnalyzer: {e}")
            traceback.print_exc()
            return self._no_analysis(f"Error: {str(e)}")
    
    def _get_simple_trend(self, candles: pd.DataFrame) -> str:
        """Determina tendencia simple"""
        if len(candles) < 20:
            return 'neutral'
        
        recent = candles.tail(20)
        first_price = recent.iloc[0]['close']
        last_price = recent.iloc[-1]['close']
        
        change_pct = ((last_price - first_price) / first_price) * 100
        
        if change_pct > 0.1:
            return 'bullish'
        elif change_pct < -0.1:
            return 'bearish'
        else:
            return 'neutral'
    
    def _no_analysis(self, reason: str) -> Dict:
        """Retorna análisis vacío"""
        return {
            'timestamp': datetime.now().isoformat(),
            'order_blocks': [],
            'fair_value_gaps': [],
            'liquidity_zones': [],
            'market_structure': {'trend': 'neutral', 'bos': None, 'choch': None, 'strength': 0},
            'inducement_signals': [],
            'mitigation_analysis': {'mitigated_blocks': [], 'pending_mitigation': [], 'fresh_blocks': []},
            'directional_bias': {'bias': 'neutral', 'confidence': 0, 'confidence_factors': []},
            'entry_signal': {
                'should_enter': False,
                'direction': None,
                'confidence': 0,
                'entry_reasons': [],
                'risk_factors': [reason],
                'is_valid': False
            },
            'confidence': 0,
            'is_valid': False,
            'error': reason
        }