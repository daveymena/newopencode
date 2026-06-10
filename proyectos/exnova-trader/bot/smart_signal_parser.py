"""
Parser Inteligente de Señales usando LLM (Groq)
Interpreta mensajes complejos, extrae horarios exactos y valida lógica de trading.
"""
import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict
from groq import Groq

class SmartSignalParser:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Falta GROQ_API_KEY en .env")
            
        self.client = Groq(api_key=self.api_key)
        self.system_prompt = """
        Eres un experto analista de trading. Tu tarea es extraer datos estructurados en JSON.
        
        Debes extraer:
        - "asset": Par de divisas (ej: "EURUSD-OTC").
        - "direction": "CALL" o "PUT".
        - "expiration": Tiempo en minutos.
        - "entry_time": Hora exacta "HH:MM" si existe.
        - "remaining_time_str": Texto exacto del tiempo restante si existe (ej: "00:10", "2 Minutos", "00:00").
        
        Prioridad para tiempo de entrada:
        1. Si hay "Tiempo restante", extráelo en "remaining_time_str".
        2. Si no, busca "Hora de entrar" en "entry_time".
        
        Si el mensaje no es señal clara, retorna {"is_signal": false}.
        """

    def parse_with_ai(self, message: str) -> Optional[Dict]:
        """
        Usa Groq para entender el mensaje y extraer la señal
        """
        try:
            # Detectar si es señal WEB
            is_web_signal = "WEB_SIGNAL_CONTEXT" in message

            # Preparar prompt
            prompt = f"""
            Analiza este mensaje:
            '''
            {message}
            '''
            Responde SOLO con el JSON.
            """
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            
            response_content = chat_completion.choices[0].message.content
            clean_json = response_content.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            
            if not data.get("is_signal", True):
                return None
            
            # Normalizar datos (Asset, Direction...)
            if "asset" in data:
                data["asset"] = data["asset"].upper().replace("/", "").replace(" ", "")
                # Detectar si ya tiene OTC
                is_otc = data["asset"].endswith("-OTC") or "OTC" in data["asset"]
                if not is_otc:
                    is_weekend = datetime.now().weekday() >= 5
                    if is_weekend and len(data["asset"]) == 6: 
                             data["asset"] += "-OTC"
            
            if "direction" in data:
                data["direction"] = data["direction"].lower()
            
            # --- LÓGICA DE TIEMPO MEJORADA (Prioridad: Countdown) ---
            data["seconds_to_wait"] = 0
            
            # 1. Intentar usar "Tiempo Restante" (Más preciso para Web)
            if data.get("remaining_time_str"):
                rem_str = data["remaining_time_str"].strip()
                seconds = 0
                try:
                    # Formato "MM:SS" (ej: 00:10)
                    if ":" in rem_str:
                        parts = rem_str.split(":")
                        seconds = int(parts[0]) * 60 + int(parts[1])
                    # Formato "X Minutos"
                    elif "min" in rem_str.lower():
                        # Extraer solo números
                        nums = [int(s) for s in rem_str.split() if s.isdigit()]
                        if nums: seconds = nums[0] * 60
                    # Solo números (asumimos minutos si es Web y > 60 seg?) No, mejor asumo segundos si es bajo.
                    
                    data["seconds_to_wait"] = seconds
                    print(f"⏳ C yber-Tiempo detectado: Faltan {seconds}s para entrar.")
                    
                    # Si ya es 0, entrar ahora.
                    return data
                    
                except Exception as ex:
                    print(f"⚠️ Error parseando tiempo restante '{rem_str}': {ex}. Usando hora exacta.")
            
            # 2. Si no hubo tiempo restante (o falló), usar Hora Exacta
            if "entry_time" in data and data["entry_time"] != "NOW":
                wait_seconds = self._calculate_wait_time(data["entry_time"])
                
                # Protección estricta solo si NO venimos de un countdown válido
                if wait_seconds < -30:
                     print(f"⌛ SEÑAL EXPIRADA: La hora {data['entry_time']} ya pasó hace {-wait_seconds}s. IGNORANDO.")
                     return None
                
                data["seconds_to_wait"] = max(0, int(wait_seconds))
            
            elif is_web_signal and "seconds_to_wait" not in data:
                # Si es web, no hay wait time calculado y no hay hora...
                if data.get("entry_time") == "NOW":
                     print("⚠️ Señal Web 'NOW' sin tiempo restante. Ignorando por seguridad.")
                     return None
                
            return data
            
        except Exception as e:
            print(f"❌ Error en SmartParser: {e}")
            return None
            
        except Exception as e:
            print(f"❌ Error en SmartParser: {e}")
            return None

    def _calculate_wait_time(self, target_time_str: str) -> float:
        """
        Calcula cuántos segundos faltan para la hora objetivo.
        Retorna negativo si ya pasó.
        """
        try:
            now = datetime.now()
            
            # Intentar parsear hora
            try:
                # Intento formato 24h
                target_time = datetime.strptime(target_time_str, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )
            except ValueError:
                try:
                    # Intento formato 12h
                     target_time = datetime.strptime(target_time_str, "%I:%M %p").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                except ValueError:
                    # Intento sin segundos
                    return 0

            # Ajuste de día si es necesario (p.ej. es 23:59 y señal es 00:01)
            # (Simplificado: asumimos mismo día por ahora)
            
            return (target_time - now).total_seconds()
            
        except Exception as e:
            print(f"⚠️ Error calculando tiempo: {e}")
            return 0
