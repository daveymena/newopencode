
"""
🕯️ PATTERN RECON STRATEGY
Detecta patrones de velas (Engulfing, Pinbar) combinados con niveles clave.
"""
class PatternReconStrategy:
    def __init__(self):
        self.name = "Pattern Recon"

    def analyze(self, df):
        if len(df) < 5:
            return {'action': 'WAIT', 'confidence': 0, 'reason': 'Datos insuficientes'}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        action = 'WAIT'
        confidence = 0
        reasons = []

        # 1. BULLISH ENGULFING (Vela verde envuelve a la roja)
        if prev['close'] < prev['open'] and last['close'] > last['open']:
            if last['close'] > prev['open'] and last['open'] < prev['close']:
                # Calcular fuerza (cuánto más grande es)
                force = (last['close'] - last['open']) / (prev['open'] - prev['close'])
                if force > 1.2:
                    action = 'CALL'
                    confidence = min(85, 60 + (force - 1) * 20)
                    reasons.append(f"Bullish Engulfing (Fuerza: {force:.1f}x)")

        # 2. BEARISH ENGULFING (Vela roja envuelve a la verde)
        elif prev['close'] > prev['open'] and last['close'] < last['open']:
            if last['close'] < prev['open'] and last['open'] > prev['close']:
                force = (last['open'] - last['close']) / (prev['close'] - prev['open'])
                if force > 1.2:
                    action = 'PUT'
                    confidence = min(85, 60 + (force - 1) * 20)
                    reasons.append(f"Bearish Engulfing (Fuerza: {force:.1f}x)")

        # 3. PINBAR / HAMMER (Rechazo extremo)
        range_l = last['high'] - last['low']
        if range_l > 0:
            upper_wick = last['high'] - max(last['close'], last['open'])
            lower_wick = min(last['close'], last['open']) - last['low']
            body = abs(last['close'] - last['open'])
            
            # Hammer (Pinbar Alcista)
            if lower_wick > body * 2.5 and upper_wick < body:
                if action == 'WAIT' or action == 'CALL':
                    action = 'CALL'
                    confidence = max(confidence, 70)
                    reasons.append("Hammer / Pinbar Alcista detectado")
            
            # Shooting Star (Pinbar Bajista)
            elif upper_wick > body * 2.5 and lower_wick < body:
                if action == 'WAIT' or action == 'PUT':
                    action = 'PUT'
                    confidence = max(confidence, 70)
                    reasons.append("Shooting Star / Pinbar Bajista detectado")

        return {
            'action': action,
            'confidence': round(confidence, 1),
            'reason': " | ".join(reasons) if reasons else "Sin patrón claro",
            'strategy': self.name
        }
