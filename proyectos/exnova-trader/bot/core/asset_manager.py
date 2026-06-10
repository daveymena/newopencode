import time
from data.market_data import MarketDataHandler

# Importar scorer refinado (DISABLED)
# Causa problemas. Usando sistema base existente.
try:
    # from core.refined_opportunity_scorer import RefinedOpportunityScorer
    REFINED_SCORER_AVAILABLE = False
except ImportError:
    REFINED_SCORER_AVAILABLE = False

class AssetManager:
    def __init__(self, market_data: MarketDataHandler):
        self.market_data = market_data
        self.current_asset = "EURUSD-OTC"
        self.current_type = "turbo" # turbo o binary
        self.min_profit = 70 # % mínimo para operar (reducido de 75 a 70)
        
        # 🎯 MODO MULTI-DIVISA
        self.multi_asset_mode = True  # Monitorear múltiples activos
        self.monitored_assets = []  # Activos siendo monitoreados
        self.asset_scores = {}  # Scores de cada activo
        
        # 🎯 Scoring refinado
        if REFINED_SCORER_AVAILABLE:
            self.refined_scorer = RefinedOpportunityScorer()
        else:
            self.refined_scorer = None
        
        # Lista de activos OTC disponibles 24/7
        self.otc_assets = [
            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC",
            "AUDUSD-OTC", "EURJPY-OTC",
            "EURGBP-OTC", "GBPJPY-OTC", "AUDJPY-OTC"
        ]
        
        # Lista de activos normales (horario de mercado)
        self.normal_assets = [
            "EURUSD", "GBPUSD", "USDJPY",
            "AUDUSD", "EURJPY"
        ]

    def find_best_asset(self, prefer_otc=True):
        """
        Busca el mejor activo disponible para operar.
        
        Args:
            prefer_otc: Si True, prioriza activos OTC (disponibles 24/7)
        """
        if not self.market_data.connected:
            print("⚠️ No conectado al broker")
            return None
        
        print("🔍 Escaneando mercado en busca de oportunidades...")
        
        try:
            # Obtener todos los activos con sus rentabilidades
            assets = self.market_data.get_open_assets(self.min_profit)
            
            if assets:
                # Filtrar por OTC si se prefiere
                if prefer_otc:
                    otc_assets = [a for a in assets if '-OTC' in a['name']]
                    if otc_assets:
                        best_asset = otc_assets[0]
                        print(f"💎 Mejor activo OTC: {best_asset['name']} (Profit: {best_asset['profit']:.0f}%)")
                        self.current_asset = best_asset['name']
                        self.current_type = best_asset['type']
                        return self.current_asset
                
                # Si no hay OTC o no se prefiere, usar el mejor disponible
                best_asset = assets[0]
                print(f"💎 Mejor activo: {best_asset['name']} (Profit: {best_asset['profit']:.0f}%)")
                self.current_asset = best_asset['name']
                self.current_type = best_asset['type']
                return self.current_asset
            
            # Si no se encontraron activos con get_open_assets, probar manualmente
            print("⚠️ No se encontraron activos con get_open_assets()")
            print("🔄 Probando activos OTC manualmente...")
            
            # Probar cada activo OTC
            for asset in self.otc_assets:
                try:
                    # Intentar obtener una vela para verificar si está disponible
                    df = self.market_data.get_candles(asset, 60, 1, time.time())
                    if not df.empty:
                        print(f"✅ Activo disponible: {asset}")
                        self.current_asset = asset
                        return asset
                except:
                    continue
            
            print("⚠️ No se encontraron activos OTC disponibles")
            
            # Como último recurso, probar activos normales
            print("🔄 Probando activos normales...")
            for asset in self.normal_assets:
                try:
                    df = self.market_data.get_candles(asset, 60, 1, time.time())
                    if not df.empty:
                        print(f"✅ Activo disponible: {asset}")
                        self.current_asset = asset
                        return asset
                except:
                    continue
            
            print("❌ No se encontraron activos operables")
            return None
            
        except Exception as e:
            print(f"❌ Error buscando activos: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_available_otc_assets(self, verbose=False):
        """
        Devuelve lista de activos OTC disponibles
        Verifica cada activo y solo incluye los que tienen datos
        """
        available = []
        unavailable = []
        
        if verbose:
            print("🔍 Verificando disponibilidad de activos...")
        
        for asset in self.otc_assets:
            try:
                df = self.market_data.get_candles(asset, 60, 1, time.time())
                if not df.empty:
                    available.append(asset)
                    if verbose:
                        print(f"   ✅ {asset} - Disponible")
                else:
                    unavailable.append(asset)
                    if verbose:
                        print(f"   ❌ {asset} - No disponible")
            except Exception as e:
                unavailable.append(asset)
                if verbose:
                    print(f"   ❌ {asset} - Error: {e}")
                continue
        
        if verbose:
            print(f"\n📊 Resumen:")
            print(f"   Disponibles: {len(available)}")
            print(f"   No disponibles: {len(unavailable)}")
        
        return available
    
    def update_available_assets(self):
        """
        Actualiza la lista de activos disponibles
        Debe llamarse periódicamente para mantener la lista actualizada
        """
        new_available = self.get_available_otc_assets(verbose=False)
        
        # Detectar cambios
        added = set(new_available) - set(self.monitored_assets)
        removed = set(self.monitored_assets) - set(new_available)
        
        if added:
            print(f"✅ Activos agregados: {', '.join(added)}")
        
        if removed:
            print(f"❌ Activos removidos: {', '.join(removed)}")
        
        # Actualizar lista
        self.monitored_assets = new_available
        
        return {
            'available': new_available,
            'added': list(added),
            'removed': list(removed),
            'total': len(new_available)
        }

    def check_asset_status(self):
        """Verifica si el activo actual sigue siendo válido."""
        try:
            df = self.market_data.get_candles(self.current_asset, 60, 1, time.time())
            return not df.empty
        except:
            return False
    
    def scan_best_opportunity(self, feature_engineer=None):
        """
        🎯 ESCANEA MÚLTIPLES ACTIVOS Y ELIGE EL MEJOR MOMENTO
        
        Analiza todos los activos monitoreados y devuelve el que tiene:
        - Mejor setup técnico
        - Mayor probabilidad de éxito
        - Momento óptimo para operar
        
        Returns:
            dict: {
                'asset': str,
                'score': float (0-100),
                'action': str (CALL/PUT),
                'confidence': float (0-1),
                'indicators': dict,
                'reasoning': str
            } o None si no hay oportunidades
        """
        if not self.market_data.connected:
            return None
        
        # Obtener lista de activos a monitorear
        if not self.monitored_assets:
            self.monitored_assets = self.get_available_otc_assets()
            if not self.monitored_assets:
                return None
        
        best_opportunity = None
        best_score = 0
        
        for asset in self.monitored_assets:
            try:
                # Obtener datos del activo
                df = self.market_data.get_candles(asset, 60, 100, time.time())
                if df.empty or len(df) < 50:
                    continue
                
                # Aplicar feature engineering si está disponible
                if feature_engineer:
                    df = feature_engineer.prepare_for_rl(df)
                
                # 🎯 USAR SCORING REFINADO SI ESTÁ DISPONIBLE
                if self.refined_scorer:
                    power_levels = self._get_power_levels(asset)
                    refined_analysis = self.refined_scorer.calculate_score(df, asset, power_levels)
                    
                    if refined_analysis['score'] > best_score:
                        best_score = refined_analysis['score']
                        best_opportunity = {
                            'asset': asset,
                            'score': refined_analysis['score'],
                            'action': refined_analysis['action'],
                            'confidence': refined_analysis['confidence'],
                            'indicators': refined_analysis['details'],
                            'reasoning': ', '.join(refined_analysis['reasons'][:3])
                        }
                    continue
                
                # Analizar el activo
                analysis = self._analyze_asset_opportunity(df, asset)
                
                if analysis and analysis['score'] > best_score:
                    best_score = analysis['score']
                    best_opportunity = analysis
                    
            except Exception as e:
                continue
        
        # Solo retornar si encontró un setup técnico con score >= 15 (REFINADO)
        min_score_threshold = 15 if self.refined_scorer else 5
        if best_opportunity and best_opportunity['score'] >= min_score_threshold:
            return best_opportunity
        
        return None
    
    def _get_power_levels(self, asset):
        """Identifica Zonas de Liquidez e Interés en M15 y M30"""
        try:
            # Pedir velas de M15 y M30 para contexto macro
            df_m15 = self.market_data.get_candles(asset, 900, 50)
            if df_m15.empty: return None
            
            # Niveles Extremos (Los muros de verdad)
            major_res = df_m15['high'].max()
            major_supp = df_m15['low'].min()
            
            # Niveles Recientes (Posibles trampas de liquidez)
            recent_high = df_m15['high'].tail(15).max() # Aumentado a 15 velas
            recent_low = df_m15['low'].tail(15).min()
            
            # Detectar si el nivel reciente es una trampa (hay uno más extremo muy cerca)
            # RANGO TRAP: 0.1% a 0.3% (Aumentado para detectar trampas visuales claras como la del usuario)
            trap_margin_min = 0.0005 # 0.05%
            trap_margin_max = 0.0030 # 0.30%
            
            # CALL TRAP: Low reciente es falso, hay un soporte mayor un poco más abajo
            dist_supp = abs(recent_low - major_supp) / major_supp
            is_trap_call = (dist_supp > trap_margin_min and dist_supp < trap_margin_max)
            
            # PUT TRAP: High reciente es falso, hay una resistencia mayor un poco más arriba
            dist_res = abs(major_res - recent_high) / major_res
            is_trap_put = (dist_res > trap_margin_min and dist_res < trap_margin_max)
            
            return {
                'major_res': major_res,
                'major_supp': major_supp,
                'recent_high': recent_high,
                'recent_low': recent_low,
                'is_trap_call': is_trap_call,
                'is_trap_put': is_trap_put
            }
        except:
            return None

    def _analyze_asset_opportunity(self, df, asset):
        """
        Analiza el activo buscando setups de alta probabilidad basados en Niveles MTF
        """
        try:
            if df.empty or len(df) < 50:
                return None
            
            # 🏢 OBTENER NIVELES INSTITUCIONALES (M15)
            power_levels = self._get_power_levels(asset)
            
            last = df.iloc[-1]
            price = last['close']
            rsi = last.get('rsi', 50)
            
            # Calcular SMAs
            sma_20 = df['close'].tail(20).mean()
            sma_50 = df['close'].tail(50).mean()
            
            # Importar pandas y math para validación
            import pandas as pd
            import math
            
            # Verificar si son NaN
            if pd.isna(sma_20) or pd.isna(sma_50) or math.isnan(sma_20) or math.isnan(sma_50):
                return None

            # Bollinger
            bb_upper = last.get('bb_high', 0)
            bb_lower = last.get('bb_low', 0)
            
            setup_found = None
            action = None
            confidence = 0
            reasons = []
            
            # LOG SIMPLE (SIN EMOJIS CRITICOS POR AHORA)
            print(f"\n   Analizando {asset} | RSI: {rsi:.1f} | Precio: {price:.5f}")

            # ---------------------------------------------------------
            # ESTRATEGIA 1: SEGUIMIENTO DE TENDENCIA (TREND FOLLOWING)
            # ---------------------------------------------------------
            # 🛡️ FILTRO DE AGOTAMIENTO (ANTI-CONFIRMACIÓN TARDÍA)
            # Calculamos el tamaño promedio de los cuerpos de las últimas 10 velas
            df_recent = df.tail(11).copy()
            df_recent['body_size'] = abs(df_recent['close'] - df_recent['open'])
            avg_body = df_recent['body_size'].iloc[:-1].mean()
            current_body = abs(last['close'] - last['open'])
            
            is_exhaustion = current_body > (avg_body * 2.5) and avg_body > 0
            
            is_uptrend = sma_20 > sma_50
            is_downtrend = sma_20 < sma_50
            trend_strength = abs(sma_20 - sma_50) / (sma_50 if sma_50 != 0 else 1)
            
            if is_exhaustion:
                # Si la vela es gigante, el movimiento probablemente ya terminó
                # print(f"      🛡️ Bloqueando entrada por VELA DE AGOTAMIENTO (Tamaño: {current_body:.5f} vs Avg: {avg_body:.5f})")
                pass
            
            # Definir variables locales (M1)
            local_low = df['low'].min()
            local_high = df['high'].max()
            last = df.iloc[-1]
            price = last['close']
            
            # --- LÓGICA DE DIVERGENCIA AVANZADA (Opcional) ---
            # CALL EN TENDENCIA (Pullback alcista)
            if is_uptrend and trend_strength > 0.0005:
                # 🛡️ FILTRO DE NIVEL (Lógica de Muros)
                major_high = df['high'].tail(50).max()
                local_high = df['high'].tail(20).max()
                nearest_resistance = max(major_high, local_high)
                
                dist_to_res = abs(nearest_resistance - price) / (nearest_resistance if nearest_resistance != 0 else 1)
                
                # Exigir más espacio si el RSI ya está subiendo
                min_safe_dist = 0.0008 if rsi > 60 else 0.0004
                
                if dist_to_res < min_safe_dist:
                    # Bloqueado: No hay espacio para que el CALL respire
                    pass
                else:
                    dist_sma20 = (price - sma_20) / (sma_20 if sma_20 != 0 else 1)
                    if -0.001 < dist_sma20 < 0.002: # Precio cerca de SMA20
                        if rsi > 40 and rsi < 65:
                            if last['close'] > last['open']: 
                                setup_found = "TREND_PULLBACK_CALL"
                                action = "CALL"
                                confidence = 0.85
                                reasons.append("Tendencia Alcista Fuerte")
                                reasons.append("Espacio libre hacia Resistencia")
                                reasons.append("Vela de confirmacion alcista")

            # PUT EN TENDENCIA (Pullback bajista)
            elif is_downtrend and trend_strength > 0.0005:
                # 🛡️ FILTRO DE NIVEL (Lógica de Suelos)
                major_low = df['low'].tail(50).min()
                local_low = df['low'].tail(20).min()
                nearest_support = min(major_low, local_low)
                
                dist_to_supp = abs(price - nearest_support) / (price if price != 0 else 1)
                
                # Exigir más espacio si el RSI ya está bajando
                min_safe_dist = 0.0008 if rsi < 40 else 0.0004
                
                if dist_to_supp < min_safe_dist:
                    # Bloqueado: No vender contra el suelo
                    pass
                else:
                    dist_sma20 = (sma_20 - price) / (sma_20 if sma_20 != 0 else 1)
                    if -0.001 < dist_sma20 < 0.002: 
                        if rsi < 60 and rsi > 35: 
                            if last['close'] < last['open']:
                                setup_found = "TREND_PULLBACK_PUT"
                                action = "PUT"
                                confidence = 0.85
                                reasons.append("Tendencia Bajista Fuerte")
                                reasons.append("Espacio libre hacia Soporte")
                                reasons.append("Vela de confirmacion bajista")

            # CALL EN TENDENCIA (Pullback alcista) - Implícito en la lógica similar para alcista
            # (Se aplicaría lógica análoga si estuviera visible aquí, pero nos enfocamos en el PUT que falló)

            # 🏢 ESTRATEGIA: PANORAMA COMPLETO (MTF REVERSAL)
            # ---------------------------------------------------------
            # 🏢 ESTRATEGIA: PANORAMA COMPLETO (MTF REVERSAL)
            # ---------------------------------------------------------
            if power_levels:
                target_supp = power_levels['major_supp'] if power_levels['is_trap_call'] else power_levels['recent_low']
                target_res  = power_levels['major_res'] if power_levels['is_trap_put'] else power_levels['recent_high']
                
                dist_to_supp = abs(price - target_supp) / price
                dist_to_res  = abs(price - target_res) / price
                
                # 🎯 PUNTO DE EQUILIBRIO: Margen de 0.12% con verificación de mecha
                # Queremos entrar cuando el precio esté "hundido" en el soporte (CALL)
                if rsi < 30 and dist_to_supp < 0.0012:
                    # Buscamos rechazo ya iniciado (mecha)
                    lower_wick = min(last['open'], last['close']) - last['low']
                    # SWEET SPOT: Si el precio actual está cerca del mínimo, tenemos ventaja
                    is_in_sweet_spot = price <= last['open'] * 1.0005 
                    
                    if lower_wick > 0.00003 and is_in_sweet_spot:
                        setup_found = "BALANCED_ROOT_CALL"
                        if power_levels['is_trap_call']: setup_found = "SMC_SWEEP_CALL"
                        
                        action = "CALL"
                        confidence = 0.95
                        reasons.append("Equilibrio: Nivel MTF + Sweet Spot + RSI < 30")
                        reasons.append("Entrada en zona de mecha (Raíz)")
                
                # 🎯 PUNTO DE EQUILIBRIO: Margen de 0.12% para PUT
                elif rsi > 70 and dist_to_res < 0.0012:
                    upper_wick = last['high'] - max(last['open'], last['close'])
                    is_in_sweet_spot = price >= last['open'] * 0.9995
                    
                    if upper_wick > 0.00003 and is_in_sweet_spot:
                        setup_found = "BALANCED_ROOT_PUT"
                        if power_levels['is_trap_put']: setup_found = "SMC_SWEEP_PUT"
                        
                        action = "PUT"
                        confidence = 0.95
                        reasons.append("Equilibrio: Nivel MTF + Sweet Spot")
                        reasons.append("Entrada en zona de mecha (Raíz)")

            # ---------------------------------------------------------
            # ESTRATEGIA: REVERSIÓN ESTÁNDAR M1 (Si no hay MTF cerca)
            # ---------------------------------------------------------
            if not setup_found:
                # REVERSIÓN ALCISTA (CALL) - RSI Relajado
                if rsi < 35 and price <= local_low * 1.0005:
                    setup_found = "M1_REVERSAL_CALL"
                    action = "CALL"
                    confidence = 0.75
                # REVERSIÓN BAJISTA (PUT) - RSI Relajado
                elif rsi > 65 and price >= local_high * 0.9995:
                    setup_found = "M1_REVERSAL_PUT"
                    action = "PUT"
                    confidence = 0.75

            # ---------------------------------------------------------
            # 🛡️ PROTECCIÓN DE "NIVEL MEJOR" (Avoid Liquidity Traps)
            # Si hay una reversión M1, verificar que no haya un muro grande "justo arriba"
            # ---------------------------------------------------------
            if setup_found and "M1_REVERSAL" in setup_found and power_levels:
                # Caso PUT: Verificar si hay resistencia mayor cerca
                if action == "PUT":
                    dist_major_res = (power_levels['major_res'] - price) / price
                    # Si la resistencia mayor está entre 0.05% y 0.3% arriba.
                    if 0.0005 < dist_major_res < 0.0030:
                        print(f"      ⚠️ POSIBLE TRAMPA: Resistencia Mayor a {dist_major_res*100:.3f}% arriba. Operando con precaución.")
                        confidence *= 0.8 # Reducir confianza en lugar de anular
                
                # Caso CALL: Verificar si hay soporte mayor cerca
                elif action == "CALL":
                    dist_major_supp = (price - power_levels['major_supp']) / price
                    # Si el soporte mayor está entre 0.05% y 0.3% abajo.
                    if 0.0005 < dist_major_supp < 0.0030:
                        print(f"      ⚠️ POSIBLE TRAMPA: Soporte Mayor a {dist_major_supp*100:.3f}% abajo. Operando con precaución.")
                        confidence *= 0.8 # Reducir confianza en lugar de anular

            # ---------------------------------------------------------
            # RESULTADO DEL ANÁLISIS
            # ---------------------------------------------------------
            if setup_found:
                print(f"      SETUP ENCONTRADO: {setup_found}")
                print(f"      Accion: {action} | Confianza: {confidence*100:.0f}%")
                
                return {
                    'asset': asset,
                    'score': int(confidence * 100),
                    'action': action,
                    'confidence': confidence,
                    'setup': setup_found,
                    'indicators': {
                        'rsi': rsi,
                        'price': price,
                        'sma_20': sma_20,
                        'trend': "ALCISTA" if is_uptrend else "BAJISTA"
                    },
                    'reasoning': ", ".join(reasons)
                }
            else:
                # print(f"      Ningun setup claro...") # Reducir ruido
                return None

        except Exception as e:
            print(f"❌ Error analizando {asset}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None



