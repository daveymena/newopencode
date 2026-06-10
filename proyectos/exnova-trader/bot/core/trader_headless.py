"""
Trader Headless - Versión sin GUI para backend/API
No depende de PySide6/Qt, usa callbacks en lugar de signals
"""
import time
import pandas as pd
from typing import Callable, Optional, Dict, List
from core.risk import RiskManager
from config import Config
from core.trade_analyzer import TradeAnalyzer
from core.continuous_learner import ContinuousLearner
from core.decision_validator import DecisionValidator
from core.trade_intelligence import TradeIntelligence
from core.observational_learner import ObservationalLearner
from core.intelligent_filters import IntelligentFilters
from core.parallel_trainer import ParallelTrainer
from core.market_structure_analyzer import MarketStructureAnalyzer
from database.db_manager import db
from datetime import datetime
import json
import threading


class HeadlessTrader:
    """
    Trader sin dependencias de GUI.
    Usa callbacks en lugar de Qt Signals para comunicación.
    """
    
    def __init__(self, market_data, feature_engineer, agent, risk_manager, asset_manager, llm_client=None):
        self.market_data = market_data
        self.feature_engineer = feature_engineer
        self.agent = agent
        self.risk_manager = risk_manager
        self.asset_manager = asset_manager
        self.llm_client = llm_client
        self.trade_analyzer = TradeAnalyzer()
        
        # Sistema de aprendizaje continuo
        self.continuous_learner = ContinuousLearner(agent, feature_engineer, market_data)
        
        # Validador de decisiones
        self.decision_validator = DecisionValidator()
        
        # 🧠 Sistema de Inteligencia de Trading (con Groq/Ollama)
        self.trade_intelligence = TradeIntelligence(llm_client=llm_client)
        
        # 👁️ Sistema de Aprendizaje Observacional
        self.observational_learner = ObservationalLearner(
            self.continuous_learner,
            self.market_data,
            self.feature_engineer
        )
        
        # 🎯 Filtros Inteligentes basados en datos históricos
        self.intelligent_filters = IntelligentFilters()
        
        # 🎓 Entrenador Paralelo (aprende mientras opera)
        self.parallel_trainer = ParallelTrainer(
            market_data=market_data,
            feature_engineer=feature_engineer,
            agent=agent,
            llm_client=llm_client
        )
        
        # 📊 Analizador de Estructura de Mercado
        self.market_structure_analyzer = MarketStructureAnalyzer()
        
        # Callbacks (en lugar de signals)
        self.callbacks = {
            'price_update': [],
            'new_candle': [],
            'trade_signal': [],
            'log_message': [],
            'error_message': [],
            'balance_update': [],
            'decision_analysis': [],
            'stats_update': []
        }
        
        self.running = False
        self.paused = False
        self.active_trades = []
        self.thread = None
        
        # Control de tiempo entre operaciones
        self.last_trade_time = 0
        self.min_time_between_trades = 180
        self.cooldown_after_loss = 600
        self.consecutive_losses = 0
        self.last_trade_result = None
        self.last_trade_per_asset = {}
        self.cooldown_per_asset = 300
        self.trades_this_hour = []
        self.max_trades_per_hour = 3
    
    def on(self, event: str, callback: Callable):
        """Registrar callback para un evento"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def emit(self, event: str, *args):
        """Emitir evento a todos los callbacks registrados"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(*args)
                except Exception as e:
                    print(f"Error en callback {event}: {e}")
    
    def start(self):
        """Iniciar trader en un thread separado"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Detener trader"""
        self.running = False
        self.paused = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def pause(self):
        """Pausar trader"""
        self.paused = True
        self.emit('log_message', "⏸️ Bot pausado")
    
    def resume(self):
        """Reanudar trader"""
        self.paused = False
        self.emit('log_message', "▶️ Bot reanudado")
    
    def run(self):
        """Loop principal de trading (sin Qt)"""
        self.emit('log_message', "🚀 Bot iniciado en modo headless")
        
        while self.running:
            try:
                if self.paused:
                    time.sleep(1)
                    continue
                
                # Lógica de trading aquí (simplificada)
                # TODO: Implementar lógica completa del trader.py
                
                time.sleep(1)
                
            except Exception as e:
                self.emit('error_message', f"Error en loop: {e}")
                time.sleep(5)
        
        self.emit('log_message', "🛑 Bot detenido")
    
    def execute_trade(self, asset: str, direction: str, amount: float, duration: int = 60):
        """Ejecutar una operación manualmente"""
        try:
            if not self.market_data.is_connected():
                raise Exception("No conectado al broker")
            
            # Ejecutar trade
            result = self.market_data.place_trade(
                asset=asset,
                direction=direction,
                amount=amount,
                duration=duration
            )
            
            if result:
                self.emit('log_message', f"✅ Trade ejecutado: {direction.upper()} {asset}")
                self.emit('trade_signal', direction, asset)
                return result
            else:
                raise Exception("No se pudo ejecutar el trade")
                
        except Exception as e:
            self.emit('error_message', f"Error ejecutando trade: {e}")
            return None
