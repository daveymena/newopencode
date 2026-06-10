"""
Experience Buffer - Almacena experiencias reales de trading
Para entrenamiento continuo con datos reales de Exnova
"""
import pandas as pd
import numpy as np
from datetime import datetime
import os
import json

class ExperienceBuffer:
    """
    Almacena experiencias de trading real para re-entrenamiento
    """
    def __init__(self, max_size=10000, save_path="data/experiences.csv"):
        self.max_size = max_size
        self.save_path = save_path
        self.experiences = []
        
        # Cargar experiencias previas si existen
        self.load()
    
    def add_experience(self, state, action, reward, next_state, done, metadata=None):
        """
        Agrega una experiencia de trading real
        
        Args:
            state: Estado del mercado (indicadores) antes de la operación
            action: Acción tomada (0=HOLD, 1=CALL, 2=PUT)
            reward: Resultado de la operación (profit/loss)
            next_state: Estado después de la operación
            done: Si terminó el episodio
            metadata: Info adicional (activo, timestamp, etc.)
        """
        experience = {
            'timestamp': datetime.now().isoformat(),
            'state': state.tolist() if hasattr(state, 'tolist') else state,
            'action': int(action),
            'reward': float(reward),
            'next_state': next_state.tolist() if hasattr(next_state, 'tolist') else next_state,
            'done': bool(done),
            'metadata': metadata or {}
        }
        
        self.experiences.append(experience)
        
        # Limitar tamaño del buffer
        if len(self.experiences) > self.max_size:
            self.experiences = self.experiences[-self.max_size:]
        
        # Auto-guardar cada 10 experiencias
        if len(self.experiences) % 10 == 0:
            self.save()
    
    def get_recent_experiences(self, n=100):
        """Obtiene las últimas N experiencias"""
        return self.experiences[-n:] if len(self.experiences) >= n else self.experiences
    
    def get_all_experiences(self):
        """Obtiene todas las experiencias"""
        return self.experiences
    
    def save(self):
        """Guarda experiencias en disco"""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            # Guardar como JSON
            with open(self.save_path.replace('.csv', '.json'), 'w') as f:
                json.dump(self.experiences, f, indent=2)
            
            print(f"{len(self.experiences)} experiencias guardadas")
        except Exception as e:
            print(f"Error guardando experiencias: {e}")
    
    def load(self):
        """Carga experiencias desde disco"""
        try:
            json_path = self.save_path.replace('.csv', '.json')
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    self.experiences = json.load(f)
                print(f"{len(self.experiences)} experiencias cargadas")
            else:
                print("No hay experiencias previas")
        except Exception as e:
            print(f"Error cargando experiencias: {e}")
            self.experiences = []
    
    def get_statistics(self):
        """Obtiene estadísticas de las experiencias"""
        if not self.experiences:
            return {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'avg_reward': 0,
                'total_profit': 0
            }
        
        rewards = [exp['reward'] for exp in self.experiences]
        wins = sum(1 for r in rewards if r > 0)
        losses = sum(1 for r in rewards if r < 0)
        
        return {
            'total': len(self.experiences),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / len(self.experiences)) * 100 if self.experiences else 0,
            'avg_reward': np.mean(rewards),
            'total_profit': sum(rewards)
        }
    
    def clear(self):
        """Limpia todas las experiencias"""
        self.experiences = []
        self.save()
