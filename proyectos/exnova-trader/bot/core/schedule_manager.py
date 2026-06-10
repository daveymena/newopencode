"""
Gestor de Horarios de Operación
Máximo 10 operaciones por hora, 5 minutos entre operaciones
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ScheduleManager:
    """Gestiona operaciones por hora y espaciamiento"""
    
    def __init__(self, max_trades_per_hour=10, min_interval_seconds=300):
        """
        Args:
            max_trades_per_hour: Máximo de operaciones por hora (default 10)
            min_interval_seconds: Segundos mínimos entre operaciones (default 300 = 5 min)
        """
        self.max_trades_per_hour = max_trades_per_hour
        self.min_interval_seconds = min_interval_seconds
        
        self.trades_this_hour = []
        self.last_trade_time = None
        self.hour_start = datetime.now()
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Verificar si se puede ejecutar una operación
        
        Returns:
            (bool, str): (puede_operar, razón)
        """
        now = datetime.now()
        
        # Verificar si pasó una hora
        if (now - self.hour_start).total_seconds() > 3600:
            self.trades_this_hour = []
            self.hour_start = now
        
        # Verificar límite de operaciones por hora
        if len(self.trades_this_hour) >= self.max_trades_per_hour:
            remaining = 3600 - (now - self.hour_start).total_seconds()
            return False, f"Límite de {self.max_trades_per_hour} ops/hora alcanzado. Esperar {remaining:.0f}s"
        
        # Verificar intervalo mínimo entre operaciones
        if self.last_trade_time:
            elapsed = (now - self.last_trade_time).total_seconds()
            if elapsed < self.min_interval_seconds:
                wait_time = self.min_interval_seconds - elapsed
                return False, f"Esperar {wait_time:.0f}s entre operaciones (mín {self.min_interval_seconds}s)"
        
        return True, "OK"
    
    def record_trade(self, trade_data: Dict):
        """Registrar una operación ejecutada"""
        now = datetime.now()
        self.trades_this_hour.append({
            "timestamp": now,
            "asset": trade_data.get("asset"),
            "signal": trade_data.get("signal"),
            "profit": trade_data.get("profit", 0)
        })
        self.last_trade_time = now
        
        logger.info(f"Trade registrado: {len(self.trades_this_hour)}/{self.max_trades_per_hour} "
                   f"en esta hora")
    
    def get_wait_time(self) -> int:
        """Obtener segundos a esperar antes de siguiente operación"""
        
        if not self.last_trade_time:
            return 0
        
        now = datetime.now()
        elapsed = (now - self.last_trade_time).total_seconds()
        wait = max(0, self.min_interval_seconds - elapsed)
        
        return int(wait)
    
    def get_status(self) -> Dict:
        """Obtener estado del horario"""
        
        now = datetime.now()
        hour_elapsed = (now - self.hour_start).total_seconds()
        hour_remaining = max(0, 3600 - hour_elapsed)
        
        total_profit = sum(t["profit"] for t in self.trades_this_hour)
        
        return {
            "trades_this_hour": len(self.trades_this_hour),
            "max_per_hour": self.max_trades_per_hour,
            "hour_elapsed_seconds": int(hour_elapsed),
            "hour_remaining_seconds": int(hour_remaining),
            "total_profit_this_hour": f"${total_profit:+.2f}",
            "last_trade": self.last_trade_time.isoformat() if self.last_trade_time else "Ninguna",
            "next_trade_available_in": self.get_wait_time()
        }
    
    def wait_for_next_trade(self):
        """Esperar hasta que se pueda ejecutar siguiente operación"""
        
        wait_time = self.get_wait_time()
        
        if wait_time > 0:
            logger.info(f"Esperando {wait_time}s antes de siguiente operación...")
            time.sleep(wait_time)
