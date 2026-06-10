"""
Trade Evaluator v2.0 — Auto-evaluación post-operación con detección de entrada prematura
"""
import time
from typing import Dict, Optional, List
import pandas as pd


class TradeEvaluator:
    """
    Evalúa cada operación y produce un diagnóstico estructurado.
    Detecta específicamente el patrón de "entrada prematura":
    el análisis era correcto pero el precio llegó al objetivo después de la expiración.
    """

    def evaluate(self, trade_record: Dict, context_at_entry: Dict,
                  conditions_at_entry: Dict[str, bool],
                  df_m1_after: Optional[pd.DataFrame] = None) -> Dict:

        result    = trade_record.get("result", "UNKNOWN")
        direction = trade_record.get("direction", "CALL")
        asset     = trade_record.get("asset", "")
        exp_min   = trade_record.get("expiration_minutes", 1)
        entry_px  = trade_record.get("entry_price", 0.0)

        diag = {
            "result":           result,
            "asset":            asset,
            "direction":        direction,
            "timestamp":        time.time(),
            "primary_cause":    "unknown",
            "secondary_causes": [],
            "lessons":          [],
            "what_worked":      [],
            "what_failed":      [],
            "premature_entry":  False,
        }

        if result == "WIN":
            return self._evaluate_win(diag, context_at_entry, conditions_at_entry)

        return self._evaluate_loss(diag, context_at_entry, conditions_at_entry,
                                    df_m1_after, entry_px, exp_min)

    # ── WIN ───────────────────────────────────────────────────────────────────

    def _evaluate_win(self, diag: Dict, ctx: Dict, conds: Dict) -> Dict:
        diag["primary_cause"] = "correct_read"
        good = []
        zone_ctx = ctx.get("zone_context", {})
        momentum = ctx.get("momentum", {})

        if zone_ctx.get("zone_strength", 0) >= 0.65:
            good.append(f"Zona fuerte ({zone_ctx['zone_strength']:.2f}) aguantó el precio")
        if zone_ctx.get("trend_aligned"):
            good.append("A favor de la tendencia dominante")
        rsi = momentum.get("rsi_m1", 50)
        if abs(rsi - 50) >= 20:
            good.append(f"RSI en zona extrema ({rsi:.1f})")
        if conds.get("pattern_strong"):
            good.append("Patrón de vela fuerte en vela cerrada")
        if conds.get("rejection_visible"):
            good.append("Rechazo visible en la zona confirmado")
        if conds.get("mtf_aligned"):
            good.append("Múltiples timeframes alineados")
        if conds.get("candle_confirming"):
            good.append("Vela actual confirmó la dirección")

        diag["what_worked"] = good or ["Setup general favorable"]
        diag["lessons"]     = [f"✓ {w}" for w in diag["what_worked"]]
        return diag

    # ── LOSS ──────────────────────────────────────────────────────────────────

    def _evaluate_loss(self, diag: Dict, ctx: Dict, conds: Dict,
                        df_after: Optional[pd.DataFrame],
                        entry_px: float, exp_min: int) -> Dict:
        causes   = []
        failed   = []
        lessons  = []
        zone_ctx = ctx.get("zone_context", {})
        momentum = ctx.get("momentum", {})
        trend    = ctx.get("dominant_trend", "neutral")
        phase    = ctx.get("market_phase", "unknown")
        rsi      = momentum.get("rsi_m1", 50)
        direction = diag["direction"]

        # ── DIAGNÓSTICO 1: Entrada prematura ─────────────────────────────────
        # El precio eventualmente fue en la dirección correcta, pero después de expirar
        premature = False
        if df_after is not None and len(df_after) >= 3 and entry_px > 0:
            premature = self._detect_premature_entry(df_after, entry_px, direction, exp_min)

        if premature:
            diag["premature_entry"] = True
            causes.append("premature_entry")
            failed.append("ENTRADA PREMATURA — El precio fue en la dirección correcta DESPUÉS de la expiración")
            failed.append(f"El análisis era correcto pero la vela de señal aún no había cerrado completamente")
            lessons.append("✓ FIX APLICADO: Solo entrar cuando la vela de señal esté 100% cerrada (df.iloc[-2])")
            lessons.append("Aumentar expiración o esperar confirmación de vela siguiente antes de entrar")

        # ── DIAGNÓSTICO 2: Zona débil ─────────────────────────────────────────
        zs = zone_ctx.get("zone_strength", 0)
        if zs < 0.50:
            causes.append("zone_too_weak")
            failed.append(f"Zona débil (strength={zs:.2f}) — no tenía suficiente historia de reacciones")
            lessons.append("Exigir zona con strength ≥0.55 y al menos 3 toques confirmados")

        # ── DIAGNÓSTICO 3: Sin rechazo visible ───────────────────────────────
        if not conds.get("rejection_visible"):
            causes.append("no_rejection_wick")
            failed.append("Sin mecha de rechazo visible en la zona — el precio tocó pero no rebotó con fuerza")
            lessons.append("Esperar que la mecha de rechazo sea ≥30% del rango de la vela antes de entrar")

        # ── DIAGNÓSTICO 4: Contra tendencia ──────────────────────────────────
        if not zone_ctx.get("trend_aligned", True):
            causes.append("counter_trend")
            failed.append(f"Operación contra la tendencia dominante ({trend})")
            lessons.append("Evitar trades contra tendencia — si se hace, necesitar zona muy fuerte (≥0.80)")

        # ── DIAGNÓSTICO 5: RSI no extremo ────────────────────────────────────
        rsi_dist = abs(rsi - 50)
        if direction == "CALL" and rsi > 50:
            causes.append("rsi_not_extreme")
            failed.append(f"CALL con RSI={rsi:.1f} — sin sobreventa real (necesita RSI < 40)")
        elif direction == "PUT" and rsi < 50:
            causes.append("rsi_not_extreme")
            failed.append(f"PUT con RSI={rsi:.1f} — sin sobrecompra real (necesita RSI > 60)")

        # ── DIAGNÓSTICO 6: MTF no alineado ───────────────────────────────────
        if not conds.get("mtf_aligned"):
            causes.append("mtf_not_aligned")
            failed.append("M1/M5/M15 no alineados — timeframes en conflicto")
            lessons.append("Confirmar que al menos 2 de 3 timeframes apuntan en la misma dirección")

        # ── DIAGNÓSTICO 7: Fase mala ──────────────────────────────────────────
        if phase in ("dead", "volatile_ranging"):
            causes.append("bad_market_phase")
            failed.append(f"Mercado en fase desfavorable: {phase}")
            lessons.append("No operar en mercados muertos o con volatilidad errática")

        # Prioridad de causa primaria
        priority = [
            "premature_entry", "no_rejection_wick", "zone_too_weak",
            "counter_trend", "bad_market_phase", "rsi_not_extreme",
            "mtf_not_aligned",
        ]
        primary = next((p for p in priority if p in causes), "unknown")

        diag["primary_cause"]    = primary
        diag["secondary_causes"] = [c for c in causes if c != primary]
        diag["what_failed"]      = failed or ["Condiciones no cumplidas"]
        diag["lessons"]          = lessons or ["Revisar setup completo antes de la siguiente operación"]

        # ── Buscar DÓNDE debería haber entrado (real entry finder) ───────────
        if df_after is not None and len(df_after) >= 2 and entry_px > 0:
            ideal = self._find_real_entry(df_after, entry_px, direction, primary)
            if ideal:
                diag["ideal_entry"] = ideal
                diag["lessons"].append(
                    f"Entrada ideal: vela +{ideal['candle_offset']} min "
                    f"con mecha={ideal['wick_pct']:.0%} — "
                    f"{'habría ganado' if ideal['would_win'] else 'zona rompió igualmente'}"
                )

        return diag

    def _find_real_entry(self, df_after: pd.DataFrame, entry_px: float,
                          direction: str, cause: str) -> Optional[dict]:
        """
        Analiza las velas posteriores al trade para identificar DÓNDE
        se habría formado una entrada válida (con mecha de rechazo real).
        Retorna el offset de vela, porcentaje de mecha, y si habría ganado.
        """
        try:
            for i, (_, row) in enumerate(df_after.head(8).iterrows()):
                o = float(row.get("open", 0))
                c = float(row.get("close", 0))
                h = float(row.get("high", 0))
                l = float(row.get("low", 0))
                rng = h - l
                if rng <= 0:
                    continue

                if direction == "CALL":
                    wick = (min(o, c) - l) / rng
                else:
                    wick = (h - max(o, c)) / rng

                if wick >= 0.28:
                    # Esta vela muestra rechazo — ¿habría sido una entrada ganadora?
                    entry_here = c
                    would_win = False
                    remaining = df_after.iloc[i+1:i+4]
                    for _, future in remaining.iterrows():
                        if direction == "CALL" and float(future.get("high", 0)) > entry_here * 1.0003:
                            would_win = True; break
                        if direction == "PUT" and float(future.get("low", 9999)) < entry_here * 0.9997:
                            would_win = True; break

                    return {
                        "candle_offset": i + 1,
                        "wick_pct": wick,
                        "entry_price": round(entry_here, 6),
                        "would_win": would_win,
                        "note": f"Vela M1+{i+1} mostró mecha={wick:.0%} — {'ganadora' if would_win else 'zona rompió'}",
                    }
        except Exception:
            pass
        return None

    def _detect_premature_entry(self, df_after: pd.DataFrame,
                                  entry_price: float, direction: str,
                                  exp_minutes: int) -> bool:
        """
        Detecta si el precio eventualmente llegó al objetivo DESPUÉS de la expiración.
        Si es así, la entrada era correcta en dirección pero prematura en timing.
        """
        # ¿Llegó al objetivo durante la expiración?
        within_exp = df_after.head(exp_minutes)
        reached_during = False
        for _, row in within_exp.iterrows():
            if direction == "CALL" and float(row.get("high", 0)) > entry_price * 1.0003:
                reached_during = True; break
            if direction == "PUT" and float(row.get("low", 9999)) < entry_price * 0.9997:
                reached_during = True; break

        if reached_during:
            return False  # llegó a tiempo, no fue prematura

        # ¿Llegó después de la expiración?
        after_exp = df_after.iloc[exp_minutes:]
        if len(after_exp) == 0:
            return False
        for _, row in after_exp.iterrows():
            if direction == "CALL" and float(row.get("high", 0)) > entry_price * 1.0003:
                return True   # llegó después → entrada prematura
            if direction == "PUT" and float(row.get("low", 9999)) < entry_price * 0.9997:
                return True
        return False

    def format_for_display(self, diag: Dict) -> List[str]:
        lines = []
        result = diag.get("result", "?")
        icon   = "✔" if result == "WIN" else "✘"
        color  = "green" if result == "WIN" else "red"

        lines.append(f"[{color}]{icon} {diag['asset']} {diag['direction']} → {result}[/{color}]")

        if diag.get("premature_entry"):
            lines.append(f"  [yellow]⚠ ENTRADA PREMATURA — dirección correcta, timing adelantado[/yellow]")

        primary = diag.get("primary_cause", "")
        cause_labels = {
            "premature_entry":   "Vela no cerrada al entrar",
            "no_rejection_wick": "Sin rechazo visible en zona",
            "zone_too_weak":     "Zona insuficientemente fuerte",
            "counter_trend":     "Contra tendencia dominante",
            "rsi_not_extreme":   "RSI no en zona extrema",
            "mtf_not_aligned":   "Timeframes no alineados",
            "bad_market_phase":  "Fase de mercado desfavorable",
            "correct_read":      "Lectura correcta del mercado",
        }
        if primary and primary != "unknown":
            label = cause_labels.get(primary, primary)
            col   = "green" if primary == "correct_read" else "red"
            lines.append(f"  [{col}]Causa: {label}[/{col}]")

        if result == "WIN":
            for w in diag.get("what_worked", [])[:2]:
                lines.append(f"  [green]+ {w}[/green]")
        else:
            for f_item in diag.get("what_failed", [])[:2]:
                lines.append(f"  [red]− {f_item[:65]}[/red]")
            if diag.get("lessons"):
                lines.append(f"  [yellow]→ {diag['lessons'][0][:65]}[/yellow]")

        return lines
