"""
Filtro de Smart Money Concepts
Integra análisis de liquidez con las decisiones del bot
"""
import pandas as pd
from typing import Dict, Tuple, Optional
from .liquidity_zones import LiquidityAnalyzer, analyze_liquidity_for_trade
from .fvg_analyzer import FVGAnalyzer

class SmartMoneyFilter:
    """
    Filtro que previene operaciones en zonas peligrosas
    Basado en Smart Money Concepts (SMC)
    """
    
    def __init__(self, 
                 enable_liquidity_filter: bool = True,
                 min_zone_strength: float = 60,
                 max_test_count: int = 2,
                 min_distance_to_fresh_zone: float = 0.3):  # 0.3%
        """
        Args:
            enable_liquidity_filter: Activar filtro de liquidez
            min_zone_strength: Fuerza mínima de zona para considerar
            max_test_count: Máximo de tests antes de rechazar zona
            min_distance_to_fresh_zone: Distancia máxima a zona fresca (%)
        """
        self.enable_liquidity_filter = enable_liquidity_filter
        self.min_zone_strength = min_zone_strength
        self.max_test_count = max_test_count
        self.min_distance_to_fresh_zone = min_distance_to_fresh_zone
        
        self.analyzer = LiquidityAnalyzer(
            min_zone_strength=min_zone_strength,
            max_test_count=max_test_count
        )
        self.fvg_analyzer = FVGAnalyzer(min_gap_pct=0.005)
        
        self.last_analysis = None
    
    def should_trade(self, df: pd.DataFrame, direction: str, verbose: bool = False) -> Tuple[bool, Dict]:
        """
        Determina si se debe ejecutar una operación
        
        Args:
            df: DataFrame con datos OHLCV
            direction: 'call' o 'put'
            verbose: Imprimir análisis
            
        Returns:
            (should_trade, analysis_dict)
        """
        if not self.enable_liquidity_filter:
            return True, {'reason': 'Filtro desactivado'}
        
        # Analizar liquidez
        result = analyze_liquidity_for_trade(df, direction, verbose=verbose)
        
        # Analizar FVG (Fair Value Gap)
        fvg_signal = self.fvg_analyzer.analyze_signal(df, direction)
        result['fvg_analysis'] = fvg_signal
        
        self.last_analysis = result
        
        should_trade = result['should_trade']
        
        # Refinar con FVG: Si hay un FVG mitigándose, es una señal muy fuerte
        if fvg_signal['should_trade']:
            should_trade = True # Forzar entrada si la estrategia FVG lo dice
            result['reasons'].append(f"FVG Confirmado: {fvg_signal['reason']}")
            result['confidence'] = min(100, result['confidence'] + 20)
        
        # Verificaciones adicionales
        if should_trade:
            # Verificar dirección vs zona
            next_zone = result['analysis']['next_valid_zone']
            if next_zone:
                zone_type = next_zone['zone'].type.value
                
                # Si vamos a comprar (call) pero estamos cerca de resistencia, rechazar (a menos que haya FVG fuerte)
                if direction == 'call' and 'resistance' in zone_type.lower():
                    if next_zone['distance_pct'] < 0.2 and not fvg_signal['should_trade']:
                        should_trade = False
                        result['reasons'].append("Demasiado cerca de resistencia para CALL")
                
                # Si vamos a vender (put) pero estamos cerca de soporte, rechazar
                elif direction == 'put' and 'support' in zone_type.lower():
                    if next_zone['distance_pct'] < 0.2 and not fvg_signal['should_trade']:
                        should_trade = False
                        result['reasons'].append("Demasiado cerca de soporte para PUT")
        
        return should_trade, result
    
    def get_optimal_entry_price(self, df: pd.DataFrame, direction: str) -> float:
        """
        Calcula el precio óptimo de entrada basado en zonas frescas
        
        Args:
            df: DataFrame con datos
            direction: 'call' o 'put'
            
        Returns:
            Precio óptimo de entrada
        """
        analysis = self.analyzer.analyze(df)
        current_price = df['close'].iloc[-1]
        
        fresh_zones = analysis['fresh_zones']
        if not fresh_zones:
            return current_price
        
        # Filtrar zonas según dirección
        if direction == 'call':
            # Para CALL, buscar soportes frescos debajo del precio
            support_zones = [z for z in fresh_zones 
                           if 'support' in z.type.value.lower() 
                           and z.price_mid < current_price]
            if support_zones:
                # Zona más cercana debajo
                optimal_zone = max(support_zones, key=lambda z: z.price_mid)
                return optimal_zone.price_mid
        
        else:  # PUT
            # Para PUT, buscar resistencias frescas arriba del precio
            resistance_zones = [z for z in fresh_zones 
                              if 'resistance' in z.type.value.lower() 
                              and z.price_mid > current_price]
            if resistance_zones:
                # Zona más cercana arriba
                optimal_zone = min(resistance_zones, key=lambda z: z.price_mid)
                return optimal_zone.price_mid
        
        return current_price
    
    def wait_for_fresh_zone(self, df: pd.DataFrame) -> Dict:
        """
        Determina si debemos esperar a que el precio llegue a una zona fresca
        
        Returns:
            Dict con información de espera
        """
        analysis = self.analyzer.analyze(df)
        current_price = df['close'].iloc[-1]
        
        next_zone = analysis['next_valid_zone']
        
        if not next_zone:
            return {
                'should_wait': True,
                'reason': 'No hay zonas frescas identificadas',
                'wait_time_estimate': 'Indefinido'
            }
        
        distance_pct = next_zone['distance_pct']
        
        if distance_pct > self.min_distance_to_fresh_zone:
            # Estimar tiempo de espera basado en volatilidad
            volatility = df['close'].pct_change().std() * 100
            estimated_candles = int(distance_pct / volatility) if volatility > 0 else 999
            
            return {
                'should_wait': True,
                'reason': f'Zona fresca a {distance_pct:.2f}% de distancia',
                'target_price': next_zone['price'],
                'current_price': current_price,
                'distance_pct': distance_pct,
                'wait_time_estimate': f'{estimated_candles} velas aproximadamente',
                'zone_info': next_zone
            }
        
        return {
            'should_wait': False,
            'reason': 'Cerca de zona fresca',
            'zone_info': next_zone
        }
    
    def get_rejection_reasons(self) -> list:
        """Obtiene las razones por las que se rechazó la última operación"""
        if not self.last_analysis:
            return []
        return self.last_analysis.get('reasons', [])
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del filtro"""
        if not self.last_analysis:
            return {}
        
        analysis = self.last_analysis['analysis']
        
        return {
            'total_zones': len(analysis['zones']),
            'fresh_zones': len(analysis['fresh_zones']),
            'tested_levels': len(analysis['tested_levels']),
            'liquidity_traps': len(analysis['liquidity_traps']),
            'is_safe_to_trade': analysis['is_safe_to_trade'],
            'filter_active': self.enable_liquidity_filter
        }


def integrate_with_bot_decision(df: pd.DataFrame, 
                                rl_action: int,
                                llm_recommendation: str,
                                confidence: float,
                                verbose: bool = True) -> Dict:
    """
    Integra el análisis de liquidez con la decisión del bot
    
    Args:
        df: DataFrame con datos
        rl_action: Acción del agente RL (0=hold, 1=call, 2=put)
        llm_recommendation: Recomendación del LLM
        confidence: Confianza de la decisión original
        verbose: Imprimir análisis
        
    Returns:
        Dict con decisión final
    """
    # Convertir acción RL a dirección
    if rl_action == 1:
        direction = 'call'
    elif rl_action == 2:
        direction = 'put'
    else:
        return {
            'final_action': 'hold',
            'confidence': confidence,
            'reason': 'RL decidió no operar'
        }
    
    # Crear filtro
    smc_filter = SmartMoneyFilter()
    
    # Verificar con filtro de liquidez
    should_trade, liquidity_analysis = smc_filter.should_trade(df, direction, verbose=verbose)
    
    if not should_trade:
        if verbose:
            print("\n🚫 OPERACIÓN RECHAZADA POR FILTRO DE LIQUIDEZ")
            print("Razones:")
            for reason in liquidity_analysis['reasons']:
                print(f"   - {reason}")
        
        return {
            'final_action': 'hold',
            'original_action': direction,
            'confidence': 0,
            'reason': 'Rechazado por filtro de liquidez',
            'details': liquidity_analysis['reasons'],
            'recommendation': liquidity_analysis['recommendation']
        }
    
    # Verificar si debemos esperar
    wait_info = smc_filter.wait_for_fresh_zone(df)
    
    if wait_info['should_wait']:
        if verbose:
            print(f"\n⏳ ESPERAR: {wait_info['reason']}")
            if 'target_price' in wait_info:
                print(f"   Precio objetivo: {wait_info['target_price']:.5f}")
                print(f"   Tiempo estimado: {wait_info['wait_time_estimate']}")
        
        return {
            'final_action': 'wait',
            'original_action': direction,
            'confidence': confidence * 0.5,
            'reason': wait_info['reason'],
            'wait_info': wait_info
        }
    
    # Todo OK, ejecutar operación
    if verbose:
        print(f"\n✅ OPERACIÓN APROBADA")
        print(f"   Dirección: {direction.upper()}")
        print(f"   Confianza original: {confidence:.1f}%")
        print(f"   Confianza con liquidez: {liquidity_analysis['confidence']:.1f}%")
    
    # Combinar confianzas
    final_confidence = (confidence + liquidity_analysis['confidence']) / 2
    
    return {
        'final_action': direction,
        'original_action': direction,
        'confidence': final_confidence,
        'reason': 'Aprobado por todos los filtros',
        'liquidity_analysis': liquidity_analysis,
        'recommendation': liquidity_analysis['recommendation']
    }
