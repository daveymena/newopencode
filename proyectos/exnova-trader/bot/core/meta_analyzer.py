"""
Meta Analyzer - Sistema de auto-razonamiento y auto-corrección
Analiza profundamente cada operación y se corrige a sí mismo
"""
import json
from pathlib import Path
from datetime import datetime
import numpy as np

class MetaAnalyzer:
    """
    Sistema que se analiza a sí mismo y se auto-corrige
    - Analiza por qué perdió/ganó
    - Detecta errores en su propia lógica
    - Se auto-corrige basado en evidencia
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.db_path = Path("data/meta_analysis.json")
        self.analysis_history = []
        self.corrections_made = []
        self.logic_errors_detected = []
        
        # Hipótesis actuales del sistema
        self.current_hypotheses = {
            'rsi_oversold_works': True,  # ¿RSI sobreventa + CALL funciona?
            'rsi_overbought_works': True,  # ¿RSI sobrecompra + PUT funciona?
            'trend_following_works': True,  # ¿Seguir tendencia funciona?
            'counter_trend_works': False,  # ¿Contra-tendencia funciona?
            'high_confidence_reliable': True,  # ¿Alta confianza = éxito?
            'fvg_mitigation_works': True,  # ¿Mitigación de FVG funciona?
            'ollama_adds_value': True,  # ¿Ollama mejora decisiones?
        }
        
        # Evidencia acumulada para cada hipótesis
        self.evidence = {key: {'support': 0, 'against': 0} for key in self.current_hypotheses.keys()}
        
        self.load_meta_data()
    
    def load_meta_data(self):
        """Carga datos de meta-análisis"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.analysis_history = data.get('history', [])
                    self.corrections_made = data.get('corrections', [])
                    self.current_hypotheses = data.get('hypotheses', self.current_hypotheses)
                    self.evidence = data.get('evidence', self.evidence)
                    print(f"🧠 Meta-Análisis cargado: {len(self.corrections_made)} correcciones previas")
            except Exception as e:
                print(f"⚠️ Error cargando meta-análisis: {e}")
    
    def save_meta_data(self):
        """Guarda datos de meta-análisis"""
        try:
            self.db_path.parent.mkdir(exist_ok=True)
            data = {
                'history': self.analysis_history[-100:],
                'corrections': self.corrections_made[-50:],
                'hypotheses': self.current_hypotheses,
                'evidence': self.evidence
            }
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error guardando meta-análisis: {e}")
    
    def deep_analyze_result(self, trade_data, result, market_context):
        """
        Análisis profundo de por qué ganó o perdió
        Incluye auto-razonamiento y detección de errores lógicos
        """
        won = result.get('won', False)
        profit = result.get('profit', 0)
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'trade_id': trade_data.get('order_id'),
            'asset': trade_data.get('asset'),
            'action': trade_data.get('direction'),
            'won': won,
            'profit': profit,
            'deep_reasons': [],
            'logic_errors': [],
            'corrections_needed': [],
            'hypothesis_updates': []
        }
        
        # 1. ANÁLISIS TÉCNICO PROFUNDO
        technical_analysis = self._analyze_technical_factors(trade_data, won, market_context)
        analysis['deep_reasons'].extend(technical_analysis['reasons'])
        
        # 2. ANÁLISIS DE DECISIÓN
        decision_analysis = self._analyze_decision_quality(trade_data, won, market_context)
        analysis['deep_reasons'].extend(decision_analysis['reasons'])
        
        # 3. DETECCIÓN DE ERRORES LÓGICOS
        logic_errors = self._detect_logic_errors(trade_data, won, market_context)
        analysis['logic_errors'] = logic_errors
        
        # 4. ACTUALIZAR HIPÓTESIS CON EVIDENCIA
        hypothesis_updates = self._update_hypotheses(trade_data, won, market_context)
        analysis['hypothesis_updates'] = hypothesis_updates
        
        # 5. GENERAR CORRECCIONES
        corrections = self._generate_corrections(logic_errors, hypothesis_updates)
        analysis['corrections_needed'] = corrections
        
        # 6. ANÁLISIS CON LLM (si disponible)
        if self.llm_client:
            llm_analysis = self._get_llm_deep_reasoning(trade_data, result, market_context, analysis)
            analysis['llm_reasoning'] = llm_analysis
        
        # Guardar análisis
        self.analysis_history.append(analysis)
        
        # Aplicar correcciones si es necesario
        if corrections:
            self._apply_corrections(corrections)
        
        self.save_meta_data()
        
        return analysis
    
    def _analyze_technical_factors(self, trade_data, won, market_context):
        """Analiza factores técnicos profundamente"""
        reasons = []
        
        rsi = market_context.get('rsi', 50)
        action = trade_data.get('direction', '').lower()
        macd = market_context.get('macd', 0)
        trend = market_context.get('trend', 'neutral')
        
        # ANÁLISIS RSI
        if action == 'call':
            if rsi < 30:
                if won:
                    reasons.append(f"✅ RSI sobreventa ({rsi:.1f}) + CALL funcionó → Hipótesis confirmada")
                    self.evidence['rsi_oversold_works']['support'] += 1
                else:
                    reasons.append(f"❌ RSI sobreventa ({rsi:.1f}) + CALL falló → ¿Por qué? Analizar contexto")
                    self.evidence['rsi_oversold_works']['against'] += 1
                    
                    # Auto-razonamiento: ¿Por qué falló si RSI estaba bien?
                    if trend == 'downtrend':
                        reasons.append(f"   🔍 RAZÓN: Tendencia bajista dominó sobre RSI sobreventa")
                        reasons.append(f"   💡 LECCIÓN: RSI sobreventa NO funciona en tendencia bajista fuerte")
            elif rsi > 50:
                if not won:
                    reasons.append(f"❌ RSI alto ({rsi:.1f}) + CALL fue mala idea → Error lógico detectado")
                    reasons.append(f"   🔧 CORRECCIÓN: NO operar CALL con RSI > 50")
        
        elif action == 'put':
            if rsi > 70:
                if won:
                    reasons.append(f"✅ RSI sobrecompra ({rsi:.1f}) + PUT funcionó → Hipótesis confirmada")
                    self.evidence['rsi_overbought_works']['support'] += 1
                else:
                    reasons.append(f"❌ RSI sobrecompra ({rsi:.1f}) + PUT falló → Analizar por qué")
                    self.evidence['rsi_overbought_works']['against'] += 1
                    
                    if trend == 'uptrend':
                        reasons.append(f"   🔍 RAZÓN: Tendencia alcista dominó sobre RSI sobrecompra")
                        reasons.append(f"   💡 LECCIÓN: RSI sobrecompra NO funciona en tendencia alcista fuerte")
            elif rsi < 50:
                if not won:
                    reasons.append(f"❌ RSI bajo ({rsi:.1f}) + PUT fue mala idea → Error lógico detectado")
                    reasons.append(f"   🔧 CORRECCIÓN: NO operar PUT con RSI < 50")
        
        # ANÁLISIS TENDENCIA
        if 'uptrend' in trend and action == 'call':
            if won:
                reasons.append(f"✅ Seguir tendencia alcista funcionó")
                self.evidence['trend_following_works']['support'] += 1
            else:
                reasons.append(f"❌ Seguir tendencia alcista falló → ¿Cambio de tendencia?")
        
        if 'downtrend' in trend and action == 'put':
            if won:
                reasons.append(f"✅ Seguir tendencia bajista funcionó")
                self.evidence['trend_following_works']['support'] += 1
            else:
                reasons.append(f"❌ Seguir tendencia bajista falló → ¿Cambio de tendencia?")
        
        # CONTRA-TENDENCIA
        if ('uptrend' in trend and action == 'put') or ('downtrend' in trend and action == 'call'):
            if won:
                reasons.append(f"✅ Contra-tendencia funcionó → Revisar hipótesis")
                self.evidence['counter_trend_works']['support'] += 1
            else:
                reasons.append(f"❌ Contra-tendencia falló → Hipótesis confirmada (evitar)")
                self.evidence['counter_trend_works']['against'] += 1
        
        return {'reasons': reasons}
    
    def _analyze_decision_quality(self, trade_data, won, market_context):
        """Analiza la calidad de la decisión tomada"""
        reasons = []
        
        confidence = trade_data.get('confidence', 0)
        setup_type = trade_data.get('setup_type', 'unknown')
        
        # ANÁLISIS DE CONFIANZA
        if confidence >= 80:
            if won:
                reasons.append(f"✅ Alta confianza ({confidence}%) fue correcta")
                self.evidence['high_confidence_reliable']['support'] += 1
            else:
                reasons.append(f"❌ Alta confianza ({confidence}%) fue incorrecta → ERROR GRAVE")
                reasons.append(f"   🔍 ANÁLISIS: ¿Qué falló en el cálculo de confianza?")
                self.evidence['high_confidence_reliable']['against'] += 1
                
                # Auto-razonamiento: ¿Por qué la confianza estaba mal?
                rsi = market_context.get('rsi', 50)
                if 45 < rsi < 55:
                    reasons.append(f"   💡 CAUSA: RSI neutral ({rsi:.1f}) no debió dar alta confianza")
                    reasons.append(f"   🔧 CORRECCIÓN: Penalizar confianza cuando RSI está neutral")
        
        elif confidence < 70:
            if won:
                reasons.append(f"✅ Baja confianza ({confidence}%) pero ganó → Subestimamos la oportunidad")
                reasons.append(f"   💡 LECCIÓN: Revisar cálculo de confianza para este setup")
        
        # ANÁLISIS DE SETUP
        if setup_type == 'M1_REVERSAL_CALL' or setup_type == 'M1_REVERSAL_PUT':
            if won:
                reasons.append(f"✅ Setup de reversión M1 funcionó")
            else:
                reasons.append(f"❌ Setup de reversión M1 falló")
                reasons.append(f"   🔍 PREGUNTA: ¿Fue reversión real o falsa señal?")
                
                # Verificar si había confirmación
                if market_context.get('macd', 0) * (1 if 'CALL' in setup_type else -1) < 0:
                    reasons.append(f"   💡 CAUSA: MACD no confirmó la reversión")
                    reasons.append(f"   🔧 CORRECCIÓN: Exigir confirmación de MACD en reversiones")
        
        return {'reasons': reasons}
    
    def _detect_logic_errors(self, trade_data, won, market_context):
        """Detecta errores en la lógica de decisión"""
        errors = []
        
        rsi = market_context.get('rsi', 50)
        action = trade_data.get('direction', '').lower()
        confidence = trade_data.get('confidence', 0)
        trend = market_context.get('trend', 'neutral')
        
        # ERROR 1: RSI neutral con alta confianza
        if 45 < rsi < 55 and confidence > 75:
            errors.append({
                'type': 'confidence_calculation_error',
                'description': f'RSI neutral ({rsi:.1f}) no debería dar confianza {confidence}%',
                'severity': 'HIGH',
                'correction': 'Penalizar confianza cuando RSI está en zona neutral (45-55)'
            })
        
        # ERROR 2: Contra-tendencia sin justificación
        if (('uptrend' in trend and action == 'put') or ('downtrend' in trend and action == 'call')):
            if not market_context.get('fvg_detected', False):
                errors.append({
                    'type': 'counter_trend_without_reason',
                    'description': f'Operó contra tendencia {trend} sin FVG u Order Block',
                    'severity': 'MEDIUM',
                    'correction': 'Solo operar contra-tendencia si hay FVG o Order Block confirmado'
                })
        
        # ERROR 3: Baja volatilidad con expiración corta
        atr = market_context.get('atr', 0)
        if atr < 0.0003 and trade_data.get('duration', 60) <= 60:
            errors.append({
                'type': 'volatility_mismatch',
                'description': f'Baja volatilidad (ATR {atr:.5f}) con expiración corta',
                'severity': 'LOW',
                'correction': 'Usar expiración más larga (3-5 min) cuando volatilidad es baja'
            })
        
        # ERROR 4: Ollama rechazó pero se ejecutó igual
        if market_context.get('ollama_rejected', False) and not won:
            errors.append({
                'type': 'ignored_ollama_warning',
                'description': 'Ollama rechazó pero se ejecutó con fast-track y perdió',
                'severity': 'HIGH',
                'correction': 'Revisar criterios de fast-track - Ollama tenía razón'
            })
        
        return errors
    
    def _update_hypotheses(self, trade_data, won, market_context):
        """Actualiza hipótesis basado en evidencia"""
        updates = []
        
        # Revisar cada hipótesis
        for hypothesis, is_valid in self.current_hypotheses.items():
            evidence = self.evidence[hypothesis]
            total = evidence['support'] + evidence['against']
            
            if total >= 10:  # Suficiente evidencia para evaluar
                support_rate = evidence['support'] / total
                
                # Si hipótesis es válida pero evidencia dice lo contrario
                if is_valid and support_rate < 0.4:
                    self.current_hypotheses[hypothesis] = False
                    updates.append({
                        'hypothesis': hypothesis,
                        'old_value': True,
                        'new_value': False,
                        'reason': f'Evidencia insuficiente: {support_rate*100:.1f}% de soporte',
                        'evidence': evidence
                    })
                
                # Si hipótesis es inválida pero evidencia dice lo contrario
                elif not is_valid and support_rate > 0.6:
                    self.current_hypotheses[hypothesis] = True
                    updates.append({
                        'hypothesis': hypothesis,
                        'old_value': False,
                        'new_value': True,
                        'reason': f'Evidencia fuerte: {support_rate*100:.1f}% de soporte',
                        'evidence': evidence
                    })
        
        return updates
    
    def _generate_corrections(self, logic_errors, hypothesis_updates):
        """Genera correcciones basadas en errores y actualizaciones"""
        corrections = []
        
        # Correcciones por errores lógicos
        for error in logic_errors:
            if error['severity'] in ['HIGH', 'MEDIUM']:
                corrections.append({
                    'type': 'logic_fix',
                    'target': error['type'],
                    'action': error['correction'],
                    'priority': error['severity']
                })
        
        # Correcciones por cambios de hipótesis
        for update in hypothesis_updates:
            corrections.append({
                'type': 'hypothesis_change',
                'target': update['hypothesis'],
                'action': f"Cambiar de {update['old_value']} a {update['new_value']}",
                'reason': update['reason'],
                'priority': 'HIGH'
            })
        
        return corrections
    
    def _apply_corrections(self, corrections):
        """Aplica correcciones al sistema"""
        for correction in corrections:
            self.corrections_made.append({
                'timestamp': datetime.now().isoformat(),
                'correction': correction
            })
            
            print(f"\n🔧 AUTO-CORRECCIÓN APLICADA:")
            print(f"   Tipo: {correction['type']}")
            print(f"   Target: {correction['target']}")
            print(f"   Acción: {correction['action']}")
            print(f"   Prioridad: {correction.get('priority', 'NORMAL')}")
    
    def _get_llm_deep_reasoning(self, trade_data, result, market_context, preliminary_analysis):
        """Usa LLM para razonamiento profundo"""
        if not self.llm_client:
            return {}
        
        won = result.get('won', False)
        
        prompt = f"""
Eres un analista experto que debe RAZONAR PROFUNDAMENTE sobre esta operación.

OPERACIÓN:
- Activo: {trade_data.get('asset')}
- Acción: {trade_data.get('direction')}
- Resultado: {'GANÓ' if won else 'PERDIÓ'}
- Profit: ${result.get('profit', 0):.2f}

CONTEXTO DE MERCADO:
- RSI: {market_context.get('rsi', 'N/A')}
- Tendencia: {market_context.get('trend', 'N/A')}
- MACD: {market_context.get('macd', 'N/A')}
- Confianza: {trade_data.get('confidence', 0)}%

ANÁLISIS PRELIMINAR:
{json.dumps(preliminary_analysis.get('deep_reasons', []), indent=2)}

ERRORES LÓGICOS DETECTADOS:
{json.dumps(preliminary_analysis.get('logic_errors', []), indent=2)}

TU TAREA:
1. ¿Por qué {'ganó' if won else 'perdió'} REALMENTE? (razonamiento profundo)
2. ¿Qué error cometió el sistema? (si perdió)
3. ¿Qué hizo bien el sistema? (si ganó)
4. ¿Cómo debe corregirse el sistema?
5. ¿Qué hipótesis debe cambiar?

RESPONDE EN JSON:
{{
    "root_cause": "causa raíz del resultado",
    "system_error": "error del sistema (si perdió)" o null,
    "system_success": "acierto del sistema (si ganó)" o null,
    "correction_needed": "corrección específica necesaria",
    "hypothesis_to_change": "hipótesis que debe cambiar",
    "confidence_in_analysis": 0-100
}}
"""
        
        try:
            response = self.llm_client._safe_query(prompt)
            
            # Parsear JSON
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        
        except Exception as e:
            print(f"⚠️ Error en razonamiento LLM: {e}")
        
        return {}
    
    def get_meta_report(self):
        """Genera reporte de meta-análisis"""
        return {
            'total_analyses': len(self.analysis_history),
            'corrections_made': len(self.corrections_made),
            'current_hypotheses': self.current_hypotheses,
            'evidence_summary': {
                key: {
                    'support': ev['support'],
                    'against': ev['against'],
                    'support_rate': ev['support'] / (ev['support'] + ev['against']) if (ev['support'] + ev['against']) > 0 else 0
                }
                for key, ev in self.evidence.items()
            },
            'recent_corrections': self.corrections_made[-5:] if self.corrections_made else []
        }
