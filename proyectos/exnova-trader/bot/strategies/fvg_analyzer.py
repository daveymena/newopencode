import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

class FVGAnalyzer:
    """
    Analizador de Fair Value Gaps (FVG) para Opciones Binarias.
    Identifica desequilibrios en el mercado basados en patrones de 3 velas.
    """
    
    def __init__(self, 
                 min_gap_pct: float = 0.01,  # Tamaño mínimo del gap en %
                 min_body_ratio: float = 1.5): # La vela central debe ser x veces mayor al promedio
        self.min_gap_pct = min_gap_pct
        self.min_body_ratio = min_body_ratio

    def find_fvgs(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """
        Encuentra todos los FVGs en el DataFrame proporcionado.
        
        Returns:
            Dict con listas de FVGs alcistas y bajistas.
        """
        if len(df) < 3:
            return {'bullish': [], 'bearish': []}
            
        bullish_fvgs = []
        bearish_fvgs = []
        
        # Calcular promedio de cuerpos para filtro de intensidad
        bodies = abs(df['close'] - df['open'])
        avg_body = bodies.rolling(window=10).mean()
        
        for i in range(2, len(df)):
            v1 = df.iloc[i-2]
            v2 = df.iloc[i-1]
            v3 = df.iloc[i]
            
            # 1. Detectar FVG Alcista (V2 es alcista y fuerte)
            # Condición: High(V1) < Low(V3)
            if v1['high'] < v3['low']:
                gap_size = v3['low'] - v1['high']
                current_price = df['close'].iloc[-1]
                
                # Filtros de calidad
                body_v2 = abs(v2['close'] - v2['open'])
                if body_v2 > (avg_body.iloc[i-1] * self.min_body_ratio):
                    bullish_fvgs.append({
                        'index': i-1,
                        'top': v3['low'],
                        'bottom': v1['high'],
                        'middle': (v3['low'] + v1['high']) / 2,
                        'size': gap_size,
                        'is_mitigated': current_price < v1['high'], # Ya fue rellenado?
                        'timestamp': v2.name if hasattr(v2, 'name') else i-1
                    })
            
            # 2. Detectar FVG Bajista (V2 es bajista y fuerte)
            # Condición: Low(V1) > High(V3)
            elif v1['low'] > v3['high']:
                gap_size = v1['low'] - v3['high']
                current_price = df['close'].iloc[-1]
                
                # Filtros de calidad
                body_v2 = abs(v2['close'] - v2['open'])
                if body_v2 > (avg_body.iloc[i-1] * self.min_body_ratio):
                    bearish_fvgs.append({
                        'index': i-1,
                        'top': v1['low'],
                        'bottom': v3['high'],
                        'middle': (v1['low'] + v3['high']) / 2,
                        'size': gap_size,
                        'is_mitigated': current_price > v1['low'], # Ya fue rellenado?
                        'timestamp': v2.name if hasattr(v2, 'name') else i-1
                    })
                    
        return {
            'bullish': bullish_fvgs,
            'bearish': bearish_fvgs
        }

    def get_latest_fvg(self, df: pd.DataFrame) -> Optional[Dict]:
        """Obtiene el FVG más reciente que aún no ha sido mitigado."""
        fvgs = self.find_fvgs(df)
        all_fvgs = fvgs['bullish'] + fvgs['bearish']
        
        if not all_fvgs:
            return None
            
        # Ordenar por el más reciente (mayor índice)
        latest = sorted(all_fvgs, key=lambda x: x['index'], reverse=True)
        
        # Retornar el primero que no esté mitigado
        for fvg in latest:
            if not fvg['is_mitigated']:
                fvg['type'] = 'bullish' if fvg in fvgs['bullish'] else 'bearish'
                return fvg
                
        return None

    def analyze_signal(self, df: pd.DataFrame, direction: str) -> Dict:
        """
        Analiza si la dirección propuesta ('call'/'put') coincide con un FVG activo.
        """
        current_price = df['close'].iloc[-1]
        latest_fvg = self.get_latest_fvg(df)
        
        if not latest_fvg:
            return {'should_trade': False, 'reason': 'No active FVG found'}
            
        fvg_type = latest_fvg['type']
        
        # Caso CALL: Buscamos un FVG alcista debajo del precio actual (retroceso para comprar)
        if direction == 'call' and fvg_type == 'bullish':
            # El precio debe estar cerca o entrando al FVG
            if current_price <= latest_fvg['top'] and current_price >= latest_fvg['bottom']:
                return {
                    'should_trade': True, 
                    'reason': 'Price inside Bullish FVG (Buying imbalance)',
                    'fvg': latest_fvg
                }
            elif current_price > latest_fvg['top']:
                dist = (current_price - latest_fvg['top']) / current_price * 100
                return {
                    'should_trade': False, 
                    'reason': f'Waiting for pullback to Bullish FVG ({dist:.3f}% away)',
                    'fvg': latest_fvg
                }
                
        # Caso PUT: Buscamos un FVG bajista arriba del precio actual (retroceso para vender)
        if direction == 'put' and fvg_type == 'bearish':
            if current_price >= latest_fvg['bottom'] and current_price <= latest_fvg['top']:
                return {
                    'should_trade': True, 
                    'reason': 'Price inside Bearish FVG (Selling imbalance)',
                    'fvg': latest_fvg
                }
            elif current_price < latest_fvg['bottom']:
                dist = (latest_fvg['bottom'] - current_price) / current_price * 100
                return {
                    'should_trade': False, 
                    'reason': f'Waiting for pullback to Bearish FVG ({dist:.3f}% away)',
                    'fvg': latest_fvg
                }
                
        return {
            'should_trade': False, 
            'reason': f'No matching FVG for {direction.upper()} (Found {fvg_type} instead)'
        }
