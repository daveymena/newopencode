"""
Trade Intelligence - Analiza cada operación para aprender
Por qué ganó, por qué perdió, qué debe mejorar
"""
import pandas as pd
import numpy as np
from datetime import datetime

class TradeIntelligence:
    """
    Sistema inteligente que analiza cada operación y aprende de ella
    Usa Groq para análisis profundo y recomendaciones inteligentes
    """
    def __init__(self, llm_client=None):
        self.trade_history = []
        self.winning_patterns = []
        self.losing_patterns = []
        self.llm_client = llm_client  # Cliente Groq para análisis inteligente
        
        # Configuración adaptativa
        self.recommended_min_confidence = 0.70
        self.recommended_wait_time = 0
        self.recommended_score_threshold = 50
        
        # 🧠 PERSISTENCIA Y EVOLUCIÓN
        from pathlib import Path
        import json
        self.db_path = Path("data/learning_database.json")
        self.load_history()
        
        # Inicializar Refinador de Estrategia
        try:
            from ai_strategy_refiner import AIStrategyRefiner
            self.refiner = AIStrategyRefiner(db_path=str(self.db_path))
        except ImportError:
            print("⚠️ No se pudo importar AIStrategyRefiner")
            self.refiner = None
        
    def load_history(self):
        """Carga historial persistente"""
        import json
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.trade_history = data.get('operations', [])
                    print(f"🧠 Inteligencia cargada: {len(self.trade_history)} operaciones previas")
            except Exception as e:
                print(f"⚠️ Error cargando historia: {e}")
                self.trade_history = []
        else:
            self.trade_history = []

    def save_history(self):
        """Guarda historial en disco"""
        import json
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            data = {'operations': self.trade_history}
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error guardando historia: {e}")

    def analyze_trade_result(self, trade_data, result):
        """
        Analiza una operación completada y aprende de ella
        
        Args:
            trade_data: dict con datos de la operación
            result: dict con resultado (won, profit, etc.) o bool
            
        Returns:
            dict: Análisis completo con recomendaciones
        """
        # Manejo robusto de result - puede venir como dict o bool
        try:
            if isinstance(result, dict):
                won = result.get('won', False)
                profit = result.get('profit', 0)
            elif isinstance(result, bool):
                won = result
                profit = 0
            else:
                # Fallback seguro
                won = bool(result)
                profit = 0
        except Exception as e:
            print(f"[ERROR] Error parseando result en analyze_trade_result: {e}, result={result}")
            won = False
            profit = 0
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'asset': trade_data.get('asset'),
            'action': trade_data.get('direction', 'N/A').upper(), # Normalizar para el Refiner
            'result': 'win' if won else 'loose',                 # Normalizar para el Refiner
            'won': won,
            'profit': profit,
            'strategy': {'confidence': 0}, # Placeholder para compatibilidad
            'reasons': [],
            'lessons': [],
            'recommendations': [],
            'pattern': {}
        }
        
        # Extraer patrón de la operación
        pattern = self._extract_pattern(trade_data)
        analysis['pattern'] = pattern
        
        # Rellenar datos de estrategia si están disponibles en trade_data
        if 'strategy_data' in trade_data:
            analysis['strategy'] = trade_data['strategy_data']
        
        if result['won']:
            # GANÓ - Analizar por qué
            analysis['reasons'] = self._analyze_win(trade_data, pattern)
            self.winning_patterns.append(pattern)
        else:
            # PERDIÓ - Analizar por qué
            analysis['reasons'] = self._analyze_loss(trade_data, pattern)
            self.losing_patterns.append(pattern)
        
        # Generar lecciones
        analysis['lessons'] = self._generate_lessons(pattern, result['won'])
        
        # 🧠 GROQ: Análisis profundo con IA
        if self.llm_client:
            try:
                groq_analysis = self._get_groq_deep_analysis(trade_data, pattern, result)
                analysis['groq_insights'] = groq_analysis
            except Exception as e:
                analysis['groq_insights'] = {'error': str(e)}
        
        # Generar recomendaciones
        analysis['recommendations'] = self._generate_recommendations()
        
        # Guardar en historial
        self.trade_history.append(analysis)
        
        # Limitar historial a últimas 500 operaciones (aumentado para mejor aprendizaje)
        if len(self.trade_history) > 500:
            self.trade_history = self.trade_history[-500:]
            
        # 💾 PERSISTIR DATOS INMEDIATAMENTE
        self.save_history()
        
        # 🧠 TRIGGER DE EVOLUCIÓN (Cada 5 operaciones)
        if len(self.trade_history) >= 10 and len(self.trade_history) % 5 == 0:
            if self.refiner:
                print("\n🧠 DETONANDO AUTO-EVOLUCIÓN DE ESTRATEGIA...")
                try:
                    self.refiner.analyze_and_evolve()
                except Exception as e:
                    print(f"⚠️ Error en evolución: {e}")

        return analysis
    
    def _extract_pattern(self, trade_data):
        """Extrae el patrón de la operación"""
        df = trade_data.get('df_before')
        
        if df is None or df.empty:
            return {}
        
        last = df.iloc[-1]
        
        pattern = {
            'direction': trade_data.get('direction'),
            'asset': trade_data.get('asset'),
            'entry_price': trade_data.get('entry_price'),
            'amount': trade_data.get('amount'),
            'duration': trade_data.get('duration', 60),
            
            # Indicadores en el momento de entrada
            'rsi': last.get('rsi', 50),
            'macd': last.get('macd', 0),
            'atr': last.get('atr', 0),
            'bb_position': self._get_bb_position(last),
            
            # Contexto del mercado
            'trend': self._get_trend(df),
            'volatility': self._get_volatility(df),
            'momentum': self._get_momentum(df),
            
            # Timing
            'time_of_day': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
        }
        
        return pattern
    
    def _get_bb_position(self, candle):
        """Determina posición en Bollinger Bands"""
        if 'bb_low' not in candle or 'bb_high' not in candle:
            return 'UNKNOWN'
        
        price = candle['close']
        bb_low = candle['bb_low']
        bb_high = candle['bb_high']
        bb_mid = (bb_low + bb_high) / 2
        
        if price <= bb_low:
            return 'LOWER'
        elif price >= bb_high:
            return 'UPPER'
        elif price < bb_mid:
            return 'BELOW_MID'
        else:
            return 'ABOVE_MID'
    
    def _get_trend(self, df):
        """Determina la tendencia"""
        if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
            return 'UNKNOWN'
        
        last = df.iloc[-1]
        sma_20 = last['sma_20']
        sma_50 = last['sma_50']
        price = last['close']
        
        if sma_20 > sma_50 and price > sma_20:
            return 'STRONG_UPTREND'
        elif sma_20 > sma_50:
            return 'UPTREND'
        elif sma_20 < sma_50 and price < sma_20:
            return 'STRONG_DOWNTREND'
        elif sma_20 < sma_50:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'
    
    def _get_volatility(self, df):
        """Determina la volatilidad"""
        if 'atr' not in df.columns:
            return 'UNKNOWN'
        
        current_atr = df.iloc[-1]['atr']
        avg_atr = df['atr'].mean()
        
        if current_atr > avg_atr * 1.5:
            return 'HIGH'
        elif current_atr < avg_atr * 0.7:
            return 'LOW'
        else:
            return 'NORMAL'
    
    def _get_momentum(self, df):
        """Determina el momentum"""
        if 'rsi' not in df.columns or 'macd' not in df.columns:
            return 'UNKNOWN'
        
        last = df.iloc[-1]
        rsi = last['rsi']
        macd = last['macd']
        
        if rsi > 60 and macd > 0:
            return 'STRONG_BULLISH'
        elif rsi > 50 and macd > 0:
            return 'BULLISH'
        elif rsi < 40 and macd < 0:
            return 'STRONG_BEARISH'
        elif rsi < 50 and macd < 0:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _analyze_win(self, trade_data, pattern):
        """Analiza por qué ganó"""
        reasons = []
        
        # Analizar RSI
        rsi = pattern.get('rsi', 50)
        if pattern['direction'] == 'call' and rsi < 35:
            reasons.append(f"✅ RSI sobreventa ({rsi:.0f}) + CALL = Reversión exitosa")
        elif pattern['direction'] == 'put' and rsi > 65:
            reasons.append(f"✅ RSI sobrecompra ({rsi:.0f}) + PUT = Reversión exitosa")
        
        # Analizar Bollinger Bands
        bb_pos = pattern.get('bb_position')
        if pattern['direction'] == 'call' and bb_pos == 'LOWER':
            reasons.append("✅ Precio en BB inferior + CALL = Rebote exitoso")
        elif pattern['direction'] == 'put' and bb_pos == 'UPPER':
            reasons.append("✅ Precio en BB superior + PUT = Rebote exitoso")
        
        # Analizar tendencia
        trend = pattern.get('trend')
        if pattern['direction'] == 'call' and 'UPTREND' in trend:
            reasons.append(f"✅ Tendencia alcista + CALL = A favor de la tendencia")
        elif pattern['direction'] == 'put' and 'DOWNTREND' in trend:
            reasons.append(f"✅ Tendencia bajista + PUT = A favor de la tendencia")
        
        # Analizar momentum
        momentum = pattern.get('momentum')
        if pattern['direction'] == 'call' and 'BULLISH' in momentum:
            reasons.append(f"✅ Momentum alcista + CALL = Confirmación correcta")
        elif pattern['direction'] == 'put' and 'BEARISH' in momentum:
            reasons.append(f"✅ Momentum bajista + PUT = Confirmación correcta")
        
        # Analizar volatilidad
        volatility = pattern.get('volatility')
        duration = pattern.get('duration', 60)
        if volatility == 'HIGH' and duration <= 60:
            reasons.append("✅ Alta volatilidad + Expiración corta = Timing correcto")
        elif volatility == 'LOW' and duration >= 180:
            reasons.append("✅ Baja volatilidad + Expiración larga = Timing correcto")
        
        if not reasons:
            reasons.append("✅ Condiciones generales favorables")
        
        return reasons
    
    def _analyze_loss(self, trade_data, pattern):
        """Analiza por qué perdió"""
        reasons = []
        
        # Analizar RSI
        rsi = pattern.get('rsi', 50)
        if pattern['direction'] == 'call' and rsi > 60:
            reasons.append(f"❌ RSI alto ({rsi:.0f}) + CALL = Entrada tardía en sobrecompra")
        elif pattern['direction'] == 'put' and rsi < 40:
            reasons.append(f"❌ RSI bajo ({rsi:.0f}) + PUT = Entrada tardía en sobreventa")
        elif 45 < rsi < 55:
            reasons.append(f"❌ RSI neutral ({rsi:.0f}) = Señal débil, debió esperar")
        
        # Analizar Bollinger Bands
        bb_pos = pattern.get('bb_position')
        if pattern['direction'] == 'call' and bb_pos == 'UPPER':
            reasons.append("❌ Precio en BB superior + CALL = Contra la resistencia")
        elif pattern['direction'] == 'put' and bb_pos == 'LOWER':
            reasons.append("❌ Precio en BB inferior + PUT = Contra el soporte")
        elif bb_pos in ['BELOW_MID', 'ABOVE_MID']:
            reasons.append("❌ Precio en zona neutral = Señal débil, debió esperar")
        
        # Analizar tendencia
        trend = pattern.get('trend')
        if pattern['direction'] == 'call' and 'DOWNTREND' in trend:
            reasons.append(f"❌ Tendencia bajista + CALL = Contra la tendencia")
        elif pattern['direction'] == 'put' and 'UPTREND' in trend:
            reasons.append(f"❌ Tendencia alcista + PUT = Contra la tendencia")
        elif trend == 'SIDEWAYS':
            reasons.append("❌ Mercado lateral = Difícil predecir, debió esperar")
        
        # Analizar momentum
        momentum = pattern.get('momentum')
        if pattern['direction'] == 'call' and 'BEARISH' in momentum:
            reasons.append(f"❌ Momentum bajista + CALL = Señales contradictorias")
        elif pattern['direction'] == 'put' and 'BULLISH' in momentum:
            reasons.append(f"❌ Momentum alcista + PUT = Señales contradictorias")
        elif momentum == 'NEUTRAL':
            reasons.append("❌ Momentum neutral = Señal débil, debió esperar")
        
        # Analizar volatilidad
        volatility = pattern.get('volatility')
        duration = pattern.get('duration', 60)
        if volatility == 'HIGH' and duration >= 180:
            reasons.append("❌ Alta volatilidad + Expiración larga = Mucho tiempo para cambios")
        elif volatility == 'LOW' and duration <= 60:
            reasons.append("❌ Baja volatilidad + Expiración corta = Poco movimiento esperado")
        
        if not reasons:
            reasons.append("❌ Condiciones desfavorables o timing incorrecto")
        
        return reasons
    
    def _generate_lessons(self, pattern, won):
        """Genera lecciones de la operación"""
        lessons = []
        
        if won:
            # Lecciones de éxito
            lessons.append("📚 LECCIÓN: Este tipo de setup funciona bien")
            
            # Identificar qué funcionó
            if pattern.get('rsi', 50) < 35 and pattern['direction'] == 'call':
                lessons.append("   → RSI < 35 + CALL es confiable")
            elif pattern.get('rsi', 50) > 65 and pattern['direction'] == 'put':
                lessons.append("   → RSI > 65 + PUT es confiable")
            
            if pattern.get('bb_position') in ['LOWER', 'UPPER']:
                lessons.append("   → Operar en extremos de BB es efectivo")
            
            if 'STRONG' in pattern.get('trend', ''):
                lessons.append("   → Tendencias fuertes son confiables")
        
        else:
            # Lecciones de error
            lessons.append("📚 LECCIÓN: Evitar este tipo de setup")
            
            # Identificar qué falló
            if 45 < pattern.get('rsi', 50) < 55:
                lessons.append("   → NO operar con RSI neutral (45-55)")
            
            if pattern.get('bb_position') in ['BELOW_MID', 'ABOVE_MID']:
                lessons.append("   → NO operar en zona neutral de BB")
            
            if pattern.get('trend') == 'SIDEWAYS':
                lessons.append("   → NO operar en mercado lateral")
            
            if pattern.get('momentum') == 'NEUTRAL':
                lessons.append("   → NO operar sin momentum claro")
            
            # Contra-tendencia
            if (pattern['direction'] == 'call' and 'DOWNTREND' in pattern.get('trend', '')) or \
               (pattern['direction'] == 'put' and 'UPTREND' in pattern.get('trend', '')):
                lessons.append("   → NO operar contra la tendencia")
        
        return lessons
    
    def _generate_recommendations(self):
        """Genera recomendaciones basadas en historial"""
        if len(self.trade_history) < 10:
            return ["⏳ Necesita más operaciones para generar recomendaciones (mínimo 10)"]
        
        recommendations = []
        
        # Analizar últimas 20 operaciones
        recent = self.trade_history[-20:]
        wins = sum(1 for t in recent if t['won'])
        losses = len(recent) - wins
        win_rate = (wins / len(recent)) * 100
        
        # RECOMENDACIÓN 1: Ajustar confianza mínima
        if win_rate < 45:
            self.recommended_min_confidence = 0.80
            recommendations.append("🎯 RECOMENDACIÓN: Aumentar confianza mínima a 80% (win rate bajo)")
        elif win_rate > 70:
            self.recommended_min_confidence = 0.65
            recommendations.append("🎯 RECOMENDACIÓN: Puede reducir confianza mínima a 65% (win rate alto)")
        else:
            self.recommended_min_confidence = 0.70
            recommendations.append("🎯 RECOMENDACIÓN: Mantener confianza mínima en 70%")
        
        # RECOMENDACIÓN 2: Analizar patrones perdedores
        losing_patterns = [t['pattern'] for t in recent if not t['won']]
        
        if losing_patterns:
            # Contar RSI neutral en pérdidas
            neutral_rsi_losses = sum(1 for p in losing_patterns if 45 < p.get('rsi', 50) < 55)
            if neutral_rsi_losses >= 3:
                recommendations.append("⚠️ RECOMENDACIÓN: Evitar operar con RSI neutral (45-55)")
            
            # Contar operaciones contra tendencia
            counter_trend_losses = sum(1 for p in losing_patterns 
                                      if (p['direction'] == 'call' and 'DOWNTREND' in p.get('trend', '')) or
                                         (p['direction'] == 'put' and 'UPTREND' in p.get('trend', '')))
            if counter_trend_losses >= 3:
                recommendations.append("⚠️ RECOMENDACIÓN: NO operar contra la tendencia")
            
            # Contar mercado lateral
            sideways_losses = sum(1 for p in losing_patterns if p.get('trend') == 'SIDEWAYS')
            if sideways_losses >= 2:
                recommendations.append("⚠️ RECOMENDACIÓN: Evitar operar en mercado lateral")
        
        # RECOMENDACIÓN 3: Analizar patrones ganadores
        winning_patterns = [t['pattern'] for t in recent if t['won']]
        
        if winning_patterns:
            # Contar RSI extremo en ganancias
            extreme_rsi_wins = sum(1 for p in winning_patterns 
                                  if p.get('rsi', 50) < 35 or p.get('rsi', 50) > 65)
            if extreme_rsi_wins >= 3:
                recommendations.append("✅ RECOMENDACIÓN: Priorizar operaciones con RSI extremo (<35 o >65)")
            
            # Contar BB extremos en ganancias
            bb_extreme_wins = sum(1 for p in winning_patterns 
                                 if p.get('bb_position') in ['LOWER', 'UPPER'])
            if bb_extreme_wins >= 3:
                recommendations.append("✅ RECOMENDACIÓN: Priorizar operaciones en extremos de BB")
        
        # RECOMENDACIÓN 4: Timing
        if losses >= 3:
            self.recommended_wait_time = 30
            recommendations.append("⏱️ RECOMENDACIÓN: Esperar 30s adicionales antes de entrar")
        else:
            self.recommended_wait_time = 0
        
        # RECOMENDACIÓN 5: Score threshold
        if win_rate < 50:
            self.recommended_score_threshold = 70
            recommendations.append("📊 RECOMENDACIÓN: Aumentar score mínimo a 70 (más selectivo)")
        elif win_rate > 65:
            self.recommended_score_threshold = 55
            recommendations.append("📊 RECOMENDACIÓN: Puede reducir score mínimo a 55")
        else:
            self.recommended_score_threshold = 60
        
        return recommendations
    
    def _get_groq_deep_analysis(self, trade_data, pattern, result):
        """
        Usa Groq para análisis profundo de la operación
        
        Returns:
            dict: Análisis detallado con insights de IA
        """
        if not self.llm_client:
            return {}
        
        # Preparar contexto para Groq
        context = f"""
Eres un analista experto de trading de opciones binarias. Analiza esta operación:

OPERACIÓN:
- Dirección: {pattern.get('direction', 'N/A').upper()}
- Activo: {pattern.get('asset', 'N/A')}
- Resultado: {'GANÓ' if result.get('won', False) else 'PERDIÓ'}
- Profit: ${result.get('profit', 0):.2f}

INDICADORES EN EL MOMENTO DE ENTRADA:
- RSI: {pattern.get('rsi', 'N/A')}
- MACD: {pattern.get('macd', 'N/A')}
- Posición en BB: {pattern.get('bb_position', 'N/A')}
- Tendencia: {pattern.get('trend', 'N/A')}
- Volatilidad: {pattern.get('volatility', 'N/A')}
- Momentum: {pattern.get('momentum', 'N/A')}

ANÁLISIS REQUERIDO:
1. ¿Por qué {'ganó' if result.get('won', False) else 'perdió'}? (análisis profundo)
2. ¿Qué debió hacer diferente? (si perdió)
3. ¿Qué hizo bien? (si ganó)
4. ¿Qué ajustes recomiendas para futuras operaciones?
5. ¿Qué patrón específico debe {'replicar' if result.get('won', False) else 'evitar'}?

Responde en formato JSON:
{{
    "analisis_profundo": "explicación detallada",
    "factor_clave": "el factor más importante",
    "error_principal": "si perdió, cuál fue el error" o null,
    "acierto_principal": "si ganó, cuál fue el acierto" o null,
    "ajuste_confianza": "aumentar/mantener/reducir",
    "ajuste_timing": "esperar_mas/mantener/entrar_rapido",
    "patron_identificado": "descripción del patrón",
    "recomendacion_especifica": "acción concreta para mejorar"
}}
"""
        
        try:
            # Usar el método seguro que maneja rotación y fallback automáticamente
            response = self.llm_client._safe_query(context)
            source = "Groq" if self.llm_client.use_groq and self.llm_client.groq_client else "Ollama"
            
            # Intentar parsear JSON con manejo robusto
            import json
            import re
            
            # Limpiar respuesta: remover markdown, espacios extra, etc.
            response = response.strip()
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                
                # Intentar parsear de forma robusta
                try:
                    import json
                    groq_data = json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        import ast
                        groq_data = ast.literal_eval(json_str)
                    except:
                        print(f"⚠️ Falló parseo total de JSON/AST de {source}")
                        # Intentar extraer por texto si falla todo
                        return {
                            'source': f"{source} (Text Fallback)",
                            'analisis_profundo': json_str[:500],
                            'factor_clave': "Error de formato en IA",
                            'error_principal': None,
                            'acierto_principal': None,
                            'ajuste_confianza': 'mantener',
                            'ajuste_timing': 'mantener',
                            'patron_identificado': '',
                            'recomendacion_especifica': 'Revisar logs'
                        }
                    
                return {
                    'source': source,
                    'analisis_profundo': groq_data.get('analisis_profundo', ''),
                    'factor_clave': groq_data.get('factor_clave', ''),
                    'error_principal': groq_data.get('error_principal'),
                    'acierto_principal': groq_data.get('acierto_principal'),
                    'ajuste_confianza': groq_data.get('ajuste_confianza', 'mantener'),
                    'ajuste_timing': groq_data.get('ajuste_timing', 'mantener'),
                    'patron_identificado': groq_data.get('patron_identificado', ''),
                    'recomendacion_especifica': groq_data.get('recomendacion_especifica', '')
                }
            
            # Si no puede parsear JSON, usar respuesta como texto
            return {
                'source': source,
                'analisis_profundo': response[:500] if len(response) > 500 else response,
                'factor_clave': 'Ver análisis profundo',
                'error_principal': None,
                'acierto_principal': None,
                'ajuste_confianza': 'mantener',
                'ajuste_timing': 'mantener',
                'patron_identificado': '',
                'recomendacion_especifica': ''
            }
        
        except Exception as e:
            print(f"❌ Error completo en análisis Groq/Ollama: {e}")
            return {
                'error': str(e),
                'analisis_profundo': 'Error en análisis de IA',
                'source': 'Error'
            }
    
    def _apply_groq_recommendations(self):
        """
        Aplica las recomendaciones de Groq de las últimas operaciones
        """
        if not self.trade_history:
            return
        
        # Analizar últimas 5 operaciones con insights de Groq
        recent_with_groq = [t for t in self.trade_history[-5:] if 'groq_insights' in t]
        
        if not recent_with_groq:
            return
        
        # Contar recomendaciones de ajuste de confianza
        aumentar_confianza = sum(1 for t in recent_with_groq 
                                 if t.get('groq_insights', {}).get('ajuste_confianza') == 'aumentar')
        reducir_confianza = sum(1 for t in recent_with_groq 
                               if t.get('groq_insights', {}).get('ajuste_confianza') == 'reducir')
        
        # Aplicar ajuste de confianza
        if aumentar_confianza >= 3:
            self.recommended_min_confidence = min(0.85, self.recommended_min_confidence + 0.05)
        elif reducir_confianza >= 3:
            self.recommended_min_confidence = max(0.60, self.recommended_min_confidence - 0.05)
        
        # Contar recomendaciones de timing
        esperar_mas = sum(1 for t in recent_with_groq 
                         if t.get('groq_insights', {}).get('ajuste_timing') == 'esperar_mas')
        
        # Aplicar ajuste de timing
        if esperar_mas >= 3:
            self.recommended_wait_time = min(60, self.recommended_wait_time + 15)
        elif esperar_mas == 0:
            self.recommended_wait_time = max(0, self.recommended_wait_time - 10)
    
    def get_intelligence_summary(self):
        """Obtiene resumen de inteligencia acumulada"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'recommendations': []
            }
        
        total = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t['won'])
        win_rate = (wins / total) * 100 if total > 0 else 0
        
        return {
            'total_trades': total,
            'wins': wins,
            'losses': total - wins,
            'win_rate': win_rate,
            'recommended_min_confidence': self.recommended_min_confidence,
            'recommended_wait_time': self.recommended_wait_time,
            'recommended_score_threshold': self.recommended_score_threshold,
            'winning_patterns_count': len(self.winning_patterns),
            'losing_patterns_count': len(self.losing_patterns),
            'recommendations': self._generate_recommendations()
        }
