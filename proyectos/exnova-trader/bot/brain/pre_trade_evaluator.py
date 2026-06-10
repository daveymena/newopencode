"""
PreTradeEvaluator — Evalúa si entrar en la próxima operación o esperar
Lógica:
- Después de una operación (ganó o perdió), analiza qué pasó
- Antes de la siguiente entrada, compara el nuevo setup contra "esperar"
- Si el nuevo setup no es MEJOR que la media reciente, prefiere esperar
- Nunca descarta una entrada excelente por el historial reciente
"""
import time
from typing import Dict, Optional, List
from dataclasses import dataclass

from brain.market_intelligence import get_market_intelligence, MarketIntelligence


@dataclass
class PreTradeDecision:
    should_enter: bool
    quality_vs_prev: str   # "MEJOR", "SIMILAR", "PEOR", "PRIMERA"
    reasoning: List[str]
    suggestion: str
    prev_loss_cause: str
    new_setup_score: float
    wait_for_better: bool


class PreTradeEvaluator:
    """
    Antes de cada nueva entrada, evalúa:
    1. ¿Qué pasó en la operación anterior?
    2. ¿El nuevo setup es mejor, similar o peor?
    3. ¿Vale la pena entrar ahora o esperar algo más claro?
    """

    def evaluate_entry(self,
                        last_trade: Optional[Dict],
                        last_diagnosis: Optional[Dict],
                        new_signal: Dict,
                        cascade: "CascadeResult",  # type: ignore
                        recent_trades: List[Dict]) -> PreTradeDecision:

        reasoning = []
        wait_for_better = False

        # ── 1. Analizar el historial reciente ────────────────────────────────
        last_5 = recent_trades[-5:] if recent_trades else []
        wins   = sum(1 for t in last_5 if t.get("result") == "WIN")
        losses = sum(1 for t in last_5 if t.get("result") == "LOSS")
        recent_wr = wins / len(last_5) if last_5 else None

        # ── 2. Causa del último trade ────────────────────────────────────────
        prev_loss_cause = ""
        if last_trade and last_trade.get("result") == "LOSS" and last_diagnosis:
            prev_loss_cause = last_diagnosis.get("primary_cause", "")
            reasoning.append(f"Última pérdida fue por: {prev_loss_cause}")

            # Si el nuevo setup tiene el mismo problema, advertir
            new_has_same_issue = self._check_same_issue(
                prev_loss_cause, new_signal, cascade
            )
            if new_has_same_issue:
                reasoning.append(f"⚠ El nuevo setup podría tener el mismo problema")
                wait_for_better = True

        elif last_trade and last_trade.get("result") == "WIN":
            reasoning.append(f"Última operación ganada — buen momentum")

        # ── 3. Score del nuevo setup ─────────────────────────────────────────
        new_score = new_signal.get("score", 0)
        ai_label  = new_signal.get("ai_label", "NORMAL")
        cascade_ok = cascade.cascade_aligned if cascade else False

        # Score ponderado del nuevo setup
        new_setup_score = (
            new_score * 0.35 +
            new_signal.get("confidence", 0.5) * 100 * 0.25 +
            new_signal.get("zone_strength", 0.5) * 100 * 0.20 +
            (cascade.alignment_score * 100 if cascade else 50) * 0.20
        )

        # ── 4. Comparar con promedio reciente ────────────────────────────────
        avg_recent_score = self._get_avg_score(last_5)

        if not last_5:
            quality_vs_prev = "PRIMERA"
            reasoning.append("Primera operación — procediendo con el setup actual")
        elif new_setup_score >= avg_recent_score * 1.15:
            quality_vs_prev = "MEJOR"
            reasoning.append(f"Setup MEJOR que el promedio reciente ({new_setup_score:.0f} vs {avg_recent_score:.0f})")
        elif new_setup_score >= avg_recent_score * 0.85:
            quality_vs_prev = "SIMILAR"
            reasoning.append(f"Setup similar al promedio reciente ({new_setup_score:.0f} vs {avg_recent_score:.0f})")
        else:
            quality_vs_prev = "PEOR"
            reasoning.append(f"Setup PEOR que el promedio ({new_setup_score:.0f} vs {avg_recent_score:.0f})")
            wait_for_better = True

        # ── 4b. Market Intelligence ──────────────────────────────────────────
        m_intel = get_market_intelligence()
        session = MarketIntelligence.get_current_session()
        reasoning.append(f"Sesión actual: {session.upper()}")

        mi_skip, mi_reason = m_intel.should_skip_trade(
            asset=new_signal.get("asset", ""),
            confidence=new_signal.get("confidence", 0.5),
            direction=new_signal.get("signal", "CALL"),
            expiration_sec=new_signal.get("expiration", 60)
        )
        if mi_skip:
            reasoning.append(f"⚠ MI: {mi_reason}")
            wait_for_better = True

        trap_warnings = m_intel.get_trap_warnings(new_signal.get("asset", ""))
        for tw in trap_warnings:
            reasoning.append(f"⚠ {tw}")

        # ── 5. Evaluación de cascada ──────────────────────────────────────────
        if cascade:
            if cascade.cascade_aligned:
                reasoning.append(f"✓ Cascada alineada ({cascade.alignment_score:.0%}) — H1:{cascade.h1_trend} M15:{cascade.m15_trend} M5:{cascade.m5_trend}")
            else:
                reasoning.append(f"✗ Cascada no alineada — esperar mejor alineación TF")
                wait_for_better = True

            if cascade.trend_advanced:
                reasoning.append(f"✓ Tendencia avanzada {cascade.advancement_bars} períodos")
            else:
                reasoning.append(f"✗ Tendencia aún no avanzó suficiente — esperar {3 - cascade.advancement_bars} períodos más")
                wait_for_better = True

            if cascade.at_valid_sr and cascade.nearest_sr:
                sr = cascade.nearest_sr
                reasoning.append(f"✓ En S/R válido: {sr.level_type} {sr.price:.5f} ({sr.period_source}, dist={sr.distance_pct*100:.2f}%)")
            else:
                reasoning.append(f"✗ Precio no en S/R del período 15 o 20")
                if quality_vs_prev not in ("MEJOR", "PRIMERA"):
                    wait_for_better = True

            if cascade.liquidity_risk:
                reasoning.append(f"✗ Riesgo de liquidez: {cascade.liquidity_reason}")
                wait_for_better = True

        # ── 6. Excepción: setup excelente overrides la espera ────────────────
        # Si la IA dice EXCELENTE y la cascada está alineada, entrar siempre
        if ai_label == "EXCELENTE" and cascade_ok and new_score >= 70:
            wait_for_better = False
            reasoning.append("✓ Setup EXCELENTE con cascada alineada — override de espera")
        elif ai_label == "BUENO" and cascade_ok and new_score >= 60 and not cascade.liquidity_risk:
            wait_for_better = False
            reasoning.append("✓ Setup BUENO con cascada — procediendo")
        # Zona fuerte (≥0.85) override: cascada es advisory, no bloqueante
        zone_str = new_signal.get("zone_strength", 0.0)
        if zone_str >= 0.85:
            if wait_for_better:
                reasoning.append(f"✓ Zona muy fuerte ({zone_str:.2f}) — override de espera")
                wait_for_better = False

        # ── 7. Rachas de pérdidas recientes ──────────────────────────────────
        if losses >= 3 and wins == 0:
            reasoning.append(f"⚠ {losses} pérdidas recientes — exigencia más alta")
            if new_setup_score < avg_recent_score * 1.20:
                wait_for_better = True
                reasoning.append("→ Esperando setup superior por racha negativa")

        # Decisión final — cascada es advisory, no bloquea
        should_enter = not wait_for_better

        suggestion = (
            "ENTRAR — setup favorable con tendencia confirmada" if should_enter else
            f"ESPERAR — {reasoning[-1] if reasoning else 'setup insuficiente'}"
        )

        return PreTradeDecision(
            should_enter=should_enter,
            quality_vs_prev=quality_vs_prev,
            reasoning=reasoning,
            suggestion=suggestion,
            prev_loss_cause=prev_loss_cause,
            new_setup_score=round(new_setup_score, 1),
            wait_for_better=wait_for_better,
        )

    def _check_same_issue(self, prev_cause: str, signal: Dict, cascade) -> bool:
        """Verifica si el nuevo setup tiene el mismo problema que causó la pérdida anterior."""
        if prev_cause == "premature_entry":
            return False  # Ya está corregido en el engine
        if prev_cause == "no_rejection_wick":
            return signal.get("rejection_wick", 0) < 0.20
        if prev_cause == "zone_too_weak":
            return signal.get("zone_strength", 0) < 0.55
        if prev_cause == "counter_trend":
            return cascade and not cascade.cascade_aligned
        if prev_cause == "mtf_not_aligned":
            return cascade and not cascade.cascade_aligned
        return False

    def _get_avg_score(self, trades: List[Dict]) -> float:
        scores = [t.get("confidence", 0.5) * 100 for t in trades]
        return float(np.mean(scores)) if scores else 50.0

    # Importar numpy inline para evitar problema de imports circulares
    def __init__(self):
        import numpy as _np
        global np
        np = _np
