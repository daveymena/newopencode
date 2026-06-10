"""
Parser de Señales de Telegram
Extrae información de señales de opciones binarias de grupos de Telegram
"""

import re
from typing import Optional, Dict
from datetime import datetime

class SignalParser:
    """
    Parsea mensajes de señales de trading de Telegram
    
    Formatos soportados robustos:
    - "EURUSD-OTC CALL 5 MIN"
    - "EUR/USD VENTA M3"
    - "🟢 AUDCAD 3M ⬆️"
    - "USDJPY PUT 5"
    """
    
    # Patrones de activos (orden importa: más específico primero)
    ASSET_PATTERNS = [
        r'\b([A-Z]{3}/[A-Z]{3}(?:-OTC)?)\b',  # EUR/USD-OTC
        r'\b([A-Z]{3}[A-Z]{3}(?:-OTC)?)\b',   # EURUSD-OTC
        r'\b([A-Z]{6}(?:-OTC)?)\b',           # EURUSD
    ]
    
    # Mapeo de direcciones (palabras clave y emojis)
    DIRECTION_MAP = {
        'CALL': ['CALL', 'BUY', 'COMPRA', 'ARRIBA', 'UP', 'SUBE', 'ALZA', '🟢', '⬆', '💚', '🟩'],
        'PUT': ['PUT', 'SELL', 'VENTA', 'ABAJO', 'DOWN', 'BAJA', 'CAE', '🔴', '⬇', '❤️', '🟥']
    }
    
    # Patrones de tiempo
    TIME_PATTERNS = [
        r'\b(\d+)\s*(?:MIN|MINUTOS?|M|MINUTES?)\b',  # 5 MIN, 5M
        r'\bM(\d+)\b',                                # M5
        r'\b(\d+)M\b',                                # 5M
        r'\b(\d+)\s*$',                               # 5 al final (riesgoso pero común)
    ]
    
    def __init__(self):
        self.last_signal = None
        self.signal_count = 0
    
    def parse(self, message: str) -> Optional[Dict]:
        """
        Parsea un mensaje de señal
        """
        if not message or len(message) < 5:
            return None
        
        # Limpieza básica y mayúsculas
        message_clean = message.upper().strip()
        
        # 1. Extraer Activo
        asset = self._extract_asset(message_clean)
        if not asset:
            return None
            
        # 2. Extraer Dirección
        direction = self._extract_direction(message_clean)
        if not direction:
            return None
            
        # 3. Extraer Expiración
        expiration = self._extract_expiration(message_clean)
        if not expiration:
            # Default inteligente: si dice "Turbo" o algo así, usar 1 min
            # Si no, usar 5 min por seguridad o lo que el usuario prefiera
            if "TURBO" in message_clean:
                expiration = 1
            else:
                expiration = 5  # Default más seguro
                
        # Normalizar activo
        asset = self._normalize_asset(asset)
        
        signal = {
            'asset': asset,
            'direction': direction,
            'expiration': expiration,
            'raw_message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        self.last_signal = signal
        self.signal_count += 1
        
        return signal
    
    def _extract_asset(self, message: str) -> Optional[str]:
        for pattern in self.ASSET_PATTERNS:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        return None
    
    def _extract_direction(self, message: str) -> Optional[str]:
        # Buscar palabras clave
        for key, variants in self.DIRECTION_MAP.items():
            for variant in variants:
                if variant in message:
                    return key.lower()  # 'call' o 'put'
        return None
    
    def _extract_expiration(self, message: str) -> Optional[int]:
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, message)
            if match:
                try:
                    val = int(match.group(1))
                    if 1 <= val <= 60:  # Rango lógico
                        return val
                except ValueError:
                    continue
        return None
    
    def _normalize_asset(self, asset: str) -> str:
        # Remover / y - incorrectos
        asset = asset.replace('/', '').replace(' ', '')
        
        # Asegurar -OTC si es fin de semana o si el usuario lo prefiere
        # Por ahora, asumimos que si no tiene -OTC, se lo ponemos si es par de divisas
        if not asset.endswith('-OTC') and not asset.endswith('OTC'):
            # Lista de pares comunes que suelen ser OTC en Exnova
            if len(asset) == 6:  # EURUSD
                asset = f"{asset}-OTC"
        
        # Normalizar OTC (a veces viene como EURUSDOTC)
        if asset.endswith('OTC') and not asset.endswith('-OTC'):
             asset = asset.replace('OTC', '-OTC')
             
        return asset
    
    def is_valid_signal(self, message: str) -> bool:
        """Verifica si un mensaje parece ser una señal válida"""
        signal = self.parse(message)
        return signal is not None
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del parser"""
        return {
            'total_signals_parsed': self.signal_count,
            'last_signal': self.last_signal
        }


# Ejemplos de uso
if __name__ == "__main__":
    parser = SignalParser()
    
    # Ejemplos de mensajes
    test_messages = [
        "EURUSD-OTC CALL 3",
        "EUR/USD PUT 5 MIN",
        "🟢 CALL GBPUSD-OTC M3",
        "⬇️ PUT USDJPY 5M",
        "COMPRA AUDUSD-OTC 3 MINUTOS",
        "VENTA EUR/USD 5M",
        "Hola, ¿cómo están?",  # No es señal
    ]
    
    print("=" * 60)
    print("PRUEBAS DE PARSER DE SEÑALES")
    print("=" * 60)
    
    for msg in test_messages:
        signal = parser.parse(msg)
        if signal:
            print(f"\n✅ SEÑAL DETECTADA:")
            print(f"   Mensaje: {msg}")
            print(f"   Asset: {signal['asset']}")
            print(f"   Dirección: {signal['direction'].upper()}")
            print(f"   Expiración: {signal['expiration']} min")
        else:
            print(f"\n❌ No es señal: {msg}")
    
    print("\n" + "=" * 60)
    print(f"Total señales parseadas: {parser.signal_count}")
    print("=" * 60)
