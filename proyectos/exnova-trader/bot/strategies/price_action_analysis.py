"""
Price Action Analysis - Análisis avanzado de acción del precio
Detecta Equal Highs/Lows, zonas de liquidez, rupturas de estructura
"""
import pandas as pd
import numpy as np

class PriceActionAnalysis:
    """
    Analiza patrones de price action avanzados:
    - Equal Highs/Lows (EQH/EQL)
    - Zonas de liquidez
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Failure to break (debilidad)
    """
    
    def __init__(self, tolerance=0.0002):
        """
        Args:
            tolerance: Tolerancia para considerar highs/lows iguales (0.02% por defecto)
        """
        self.tolerance = tolerance
        
    def analyze(self, df):
        """
        Análisis completo de price action
        
        Returns:
            dict con análisis completo
        """
        if df.empty or len(df) < 20:
            return None
        
        analysis = {
            'equal_highs': self.detect_equal_highs(df),
            'equal_lows': self.detect_equal_lows(df),
            'liquidity_zones': self.detect_liquidity_zones(df),
            'structure_break': self.detect_structure_break(df),
            'weakness': self.detect_weakness(df),
            'recommendation': None,
            'confidence': 0,
            'reasons': []
        }
        
        # Generar recomendación basada en price action
        analysis = self._generate_recommendation(analysis, df)
        
        return analysis
    
    def detect_equal_highs(self, df, lookback=10):
        """
        Detecta Equal Highs (EQH) - Máximos iguales
        Indica posible zona de liquidez para romper al alza
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        highs = recent['high'].values
        
        # Buscar dos o más highs similares
        equal_highs = []
        for i in range(len(highs) - 1):
            for j in range(i + 1, len(highs)):
                diff_pct = abs(highs[i] - highs[j]) / highs[i]
                if diff_pct <= self.tolerance:
                    equal_highs.append({
                        'level': (highs[i] + highs[j]) / 2,
                        'count': 2,
                        'strength': 'medium'
                    })
        
        if equal_highs:
            # Agrupar niveles similares
            level = np.mean([eq['level'] for eq in equal_highs])
            count = len(equal_highs) + 1
            
            return {
                'detected': True,
                'level': level,
                'count': count,
                'strength': 'strong' if count >= 3 else 'medium',
                'current_price': df.iloc[-1]['close'],
                'distance': level - df.iloc[-1]['close'],
                'distance_pct': ((level - df.iloc[-1]['close']) / df.iloc[-1]['close']) * 100
            }
        
        return None
    
    def detect_equal_lows(self, df, lookback=10):
        """
        Detecta Equal Lows (EQL) - Mínimos iguales
        Indica posible zona de liquidez para romper a la baja
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        lows = recent['low'].values
        
        # Buscar dos o más lows similares
        equal_lows = []
        for i in range(len(lows) - 1):
            for j in range(i + 1, len(lows)):
                diff_pct = abs(lows[i] - lows[j]) / lows[i]
                if diff_pct <= self.tolerance:
                    equal_lows.append({
                        'level': (lows[i] + lows[j]) / 2,
                        'count': 2,
                        'strength': 'medium'
                    })
        
        if equal_lows:
            # Agrupar niveles similares
            level = np.mean([eq['level'] for eq in equal_lows])
            count = len(equal_lows) + 1
            
            return {
                'detected': True,
                'level': level,
                'count': count,
                'strength': 'strong' if count >= 3 else 'medium',
                'current_price': df.iloc[-1]['close'],
                'distance': df.iloc[-1]['close'] - level,
                'distance_pct': ((df.iloc[-1]['close'] - level) / df.iloc[-1]['close']) * 100
            }
        
        return None
    
    def detect_liquidity_zones(self, df, lookback=20):
        """
        Detecta zonas de liquidez (donde hay stops acumulados)
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        
        # Zonas de liquidez típicas:
        # 1. Por encima de máximos recientes (stops de shorts)
        # 2. Por debajo de mínimos recientes (stops de longs)
        
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        current_price = df.iloc[-1]['close']
        
        zones = []
        
        # Zona de liquidez superior
        if current_price < recent_high:
            zones.append({
                'type': 'buy_side',  # Liquidez de compra (stops de shorts)
                'level': recent_high,
                'distance': recent_high - current_price,
                'distance_pct': ((recent_high - current_price) / current_price) * 100,
                'likely_direction': 'up'  # Precio tiende a buscar esta liquidez
            })
        
        # Zona de liquidez inferior
        if current_price > recent_low:
            zones.append({
                'type': 'sell_side',  # Liquidez de venta (stops de longs)
                'level': recent_low,
                'distance': current_price - recent_low,
                'distance_pct': ((current_price - recent_low) / current_price) * 100,
                'likely_direction': 'down'  # Precio tiende a buscar esta liquidez
            })
        
        return zones if zones else None
    
    def detect_structure_break(self, df, lookback=15):
        """
        Detecta Break of Structure (BOS) - Ruptura de estructura
        Indica cambio de tendencia o continuación fuerte
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        
        # Identificar swing highs y lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(recent) - 2):
            # Swing high: high mayor que 2 velas antes y después
            if (recent.iloc[i]['high'] > recent.iloc[i-1]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i-2]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i+1]['high'] and
                recent.iloc[i]['high'] > recent.iloc[i+2]['high']):
                swing_highs.append(recent.iloc[i]['high'])
            
            # Swing low: low menor que 2 velas antes y después
            if (recent.iloc[i]['low'] < recent.iloc[i-1]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i-2]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i+1]['low'] and
                recent.iloc[i]['low'] < recent.iloc[i+2]['low']):
                swing_lows.append(recent.iloc[i]['low'])
        
        current_price = df.iloc[-1]['close']
        
        # Detectar ruptura alcista (BOS bullish)
        if swing_highs and current_price > max(swing_highs):
            return {
                'detected': True,
                'type': 'bullish',
                'broken_level': max(swing_highs),
                'strength': 'strong',
                'implication': 'Continuación alcista probable'
            }
        
        # Detectar ruptura bajista (BOS bearish)
        if swing_lows and current_price < min(swing_lows):
            return {
                'detected': True,
                'type': 'bearish',
                'broken_level': min(swing_lows),
                'strength': 'strong',
                'implication': 'Continuación bajista probable'
            }
        
        return None
    
    def detect_weakness(self, df, lookback=10):
        """
        Detecta debilidad (failure to break) - Fallo al romper niveles
        Indica posible reversión
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        
        # Detectar intentos fallidos de romper máximos
        highs = recent['high'].values
        closes = recent['close'].values
        
        # Buscar patrón: precio toca máximo pero cierra por debajo
        weakness_signals = []
        
        for i in range(1, len(recent)):
            prev_high = highs[i-1]
            curr_high = highs[i]
            curr_close = closes[i]
            
            # Intento fallido de romper al alza
            if curr_high >= prev_high * 0.9999 and curr_close < prev_high * 0.999:
                weakness_signals.append({
                    'type': 'failed_breakout_up',
                    'level': prev_high,
                    'implication': 'Debilidad alcista, posible reversión a la baja'
                })
        
        # Buscar patrón: precio toca mínimo pero cierra por encima
        lows = recent['low'].values
        
        for i in range(1, len(recent)):
            prev_low = lows[i-1]
            curr_low = lows[i]
            curr_close = closes[i]
            
            # Intento fallido de romper a la baja
            if curr_low <= prev_low * 1.0001 and curr_close > prev_low * 1.001:
                weakness_signals.append({
                    'type': 'failed_breakout_down',
                    'level': prev_low,
                    'implication': 'Debilidad bajista, posible reversión al alza'
                })
        
        if weakness_signals:
            return {
                'detected': True,
                'signals': weakness_signals,
                'count': len(weakness_signals),
                'latest': weakness_signals[-1]
            }
        
        return None
    
    def _generate_recommendation(self, analysis, df):
        """
        Genera recomendación basada en price action
        """
        reasons = []
        confidence = 0
        recommendation = None
        
        current_price = df.iloc[-1]['close']
        
        # 1. Analizar Equal Highs
        if analysis['equal_highs']:
            eqh = analysis['equal_highs']
            if abs(eqh['distance_pct']) < 0.5:  # Cerca del nivel
                reasons.append(f"🎯 Equal Highs en {eqh['level']:.5f} ({eqh['count']} toques)")
                reasons.append(f"💧 Zona de liquidez superior - Precio busca romper")
                recommendation = 'CALL'
                confidence += 30
        
        # 2. Analizar Equal Lows
        if analysis['equal_lows']:
            eql = analysis['equal_lows']
            if abs(eql['distance_pct']) < 0.5:  # Cerca del nivel
                reasons.append(f"🎯 Equal Lows en {eql['level']:.5f} ({eql['count']} toques)")
                reasons.append(f"💧 Zona de liquidez inferior - Precio busca romper")
                recommendation = 'PUT'
                confidence += 30
        
        # 3. Analizar zonas de liquidez
        if analysis['liquidity_zones']:
            for zone in analysis['liquidity_zones']:
                if abs(zone['distance_pct']) < 1.0:  # Cerca de la zona
                    reasons.append(f"💧 Liquidez {zone['type']} en {zone['level']:.5f}")
                    if zone['likely_direction'] == 'up':
                        recommendation = 'CALL'
                        confidence += 20
                    else:
                        recommendation = 'PUT'
                        confidence += 20
        
        # 4. Analizar ruptura de estructura
        if analysis['structure_break']:
            bos = analysis['structure_break']
            reasons.append(f"🔥 Break of Structure {bos['type']}")
            reasons.append(f"📈 {bos['implication']}")
            if bos['type'] == 'bullish':
                recommendation = 'CALL'
                confidence += 35
            else:
                recommendation = 'PUT'
                confidence += 35
        
        # 5. Analizar debilidad
        if analysis['weakness']:
            weak = analysis['weakness']
            latest = weak['latest']
            reasons.append(f"⚠️ Debilidad detectada: {latest['type']}")
            reasons.append(f"🔄 {latest['implication']}")
            if 'failed_breakout_up' in latest['type']:
                recommendation = 'PUT'
                confidence += 25
            else:
                recommendation = 'CALL'
                confidence += 25
        
        # Normalizar confianza
        confidence = min(confidence, 100)
        
        analysis['recommendation'] = recommendation
        analysis['confidence'] = confidence / 100
        analysis['reasons'] = reasons
        
        return analysis
    
    def get_summary(self, analysis):
        """
        Genera resumen legible del análisis
        """
        if not analysis:
            return "No hay análisis de price action disponible"
        
        lines = []
        lines.append("=" * 60)
        lines.append("📊 ANÁLISIS DE PRICE ACTION")
        lines.append("=" * 60)
        
        # Equal Highs
        if analysis['equal_highs']:
            eqh = analysis['equal_highs']
            lines.append(f"\n🎯 EQUAL HIGHS DETECTADOS:")
            lines.append(f"   Nivel: {eqh['level']:.5f}")
            lines.append(f"   Toques: {eqh['count']}")
            lines.append(f"   Fuerza: {eqh['strength']}")
            lines.append(f"   Distancia: {eqh['distance_pct']:.2f}%")
        
        # Equal Lows
        if analysis['equal_lows']:
            eql = analysis['equal_lows']
            lines.append(f"\n🎯 EQUAL LOWS DETECTADOS:")
            lines.append(f"   Nivel: {eql['level']:.5f}")
            lines.append(f"   Toques: {eql['count']}")
            lines.append(f"   Fuerza: {eql['strength']}")
            lines.append(f"   Distancia: {eql['distance_pct']:.2f}%")
        
        # Zonas de liquidez
        if analysis['liquidity_zones']:
            lines.append(f"\n💧 ZONAS DE LIQUIDEZ:")
            for zone in analysis['liquidity_zones']:
                lines.append(f"   {zone['type']}: {zone['level']:.5f}")
                lines.append(f"   Dirección probable: {zone['likely_direction']}")
        
        # Ruptura de estructura
        if analysis['structure_break']:
            bos = analysis['structure_break']
            lines.append(f"\n🔥 BREAK OF STRUCTURE:")
            lines.append(f"   Tipo: {bos['type']}")
            lines.append(f"   Nivel roto: {bos['broken_level']:.5f}")
            lines.append(f"   {bos['implication']}")
        
        # Debilidad
        if analysis['weakness']:
            weak = analysis['weakness']
            lines.append(f"\n⚠️ DEBILIDAD DETECTADA:")
            lines.append(f"   Señales: {weak['count']}")
            lines.append(f"   {weak['latest']['implication']}")
        
        # Recomendación
        if analysis['recommendation']:
            lines.append(f"\n" + "=" * 60)
            lines.append(f"💡 RECOMENDACIÓN: {analysis['recommendation']}")
            lines.append(f"📊 Confianza: {analysis['confidence']*100:.0f}%")
            if analysis['reasons']:
                lines.append(f"\n📝 Razones:")
                for reason in analysis['reasons']:
                    lines.append(f"   {reason}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
