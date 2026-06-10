"""
Consistency Manager - Filtro de equilibrio para operaciones 24/7
Analiza el historial en tiempo real para filtrar rachas negativas y optimizar consistencia.
"""
from database.db_manager import db
from datetime import datetime, timedelta
import pandas as pd

class ConsistencyManager:
    def __init__(self):
        self.min_hourly_winrate = 49.0 # Relajado para permitir más operaciones
        self.min_asset_winrate = 49.0  # Relajado para permitir más operaciones
        self.limit_losses_24h = 10      
        self.limit_losses_1h = 3        # Aumentado a 3 pérdidas antes de pausar
        
    def should_allow_trade(self, asset: str) -> tuple[bool, str]:
        """
        Determina si el bot está en 'equilibrio' para este activo y momento.
        """
        current_hour = datetime.now().hour
        
        # 1. Verificar Rendimiento por Hora (Histórico)
        try:
            hourly_stats = db.get_performance_by_hour()
            for h in hourly_stats:
                if int(h['hour']) == current_hour:
                    if h['win_rate'] < self.min_hourly_winrate and h['total_trades'] > 10:
                        return False, f"⚖️ INCONSISTENCIA: Hora {current_hour}:00 tiene winrate bajo ({h['win_rate']}%). Evitando mercado inestable."
        except Exception as e:
            print(f"⚠️ Error ConsistencyManager (Hour): {e}")

        # 2. Verificar Rendimiento por Activo (Histórico)
        try:
            asset_stats = db.get_performance_by_asset()
            for a in asset_stats:
                if a['asset'] == asset:
                    if a['win_rate'] < self.min_asset_winrate and a['total_trades'] > 15:
                        return False, f"⚖️ INCONSISTENCIA: El activo {asset} es estadísticamente perdedor ({a['win_rate']}%). Buscando mejor par."
        except Exception as e:
            print(f"⚠️ Error ConsistencyManager (Asset): {e}")

        # 3. Control de Daños Recientes (Última Hora)
        try:
            recent_trades = db.get_recent_trades(limit=10, asset=asset)
            if recent_trades:
                one_hour_ago = datetime.now() - timedelta(hours=1)
                losses_1h = sum(1 for t in recent_trades if t['result'] == 'loss' and t['entry_time'] > one_hour_ago)
                
                if losses_1h >= self.limit_losses_1h:
                    return False, f"⚖️ EQUILIBRIO: {losses_1h} pérdidas en la última hora para {asset}. Pausando activo por 30 min para reposar."
        except Exception as e:
            print(f"⚠️ Error ConsistencyManager (Recent): {e}")

        return True, "✅ Consistencia Validada"

    def get_dynamic_confidence_threshold(self) -> float:
        """
        MODO BERSERKER: Confianza mínima del 45% para forzar operaciones.
        """
        return 0.45
