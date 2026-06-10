"""
🎯 ESTRATEGIA BOLLINGER + RSI (Patrón de Entradas Reales)
Basada en análisis de imágenes de entradas ganadoras del Google Drive
"""
import pandas as pd
import numpy as np

class BollingerRSIStrategy:
    """
    Estrategia de reversión en extremos usando:
    - Bandas de Bollinger (20, 2)
    - RSI (14)
    - Patrones de velas
    - MACD (confirmación)
    
    Basada en patrones reales de entradas ganadoras
    """
    
    def __init__(self):
        self.name = "Bollinger+RSI Reversal"
        
    def calculate_indicators(self, df):
        """Calcula todos los indicadores necesarios"""
        # Bandas de Bollinger (20, 2)
        if 'bb_high' not in df.columns or 'bb_mid' not in df.columns or 'bb_low' not in df.columns:
            sma = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            df['bb_high'] = sma + (std * 2)
            df['bb_mid'] = sma
            df['bb_low'] = sma - (std * 2)
        
        # RSI (14)
        if 'rsi' not in df.columns:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        if 'macd' not in df.columns:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
        
        return df
    
    def analyze(self, df, min_confidence=75):
        """
        Analiza el mercado buscando el patrón exacto de las imágenes
        """
        try:
            if len(df) < 50:
                return {'action': 'WAIT', 'confidence': 0, 'reason': 'Datos insuficientes'}
            
            df = self.calculate_indicators(df)
            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            
            current_price = last_candle['close']
            rsi = last_candle['rsi']
            bb_high = last_candle['bb_high']
            bb_low = last_candle['bb_low']
            bb_mid = last_candle['bb_mid']
            
            # 4. Filtro de Tendencia (SMA 100)
            if 'sma_100' not in df.columns:
                df['sma_100'] = df['close'].rolling(window=100).mean()
            current_sma = df['sma_100'].iloc[-1]
            trend_up = current_price > current_sma
            
            # 5. Filtro de Volatilidad (ATR)
            # Evitar operar si la vela actual es demasiado "grande" comparada con el promedio
            if 'atr' not in df.columns:
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                df['atr'] = tr.rolling(window=14).mean()
            
            current_atr = df['atr'].iloc[-1]
            last_candle_range = last_candle['high'] - last_candle['low']
            
            # En modo aprendizaje (< 70 confianza), somos menos estrictos con la volatilidad
            volatility_limit = 4 if min_confidence < 70 else 3
            if current_atr > 0 and last_candle_range > current_atr * volatility_limit:
                return {'action': 'WAIT', 'confidence': 0, 'reason': f'Volatilidad Extrema (Vela > {volatility_limit}x ATR)'}

            # --- ANÁLISIS PARA CALL (Compra en Banda Inferior) ---
            call_score = 0
            call_reasons = []
            
            # 1. Agotamiento Extremo (OBLIGATORIO)
            # Ya no entramos en 30, buscamos el "máximo dolor" del mercado (RSI < 25)
            extreme_rsi_limit = 25
            if rsi <= extreme_rsi_limit:
                call_score += 40
                call_reasons.append(f"Agotamiento RSI Extremo ({rsi:.1f})")
            else:
                call_score = 0
            
            if call_score > 0:
                # 2. Perforación y Rechazo de Banda Inferior (OBLIGATORIO)
                # El precio debe haber perforado la banda y mostrado rechazo (mecha)
                lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
                wick_pct = (lower_wick / last_candle_range) if last_candle_range > 0 else 0
                
                # Exigimos que el mínimo de la vela esté REALMENTE abajo de la banda
                if last_candle['low'] < bb_low:
                    call_score += 20
                    call_reasons.append("Perforación de Banda")
                    
                    # Bonus por mecha de rechazo larga (Spring)
                    if wick_pct > 0.45:
                        call_score += 20
                        call_reasons.append(f"Rechazo Spring ({wick_pct*100:.0f}%)")
                    elif min_confidence > 80: # En modo élite, la mecha es obligatoria
                        call_score = 0
                else:
                    call_score = 0

            if call_score > 0:
                # 3. Confirmación de Giro (Vela Verde)
                # No intentamos atrapar un cuchillo que cae, esperamos a que la primera vela verde cierre
                candle_is_bullish = last_candle['close'] > last_candle['open']
                if candle_is_bullish:
                    call_score += 20
                    call_reasons.append("Confirmación de Giro (Verde)")
                else:
                    # Si la vela es roja pero tiene un RSI bajísimo (< 15), es un "climax"
                    if rsi < 15:
                        call_score += 10
                        call_reasons.append("Clímax de Venta")
                    else:
                        call_score = 0 # Esperar a la vela verde

            # --- ANÁLISIS PARA PUT (Venta en Banda Superior) ---
            put_score = 0
            put_reasons = []
            
            # 1. Agotamiento Extremo (OBLIGATORIO) 
            # Ya no entramos en 70, buscamos el agotamiento total (RSI > 75)
            extreme_rsi_limit_put = 75
            if rsi >= extreme_rsi_limit_put:
                put_score += 40
                put_reasons.append(f"Agotamiento RSI Extremo ({rsi:.1f})")
            else:
                put_score = 0
            
            if put_score > 0:
                # 2. Perforación y Rechazo de Banda Superior (OBLIGATORIO)
                upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
                wick_pct = (upper_wick / last_candle_range) if last_candle_range > 0 else 0
                
                if last_candle['high'] > bb_high:
                    put_score += 20
                    put_reasons.append("Perforación de Banda")
                    
                    # Bonus por mecha de rechazo larga (Upthrust)
                    if wick_pct > 0.45:
                        put_score += 20
                        put_reasons.append(f"Rechazo Upthrust ({wick_pct*100:.0f}%)")
                    elif min_confidence > 80:
                        put_score = 0
                else:
                    put_score = 0

            if put_score > 0:
                # 3. Confirmación de Giro (Vela Roja)
                candle_is_bearish = last_candle['close'] < last_candle['open']
                if candle_is_bearish:
                    put_score += 20
                    put_reasons.append("Confirmación de Giro (Roja)")
                else:
                    if rsi > 85:
                        put_score += 10
                        put_reasons.append("Clímax de Compra")
                    else:
                        put_score = 0 # Esperar a la vela roja
            
            # --- DECISIÓN FINAL ---
            final_threshold = max(75, min_confidence)
            
            if call_score >= final_threshold and call_score >= put_score:
                return {
                    'action': 'CALL',
                    'confidence': min(call_score, 99),
                    'strategy': 'Bollinger+RSI Rigorous Reversal',
                    'reason': ' | '.join(call_reasons),
                    'details': {'price': current_price, 'rsi': rsi, 'score': call_score},
                    'expiration': 180
                }
            
            elif put_score >= final_threshold and put_score > call_score:
                return {
                    'action': 'PUT',
                    'confidence': min(put_score, 99),
                    'strategy': 'Bollinger+RSI Rigorous Reversal',
                    'reason': ' | '.join(put_reasons),
                    'details': {'price': current_price, 'rsi': rsi, 'score': put_score},
                    'expiration': 180
                }

            
            else:
                # No cumple las condiciones mínimas
                max_score = max(call_score, put_score)
                return {
                    'action': 'WAIT',
                    'confidence': max_score,
                    'reason': f'Score insuficiente ({max_score}/100, mínimo 75)'
                }
                
        except Exception as e:
            # Si hay cualquier error, retornar WAIT para no detener el bot
            print(f"❌ Error en BollingerRSIStrategy: {str(e)}")
            return {
                'action': 'WAIT',
                'confidence': 0,
                'reason': f'Error en análisis: {str(e)}'
            }
