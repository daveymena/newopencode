"""
Helper methods for LiveTrader
"""

def analyze_indicators(df):
    """
    Analiza indicadores técnicos del DataFrame
    """
    if df.empty or len(df) < 1:
        return {}
    
    last_row = df.iloc[-1]
    analysis = {}
    
    # RSI
    if 'rsi' in df.columns:
        rsi = last_row['rsi']
        if rsi < 30:
            analysis['rsi'] = {'value': rsi, 'signal': 'CALL', 'strength': 'strong'}
        elif rsi > 70:
            analysis['rsi'] = {'value': rsi, 'signal': 'PUT', 'strength': 'strong'}
        else:
            analysis['rsi'] = {'value': rsi, 'signal': 'NEUTRAL', 'strength': 'weak'}
    
    # MACD
    if 'macd' in df.columns:
        macd = last_row['macd']
        analysis['macd'] = {
            'value': macd,
            'signal': 'CALL' if macd > 0 else 'PUT',
            'strength': 'medium'
        }
    
    # Bollinger Bands
    if 'bb_high' in df.columns and 'bb_low' in df.columns:
        price = last_row['close']
        bb_high = last_row['bb_high']
        bb_low = last_row['bb_low']
        
        if price <= bb_low:
            analysis['bollinger'] = {'signal': 'CALL', 'strength': 'medium'}
        elif price >= bb_high:
            analysis['bollinger'] = {'signal': 'PUT', 'strength': 'medium'}
        else:
            analysis['bollinger'] = {'signal': 'NEUTRAL', 'strength': 'weak'}
    
    return analysis

def get_llm_advice(llm_client, df, asset):
    """
    Obtiene consejo del LLM
    """
    if df.empty or len(df) < 10:
        return None
    
    try:
        # Preparar contexto para el LLM
        last_row = df.iloc[-1]
        context = f"""
Analiza el siguiente activo: {asset}

Indicadores actuales:
- RSI: {last_row.get('rsi', 'N/A')}
- MACD: {last_row.get('macd', 'N/A')}
- Precio: {last_row.get('close', 'N/A')}

¿Recomendarías CALL, PUT o HOLD? Responde solo con una palabra: CALL, PUT o HOLD.
"""
        
        response = llm_client.get_advice(context)
        
        # Extraer recomendación
        if 'CALL' in response.upper():
            return 'CALL'
        elif 'PUT' in response.upper():
            return 'PUT'
        else:
            return 'HOLD'
    except:
        return None
