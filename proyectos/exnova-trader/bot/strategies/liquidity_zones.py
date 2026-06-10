"""
Análisis de Zonas de Liquidez y Niveles Testeados
Detecta niveles que ya fueron liquidados/testeados para evitar trampas
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class ZoneStatus(Enum):
    """Estado de una zona de precio"""
    FRESH = "fresh"  # Zona fresca, no testeada
    TESTED = "tested"  # Zona testeada 1 vez
    WEAK = "weak"  # Zona testeada 2+ veces
    BROKEN = "broken"  # Zona rota/liquidada
    INVALID = "invalid"  # Zona inválida

class ZoneType(Enum):
    """Tipo de zona"""
    SUPPORT = "support"
    RESISTANCE = "resistance"
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fvg"
    LIQUIDITY_POOL = "liquidity_pool"

@dataclass
class LiquidityZone:
    """Zona de liquidez identificada"""
    type: ZoneType
    price_high: float
    price_low: float
    created_at: datetime
    volume: float
    strength: float  # 0-100
    status: ZoneStatus
    test_count: int = 0
    last_tested: Optional[datetime] = None
    broken_at: Optional[datetime] = None
    
    @property
    def price_mid(self) -> float:
        return (self.price_high + self.price_low) / 2
    
    @property
    def is_valid(self) -> bool:
        """Zona válida para operar"""
        return self.status in [ZoneStatus.FRESH, ZoneStatus.TESTED]
    
    @property
    def is_fresh(self) -> bool:
        """Zona fresca (nunca testeada)"""
        return self.status == ZoneStatus.FRESH

class LiquidityAnalyzer:
    """
    Analizador de zonas de liquidez y niveles testeados
    """
    
    def __init__(self, 
                 lookback_periods: int = 100,
                 zone_threshold: float = 0.0005,  # 0.05% para considerar mismo nivel
                 min_zone_strength: float = 60,
                 max_test_count: int = 2):
        """
        Args:
            lookback_periods: Períodos históricos a analizar
            zone_threshold: Umbral para considerar mismo nivel de precio
            min_zone_strength: Fuerza mínima para considerar zona válida
            max_test_count: Máximo de tests antes de considerar zona débil
        """
        self.lookback_periods = lookback_periods
        self.zone_threshold = zone_threshold
        self.min_zone_strength = min_zone_strength
        self.max_test_count = max_test_count
        self.zones: List[LiquidityZone] = []
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Analiza el mercado y detecta zonas de liquidez
        
        Args:
            df: DataFrame con OHLCV
            
        Returns:
            Dict con análisis completo
        """
        # 1. Identificar zonas de liquidez
        self._identify_zones(df)
        
        # 2. Actualizar estado de zonas
        self._update_zone_status(df)
        
        # 3. Detectar niveles testeados
        tested_levels = self._detect_tested_levels(df)
        
        # 4. Identificar trampas de liquidez
        liquidity_traps = self._detect_liquidity_traps(df)
        
        # 5. Encontrar zonas frescas (mejores para operar)
        fresh_zones = self._get_fresh_zones()
        
        # 6. Calcular precio actual
        current_price = df['close'].iloc[-1]
        
        # 7. Encontrar próxima zona válida
        next_valid_zone = self._find_next_valid_zone(current_price)
        
        # 8. Determinar si es seguro operar
        is_safe_to_trade = self._is_safe_to_trade(current_price)
        
        return {
            'zones': self.zones,
            'fresh_zones': fresh_zones,
            'tested_levels': tested_levels,
            'liquidity_traps': liquidity_traps,
            'next_valid_zone': next_valid_zone,
            'is_safe_to_trade': is_safe_to_trade,
            'current_price': current_price,
            'recommendation': self._generate_recommendation(
                current_price, 
                next_valid_zone, 
                is_safe_to_trade
            )
        }
    
    def _identify_zones(self, df: pd.DataFrame):
        """Identifica zonas de liquidez en el gráfico"""
        self.zones = []
        
        # 1. Order Blocks (bloques de órdenes)
        order_blocks = self._find_order_blocks(df)
        self.zones.extend(order_blocks)
        
        # 2. Fair Value Gaps (huecos de valor justo)
        fvgs = self._find_fair_value_gaps(df)
        self.zones.extend(fvgs)
        
        # 3. Liquidity Pools (pools de liquidez)
        liquidity_pools = self._find_liquidity_pools(df)
        self.zones.extend(liquidity_pools)
        
        # 4. Support/Resistance tradicionales
        sr_zones = self._find_support_resistance(df)
        self.zones.extend(sr_zones)
    
    def _find_order_blocks(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Encuentra Order Blocks (bloques de órdenes institucionales)
        Un OB es la última vela antes de un movimiento fuerte
        """
        zones = []
        
        for i in range(2, len(df) - 1):
            # Bullish Order Block (antes de subida)
            if (df['close'].iloc[i] > df['close'].iloc[i-1] and
                df['close'].iloc[i+1] > df['close'].iloc[i] * 1.002):  # 0.2% subida
                
                zone = LiquidityZone(
                    type=ZoneType.ORDER_BLOCK,
                    price_high=df['high'].iloc[i-1],
                    price_low=df['low'].iloc[i-1],
                    created_at=df.index[i-1],
                    volume=df['volume'].iloc[i-1] if 'volume' in df else 0,
                    strength=self._calculate_zone_strength(df, i-1, 'bullish'),
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
            
            # Bearish Order Block (antes de bajada)
            elif (df['close'].iloc[i] < df['close'].iloc[i-1] and
                  df['close'].iloc[i+1] < df['close'].iloc[i] * 0.998):  # 0.2% bajada
                
                zone = LiquidityZone(
                    type=ZoneType.ORDER_BLOCK,
                    price_high=df['high'].iloc[i-1],
                    price_low=df['low'].iloc[i-1],
                    created_at=df.index[i-1],
                    volume=df['volume'].iloc[i-1] if 'volume' in df else 0,
                    strength=self._calculate_zone_strength(df, i-1, 'bearish'),
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
        
        return zones
    
    def _find_fair_value_gaps(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Encuentra Fair Value Gaps (huecos de valor justo)
        Un FVG es un hueco en el precio que el mercado tiende a rellenar
        """
        zones = []
        
        for i in range(1, len(df) - 1):
            # Bullish FVG (hueco alcista)
            if df['low'].iloc[i+1] > df['high'].iloc[i-1]:
                zone = LiquidityZone(
                    type=ZoneType.FAIR_VALUE_GAP,
                    price_high=df['low'].iloc[i+1],
                    price_low=df['high'].iloc[i-1],
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=70,  # FVGs son generalmente fuertes
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
            
            # Bearish FVG (hueco bajista)
            elif df['high'].iloc[i+1] < df['low'].iloc[i-1]:
                zone = LiquidityZone(
                    type=ZoneType.FAIR_VALUE_GAP,
                    price_high=df['low'].iloc[i-1],
                    price_low=df['high'].iloc[i+1],
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=70,
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
        
        return zones
    
    def _find_liquidity_pools(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Encuentra Liquidity Pools (acumulación de stops)
        Niveles donde hay muchos stops de traders retail
        """
        zones = []
        
        # Buscar swing highs/lows (donde suelen estar los stops)
        for i in range(5, len(df) - 5):
            # Swing High (resistencia con stops arriba)
            if (df['high'].iloc[i] == df['high'].iloc[i-5:i+5].max()):
                zone = LiquidityZone(
                    type=ZoneType.LIQUIDITY_POOL,
                    price_high=df['high'].iloc[i] * 1.001,  # Stops justo arriba
                    price_low=df['high'].iloc[i],
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=80,  # Pools de liquidez son muy fuertes
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
            
            # Swing Low (soporte con stops abajo)
            elif (df['low'].iloc[i] == df['low'].iloc[i-5:i+5].min()):
                zone = LiquidityZone(
                    type=ZoneType.LIQUIDITY_POOL,
                    price_high=df['low'].iloc[i],
                    price_low=df['low'].iloc[i] * 0.999,  # Stops justo abajo
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=80,
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
        
        return zones
    
    def _find_support_resistance(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """Encuentra niveles de soporte y resistencia tradicionales"""
        zones = []
        
        # Usar pivots para S/R
        highs = df['high'].values
        lows = df['low'].values
        
        # Resistencias (máximos locales)
        for i in range(10, len(df) - 10):
            if highs[i] == max(highs[i-10:i+10]):
                zone = LiquidityZone(
                    type=ZoneType.RESISTANCE,
                    price_high=highs[i] * 1.0005,
                    price_low=highs[i] * 0.9995,
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=self._calculate_zone_strength(df, i, 'resistance'),
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
        
        # Soportes (mínimos locales)
        for i in range(10, len(df) - 10):
            if lows[i] == min(lows[i-10:i+10]):
                zone = LiquidityZone(
                    type=ZoneType.SUPPORT,
                    price_high=lows[i] * 1.0005,
                    price_low=lows[i] * 0.9995,
                    created_at=df.index[i],
                    volume=df['volume'].iloc[i] if 'volume' in df else 0,
                    strength=self._calculate_zone_strength(df, i, 'support'),
                    status=ZoneStatus.FRESH
                )
                zones.append(zone)
        
        return zones
    
    def _calculate_zone_strength(self, df: pd.DataFrame, idx: int, zone_type: str) -> float:
        """
        Calcula la fuerza de una zona (0-100)
        Basado en volumen, rango de vela, y contexto
        """
        strength = 50  # Base
        
        # Factor de volumen
        if 'volume' in df.columns:
            avg_volume = df['volume'].iloc[max(0, idx-20):idx].mean()
            if df['volume'].iloc[idx] > avg_volume * 1.5:
                strength += 20
            elif df['volume'].iloc[idx] > avg_volume:
                strength += 10
        
        # Factor de rango de vela
        candle_range = df['high'].iloc[idx] - df['low'].iloc[idx]
        avg_range = (df['high'] - df['low']).iloc[max(0, idx-20):idx].mean()
        if candle_range > avg_range * 1.5:
            strength += 15
        
        # Factor de tiempo (zonas más antiguas son más fuertes)
        age = len(df) - idx
        if age > 50:
            strength += 15
        elif age > 20:
            strength += 10
        
        return min(100, strength)
    
    def _update_zone_status(self, df: pd.DataFrame):
        """Actualiza el estado de todas las zonas basado en precio actual"""
        current_price = df['close'].iloc[-1]
        
        for zone in self.zones:
            # Verificar si el precio ha testeado esta zona
            if self._is_price_in_zone(current_price, zone):
                zone.test_count += 1
                zone.last_tested = df.index[-1]
                
                # Actualizar estado según número de tests
                if zone.test_count == 1:
                    zone.status = ZoneStatus.TESTED
                elif zone.test_count >= self.max_test_count:
                    zone.status = ZoneStatus.WEAK
            
            # Verificar si la zona fue rota
            if self._is_zone_broken(df, zone):
                zone.status = ZoneStatus.BROKEN
                zone.broken_at = df.index[-1]
    
    def _is_price_in_zone(self, price: float, zone: LiquidityZone) -> bool:
        """Verifica si un precio está dentro de una zona"""
        return zone.price_low <= price <= zone.price_high
    
    def _is_zone_broken(self, df: pd.DataFrame, zone: LiquidityZone) -> bool:
        """
        Verifica si una zona fue rota (precio cerró más allá con volumen)
        """
        recent_closes = df['close'].iloc[-5:]
        
        if zone.type in [ZoneType.SUPPORT, ZoneType.ORDER_BLOCK]:
            # Soporte roto si cierra debajo
            return any(recent_closes < zone.price_low * 0.999)
        else:
            # Resistencia rota si cierra arriba
            return any(recent_closes > zone.price_high * 1.001)
    
    def _detect_tested_levels(self, df: pd.DataFrame) -> List[Dict]:
        """Detecta niveles que ya fueron testeados recientemente"""
        tested = []
        
        for zone in self.zones:
            if zone.status in [ZoneStatus.TESTED, ZoneStatus.WEAK]:
                tested.append({
                    'price': zone.price_mid,
                    'type': zone.type.value,
                    'test_count': zone.test_count,
                    'last_tested': zone.last_tested,
                    'strength': zone.strength,
                    'warning': 'Nivel testeado - Evitar' if zone.test_count >= 2 else 'Nivel testeado 1 vez'
                })
        
        return tested
    
    def _detect_liquidity_traps(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detecta trampas de liquidez (fake breakouts)
        Cuando el precio rompe un nivel pero vuelve rápidamente
        """
        traps = []
        
        for i in range(len(df) - 10, len(df)):
            for zone in self.zones:
                # Trampa alcista (fake breakout arriba)
                if (df['high'].iloc[i] > zone.price_high and
                    df['close'].iloc[i] < zone.price_high):
                    traps.append({
                        'type': 'bull_trap',
                        'price': zone.price_high,
                        'detected_at': df.index[i],
                        'warning': '⚠️ Trampa alcista detectada - NO comprar'
                    })
                
                # Trampa bajista (fake breakout abajo)
                elif (df['low'].iloc[i] < zone.price_low and
                      df['close'].iloc[i] > zone.price_low):
                    traps.append({
                        'type': 'bear_trap',
                        'price': zone.price_low,
                        'detected_at': df.index[i],
                        'warning': '⚠️ Trampa bajista detectada - NO vender'
                    })
        
        return traps
    
    def _get_fresh_zones(self) -> List[LiquidityZone]:
        """Obtiene solo las zonas frescas (no testeadas)"""
        return [z for z in self.zones if z.is_fresh and z.strength >= self.min_zone_strength]
    
    def _find_next_valid_zone(self, current_price: float) -> Optional[Dict]:
        """
        Encuentra la próxima zona válida (fresca) más cercana al precio actual
        """
        valid_zones = [z for z in self.zones if z.is_valid and z.strength >= self.min_zone_strength]
        
        if not valid_zones:
            return None
        
        # Encontrar zona más cercana
        closest_zone = min(valid_zones, key=lambda z: abs(z.price_mid - current_price))
        
        distance_pct = abs(closest_zone.price_mid - current_price) / current_price * 100
        
        return {
            'zone': closest_zone,
            'price': closest_zone.price_mid,
            'distance_pct': distance_pct,
            'type': closest_zone.type.value,
            'status': closest_zone.status.value,
            'strength': closest_zone.strength,
            'direction': 'above' if closest_zone.price_mid > current_price else 'below'
        }
    
    def _is_safe_to_trade(self, current_price: float) -> bool:
        """
        Determina si es seguro operar en el precio actual
        Evita zonas testeadas y trampas
        """
        # Verificar si estamos en una zona testeada
        for zone in self.zones:
            if self._is_price_in_zone(current_price, zone):
                if zone.status in [ZoneStatus.WEAK, ZoneStatus.BROKEN]:
                    return False
                if zone.test_count >= self.max_test_count:
                    return False
        
        # Verificar si hay zonas frescas cercanas
        fresh_zones = self._get_fresh_zones()
        if not fresh_zones:
            return False
        
        # Verificar distancia a zona fresca más cercana
        closest_fresh = min(fresh_zones, key=lambda z: abs(z.price_mid - current_price))
        distance_pct = abs(closest_fresh.price_mid - current_price) / current_price * 100
        
        # Si estamos muy lejos de una zona fresca, no es seguro
        if distance_pct > 0.5:  # 0.5%
            return False
        
        return True
    
    def _generate_recommendation(self, 
                                 current_price: float, 
                                 next_zone: Optional[Dict],
                                 is_safe: bool) -> str:
        """Genera recomendación basada en el análisis"""
        if not is_safe:
            return "⛔ NO OPERAR - Precio en zona testeada o sin zonas frescas cercanas"
        
        if not next_zone:
            return "⚠️ ESPERAR - No hay zonas válidas identificadas"
        
        if next_zone['distance_pct'] < 0.1:  # Muy cerca
            if next_zone['zone'].type == ZoneType.SUPPORT:
                return f"✅ COMPRAR - Cerca de soporte fresco en {next_zone['price']:.5f}"
            else:
                return f"✅ VENDER - Cerca de resistencia fresca en {next_zone['price']:.5f}"
        
        elif next_zone['distance_pct'] < 0.3:  # Distancia razonable
            return f"⏳ ESPERAR - Acercándose a zona fresca en {next_zone['price']:.5f} ({next_zone['distance_pct']:.2f}%)"
        
        else:
            return f"⏳ ESPERAR - Zona fresca lejana en {next_zone['price']:.5f} ({next_zone['distance_pct']:.2f}%)"


def analyze_liquidity_for_trade(df: pd.DataFrame, 
                                 direction: str,
                                 verbose: bool = True) -> Dict:
    """
    Función helper para analizar liquidez antes de una operación
    
    Args:
        df: DataFrame con datos OHLCV
        direction: 'call' o 'put'
        verbose: Imprimir análisis detallado
        
    Returns:
        Dict con análisis y recomendación
    """
    analyzer = LiquidityAnalyzer()
    analysis = analyzer.analyze(df)
    
    current_price = analysis['current_price']
    is_safe = analysis['is_safe_to_trade']
    recommendation = analysis['recommendation']
    
    if verbose:
        print("\n" + "="*60)
        print("📊 ANÁLISIS DE LIQUIDEZ Y ZONAS TESTEADAS")
        print("="*60)
        print(f"\n💰 Precio Actual: {current_price:.5f}")
        print(f"🎯 Dirección Propuesta: {direction.upper()}")
        print(f"\n{'✅' if is_safe else '⛔'} Seguro para Operar: {'SÍ' if is_safe else 'NO'}")
        print(f"\n📋 Recomendación: {recommendation}")
        
        # Zonas frescas
        fresh_zones = analysis['fresh_zones']
        print(f"\n🆕 Zonas Frescas Encontradas: {len(fresh_zones)}")
        for i, zone in enumerate(fresh_zones[:5], 1):
            print(f"   {i}. {zone.type.value.upper()} en {zone.price_mid:.5f} "
                  f"(Fuerza: {zone.strength:.0f})")
        
        # Niveles testeados
        tested = analysis['tested_levels']
        if tested:
            print(f"\n⚠️  Niveles Testeados (EVITAR): {len(tested)}")
            for level in tested[:3]:
                print(f"   - {level['price']:.5f} ({level['type']}) "
                      f"- Testeado {level['test_count']} veces")
        
        # Trampas detectadas
        traps = analysis['liquidity_traps']
        if traps:
            print(f"\n🚨 Trampas de Liquidez Detectadas: {len(traps)}")
            for trap in traps[:3]:
                print(f"   - {trap['warning']}")
        
        # Próxima zona válida
        next_zone = analysis['next_valid_zone']
        if next_zone:
            print(f"\n🎯 Próxima Zona Válida:")
            print(f"   Precio: {next_zone['price']:.5f}")
            print(f"   Tipo: {next_zone['type']}")
            print(f"   Distancia: {next_zone['distance_pct']:.2f}%")
            print(f"   Fuerza: {next_zone['strength']:.0f}/100")
        
        print("\n" + "="*60)
    
    return {
        'should_trade': is_safe,
        'confidence': 85 if is_safe else 15,
        'recommendation': recommendation,
        'analysis': analysis,
        'reasons': _generate_reasons(analysis, direction)
    }


def _generate_reasons(analysis: Dict, direction: str) -> List[str]:
    """Genera razones para la decisión"""
    reasons = []
    
    if not analysis['is_safe_to_trade']:
        reasons.append("Precio en zona testeada o débil")
    
    if not analysis['fresh_zones']:
        reasons.append("No hay zonas frescas disponibles")
    
    if analysis['liquidity_traps']:
        reasons.append(f"Detectadas {len(analysis['liquidity_traps'])} trampas de liquidez")
    
    if analysis['tested_levels']:
        reasons.append(f"{len(analysis['tested_levels'])} niveles ya testeados")
    
    next_zone = analysis['next_valid_zone']
    if next_zone and next_zone['distance_pct'] > 0.5:
        reasons.append(f"Zona fresca lejana ({next_zone['distance_pct']:.2f}%)")
    
    if not reasons:
        reasons.append("Condiciones óptimas para operar")
        reasons.append("Zona fresca cercana")
        reasons.append("Sin niveles testeados en el camino")
    
    return reasons
