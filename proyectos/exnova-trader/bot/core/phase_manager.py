"""
Gestor de Fases del Bot
Fase 1: Recolección de datos (sin restricciones)
Fase 2: Producción (10 ops/hora, 5 min entre ops)
"""

import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PhaseManager:
    """Gestiona transición automática entre fases"""
    
    # Umbrales para cambiar a producción
    MIN_TRADES_FOR_PRODUCTION = 100  # Mínimo 100 operaciones
    MIN_WIN_RATE_FOR_PRODUCTION = 55  # Mínimo 55% de ganancia
    MIN_DAYS_DATA = 3  # Mínimo 3 días de datos
    
    def __init__(self):
        self.phase = "COLLECTION"  # COLLECTION o PRODUCTION
        self.phase_start = datetime.now()
        self.load_phase_state()
    
    def load_phase_state(self):
        """Cargar estado de fase anterior"""
        try:
            if os.path.exists("data/phase_state.json"):
                with open("data/phase_state.json", "r") as f:
                    state = json.load(f)
                    self.phase = state.get("phase", "COLLECTION")
                    self.phase_start = datetime.fromisoformat(state.get("phase_start", datetime.now().isoformat()))
                    logger.info(f"Fase cargada: {self.phase}")
        except Exception as e:
            logger.error(f"Error cargando fase: {e}")
    
    def save_phase_state(self):
        """Guardar estado de fase"""
        try:
            os.makedirs("data", exist_ok=True)
            state = {
                "phase": self.phase,
                "phase_start": self.phase_start.isoformat(),
                "timestamp": datetime.now().isoformat()
            }
            with open("data/phase_state.json", "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando fase: {e}")
    
    def check_phase_transition(self, learning_data: dict) -> bool:
        """
        Verificar si debe cambiar a fase de producción
        
        Returns:
            bool: True si cambió de fase
        """
        
        if self.phase == "PRODUCTION":
            return False  # Ya en producción
        
        # Verificar criterios
        total_trades = learning_data.get("total_trades", 0)
        win_rate = learning_data.get("win_rate", 0)
        
        # Calcular días desde inicio
        days_elapsed = (datetime.now() - self.phase_start).days
        
        logger.info(f"Verificando transición: {total_trades} trades, {win_rate:.1f}% WR, {days_elapsed} días")
        
        # Criterios para cambiar a producción
        if (total_trades >= self.MIN_TRADES_FOR_PRODUCTION and
            win_rate >= self.MIN_WIN_RATE_FOR_PRODUCTION and
            days_elapsed >= self.MIN_DAYS_DATA):
            
            logger.warning(f"🚀 TRANSICIÓN A PRODUCCIÓN")
            logger.warning(f"   ✅ {total_trades} operaciones (mín {self.MIN_TRADES_FOR_PRODUCTION})")
            logger.warning(f"   ✅ {win_rate:.1f}% WR (mín {self.MIN_WIN_RATE_FOR_PRODUCTION}%)")
            logger.warning(f"   ✅ {days_elapsed} días (mín {self.MIN_DAYS_DATA})")
            
            self.phase = "PRODUCTION"
            self.phase_start = datetime.now()
            self.save_phase_state()
            
            return True
        
        return False
    
    def get_phase(self) -> str:
        """Obtener fase actual"""
        return self.phase
    
    def is_production(self) -> bool:
        """¿Está en modo producción?"""
        return self.phase == "PRODUCTION"
    
    def is_collection(self) -> bool:
        """¿Está en modo recolección?"""
        return self.phase == "COLLECTION"
    
    def get_status(self) -> dict:
        """Obtener estado de fases"""
        days_elapsed = (datetime.now() - self.phase_start).days
        
        return {
            "current_phase": self.phase,
            "phase_start": self.phase_start.isoformat(),
            "days_in_phase": days_elapsed,
            "requirements": {
                "min_trades": self.MIN_TRADES_FOR_PRODUCTION,
                "min_win_rate": f"{self.MIN_WIN_RATE_FOR_PRODUCTION}%",
                "min_days": self.MIN_DAYS_DATA
            }
        }
