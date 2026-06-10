"""
Unified Scoring Engine v3.0 - Motor de Scoring Inteligente
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    CALL = "CALL"
    PUT = "PUT"
    NEUTRAL = "NEUTRAL"


@dataclass
class ScoringCategory:
    name: str
    weight: float
    score: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScoringResult:
    total_score: float
    signal_type: SignalType
    confidence: float
    categories: Dict[str, ScoringCategory]
    reasons_to_trade: List[str]
    warnings: List[str]
    expected_winrate: float
    market_phase: str
    recommendation: str


class UnifiedScoringEngine:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.min_score_to_trade = 72
        self.categories: Dict[str, ScoringCategory] = {}
        self._initialize_categories()

    def _default_config(self) -> Dict:
        return {
            'weights': {
                'market_structure': 0.20,
                'smart_money': 0.18,
                'technical_indicators': 0.18,
                'multi_timeframe': 0.18,
                'risk_management': 0.10,
                'temporal_context': 0.08,
                'momentum': 0.05,
                'market_phase': 0.03,
            },
            'thresholds': {
                'min_score': 72,
                'high_confidence': 82,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
            }
        }

    def _initialize_categories(self):
        weights = self.config['weights']
        for key, weight in weights.items():
            self.categories[key] = ScoringCategory(name=key, weight=weight)

    def score(self, df: pd.DataFrame, df_m5=None, df_m15=None,
              current_price: float = 0.0, asset: str = "EUR/USD",
              account_balance: float = 100.0,
              smart_money_data: Optional[Dict] = None,
              market_structure_data: Optional[Dict] = None) -> ScoringResult:

        reasons = []
        warnings = []
        sm_data = smart_money_data or {}
        ms_data = market_structure_data or {}

        # Simplified scoring using available data
        last = df.iloc[-1] if len(df) > 0 else {}
        rsi = float(last.get('rsi', 50)) if hasattr(last, 'get') else 50
        macd = float(last.get('macd', 0)) if hasattr(last, 'get') else 0
        macd_signal = float(last.get('macd_signal', 0)) if hasattr(last, 'get') else 0

        # Score each category
        tech_score = 50.0
        if rsi < 30: tech_score = 85; reasons.append(f"RSI sobreventa ({rsi:.1f})")
        elif rsi > 70: tech_score = 85; reasons.append(f"RSI sobrecompra ({rsi:.1f})")
        elif rsi < 40 or rsi > 60: tech_score = 65
        self.categories['technical_indicators'].score = tech_score

        macd_score = 75.0 if macd > macd_signal else 65.0 if macd > 0 else 50.0
        self.categories['momentum'].score = macd_score

        ms_score = 70.0
        trend = ms_data.get('trend_direction', 'neutral')
        if trend in ('uptrend', 'downtrend'):
            ms_score = 80.0
            reasons.append(f"Tendencia: {trend}")
        self.categories['market_structure'].score = ms_score

        sm_score = 60.0
        if sm_data.get('order_block_hit'): sm_score = 80.0; reasons.append("Order Block hit")
        if sm_data.get('fvg_hit'): sm_score = 90.0; reasons.append("FVG hit")
        self.categories['smart_money'].score = sm_score

        self.categories['multi_timeframe'].score = 65.0
        self.categories['risk_management'].score = 70.0
        self.categories['temporal_context'].score = 70.0
        self.categories['market_phase'].score = 60.0

        total_score = sum(cat.score * cat.weight for cat in self.categories.values())

        # Signal direction
        if rsi < 35 or (macd > macd_signal and trend == 'uptrend'):
            signal_type = SignalType.CALL
        elif rsi > 65 or (macd < macd_signal and trend == 'downtrend'):
            signal_type = SignalType.PUT
        elif len(df) >= 5:
            signal_type = SignalType.CALL if df['close'].iloc[-1] > df['close'].iloc[-5] else SignalType.PUT
        else:
            signal_type = SignalType.NEUTRAL

        confidence = total_score / 100.0
        high_cats = sum(1 for cat in self.categories.values() if cat.score >= 65)
        recommendation = "TRADE" if total_score >= self.min_score_to_trade and high_cats >= 4 else "WAIT"

        if recommendation == "WAIT":
            warnings.append(f"Score {total_score:.1f} insuficiente")

        expected_winrate = 0.45 + (total_score / 100) * 0.35
        expected_winrate = min(0.82, max(0.45, expected_winrate))

        phase = "trending" if abs(rsi - 50) > 15 else "ranging"

        return ScoringResult(
            total_score=total_score,
            signal_type=signal_type,
            confidence=confidence,
            categories=dict(self.categories),
            reasons_to_trade=reasons,
            warnings=warnings,
            expected_winrate=expected_winrate,
            market_phase=phase,
            recommendation=recommendation
        )


_scoring_engine: Optional[UnifiedScoringEngine] = None


def get_scoring_engine() -> UnifiedScoringEngine:
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = UnifiedScoringEngine()
    return _scoring_engine
