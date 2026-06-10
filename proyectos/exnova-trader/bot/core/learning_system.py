"""
Sistema de Aprendizaje Continuo con IA
Analiza cada operación y refina parámetros automáticamente
"""

import json
import logging
from datetime import datetime
from typing import Dict, List
import os

logger = logging.getLogger(__name__)

class LearningSystem:
    """Sistema que aprende de cada operación y refina parámetros"""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
        self.trades_log = []
        self.learning_data = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_profit": 0,
            "patterns": {},
            "refinements": []
        }
        self.load_learning_data()
    
    def load_learning_data(self):
        """Cargar datos de aprendizaje previos"""
        try:
            if os.path.exists("data/learning_data.json"):
                with open("data/learning_data.json", "r") as f:
                    self.learning_data = json.load(f)
                logger.info(f"Datos de aprendizaje cargados: WR={self.learning_data['win_rate']:.1f}%")
        except Exception as e:
            logger.error(f"Error cargando datos: {e}")
    
    def save_learning_data(self):
        """Guardar datos de aprendizaje"""
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/learning_data.json", "w") as f:
                json.dump(self.learning_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando datos: {e}")
    
    def record_trade(self, trade_data: Dict):
        """Registrar una operación completada"""
        
        self.trades_log.append(trade_data)
        
        # Actualizar estadísticas
        self.learning_data["total_trades"] += 1
        
        if trade_data["status"] == "WIN":
            self.learning_data["wins"] += 1
        else:
            self.learning_data["losses"] += 1
        
        # Calcular win rate
        total = self.learning_data["total_trades"]
        wins = self.learning_data["wins"]
        self.learning_data["win_rate"] = (wins / total * 100) if total > 0 else 0
        
        # Calcular ganancia promedio
        total_profit = sum(t.get("profit", 0) for t in self.trades_log)
        self.learning_data["avg_profit"] = total_profit / total if total > 0 else 0
        
        logger.info(f"Trade registrado: {trade_data['asset']} {trade_data['signal']} "
                   f"${trade_data['profit']:+.2f} | WR: {self.learning_data['win_rate']:.1f}%")
        
        self.save_learning_data()
    
    def analyze_with_ai(self, trade_data: Dict) -> Dict:
        """Analizar operación con IA para extraer lecciones"""
        
        if not self.ai_client:
            return {"analysis": "IA no disponible"}
        
        try:
            status = trade_data["status"]
            asset = trade_data["asset"]
            signal = trade_data["signal"]
            profit = trade_data["profit"]
            reason = trade_data.get("reason", "")
            
            if status == "WIN":
                prompt = f"""
Analiza por qué esta operación GANÓ:
- Activo: {asset}
- Señal: {signal}
- Ganancia: ${profit:.2f}
- Razón: {reason}

¿Qué patrones o características hicieron que ganara?
¿Cómo podemos replicar esto?
Sé conciso (máx 100 palabras).
"""
            else:
                prompt = f"""
Analiza por qué esta operación PERDIÓ:
- Activo: {asset}
- Señal: {signal}
- Pérdida: ${profit:.2f}
- Razón: {reason}

¿Qué falló? ¿Qué señal faltó?
¿Cómo evitar esto en el futuro?
Sé conciso (máx 100 palabras).
"""
            
            # Llamar a IA
            analysis = self.ai_client.analyze(prompt)
            
            return {
                "status": status,
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en análisis IA: {e}")
            return {"error": str(e)}
    
    def get_refinements(self) -> List[str]:
        """Obtener refinamientos sugeridos basados en aprendizaje"""
        
        refinements = []
        
        # Si win rate es bajo, sugerir filtros más estrictos
        if self.learning_data["win_rate"] < 50:
            refinements.append("❌ Win rate bajo (<50%) - Aumentar confianza mínima a 70%")
            refinements.append("❌ Considerar filtros adicionales (RSI extremo, MACD fuerte)")
        
        # Si win rate es bueno, mantener
        elif self.learning_data["win_rate"] >= 60:
            refinements.append("✅ Win rate bueno (>60%) - Mantener estrategia actual")
        
        # Analizar por activo
        asset_stats = {}
        for trade in self.trades_log[-50:]:  # Últimas 50 operaciones
            asset = trade["asset"]
            if asset not in asset_stats:
                asset_stats[asset] = {"wins": 0, "total": 0}
            
            asset_stats[asset]["total"] += 1
            if trade["status"] == "WIN":
                asset_stats[asset]["wins"] += 1
        
        # Sugerir activos mejores
        for asset, stats in asset_stats.items():
            wr = stats["wins"] / stats["total"] * 100 if stats["total"] > 0 else 0
            if wr > 65:
                refinements.append(f"⭐ {asset}: {wr:.0f}% WR - Aumentar operaciones aquí")
            elif wr < 40:
                refinements.append(f"⚠️ {asset}: {wr:.0f}% WR - Reducir operaciones aquí")
        
        return refinements
    
    def get_status(self) -> Dict:
        """Obtener estado actual del aprendizaje"""
        return {
            "total_trades": self.learning_data["total_trades"],
            "wins": self.learning_data["wins"],
            "losses": self.learning_data["losses"],
            "win_rate": f"{self.learning_data['win_rate']:.1f}%",
            "avg_profit": f"${self.learning_data['avg_profit']:+.2f}",
            "refinements": self.get_refinements()
        }
