"""
Filtros Inteligentes basados en Datos Históricos (JSON)
Consulta la base de conocimientos JSON para tomar decisiones informadas
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import json
from pathlib import Path

class IntelligentFilters:
    """
    Filtros que aprenden de datos históricos (JSON) para mejorar decisiones
    """
    
    def __init__(self, db_path: str = "data/learning_database.json"):
        self.min_pattern_win_rate = 52.0  # Reducido de 58% (más realista)
        self.min_pattern_occurrences = 12    # Aumentado de 8 (más confiable)
        self.min_hourly_win_rate = 50.0    # Reducido de 55% (más realista)
        self.min_hourly_occurrences = 8    # Nuevo: Requiere más datos
        self.db_path = Path(db_path)
        self.history_cache = []
        self.last_load_time = 0
        self.load_history()
        
    def load_history(self):
        """Carga o recarga el historial JSON"""
        import time
        if time.time() - self.last_load_time < 30: # Cache por 30s
            return
            
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history_cache = data.get('operations', [])
                self.last_load_time = time.time()
            except Exception as e:
                print(f"⚠️ Error cargando cache de filtros: {e}")
                self.history_cache = []
        else:
            self.history_cache = []

    def _get_matches(self, asset=None, days=30):
        """Filtra operaciones relevantes de la cache"""
        self.load_history() # Asegurar datos frescos
        matches = []
        limit_date = datetime.now() - timedelta(days=days)
        
        for op in self.history_cache:
            # Filtro fecha
            try:
                op_date = datetime.fromisoformat(op.get('timestamp', ''))
                if op_date < limit_date: continue
            except: continue
            
            # Filtro activo
            if asset and op.get('asset') != asset:
                continue
                
            matches.append(op)
        return matches
        
    def should_trade(self, asset: str, pattern_type: Optional[str] = None, 
                    current_conditions: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Decide si se debe operar basándose en datos históricos
        
        Returns:
            (should_trade, reason)
        """
        
        # 1. Verificar rendimiento del activo
        asset_approved, asset_reason = self._check_asset_performance(asset)
        if not asset_approved:
            return False, asset_reason
        
        # 2. Verificar rendimiento del patrón
        if pattern_type:
            pattern_approved, pattern_reason = self._check_pattern_performance(
                pattern_type, asset
            )
            if not pattern_approved:
                return False, pattern_reason
        
        # 3. Verificar hora del día
        hour_approved, hour_reason = self._check_hourly_performance()
        if not hour_approved:
            return False, hour_reason
        
        # 4. Verificar errores comunes
        if current_conditions:
            error_approved, error_reason = self._check_common_errors(current_conditions)
            if not error_approved:
                return False, error_reason
        
        # 5. Verificar racha reciente
        streak_approved, streak_reason = self._check_recent_streak(asset)
        if not streak_approved:
            return False, streak_reason
        
        return True, "✅ Todas las validaciones pasadas"
    
    def _check_asset_performance(self, asset: str) -> Tuple[bool, str]:
        """Verifica el rendimiento histórico del activo (JSON)"""
        matches = self._get_matches(asset=asset, days=30)
        
        if not matches:
             return True, f"Sin historial para {asset}"
             
        wins = sum(1 for op in matches if op.get('won', False))
        total = len(matches)
        win_rate = (wins / total) * 100
        
        if total < 10:
             return True, f"{asset}: Solo {total} trades (Datos insuficientes)"
             
        if win_rate < 45:
             return False, f"❌ {asset} tiene Win Rate Pobre: {win_rate:.1f}% ({wins}/{total})"
             
        return True, f"✅ {asset}: {win_rate:.1f}% WR ({total} trades)"

    def _check_pattern_performance(self, pattern_type: str, asset: str) -> Tuple[bool, str]:
        """Verifica el rendimiento histórico del patrón (JSON)"""
        # Filtrar por activo y patrón
        matches = [op for op in self._get_matches(asset=asset, days=90) 
                  if op.get('pattern', {}).get('type') == pattern_type]
                  
        if not matches:
            return True, f"Sin datos para patrón {pattern_type}"
            
        wins = sum(1 for op in matches if op.get('won', False))
        total = len(matches)
        
        if total == 0: return True, "N/A"
        win_rate = (wins / total) * 100
        
        # Requiere más datos antes de rechazar
        if total < self.min_pattern_occurrences:
            return True, f"Patrón {pattern_type}: Solo {total} obs."
            
        if win_rate < self.min_pattern_win_rate:
            return False, f"❌ Patrón {pattern_type} rinde mal: {win_rate:.1f}%"
            
        return True, f"✅ Patrón {pattern_type}: {win_rate:.1f}% WR"

    def _check_hourly_performance(self) -> Tuple[bool, str]:
        """Verifica el rendimiento en la hora actual (JSON)"""
        current_hour = datetime.now().hour
        matches = self._get_matches(days=30) # Todos los activos
        
        # Filtrar por hora
        hour_matches = []
        for op in matches:
            try:
                op_hour = datetime.fromisoformat(op.get('timestamp', '')).hour
                if op_hour == current_hour:
                    hour_matches.append(op)
            except: continue
            
        if not hour_matches:
            return True, f"Sin historial hora {current_hour}:00"
            
        wins = sum(1 for op in hour_matches if op.get('won', False))
        total = len(hour_matches)
        if total == 0: return True, "N/A"
        
        win_rate = (wins / total) * 100
        
        # Requiere más datos antes de rechazar
        if total < self.min_hourly_occurrences:
            return True, f"Hora {current_hour}: Pocos datos ({total})"
            
        if win_rate < self.min_hourly_win_rate:
            return False, f"❌ Hora {current_hour} es MALA para operar: {win_rate:.1f}%"
            
        return True, f"✅ Hora {current_hour} es segura ({win_rate:.1f}%)"
    
    def _check_common_errors(self, current_conditions: Dict) -> Tuple[bool, str]:
        """Verifica si las condiciones actuales coinciden con errores comunes (JSON)"""
        # Buscar operaciones perdedoras recientes
        losses = [op for op in self._get_matches(days=30) if not op.get('won', False)]
        
        matches_found = 0
        for loss in losses:
            loss_conditions = loss.get('market_context', {})
            # Si no hay contexto, buscar en 'state_before' si es legible, o patterns
            if not loss_conditions and 'pattern' in loss:
                 pass # Simple pattern match check could be done here
            
            # Comparativo simplificado de indicadores clave
            if self._conditions_match(current_conditions, loss_conditions):
                matches_found += 1
                
        if matches_found >= 3:
             return False, f"❌ Condiciones similares a {matches_found} pérdidas recientes"
             
        return True, "✅ No coincide con errores conocidos"

    def _check_recent_streak(self, asset: str) -> Tuple[bool, str]:
        """Verifica la racha reciente en el activo (JSON)"""
        # Obtener ultimas 5 operaciones del activo
        matches = self._get_matches(asset=asset, days=7)
        matches.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        recent = matches[:5]
        
        if len(recent) < 3:
            return True, "Sin racha reciente"
            
        consecutive_losses = 0
        for op in recent:
            if not op.get('won', False):
                consecutive_losses += 1
            else:
                break
                
        if consecutive_losses >= 3:
            return False, f"❌ {consecutive_losses} pérdidas consecutivas en {asset}"
            
        return True, f"✅ Racha aceptable en {asset}"

    def _conditions_match(self, current: Dict, historical: Dict, threshold: float = 0.8) -> bool:
        """Compara condiciones actuales con históricas"""
        if not historical: return False
        
        matches = 0
        total = 0
        key_indicators = ['rsi', 'macd', 'volatility']
        
        for k in key_indicators:
            if k in current and k in historical:
                total += 1
                try:
                    v1 = float(current[k])
                    v2 = float(historical[k])
                    # Si están cerca (20% margen)
                    if abs(v1 - v2) / (abs(v2) + 0.0001) < 0.2:
                        matches += 1
                except: pass
                
        if total == 0: return False
        return (matches / total) >= threshold

    def get_recommended_confidence(self, asset: str) -> float:
        """Recomienda nivel de confianza mínimo basado en rendimiento (JSON)"""
        matches = self._get_matches(asset=asset, days=30)
        if not matches: return 0.65
        
        wins = sum(1 for op in matches if op.get('won', False))
        total = len(matches)
        if total < 10: return 0.65
        
        win_rate = (wins / total) * 100
        
        if win_rate >= 70: return 0.55
        elif win_rate >= 60: return 0.65
        elif win_rate >= 50: return 0.75
        else: return 0.85 
    
    def get_statistics_summary(self) -> Dict:
        """Obtiene resumen de estadísticas para mostrar en GUI"""
        try:
            stats_7d = db.get_performance_stats(days=7)
            stats_30d = db.get_performance_stats(days=30)
            best_patterns = db.get_best_patterns(min_occurrences=10)
            common_errors = db.get_common_errors(limit=5)
            
            return {
                'last_7_days': stats_7d,
                'last_30_days': stats_30d,
                'best_patterns': best_patterns[:5],
                'common_errors': common_errors,
                'total_trades_db': stats_30d.get('total_trades', 0) if stats_30d else 0
            }
        except Exception as e:
            print(f"[WARNING] Error obteniendo resumen: {e}")
            return {}
