"""
🛡️ FILTROS OBLIGATORIOS PARA TRADING
Basado en análisis de 14 operaciones con 78.6% win rate

REGLAS CRÍTICAS:
1. MACD debe estar alineado con la dirección
2. Tendencia (SMA20) debe estar alineada con la dirección
3. RSI debe estar en zona favorable (opcional pero recomendado)

RESULTADO ESPERADO:
- Eliminar 100% de las pérdidas por operar contra tendencia/MACD
- Mantener o mejorar win rate actual (78.6%)
"""

class MandatoryFilters:
    """
    Filtros obligatorios que DEBEN pasar antes de ejecutar cualquier operación.
    Basado en análisis de patrones de pérdidas identificados.
    """
    
    def __init__(self):
        self.filters_enabled = {
            'macd': True,      # CRÍTICO: Todas las pérdidas tenían MACD en contra
            'trend': True,     # CRÍTICO: Todas las pérdidas operaban contra tendencia
            'rsi': True        # RECOMENDADO: 100% efectividad en extremos
        }
        
        # Estadísticas de filtros
        self.stats = {
            'total_checks': 0,
            'passed': 0,
            'rejected_by_macd': 0,
            'rejected_by_trend': 0,
            'rejected_by_rsi': 0
        }
    
    def validate_trade(self, direction: str, indicators: dict, strict_mode: bool = True) -> tuple:
        """
        Valida si una operación debe ejecutarse basándose en filtros obligatorios.
        
        Args:
            direction: 'call' o 'put'
            indicators: dict con 'rsi', 'macd', 'price', 'sma_20'
            strict_mode: Si True, aplica todos los filtros. Si False, solo MACD y Tendencia
        
        Returns:
            (should_trade: bool, reason: str, warnings: list)
        """
        self.stats['total_checks'] += 1
        warnings = []
        
        # Extraer indicadores
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        price = indicators.get('price', 0)
        sma_20 = indicators.get('sma_20', price)
        
        direction_lower = direction.lower()
        
        # ========================================
        # FILTRO 1: MACD (CRÍTICO)
        # ========================================
        if self.filters_enabled['macd']:
            if direction_lower == 'call' and macd <= 0:
                self.stats['rejected_by_macd'] += 1
                return False, f"❌ MACD negativo ({macd:.6f}) para CALL - Momentum bajista", warnings
            
            if direction_lower == 'put' and macd >= 0:
                self.stats['rejected_by_macd'] += 1
                return False, f"❌ MACD positivo ({macd:.6f}) para PUT - Momentum alcista", warnings
        
        # ========================================
        # FILTRO 2: TENDENCIA (CRÍTICO)
        # ========================================
        if self.filters_enabled['trend']:
            price_vs_sma = ((price - sma_20) / sma_20) * 100  # % diferencia
            
            if direction_lower == 'call' and price < sma_20:
                self.stats['rejected_by_trend'] += 1
                return False, f"❌ Precio {price_vs_sma:.2f}% BAJO SMA20 para CALL - Contra tendencia", warnings
            
            if direction_lower == 'put' and price > sma_20:
                self.stats['rejected_by_trend'] += 1
                return False, f"❌ Precio {price_vs_sma:.2f}% SOBRE SMA20 para PUT - Contra tendencia", warnings
        
        # ========================================
        # FILTRO 3: RSI (RECOMENDADO)
        # ========================================
        if self.filters_enabled['rsi'] and strict_mode:
            # RSI extremos son MUY confiables (100% efectividad)
            # Pero no rechazamos, solo advertimos si no está en zona óptima
            
            if direction_lower == 'call':
                if rsi > 60:
                    warnings.append(f"⚠️ RSI alto ({rsi:.1f}) para CALL - Posible reversión bajista")
                elif rsi < 40:
                    warnings.append(f"✅ RSI bajo ({rsi:.1f}) para CALL - Zona óptima (100% histórico)")
            
            if direction_lower == 'put':
                if rsi < 40:
                    warnings.append(f"⚠️ RSI bajo ({rsi:.1f}) para PUT - Posible reversión alcista")
                elif rsi > 60:
                    warnings.append(f"✅ RSI alto ({rsi:.1f}) para PUT - Zona óptima (100% histórico)")
        
        # ========================================
        # TODOS LOS FILTROS PASADOS
        # ========================================
        self.stats['passed'] += 1
        
        # Construir mensaje de confirmación
        confirmations = []
        confirmations.append(f"✅ MACD alineado ({macd:.6f})")
        
        price_vs_sma = ((price - sma_20) / sma_20) * 100
        if direction_lower == 'call':
            confirmations.append(f"✅ Precio {price_vs_sma:.2f}% sobre SMA20 (a favor de tendencia)")
        else:
            confirmations.append(f"✅ Precio {price_vs_sma:.2f}% bajo SMA20 (a favor de tendencia)")
        
        if rsi < 40 and direction_lower == 'call':
            confirmations.append(f"✅ RSI {rsi:.1f} en zona óptima para CALL")
        elif rsi > 60 and direction_lower == 'put':
            confirmations.append(f"✅ RSI {rsi:.1f} en zona óptima para PUT")
        
        reason = "\n   ".join(confirmations)
        
        return True, reason, warnings
    
    def get_statistics(self) -> dict:
        """Retorna estadísticas de uso de filtros"""
        if self.stats['total_checks'] == 0:
            return {
                'total_checks': 0,
                'pass_rate': 0,
                'rejection_rate': 0,
                'macd_rejection_rate': 0,
                'trend_rejection_rate': 0,
                'rsi_rejection_rate': 0
            }
        
        total = self.stats['total_checks']
        return {
            'total_checks': total,
            'passed': self.stats['passed'],
            'pass_rate': (self.stats['passed'] / total) * 100,
            'rejection_rate': ((total - self.stats['passed']) / total) * 100,
            'macd_rejection_rate': (self.stats['rejected_by_macd'] / total) * 100,
            'trend_rejection_rate': (self.stats['rejected_by_trend'] / total) * 100,
            'rsi_rejection_rate': (self.stats['rejected_by_rsi'] / total) * 100
        }
    
    def reset_statistics(self):
        """Resetea las estadísticas"""
        self.stats = {
            'total_checks': 0,
            'passed': 0,
            'rejected_by_macd': 0,
            'rejected_by_trend': 0,
            'rejected_by_rsi': 0
        }
    
    def enable_filter(self, filter_name: str, enabled: bool = True):
        """Habilita o deshabilita un filtro específico"""
        if filter_name in self.filters_enabled:
            self.filters_enabled[filter_name] = enabled
    
    def get_filter_status(self) -> dict:
        """Retorna el estado de cada filtro"""
        return self.filters_enabled.copy()


# ========================================
# EJEMPLO DE USO
# ========================================
if __name__ == "__main__":
    filters = MandatoryFilters()
    
    # Caso 1: CALL con MACD negativo (DEBE RECHAZAR)
    print("\n=== TEST 1: CALL con MACD negativo ===")
    indicators = {
        'rsi': 45,
        'macd': -0.001,  # Negativo
        'price': 1.3150,
        'sma_20': 1.3140
    }
    should_trade, reason, warnings = filters.validate_trade('call', indicators)
    print(f"Resultado: {should_trade}")
    print(f"Razón: {reason}")
    
    # Caso 2: CALL con todo alineado (DEBE PASAR)
    print("\n=== TEST 2: CALL con todo alineado ===")
    indicators = {
        'rsi': 35,  # Bajo (óptimo para CALL)
        'macd': 0.002,  # Positivo
        'price': 1.3150,
        'sma_20': 1.3140  # Precio sobre SMA
    }
    should_trade, reason, warnings = filters.validate_trade('call', indicators)
    print(f"Resultado: {should_trade}")
    print(f"Razón: {reason}")
    if warnings:
        print("Advertencias:")
        for w in warnings:
            print(f"  {w}")
    
    # Caso 3: PUT contra tendencia (DEBE RECHAZAR)
    print("\n=== TEST 3: PUT contra tendencia ===")
    indicators = {
        'rsi': 65,
        'macd': -0.001,  # Negativo (OK para PUT)
        'price': 1.3150,
        'sma_20': 1.3140  # Precio SOBRE SMA (contra tendencia para PUT)
    }
    should_trade, reason, warnings = filters.validate_trade('put', indicators)
    print(f"Resultado: {should_trade}")
    print(f"Razón: {reason}")
    
    # Caso 4: PUT con todo alineado (DEBE PASAR)
    print("\n=== TEST 4: PUT con todo alineado ===")
    indicators = {
        'rsi': 72,  # Alto (óptimo para PUT)
        'macd': -0.002,  # Negativo
        'price': 1.3130,
        'sma_20': 1.3150  # Precio bajo SMA
    }
    should_trade, reason, warnings = filters.validate_trade('put', indicators)
    print(f"Resultado: {should_trade}")
    print(f"Razón: {reason}")
    if warnings:
        print("Advertencias:")
        for w in warnings:
            print(f"  {w}")
    
    # Mostrar estadísticas
    print("\n=== ESTADÍSTICAS ===")
    stats = filters.get_statistics()
    print(f"Total checks: {stats['total_checks']}")
    print(f"Pass rate: {stats['pass_rate']:.1f}%")
    print(f"Rejection rate: {stats['rejection_rate']:.1f}%")
    print(f"  - Por MACD: {stats['macd_rejection_rate']:.1f}%")
    print(f"  - Por Tendencia: {stats['trend_rejection_rate']:.1f}%")
