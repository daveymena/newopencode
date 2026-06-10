"""
Multi-Timeframe Analyzer - Análisis de múltiples temporalidades
Entiende el contexto completo del mercado para evitar trampas
"""
import pandas as pd
from datetime import datetime

class MultiTimeframeAnalyzer:
    def __init__(self, market_data):
        self.market_data = market_data
        self.timeframes = {
            'M1': 60,    # 1 minuto - Ejecución
            'M5': 300,   # 5 minutos - Estructura intermedia  
            'M15': 900,  # 15 minutos - Contexto general
            'H1': 3600   # 1 hora - Tendencia principal
        }
    
    def analyze_all_timeframes(self, asset):
        context = {
            'timestamp': datetime.now().isoformat(),
            'asset': asset,
            'timeframes': {},
            'confluence': {},
            'recommendation': {}
        }
        
        for tf_name, tf_seconds in self.timeframes.items():
            try:
                df = self.market_data.get_candles(asset, tf_seconds, 100)
                if df is not None and len(df) >= 50:
                    analysis = self._analyze_timeframe(df, tf_name)
                    context['timeframes'][tf_name] = analysis
            except Exception as e:
                print(f"Error analizando {tf_name}: {e}")
        
        context['confluence'] = self._check_confluence(context['timeframes'])
        context['recommendation'] = self._generate_recommendation(context['confluence'])
        
        return context
    
    def _analyze_timeframe(self, df, tf_name):
        last = df.iloc[-1]
        
        trend = self._get_trend(df)
        rsi = last.get('rsi', 50)
        
        return {
            'trend': trend,
            'rsi': rsi,
            'price': last['close'],
            'strength': self._calculate_strength(df)
        }
    
    def _get_trend(self, df):
        if len(df) < 20:
            return 'neutral'
        
        sma_20 = df['close'].rolling(20).mean().iloc[-1]
        sma_50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma_20
        price = df.iloc[-1]['close']
        
        if sma_20 > sma_50 and price > sma_20:
            return 'uptrend'
        elif sma_20 < sma_50 and price < sma_20:
            return 'downtrend'
        return 'neutral'
    
    def _calculate_strength(self, df):
        if len(df) < 20:
            return 0
        
        price_change = ((df.iloc[-1]['close'] - df.iloc[-20]['close']) / df.iloc[-20]['close']) * 100
        return abs(price_change)
    
    def _check_confluence(self, timeframes):
        if not timeframes:
            return {'aligned': False, 'score': 0}
        
        trends = [tf['trend'] for tf in timeframes.values()]
        
        uptrend_count = trends.count('uptrend')
        downtrend_count = trends.count('downtrend')
        
        total = len(trends)
        
        if uptrend_count >= total * 0.75:
            return {'aligned': True, 'direction': 'CALL', 'score': (uptrend_count / total) * 100}
        elif downtrend_count >= total * 0.75:
            return {'aligned': True, 'direction': 'PUT', 'score': (downtrend_count / total) * 100}
        
        return {'aligned': False, 'score': 0, 'reason': 'Temporalidades no alineadas'}
    
    def _generate_recommendation(self, confluence):
        if confluence['aligned']:
            return {
                'should_trade': True,
                'direction': confluence['direction'],
                'confidence': confluence['score'],
                'reason': f"Confluencia de {confluence['score']:.0f}% en múltiples temporalidades"
            }
        
        return {
            'should_trade': False,
            'reason': confluence.get('reason', 'Sin confluencia clara')
        }
