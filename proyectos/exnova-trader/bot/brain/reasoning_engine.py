import json
from typing import Dict, Optional
from .llm_client import get_llm_client, LLMClient


class ReasoningVerdict:
    def __init__(self, raw: Dict):
        self.market_narrative = raw.get("market_narrative", "")
        self.reasoning_steps = raw.get("reasoning_steps", [])
        self.direction = raw.get("direction", "HOLD")
        self.recommended_action = raw.get("recommended_action", "WAIT")
        self.conviction = min(100, max(0, int(raw.get("conviction", 0))))
        self.risk_flags = raw.get("risk_flags", [])
        self.next_steps = raw.get("next_steps", [])
        self.entry_zone_pct = float(raw.get("entry_zone_pct", 0.0))

    @property
    def should_trade(self) -> bool:
        return self.recommended_action == "TRADE" and self.conviction >= 40

    @property
    def should_skip(self) -> bool:
        return self.recommended_action == "SKIP"

    @property
    def conviction_score(self) -> float:
        return self.conviction / 100.0

    def to_dict(self) -> Dict:
        return {
            "market_narrative": self.market_narrative,
            "reasoning_steps": self.reasoning_steps,
            "direction": self.direction,
            "recommended_action": self.recommended_action,
            "conviction": self.conviction,
            "conviction_score": self.conviction_score,
            "should_trade": self.should_trade,
            "risk_flags": self.risk_flags,
            "next_steps": self.next_steps,
            "entry_zone_pct": self.entry_zone_pct,
        }


class ReasoningEngine:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self._cache: Dict[str, ReasoningVerdict] = {}

    def reason(self, asset: str, current_price: float, zone_data: str = "",
               cascade_data: str = "", context_data: str = "",
               candle_summary: str = "", extra_m1_data: str = "",
               cache_key: str = "") -> ReasoningVerdict:
        key = cache_key or f"{asset}_{int(current_price * 100000)}"
        if key in self._cache:
            return self._cache[key]

        raw = self.llm.reason_market(
            asset=asset,
            current_price=current_price,
            zone_data=zone_data,
            cascade_data=cascade_data,
            context_data=context_data,
            candle_summary=candle_summary,
            extra_m1_data=extra_m1_data,
        )
        verdict = ReasoningVerdict(raw)
        self._cache[key] = verdict
        return verdict

    def clear_cache(self):
        self._cache.clear()


_engine_instance: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ReasoningEngine()
    return _engine_instance
