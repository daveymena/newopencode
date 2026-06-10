"""Sistema de Análisis de Estructura de Mercado REAL - Pro Version"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarketStructureAnalyzer:
    def __init__(self):
        self.min_candles_for_analysis = 50
    
    def find_sr_levels(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Detecta Soporte y Resistencia usando picos y valles locales"""
        highs = df['high'].values
        lows = df['low'].values
        
        resistances = []
        supports = []
        
        # Parámetro de sensibilidad para niveles
        window = 5
        
        for i in range(window, len(highs) - window):
            # Pico local (Resistencia)
            if all(highs[i] > highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] > highs[i+j] for j in range(1, window+1)):
                resistances.append(highs[i])
            
            # Valle local (Soporte)
            if all(lows[i] < lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] < lows[i+j] for j in range(1, window+1)):
                supports.append(lows[i])
                
        # Quedarse con los 3 más importantes/recientes
        return {
            "resistances": sorted(list(set(resistances)))[-3:],
            "supports": sorted(list(set(supports)))[:3]
        }

    def analyze_full_context(self, m1_candles: pd.DataFrame, m5_candles: Optional[pd.DataFrame] = None) -> Dict:
        """
        Análisis TOP-DOWN profesional:
        - M5 (o dataframe más largo): Define niveles de Soporte/Resistencia.
        - M1: Define momentum y gatillo de entrada.
        """
        if len(m1_candles) < self.min_candles_for_analysis:
            return self._no_signal("Insuficientes velas")
        
        try:
            # Usar M5 para niveles si está disponible, si no usar M1 largo
            ref_df = m5_candles if m5_candles is not None else m1_candles
            levels = self.find_sr_levels(ref_df)
            
            df = m1_candles.copy()
            # 1. INDICADORES
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
            
            last = df.iloc[-1]
            last_close = last['close']
            rsi = last.get('rsi', 50)
            
            # 2. PROXIMIDAD A NIVELES
            near_resistance = any(abs(last_close - res) / res < 0.0003 for res in levels['resistances'])
            near_support = any(abs(last_close - sup) / sup < 0.0003 for sup in levels['supports'])
            
            # 3. TENDENCIA Y MOMENTUM
            trend = "bullish" if last['ema_10'] > last['sma_20'] else "bearish"
            
            recent = df.tail(3)
            bullish_v = sum(1 for _, c in recent.iterrows() if c['close'] > c['open'])
            bearish_v = sum(1 for _, c in recent.iterrows() if c['close'] < c['open'])
            
            # 4. DECISIONES REALISTAS DE TRADER
            should_enter = False
            direction = None
            reasons = []
            confidence = 0

            # --- LÓGICA DE VENTA (PUT) ---
            # Caso 1: Rechazo en Resistencia (MÁS REALISTA)
            if near_resistance and bearish_v >= 1:
                should_enter = True
                direction = "PUT"
                confidence = 85
                reasons.append("Rechazo en zona de RESISTENCIA")
                reasons.append("Buscando rebote bajista")
            
            # Caso 2: Agotamiento en compra (RSI alto)
            elif rsi > 70 and bearish_v >= 1:
                should_enter = True
                direction = "PUT"
                confidence = 80
                reasons.append("Sobrecompra extrema (RSI > 70)")
                reasons.append("Agotamiento del impulso alcista")

            # --- LÓGICA DE COMPRA (CALL) ---
            # Caso 1: Rebote en Soporte (MÁS REALISTA)
            elif near_support and bullish_v >= 1:
                should_enter = True
                direction = "CALL"
                confidence = 85
                reasons.append("Rebote en zona de SOPORTE")
                reasons.append("Buscando impulso alcista")
            
            # Caso 2: Agotamiento en venta (RSI bajo)
            elif rsi < 30 and bullish_v >= 1:
                should_enter = True
                direction = "CALL"
                confidence = 80
                reasons.append("Sobreventa extrema (RSI < 30)")
                reasons.append("Agotamiento del impulso bajista")

            # --- FILTRO DE SEGURIDAD: NO COMPRAR EN RESISTENCIA / NO VENDER EN SOPORTE ---
            if direction == "CALL" and near_resistance:
                should_enter = False
                reasons.append("BLOQUEO: No se compra contra una resistencia")
            
            if direction == "PUT" and near_support:
                should_enter = False
                reasons.append("BLOQUEO: No se vende contra un soporte")

            entry_signal = {
                "should_enter": should_enter,
                "direction": direction if direction else "NONE",
                "confidence": confidence,
                "reasons": reasons,
                "market_context": {
                    "trend": trend,
                    "near_res": near_resistance,
                    "near_sup": near_support,
                    "levels": levels
                }
            }
            
            return {
                "entry_signal": entry_signal,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return self._no_signal(f"Error: {e}")

    def _no_signal(self, reason: str) -> Dict:
        return {
            "entry_signal": {
                "should_enter": False,
                "direction": "NONE",
                "confidence": 0,
                "reasons": [reason]
            }
        }
    
    def get_human_readable_analysis(self, analysis: Dict) -> str:
        """
        Convierte el análisis en texto legible para humanos
        
        Args:
            analysis: Resultado de analyze_full_context()
        
        Returns:
            str: Análisis en formato legible
        """
        if not analysis or 'entry_signal' not in analysis:
            return "❌ Sin análisis disponible"
        
        signal = analysis['entry_signal']
        
        # Construir mensaje
        lines = []
        lines.append("📊 ANÁLISIS DE ESTRUCTURA DE MERCADO")
        lines.append("")
        
        # Decisión
        if signal['should_enter']:
            emoji = "🟢" if signal['direction'] == "CALL" else "🔴"
            lines.append(f"{emoji} SEÑAL: {signal['direction']}")
            lines.append(f"   Confianza: {signal['confidence']}%")
        else:
            lines.append("⏸️ NO ENTRAR")
        
        # Razones
        if signal.get('reasons'):
            lines.append("")
            lines.append("📋 RAZONES:")
            for reason in signal['reasons']:
                lines.append(f"   • {reason}")
        
        # Contexto de mercado
        if 'market_context' in signal:
            ctx = signal['market_context']
            lines.append("")
            lines.append("🔍 CONTEXTO:")
            lines.append(f"   Tendencia: {ctx.get('trend', 'N/A')}")
            
            if ctx.get('near_res'):
                lines.append("   ⚠️ Cerca de RESISTENCIA")
            if ctx.get('near_sup'):
                lines.append("   ⚠️ Cerca de SOPORTE")
            
            # Niveles
            if 'levels' in ctx:
                levels = ctx['levels']
                if levels.get('resistances'):
                    res_str = ", ".join([f"{r:.5f}" for r in levels['resistances'][-2:]])
                    lines.append(f"   📈 Resistencias: {res_str}")
                if levels.get('supports'):
                    sup_str = ", ".join([f"{s:.5f}" for s in levels['supports'][:2]])
                    lines.append(f"   📉 Soportes: {sup_str}")
        
        return "\n".join(lines)
