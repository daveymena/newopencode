"""
Unified Scoring Engine - Motor de Scoring Inteligente Consolidado
Reemplaza los ~20 filtros dispersos con un sistema coherente de scoring 0-100
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json


class SignalType(Enum):
    """Tipo de señal"""
    CALL = "CALL"
    PUT = "PUT"
    NEUTRAL = "NEUTRAL"


@dataclass
class ScoringCategory:
    """Categoría de scoring con peso configurable"""
    name: str
    weight: float  # Peso 0-1
    score: float = 0.0  # Score calculado 0-100
    breakdown: Dict[str, float] = None  # Detalle de sub-scores

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}


@dataclass
class ScoringResult:
    """Resultado del scoring completo"""
    total_score: float  # 0-100
    signal_type: SignalType
    confidence: float  # 0-1 (normalizado del score)
    categories: Dict[str, ScoringCategory]
    reasons_to_trade: List[str]
    warnings: List[str]
    expected_winrate: float  # Winrate estimado basado en score
    market_phase: str
    recommendation: str  # "TRADE", "WAIT", "AVOID"


class UnifiedScoringEngine:
    """
    Motor de Scoring Unificado

    Reemplaza ~20 filtros dispersos con 8 categorías ponderadas:
    1. Market Structure (20%) - Tendencias, soportes/resistencias
    2. Smart Money (20%) - Order blocks, FVG, liquidity
    3. Technical Indicators (15%) - RSI, MACD, EMA
    4. Multi-Timeframe (15%) - Alineación M1/M5/M15
    5. Risk Management (10%) - Ratio R:R, posición
    6. Temporal Context (10%) - Hora, sesión, noticias
    7. Momentum (5%) - Fuerza del movimiento
    8. Market Phase (5%) - Volatilidad, rango/tendencia

    Score final 0-100 -> Confianza 0-1 para Kelly Criterion
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.categories: Dict[str, ScoringCategory] = {}
        self._initialize_categories()

        # Umbrales - SELECTIVOS pero operables
        self.min_score_to_trade = 75  # Score mínimo para operar
        self.high_confidence_threshold = 85  # Score para alta confianza
        self.min_consecutive_filters_pass = 4  # Mínimo filtros que deben pasar

    def _default_config(self) -> Dict:
        """Configuración por defecto"""
        return {
            'weights': {
                'market_structure': 0.20,
                'smart_money': 0.20,
                'technical_indicators': 0.15,
                'multi_timeframe': 0.15,
                'risk_management': 0.10,
                'temporal_context': 0.10,
                'momentum': 0.05,
                'market_phase': 0.05,
            },
            'thresholds': {
                'min_score': 65,
                'high_confidence': 80,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'min_trend_strength': 0.6,
            }
        }

    def _initialize_categories(self):
        """Inicializar categorías de scoring"""
        weights = self.config['weights']
        self.categories = {
            'market_structure': ScoringCategory(
                name="Estructura de Mercado",
                weight=weights['market_structure']
            ),
            'smart_money': ScoringCategory(
                name="Smart Money",
                weight=weights['smart_money']
            ),
            'technical_indicators': ScoringCategory(
                name="Indicadores Técnicos",
                weight=weights['technical_indicators']
            ),
            'multi_timeframe': ScoringCategory(
                name="Multi-Timeframe",
                weight=weights['multi_timeframe']
            ),
            'risk_management': ScoringCategory(
                name="Gestión de Riesgo",
                weight=weights['risk_management']
            ),
            'temporal_context': ScoringCategory(
                name="Contexto Temporal",
                weight=weights['temporal_context']
            ),
            'momentum': ScoringCategory(
                name="Momentum",
                weight=weights['momentum']
            ),
            'market_phase': ScoringCategory(
                name="Fase de Mercado",
                weight=weights['market_phase']
            ),
        }

    def score(
        self,
        df: pd.DataFrame,
        df_m5: Optional[pd.DataFrame] = None,
        df_m15: Optional[pd.DataFrame] = None,
        current_price: float = 0.0,
        asset: str = "EUR/USD",
        account_balance: float = 100.0,
        smart_money_data: Optional[Dict] = None,
        market_structure_data: Optional[Dict] = None,
    ) -> ScoringResult:
        """
        Calcular score completo para una oportunidad de trading

        Args:
            df: DataFrame M1 con velas recientes
            df_m5: DataFrame M5 (opcional)
            df_m15: DataFrame M15 (opcional)
            current_price: Precio actual
            asset: Par de trading
            account_balance: Balance de la cuenta
            smart_money_data: Datos de Smart Money (order blocks, FVG, etc.)
            market_structure_data: Datos de estructura (trend, S/R, etc.)

        Returns:
            ScoringResult con score total y recomendación
        """
        reasons_to_trade = []
        warnings = []

        # 1. Market Structure (20%)
        ms_score, ms_breakdown, ms_reasons = self._score_market_structure(
            df, market_structure_data or {}
        )
        self.categories['market_structure'].score = ms_score
        self.categories['market_structure'].breakdown = ms_breakdown
        reasons_to_trade.extend(ms_reasons)

        # 2. Smart Money (20%)
        sm_score, sm_breakdown, sm_reasons = self._score_smart_money(
            df, smart_money_data or {}
        )
        self.categories['smart_money'].score = sm_score
        self.categories['smart_money'].breakdown = sm_breakdown
        reasons_to_trade.extend(sm_reasons)

        # 3. Technical Indicators (15%)
        tech_score, tech_breakdown, tech_reasons = self._score_technical_indicators(df)
        self.categories['technical_indicators'].score = tech_score
        self.categories['technical_indicators'].breakdown = tech_breakdown
        reasons_to_trade.extend(tech_reasons)

        # 4. Multi-Timeframe (15%)
        mtf_score, mtf_breakdown, mtf_reasons = self._score_multi_timeframe(
            df, df_m5, df_m15
        )
        self.categories['multi_timeframe'].score = mtf_score
        self.categories['multi_timeframe'].breakdown = mtf_breakdown
        reasons_to_trade.extend(mtf_reasons)

        # 5. Risk Management (10%)
        rm_score, rm_breakdown, rm_reasons = self._score_risk_management(
            df, current_price, account_balance
        )
        self.categories['risk_management'].score = rm_score
        self.categories['risk_management'].breakdown = rm_breakdown
        reasons_to_trade.extend(rm_reasons)

        # 6. Temporal Context (10%)
        tc_score, tc_breakdown, tc_reasons = self._score_temporal_context(asset)
        self.categories['temporal_context'].score = tc_score
        self.categories['temporal_context'].breakdown = tc_breakdown
        reasons_to_trade.extend(tc_reasons)

        # 7. Momentum (5%)
        mom_score, mom_breakdown, mom_reasons = self._score_momentum(df)
        self.categories['momentum'].score = mom_score
        self.categories['momentum'].breakdown = mom_breakdown
        reasons_to_trade.extend(mom_reasons)

        # 8. Market Phase (5%)
        mp_score, mp_breakdown, mp_reasons = self._score_market_phase(df)
        self.categories['market_phase'].score = mp_score
        self.categories['market_phase'].breakdown = mp_breakdown
        reasons_to_trade.extend(mp_reasons)

        # Calcular score total ponderado
        total_score = sum(
            cat.score * cat.weight
            for cat in self.categories.values()
        )

        # Determinar tipo de señal
        signal_type = self._determine_signal_type(df, total_score)

        # Calcular confianza normalizada
        confidence = total_score / 100.0

        # Determinar recomendación - SELECTIVO pero operable
        # Operar si score >= 75 y al menos 4 categorías tienen score >= 65
        high_score_categories = sum(1 for cat in self.categories.values() if cat.score >= 65)

        if total_score >= self.min_score_to_trade and high_score_categories >= 4:
            recommendation = "TRADE"
        elif total_score >= 65 and high_score_categories >= 3:
            recommendation = "WAIT"
        else:
            recommendation = "AVOID"
            warnings.append(f"Score {total_score:.1f} insuficiente ({high_score_categories}/8 categorias fuertes)")

        # Calcular winrate esperado (modelo lineal simple)
        # Score 65 -> ~55% winrate, Score 100 -> ~80% winrate
        expected_winrate = 0.40 + (total_score / 100) * 0.40
        expected_winrate = min(0.85, max(0.40, expected_winrate))

        # Determinar fase de mercado
        market_phase = self._determine_market_phase(df)

        return ScoringResult(
            total_score=total_score,
            signal_type=signal_type,
            confidence=confidence,
            categories={k: v for k, v in self.categories.items()},
            reasons_to_trade=reasons_to_trade,
            warnings=warnings,
            expected_winrate=expected_winrate,
            market_phase=market_phase,
            recommendation=recommendation
        )

    def _score_market_structure(
        self,
        df: pd.DataFrame,
        ms_data: Dict
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Estructura de Mercado (20%)

        Evalúa:
        - Dirección de tendencia (HH/HL o LH/LL)
        - Fuerza de tendencia
        - Proximidad a soportes/resistencias
        """
        breakdown = {}
        reasons = []
        score = 0.0

        # Tendencia principal
        trend_direction = ms_data.get('trend_direction', 'neutral')
        trend_strength = ms_data.get('trend_strength', 0.5)

        if trend_direction == 'uptrend' and trend_strength >= 0.6:
            breakdown['trend_direction'] = 90
            reasons.append(f"Tendencia alcista fuerte (fuerza: {trend_strength:.2f})")
        elif trend_direction == 'downtrend' and trend_strength >= 0.6:
            breakdown['trend_direction'] = 90
            reasons.append(f"Tendencia bajista fuerte (fuerza: {trend_strength:.2f})")
        elif trend_direction == 'neutral' or trend_strength < 0.4:
            breakdown['trend_direction'] = 40
            reasons.append("Mercado lateral/rango")
        else:
            breakdown['trend_direction'] = 60
            reasons.append(f"Tendencia débil ({trend_direction})")

        # Soportes/Resistencias
        sr_distance = ms_data.get('nearest_sr_distance', 0.5)  # % de distancia
        if sr_distance < 0.001:  # Muy cerca de S/R
            breakdown['support_resistance'] = 30
            reasons.append("Precio muy cerca de S/R importante")
        elif sr_distance > 0.005:  # Lejos de S/R
            breakdown['support_resistance'] = 80
            reasons.append("Precio en zona limpia (lejos de S/R)")
        else:
            breakdown['support_resistance'] = 60

        # Breakdown de estructura (BOS/CHoCH)
        bos_detected = ms_data.get('bos_detected', False)
        choch_detected = ms_data.get('choch_detected', False)
        if bos_detected:
            breakdown['structure_break'] = 85
            reasons.append("Break of Structure detectado")
        elif choch_detected:
            breakdown['structure_break'] = 70
            reasons.append("Cambio de carácter detectado")
        else:
            breakdown['structure_break'] = 50

        # Calcular score promedio
        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_smart_money(
        self,
        df: pd.DataFrame,
        sm_data: Dict
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Smart Money (20%)

        Evalúa:
        - Order Blocks
        - Fair Value Gaps (FVG)
        - Liquidity grabs
        - Imbalances
        """
        breakdown = {}
        reasons = []
        score = 0.0

        # Order Blocks
        order_block_hit = sm_data.get('order_block_hit', False)
        order_block_strength = sm_data.get('order_block_strength', 0.5)
        if order_block_hit and order_block_strength > 0.7:
            breakdown['order_blocks'] = 90
            reasons.append(f"Order Block fuerte detectado (fuerza: {order_block_strength:.2f})")
        elif order_block_hit:
            breakdown['order_blocks'] = 70
            reasons.append("Order Block detectado")
        else:
            breakdown['order_blocks'] = 50

        # Fair Value Gaps (FVG)
        fvg_detected = sm_data.get('fvg_detected', False)
        fvg_hit = sm_data.get('fvg_hit', False)
        latest_fvg = sm_data.get('latest_fvg', {})
        
        if fvg_hit:
            breakdown['fvg'] = 95
            reasons.append(f"Precio mitigando FVG {latest_fvg.get('type','')} (Punto de entrada óptimo)")
        elif fvg_detected:
            breakdown['fvg'] = 75
            reasons.append("Fair Value Gap detectado (esperando mitigación)")
        else:
            breakdown['fvg'] = 50

        # Liquidity
        liquidity_grab = sm_data.get('liquidity_grab', False)
        if liquidity_grab:
            breakdown['liquidity'] = 85
            reasons.append("Liquidity grab detectado (stop hunt)")
        else:
            breakdown['liquidity'] = 50

        # Premium/Discount
        premium_discount = sm_data.get('premium_discount', 0.5)  # 0 = discount max, 1 = premium max
        if premium_discount < 0.3:  # En discount (bueno para CALL)
            breakdown['premium_discount'] = 80
            reasons.append("Precio en zona de descuento (discount)")
        elif premium_discount > 0.7:  # En premium (bueno para PUT)
            breakdown['premium_discount'] = 80
            reasons.append("Precio en zona premium")
        else:
            breakdown['premium_discount'] = 50

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_technical_indicators(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Indicadores Técnicos (15%) - ULTRA ESTRICTO

        Evalúa:
        - RSI en zonas extremas (más selectivo)
        - MACD con confirmación de cruce
        - EMAs alineadas
        """
        breakdown = {}
        reasons = []
        score = 0.0
        filters_passed = 0

        if len(df) < 30:
            return 50, {'insufficient_data': 50}, ["Datos insuficientes para indicadores"]

        # RSI - Selectivo pero operable
        if 'rsi' in df.columns:
            rsi = df['rsi'].iloc[-1]
            rsi_prev = df['rsi'].iloc[-2] if len(df) > 1 else rsi

            # RSI sobreventa con giro alcista
            if rsi < 35 and rsi > rsi_prev:
                breakdown['rsi'] = 90
                reasons.append(f"RSI sobreventa con giro ({rsi:.1f})")
                filters_passed += 1
            # RSI sobrecompra con giro bajista
            elif rsi > 65 and rsi < rsi_prev:
                breakdown['rsi'] = 90
                reasons.append(f"RSI sobrecompra con giro ({rsi:.1f})")
                filters_passed += 1
            # RSI en zona favorable (no neutra)
            elif rsi < 30 or rsi > 70:
                breakdown['rsi'] = 70
                reasons.append(f"RSI en zona extrema ({rsi:.1f})")
                filters_passed += 1
            # RSI neutro - regular
            elif 35 <= rsi <= 65:
                breakdown['rsi'] = 40
                reasons.append(f"RSI neutro ({rsi:.1f})")
            else:
                breakdown['rsi'] = 55
        else:
            breakdown['rsi'] = 50

        # MACD - Solo cruces confirmados con divergencia
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            macd_prev = df['macd'].iloc[-2] if len(df) > 2 else macd
            signal_prev = df['macd_signal'].iloc[-2] if len(df) > 2 else macd_signal
            macd_prev2 = df['macd'].iloc[-3] if len(df) > 3 else macd_prev

            # Cruce alcista
            if macd > macd_signal and macd_prev <= signal_prev:
                breakdown['macd'] = 85
                reasons.append("MACD: Cruce alcista")
                filters_passed += 1
            # Cruce bajista
            elif macd < macd_signal and macd_prev >= signal_prev:
                breakdown['macd'] = 85
                reasons.append("MACD: Cruce bajista")
                filters_passed += 1
            # MACD por encima de señal - regular
            elif macd > macd_signal:
                breakdown['macd'] = 60
                reasons.append("MACD por encima de señal")
            # MACD por debajo - regular
            else:
                breakdown['macd'] = 45
                reasons.append("MACD por debajo de señal")
        else:
            breakdown['macd'] = 50

        # EMAs - Alineación perfecta requerida
        if 'ema_9' in df.columns and 'ema_21' in df.columns:
            ema_9 = df['ema_9'].iloc[-1]
            ema_21 = df['ema_21'].iloc[-1]
            price = df['close'].iloc[-1]

            # Alineación alcista PERFECTA: precio > ema9 > ema21
            if ema_9 > ema_21 and price > ema_9 and (ema_9 - ema_21) > (df['close'].iloc[-1] * 0.001):
                breakdown['emas'] = 90
                reasons.append("EMAs: Alineación alcista PERFECTA")
                filters_passed += 1
            # Alineación bajista PERFECTA: precio < ema9 < ema21
            elif ema_9 < ema_21 and price < ema_9 and (ema_21 - ema_9) > (df['close'].iloc[-1] * 0.001):
                breakdown['emas'] = 90
                reasons.append("EMAs: Alineación bajista PERFECTA")
                filters_passed += 1
            # Sin alineación clara - Penalizar fuerte
            else:
                breakdown['emas'] = 30
                reasons.append("EMAs: Sin alineación clara - NO OPERAR")
        else:
            breakdown['emas'] = 50

        # Bonus si todos los filtros pasaron
        if filters_passed >= 3:
            score = np.mean(list(breakdown.values())) * 1.1  # 10% bonus
        else:
            score = np.mean(list(breakdown.values()))

        return min(100, score), breakdown, reasons

    def _score_multi_timeframe(
        self,
        df: pd.DataFrame,
        df_m5: Optional[pd.DataFrame],
        df_m15: Optional[pd.DataFrame]
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score Multi-Timeframe (15%)

        Evalúa alineación entre M1, M5, M15
        """
        breakdown = {}
        reasons = []
        score = 0.0

        # Dirección M1
        m1_trend = self._get_trend_direction(df)
        breakdown['m1_trend'] = 70 if m1_trend != 'neutral' else 50
        reasons.append(f"M1: {m1_trend}")

        # Dirección M5
        if df_m5 is not None and len(df_m5) > 5:
            m5_trend = self._get_trend_direction(df_m5)
            breakdown['m5_trend'] = 70 if m5_trend != 'neutral' else 50
            reasons.append(f"M5: {m5_trend}")

            # Alineación M1-M5
            if m1_trend == m5_trend and m1_trend != 'neutral':
                breakdown['alignment_m1_m5'] = 90
                reasons.append("✅ M1 y M5 alineados")
            elif m1_trend != m5_trend:
                breakdown['alignment_m1_m5'] = 30
                reasons.append("⚠️ M1 y M5 divergentes")
            else:
                breakdown['alignment_m1_m5'] = 50
        else:
            breakdown['m5_trend'] = 50
            breakdown['alignment_m1_m5'] = 50

        # Dirección M15
        if df_m15 is not None and len(df_m15) > 5:
            m15_trend = self._get_trend_direction(df_m15)
            breakdown['m15_trend'] = 70 if m15_trend != 'neutral' else 50
            reasons.append(f"M15: {m15_trend}")

            # Alineación total
            if m1_trend == m5_trend == m15_trend and m1_trend != 'neutral':
                breakdown['alignment_all'] = 100
                reasons.append("✅ M1, M5, M15 perfectamente alineados")
            else:
                breakdown['alignment_all'] = 50
        else:
            breakdown['m15_trend'] = 50
            breakdown['alignment_all'] = 50

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_risk_management(
        self,
        df: pd.DataFrame,
        current_price: float,
        account_balance: float
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Gestión de Riesgo (10%)

        Evalúa:
        - Ratio riesgo/beneficio potencial
        - Volatilidad actual
        - Tamaño de posición adecuado
        """
        breakdown = {}
        reasons = []
        score = 0.0

        # Calcular ATR para volatilidad
        if len(df) < 14:
            return 50, {'insufficient_data': 50}, ["Datos insuficientes"]

        if 'atr' in df.columns:
            atr = df['atr'].iloc[-1]
        else:
            high_low = df['high'].iloc[-14:] - df['low'].iloc[-14:]
            atr = high_low.mean()

        # ATR relativo
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

        if 0.01 <= atr_pct <= 0.1:  # Volatilidad normal
            breakdown['volatility'] = 80
            reasons.append(f"Volatilidad adecuada (ATR: {atr_pct:.3f}%)")
        elif atr_pct > 0.15:  # Muy volátil
            breakdown['volatility'] = 40
            reasons.append(f"⚠️ Volatilidad excesiva (ATR: {atr_pct:.3f}%)")
        elif atr_pct < 0.005:  # Muy plano
            breakdown['volatility'] = 50
            reasons.append("Mercado muy plano")
        else:
            breakdown['volatility'] = 60

        # Ratio R:R estimado (basado en ATR y estructura)
        # Asumimos que tomamos 1 ATR de riesgo y buscamos 2 ATR de beneficio
        breakdown['rr_ratio'] = 75  # Asumimos 1:2 por defecto
        reasons.append("Ratio R:R estimado 1:2")

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_temporal_context(
        self,
        asset: str
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Contexto Temporal (10%)

        Evalúa:
        - Sesión de trading (Londres, NY, Asia)
        - Hora del día
        - Días de la semana
        """
        from datetime import datetime

        breakdown = {}
        reasons = []
        score = 0.0

        now = datetime.now()
        hour_utc = now.hour

        # Determinar sesión
        if 7 <= hour_utc <= 16:
            session = "london"
            session_score = 90
            reasons.append("Sesión de Londres (alta liquidez)")
        elif 12 <= hour_utc <= 21:
            session = "ny"
            session_score = 90
            reasons.append("Sesión de NY (alta liquidez)")
        elif 0 <= hour_utc <= 6:
            session = "asia"
            session_score = 60
            reasons.append("Sesión de Asia (menor liquidez)")
        else:
            session = "off_peak"
            session_score = 40
            reasons.append("Fuera de sesión principal")

        breakdown['session'] = session_score

        # Superposición Londres-NY (mejor momento)
        if 12 <= hour_utc <= 16:
            breakdown['overlap'] = 95
            reasons.append("✅ Superposición Londres-NY (óptimo)")
        else:
            breakdown['overlap'] = 50

        # Día de la semana
        weekday = now.weekday()
        if weekday in [1, 2, 3]:  # Mar, Mie, Jue
            breakdown['weekday'] = 85
            reasons.append(f"Día óptimo ({now.strftime('%A')})")
        elif weekday == 0:  # Lunes
            breakdown['weekday'] = 60
            reasons.append("Lunes (mercado encontrando dirección)")
        elif weekday == 4:  # Viernes
            breakdown['weekday'] = 60
            reasons.append("Viernes (cierre de semana)")
        else:
            breakdown['weekday'] = 50

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_momentum(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Momentum (5%)

        Evalúa fuerza del movimiento actual
        """
        breakdown = {}
        reasons = []
        score = 0.0

        if len(df) < 10:
            return 50, {'insufficient_data': 50}, []

        # Momentum de precio (últimas 10 velas)
        price_change = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]
        abs_momentum = abs(price_change)

        if abs_momentum > 0.002:  # Momentum fuerte
            breakdown['price_momentum'] = 80
            reasons.append(f"Momentum fuerte ({price_change*100:.3f}%)")
        elif abs_momentum > 0.001:  # Momentum moderado
            breakdown['price_momentum'] = 60
            reasons.append(f"Momentum moderado ({price_change*100:.3f}%)")
        else:
            breakdown['price_momentum'] = 40
            reasons.append("Momentum débil")

        # Volumen (si disponible)
        if 'volume' in df.columns:
            avg_volume = df['volume'].iloc[-10:].mean()
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            if volume_ratio > 1.5:
                breakdown['volume'] = 85
                reasons.append(f"Volumen alto ({volume_ratio:.1f}x promedio)")
            elif volume_ratio > 1.0:
                breakdown['volume'] = 60
            else:
                breakdown['volume'] = 40
                reasons.append("Volumen bajo")
        else:
            breakdown['volume'] = 50

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _score_market_phase(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Score de Fase de Mercado (5%)

        Evalúa si el mercado está en tendencia o rango
        """
        breakdown = {}
        reasons = []
        score = 0.0

        if len(df) < 50:
            return 50, {'insufficient_data': 50}, []

        # ADX para determinar fase (si disponible)
        if 'adx' in df.columns:
            adx = df['adx'].iloc[-1]
            if adx > 25:
                breakdown['phase'] = 80
                reasons.append(f"Mercado en tendencia (ADX: {adx:.1f})")
            elif adx < 20:
                breakdown['phase'] = 50
                reasons.append(f"Mercado en rango (ADX: {adx:.1f})")
            else:
                breakdown['phase'] = 65
        else:
            # Estimar con rango de las últimas 50 velas
            high_range = df['high'].iloc[-50:].max()
            low_range = df['low'].iloc[-50:].min()
            price_range = high_range - low_range
            current_pos = (df['close'].iloc[-1] - low_range) / price_range if price_range > 0 else 0.5

            if 0.3 < current_pos < 0.7:
                breakdown['phase'] = 60
                reasons.append("Precio en medio del rango")
            else:
                breakdown['phase'] = 75
                reasons.append("Precio en extremos del rango (oportunidad)")

        score = np.mean(list(breakdown.values()))

        return score, breakdown, reasons

    def _get_trend_direction(self, df: pd.DataFrame) -> str:
        """Determinar dirección de tendencia simple"""
        if len(df) < 10:
            return 'neutral'

        # Usar EMAs si disponibles
        if 'ema_9' in df.columns and 'ema_21' in df.columns:
            ema_9 = df['ema_9'].iloc[-1]
            ema_21 = df['ema_21'].iloc[-1]
            if ema_9 > ema_21:
                return 'uptrend'
            elif ema_9 < ema_21:
                return 'downtrend'
            else:
                return 'neutral'

        # Usar máximos/mínimos
        recent_high = df['high'].iloc[-5:].max()
        recent_low = df['low'].iloc[-5:].min()
        prev_high = df['high'].iloc[-10:-5].max()
        prev_low = df['low'].iloc[-10:-5].min()

        if recent_high > prev_high and recent_low > prev_low:
            return 'uptrend'
        elif recent_high < prev_high and recent_low < prev_low:
            return 'downtrend'
        else:
            return 'neutral'

    def _determine_signal_type(
        self,
        df: pd.DataFrame,
        total_score: float
    ) -> SignalType:
        """Determinar si es CALL o PUT basado en datos y score"""
        if total_score < self.min_score_to_trade:
            return SignalType.NEUTRAL

        # Usar múltiples factores para determinar dirección
        signals = []

        # RSI
        if 'rsi' in df.columns:
            rsi = df['rsi'].iloc[-1]
            if rsi < 30:
                signals.append('CALL')
            elif rsi > 70:
                signals.append('PUT')

        # MACD
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            if macd > macd_signal:
                signals.append('CALL')
            else:
                signals.append('PUT')

        # EMAs
        if 'ema_9' in df.columns and 'ema_21' in df.columns:
            ema_9 = df['ema_9'].iloc[-1]
            ema_21 = df['ema_21'].iloc[-1]
            if ema_9 > ema_21:
                signals.append('CALL')
            else:
                signals.append('PUT')

        # Votar
        if signals:
            call_count = signals.count('CALL')
            put_count = signals.count('PUT')
            if call_count > put_count:
                return SignalType.CALL
            elif put_count > call_count:
                return SignalType.PUT

        # Default: usar tendencia de precio reciente
        if len(df) >= 5:
            if df['close'].iloc[-1] > df['close'].iloc[-5]:
                return SignalType.CALL
            else:
                return SignalType.PUT

        return SignalType.NEUTRAL

    def _determine_market_phase(self, df: pd.DataFrame) -> str:
        """Determinar fase actual del mercado"""
        if 'adx' in df.columns and len(df) > 14:
            adx = df['adx'].iloc[-1]
            if adx > 25:
                return "trending"
            elif adx < 20:
                return "ranging"
            else:
                return "transition"

        # Método alternativo
        if len(df) < 50:
            return "unknown"

        high_range = df['high'].iloc[-50:].max()
        low_range = df['low'].iloc[-50:].min()
        price_range = high_range - low_range

        if price_range / df['close'].iloc[-1] > 0.01:
            return "ranging"
        else:
            return "trending"

    def get_detailed_report(self, result: ScoringResult) -> str:
        """Generar reporte detallado del scoring"""
        report = []
        report.append("=" * 60)
        report.append("REPORTE DE SCORING UNIFICADO")
        report.append("=" * 60)
        report.append(f"Score Total: {result.total_score:.1f}/100")
        report.append(f"Confianza: {result.confidence*100:.1f}%")
        report.append(f"Señal: {result.signal_type.value}")
        report.append(f"Recomendación: {result.recommendation}")
        report.append(f"Winrate Esperado: {result.expected_winrate*100:.1f}%")
        report.append(f"Fase de Mercado: {result.market_phase}")
        report.append("")
        report.append("DESGLOSE POR CATEGORÍA:")
        report.append("-" * 40)

        for key, cat in result.categories.items():
            report.append(f"{cat.name}: {cat.score:.1f} (peso: {cat.weight*100:.0f}%)")
            for subkey, subval in cat.breakdown.items():
                report.append(f"  - {subkey}: {subval:.0f}")

        report.append("")
        report.append("RAZONES PARA OPERAR:")
        for reason in result.reasons_to_trade:
            report.append(f"  ✓ {reason}")

        if result.warnings:
            report.append("")
            report.append("ADVERTENCIAS:")
            for warning in result.warnings:
                report.append(f"  ⚠️ {warning}")

        report.append("=" * 60)

        return "\n".join(report)


# Singleton
_scoring_engine: Optional[UnifiedScoringEngine] = None


def get_scoring_engine() -> UnifiedScoringEngine:
    """Obtener instancia singleton"""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = UnifiedScoringEngine()
    return _scoring_engine
