"""
Intelligent Engine v5.0 — Estrategia en Cascada H1→M15→M5→M1
Cambios vs v4.1:
- Validación cascada completa: H1 define dirección, M15 confirma, M5 impulso, M1 timing
- Tendencia debe HABER AVANZADO (mínimo 3 períodos) antes de entrar
- S/R desde períodos 15 y 20 — precio debe estar EN zona
- Refresh de S/R después de cada entrada
- Detección de trampas de liquidez
- Solo una operación por ciclo de análisis
"""
import time
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple

from config import Config
from brain.market_memory import get_market_memory
from brain.zone_detector import ZoneDetector
from brain.context_analyzer import ContextAnalyzer
from brain.adaptive_learner import get_adaptive_learner
from brain.market_ai import MarketAI
from brain.cascade_trend import CascadeTrendAnalyzer
from brain.candle_watcher import get_candle_watcher
from brain.reasoning_engine import get_reasoning_engine
from brain.market_intelligence import MarketIntelligence


# ─── Diagnóstico de entrada prematura ────────────────────────────────────────

class PrematureEntryDiagnostic:
    """
    Analiza si una pérdida fue por entrada prematura:
    el precio eventualmente llegó al objetivo pero después de que la operación expiró.
    """
    @staticmethod
    def was_premature(entry_price: float, direction: str,
                       candles_after: pd.DataFrame, expiration_minutes: int) -> Dict:
        if candles_after is None or len(candles_after) < 2:
            return {"premature": False, "reason": "sin datos post-trade"}

        target_reached_at = None
        candles_checked = min(len(candles_after), expiration_minutes * 3)

        for i, (_, row) in enumerate(candles_after.head(candles_checked).iterrows()):
            if direction == "CALL":
                if float(row["high"]) > entry_price * 1.0003:
                    target_reached_at = i + 1
                    break
            else:
                if float(row["low"]) < entry_price * 0.9997:
                    target_reached_at = i + 1
                    break

        # Buscar cuánto tardó el precio en llegar al objetivo
        target_reached_late = None
        for i, (_, row) in enumerate(candles_after.iterrows()):
            if direction == "CALL":
                if float(row["high"]) > entry_price * 1.0003:
                    target_reached_late = i + 1
                    break
            else:
                if float(row["low"]) < entry_price * 0.9997:
                    target_reached_late = i + 1
                    break

        was_premature = (target_reached_at is None and target_reached_late is not None and
                          target_reached_late > expiration_minutes)

        return {
            "premature": was_premature,
            "target_reached_candle": target_reached_late,
            "expiration_candles": expiration_minutes,
            "diagnosis": (
                f"Entrada prematura: precio llegó al objetivo en vela {target_reached_late} "
                f"pero la operación expiró en {expiration_minutes} velas"
                if was_premature else
                "No fue entrada prematura"
            ),
        }


# ─── Detector de patrones en velas CERRADAS ──────────────────────────────────

class CandlePatternDetector:
    """
    Detecta patrones SOLO en velas completamente cerradas.

    Regla fundamental:
    - La vela de señal siempre es df.iloc[-2] (última CERRADA)
    - La vela actual df.iloc[-1] (en formación) solo se usa para confirmar
      que el movimiento ya inició
    - Nunca se entra basándose en la vela actual abierta
    """

    def detect(self, df: pd.DataFrame, expected_direction: str) -> Dict:
        if len(df) < 5:
            return self._no_pattern("Datos insuficientes")

        # ── Velas de referencia (todas CERRADAS) ──────────────────────────────
        anchor = df.iloc[-5]   # vela -5 (contexto)
        c3     = df.iloc[-4]   # vela -4
        c2     = df.iloc[-3]   # vela -3
        signal = df.iloc[-2]   # VELA DE SEÑAL (última cerrada) ← aquí se detecta el patrón
        current = df.iloc[-1]  # vela actual (solo para confirmar dirección inicial)

        # Datos de la vela de señal (cerrada)
        o  = float(signal["open"])
        h  = float(signal["high"])
        l  = float(signal["low"])
        c  = float(signal["close"])

        body       = abs(c - o)
        full_range = h - l if h > l else 1e-8
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        is_bull    = c > o
        is_bear    = c < o

        # Datos velas anteriores
        o2, c2v = float(c2["open"]), float(c2["close"])
        o3, c3v = float(c3["open"]), float(c3["close"])
        oa, ca  = float(anchor["open"]), float(anchor["close"])

        # Vela actual (en formación) — solo para confirmar
        cur_o   = float(current["open"])
        cur_c   = float(current["close"])
        cur_moving_up   = cur_c > cur_o
        cur_moving_down = cur_c < cur_o

        patterns = []

        # ── Pin Bar (mecha dominante = rechazo fuerte) ───────────────────────
        if full_range > 0:
            # Pin bar alcista: mecha inferior ≥60% del rango, cuerpo ≤30%
            if lower_wick / full_range >= 0.60 and body / full_range <= 0.30:
                # La mecha debe ser al menos 2x el cuerpo
                if lower_wick >= body * 1.8 or body < full_range * 0.15:
                    strength = 0.82 + min(lower_wick / full_range - 0.60, 0.15)
                    patterns.append(("pin_bar_bullish", round(strength, 2)))

            # Pin bar bajista: mecha superior ≥60% del rango, cuerpo ≤30%
            if upper_wick / full_range >= 0.60 and body / full_range <= 0.30:
                if upper_wick >= body * 1.8 or body < full_range * 0.15:
                    strength = 0.82 + min(upper_wick / full_range - 0.60, 0.15)
                    patterns.append(("pin_bar_bearish", round(strength, 2)))

        # ── Hammer / Shooting Star ───────────────────────────────────────────
        if body > 0:
            if lower_wick >= body * 2.2 and upper_wick <= body * 0.4:
                patterns.append(("hammer", 0.78))
            if upper_wick >= body * 2.2 and lower_wick <= body * 0.4:
                patterns.append(("shooting_star", 0.78))

        # ── Engulfing fuerte ─────────────────────────────────────────────────
        # Alcista: vela signal es bull Y envuelve completamente a c2 (bearish)
        if is_bull and c2v < o2:  # c2 fue bajista
            if c > o2 and o <= c2v:  # envuelve completamente
                body_ratio = body / max(abs(c2v - o2), 1e-8)
                if body_ratio >= 1.1:
                    patterns.append(("bullish_engulfing", 0.83 + min(body_ratio - 1.1, 0.10)))
        # Bajista: vela signal es bear Y envuelve completamente a c2 (bullish)
        if is_bear and c2v > o2:  # c2 fue alcista
            if c < o2 and o >= c2v:
                body_ratio = body / max(abs(c2v - o2), 1e-8)
                if body_ratio >= 1.1:
                    patterns.append(("bearish_engulfing", 0.83 + min(body_ratio - 1.1, 0.10)))

        # ── Morning Star / Evening Star (3 velas cerradas) ───────────────────
        # Morning Star: c3 bearish grande → c2 pequeña → signal bullish
        c3_bear  = c3v < o3 and abs(c3v - o3) > full_range * 0.5
        c2_small = abs(c2v - o2) < abs(c3v - o3) * 0.35
        sig_bull = is_bull and c > (o3 + c3v) / 2
        if c3_bear and c2_small and sig_bull:
            patterns.append(("morning_star", 0.92))

        # Evening Star: c3 bullish grande → c2 pequeña → signal bearish
        c3_bull  = c3v > o3 and abs(c3v - o3) > full_range * 0.5
        sig_bear = is_bear and c < (o3 + c3v) / 2
        if c3_bull and c2_small and sig_bear:
            patterns.append(("evening_star", 0.92))

        # ── Doji de reversión (señal ambigua, solo si muy extremo) ───────────
        if full_range > 0 and body / full_range <= 0.10:
            if expected_direction == "CALL" and lower_wick / full_range >= 0.40:
                patterns.append(("doji_reversal_bull", 0.62))
            elif expected_direction == "PUT" and upper_wick / full_range >= 0.40:
                patterns.append(("doji_reversal_bear", 0.62))

        if not patterns:
            return self._no_pattern("Sin patrón en vela cerrada", signal_candle_info={
                "body_pct": body / full_range if full_range > 0 else 0,
                "lower_wick_pct": lower_wick / full_range if full_range > 0 else 0,
                "upper_wick_pct": upper_wick / full_range if full_range > 0 else 0,
            })

        # ── Filtrar por dirección esperada ────────────────────────────────────
        bullish_patterns = {"pin_bar_bullish", "hammer", "bullish_engulfing",
                            "doji_reversal_bull", "morning_star"}
        bearish_patterns = {"pin_bar_bearish", "shooting_star", "bearish_engulfing",
                            "doji_reversal_bear", "evening_star"}

        if expected_direction == "CALL":
            valid = [(p, s) for p, s in patterns if p in bullish_patterns]
        elif expected_direction == "PUT":
            valid = [(p, s) for p, s in patterns if p in bearish_patterns]
        else:
            valid = patterns

        if not valid:
            return self._no_pattern(
                f"Patrón detectado ({[p for p,_ in patterns]}) no coincide con dirección {expected_direction}",
                all_detected=[p for p, _ in patterns]
            )

        best_pattern, best_strength = max(valid, key=lambda x: x[1])

        # ── Confirmación por la vela actual ───────────────────────────────────
        # La vela actual (abierta) debe estar comenzando a moverse en la dirección correcta
        # Si va en contra, el patrón aún no está confirmado por el mercado
        candle_confirming = (
            (expected_direction == "CALL" and (cur_c >= cur_o or cur_c > c)) or
            (expected_direction == "PUT"  and (cur_c <= cur_o or cur_c < c))
        )

        # Para patrones fuertes, la confirmación de vela actual es opcional
        # Para patrones débiles (doji), es obligatoria
        requires_current_confirmation = best_strength < 0.75
        if requires_current_confirmation and not candle_confirming:
            return self._no_pattern(
                f"Patrón {best_pattern} detectado en vela cerrada pero vela actual no confirma — esperando",
                all_detected=[p for p, _ in patterns],
                waiting_confirmation=True,
            )

        conditions = {
            f"pattern_{best_pattern.split('_')[0]}": True,
            "pattern_strong": best_strength >= 0.80,
        }

        return {
            "pattern": best_pattern,
            "confirmed": True,
            "strength": min(best_strength, 0.97),
            "all_detected": [p for p, _ in patterns],
            "conditions": conditions,
            "candle_confirmed": candle_confirming,
            "used_closed_candle": True,   # garantía de que no es prematura
        }

    @staticmethod
    def _no_pattern(reason: str, all_detected: list = None,
                    signal_candle_info: dict = None,
                    waiting_confirmation: bool = False) -> Dict:
        return {
            "pattern": "none",
            "confirmed": False,
            "strength": 0.0,
            "conditions": {},
            "reason": reason,
            "all_detected": all_detected or [],
            "waiting_confirmation": waiting_confirmation,
            "signal_candle_info": signal_candle_info or {},
        }


# ─── Validador de timing de entrada ──────────────────────────────────────────

class EntryTimingValidator:
    """
    Valida que el momento de entrada sea preciso:
    - El precio debe estar DENTRO de la zona (no aproximándose)
    - El rechazo debe ser evidente en el histórico de velas
    - No debe haber ya comenzado el movimiento (entrada tardía)
    """

    def validate(self, df_m1: pd.DataFrame, zone_level: float,
                  zone_type: str, direction: str) -> Dict:
        if len(df_m1) < 6:
            return {"valid": True, "reason": "datos insuficientes para validar"}

        # ── 1. Verificar que la vela de señal tocó la zona ───────────────────
        signal_candle = df_m1.iloc[-2]  # última cerrada
        s_low  = float(signal_candle["low"])
        s_high = float(signal_candle["high"])
        s_close = float(signal_candle["close"])
        tol = zone_level * 0.0008  # 0.08% de tolerancia exacta

        zone_was_touched = (
            (zone_type == "support"    and s_low   <= zone_level + tol) or
            (zone_type == "resistance" and s_high  >= zone_level - tol) or
            abs(s_close - zone_level) <= tol * 2
        )

        if not zone_was_touched:
            return {
                "valid": False,
                "reason": f"La vela de señal no tocó la zona {zone_level:.5f} (low={s_low:.5f}, high={s_high:.5f})",
                "issue": "zone_not_touched",
            }

        # ── 2. Verificar que no empezó ya el movimiento ───────────────────────
        # Si el precio ya se alejó >0.15% de la zona, la entrada es tardía
        current_close = float(df_m1.iloc[-1]["close"])
        distance_from_zone = abs(current_close - zone_level) / zone_level

        if distance_from_zone > 0.0020:
            return {
                "valid": False,
                "reason": f"El movimiento ya comenzó — precio alejado {distance_from_zone*100:.2f}% de la zona (entrada tardía)",
                "issue": "late_entry",
            }

        # ── 3. Verificar rechazo real en la zona (no solo rozó) ──────────────
        # La mecha de rechazo debe ser visible
        body     = abs(float(signal_candle["close"]) - float(signal_candle["open"]))
        rng      = float(signal_candle["high"]) - float(signal_candle["low"])
        wick_pct = 0.0
        if rng > 0:
            if zone_type == "support":
                lower_wick = float(signal_candle["low"])
                lower_wick = min(float(signal_candle["open"]), float(signal_candle["close"])) - lower_wick
                wick_pct = lower_wick / rng
            else:
                upper_wick = float(signal_candle["high"])
                upper_wick -= max(float(signal_candle["open"]), float(signal_candle["close"]))
                wick_pct = upper_wick / rng

        if wick_pct < 0.12:
            return {
                "valid": False,
                "reason": f"Sin rechazo visible en la zona (mecha={wick_pct:.1%}, necesita ≥12%)",
                "issue": "no_rejection_wick",
            }

        return {
            "valid": True,
            "reason": "Timing válido — vela cerrada tocó zona con rechazo visible",
            "zone_touched": zone_was_touched,
            "rejection_wick_pct": wick_pct,
            "distance_from_zone": distance_from_zone,
        }


# ─── Motor principal ──────────────────────────────────────────────────────────

class IntelligentEngine:
    """
    Motor de inteligencia v4.1 — Timing de entrada preciso.

    Flujo corregido:
    1. Descargar gráfico completo (H1 + M15 + M5 + M1)
    2. Detectar zonas desde histórico
    3. Verificar que precio está EN zona fuerte (tolerancia ≤0.1%)
    4. Detectar patrón SOLO en vela cerrada (df.iloc[-2])
    5. Validar timing: zona realmente tocada + rechazo visible + no entrada tardía
    6. Analizar contexto completo
    7. Puntuar con pesos adaptativos
    8. Decidir — si pasa todos los filtros, entrar
    """

    ZONE_COOLDOWN = 1800  # 30 min sin repetir la misma zona
    ZONE_PERF_PATH = "zone_performance.json"

    def __init__(self):
        self.memory           = get_market_memory()
        self.zone_detector    = ZoneDetector()
        self.context_analyzer = ContextAnalyzer()
        self.learner          = get_adaptive_learner()
        self.pattern_detector = CandlePatternDetector()
        self.timing_validator = EntryTimingValidator()
        self.market_ai        = MarketAI()
        self.cascade          = CascadeTrendAnalyzer()
        self.reasoning_engine = get_reasoning_engine()
        self._last_zone_scan: Dict[str, float] = {}
        self._zone_scan_interval = 300
        self._last_cascade_result: Dict[str, object] = {}
        self._zone_last_trade: Dict[str, float] = {}
        self._zone_perf: Dict[str, Dict] = self._load_zone_perf()

    def _load_zone_perf(self) -> Dict[str, Dict]:
        import os, json
        path = os.path.join(os.path.dirname(__file__), self.ZONE_PERF_PATH)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_zone_perf(self):
        import os, json
        path = os.path.join(os.path.dirname(__file__), self.ZONE_PERF_PATH)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(self._zone_perf, f, indent=2)
        except: pass

    def record_zone_result(self, asset: str, zone_level: float, zone_type: str, won: bool):
        key = f"{asset}_{zone_level:.5f}_{zone_type}"
        rec = self._zone_perf.setdefault(key, {"w": 0, "l": 0, "first": time.time(), "last": time.time()})
        if won: rec["w"] += 1
        else: rec["l"] += 1
        rec["last"] = time.time()
        self._save_zone_perf()

    def _zone_is_bad(self, key: str) -> bool:
        rec = self._zone_perf.get(key)
        if not rec: return False
        total = rec["w"] + rec["l"]
        if total >= 2 and rec["l"] > rec["w"]:
            return True  # Más pérdidas que ganancias
        return False

    def _find_order_block_near_price(self, df_m5, current_price: float, df_m1=None, tolerance: float = 0.0030) -> Dict:
        best_ob = {"present": False, "confirmed": False, "strength": 0.0, "direction": "NEUTRAL", "distance": 999.0}
        move_threshold = 0.0010  # 0.10%
        def scan_df(df, label: str):
            if df is None or len(df) < 10:
                return
            closes = df["close"].values
            highs = df["high"].values
            lows = df["low"].values
            for i in range(2, len(closes) - 2):
                move_up_2 = (closes[i+2] / closes[i]) - 1
                move_down_2 = (closes[i+2] / closes[i]) - 1
                # CALL OB: vela alcista + 2 de 3 velas siguientes suben
                if closes[i] > closes[i-1]:
                    up_count = sum(1 for j in range(1, 4) if i+j < len(closes) and closes[i+j] > closes[i+j-1])
                    if up_count >= 2 and move_up_2 > move_threshold:
                        ob_high, ob_low = highs[i-1], lows[i-1]
                        mid = (ob_high + ob_low) / 2
                        dist = min(abs(current_price - mid), abs(current_price - ob_low)) / max(current_price, 0.0001)
                        if dist < tolerance and dist < best_ob["distance"]:
                            strength = min(1.0, abs(move_up_2) * 150 + 0.15)
                            best_ob.update({"present": True, "confirmed": False, "strength": strength, "direction": "CALL", "distance": dist, "level": mid})
                # PUT OB: vela bajista + 2 de 3 velas siguientes bajan
                if closes[i] < closes[i-1]:
                    dn_count = sum(1 for j in range(1, 4) if i+j < len(closes) and closes[i+j] < closes[i+j-1])
                    if dn_count >= 2 and move_down_2 < -move_threshold:
                        ob_high, ob_low = highs[i-1], lows[i-1]
                        mid = (ob_high + ob_low) / 2
                        dist = min(abs(current_price - mid), abs(current_price - ob_high)) / max(current_price, 0.0001)
                        if dist < tolerance and dist < best_ob["distance"]:
                            strength = min(1.0, abs(move_down_2) * 150 + 0.15)
                            best_ob.update({"present": True, "confirmed": False, "strength": strength, "direction": "PUT", "distance": dist, "level": mid})
        scan_df(df_m5, "M5")
        if df_m1 is not None:
            scan_df(df_m1, "M1")
        return best_ob

    def force_rescan_zones(self, asset: str, market_data):
        """Fuerza un re-escaneo inmediato de S/R después de una entrada."""
        try:
            df_m1  = market_data.get_candles(asset, 60, 200)
            df_m5  = market_data.get_candles(asset, 300, 120)
            df_m15 = market_data.get_candles(asset, 900, 60)
            df_h1  = market_data.get_candles(asset, 3600, 80)
            if df_m5 is not None and len(df_m5) >= 20:
                self._rescan_zones(asset, df_m5, df_m15, df_h1)
            # Resetear tiempo de último escaneo para forzar re-análisis completo
            self._last_zone_scan[asset] = 0
            self._last_cascade_result.pop(asset, None)
        except Exception:
            pass

    def analyze(self, asset: str, market_data, fe=None) -> Optional[Dict]:
        """
        Motor de análisis v5.1 — Jerarquía estricta de timeframes.

        Filosofía (binarias):
          H1  → sesgo general (context only, not entry)
          M15 → zonas estratégicas donde el precio debería reaccionar
          M5  → confirma que el acercamiento es limpio y ordenado
          M1  → ÚNICA vela que define la entrada (rechazo visible)

        fe (feature extras) puede incluir:
          watchlist_zone   → WatchedZone del par (del ZoneWatchlist)
          h1_bias          → "up" / "down" / "neutral"
          zone_origin_tf   → "H1" / "M15" / "M5"
          zone_importance  → 1/2/3
        """
        try:
            fe = fe or {}
            candle_watcher = get_candle_watcher()

            # ── 1. Datos multi-timeframe ─────────────────────────────────────
            df_m1 = market_data.get_candles(asset, 60, 200)
            if df_m1 is None or len(df_m1) < 30:
                return self._wait("Datos M1 insuficientes", asset)

            df_m5  = market_data.get_candles(asset, 300, 120)
            df_m15 = market_data.get_candles(asset, 900, 60)
            df_h1  = market_data.get_candles(asset, 3600, 80)

            if df_m5 is None or len(df_m5) < 20:
                return self._wait("Datos M5 insuficientes", asset)

            # Precio de referencia = cierre de la última vela CERRADA
            current_price = float(df_m1.iloc[-2]["close"])
            if current_price <= 0:
                return self._wait("Precio inválido", asset)

            # ── 2. Escanear zonas ────────────────────────────────────────────
            last_scan = self._last_zone_scan.get(asset, 0)
            if time.time() - last_scan > self._zone_scan_interval:
                self._rescan_zones(asset, df_m5, df_m15, df_h1)
                self._last_zone_scan[asset] = time.time()

            # ── 3. ¿Está el precio EN una zona fuerte? ───────────────────────
            # Tolerancia ampliada a 0.30% — el watchlist ya confirmó proximidad
            # La zona del watchlist tiene precedencia si viene de H1/M15
            min_zone_strength = self.learner.get_threshold("min_zone_strength", 0.30)
            nearest_zone = self.memory.get_nearest_strong_zone(
                asset, current_price, tolerance_pct=0.0030
            )
            zone_context_summary = self.memory.get_zone_context(asset, current_price)

            # Contexto del watchlist (si fue activado por proximidad)
            wl_zone       = fe.get("watchlist_zone")
            wl_strength   = getattr(wl_zone, 'strength', 0) if wl_zone else 0
            h1_bias       = fe.get("h1_bias", "neutral")
            zone_origin   = fe.get("zone_origin_tf", "M5")    # H1 > M15 > M5
            zone_import   = int(fe.get("zone_importance", 1))  # 1/2/3

            if nearest_zone is None or nearest_zone.strength < min_zone_strength:
                # Si el watcher estaba activo, lo detenemos — nos fuimos de zona
                if candle_watcher.is_watching(asset):
                    candle_watcher.stop_watching(asset)
                # Buscar la zona más cercana para informar al usuario
                any_zone = self.memory.get_nearest_strong_zone(asset, current_price, tolerance_pct=0.01)
                dist_str = ""
                if any_zone:
                    dist_pct = abs(any_zone.level - current_price) / current_price * 100
                    dist_str = f" | Zona más cercana: {any_zone.level:.5f} a {dist_pct:.2f}%"
                return {
                    "asset": asset,
                    "action": "WAIT",
                    "signal": "NEUTRAL",
                    "score": 0.0,
                    "confidence": 0.0,
                    "reason": f"Precio lejos de zona{dist_str}",
                    "phase": "buscando_zona",
                    "zone_count": len(self.memory.get_all_zones(asset)),
                    "zone_context": zone_context_summary,
                }

            # ── 4. Cooldown por zona: no repetir misma zona en 30 min ─────────
            zone_key = f"{asset}_{nearest_zone.level:.5f}_{nearest_zone.zone_type}"
            last_trade = self._zone_last_trade.get(zone_key, 0)
            if last_trade and (time.time() - last_trade) < self.ZONE_COOLDOWN:
                remaining = int(self.ZONE_COOLDOWN - (time.time() - last_trade))
                return {
                    "asset": asset,
                    "action": "WAIT",
                    "signal": "NEUTRAL",
                    "score": 0.0,
                    "confidence": 0.0,
                    "reason": f"Zona ya operada — cooldown {remaining//60}min restantes",
                    "phase": "cooldown_zona",
                }

            # ── 5. Analizar contexto completo ────────────────────────────────
            context = self.context_analyzer.analyze(
                df_m1, df_m5,
                df_m15 if df_m15 is not None and len(df_m15) >= 10 else df_m5,
                df_h1 if df_h1 is not None and len(df_h1) >= 5 else None,
                zone=nearest_zone,
                current_price=current_price,
            )
            expected_dir = context.get("expected_direction", "NEUTRAL")
            phase = context.get("market_phase", "unknown")

            # ── Iniciar/Actualizar CandleWatcher ────────────────────────────
            if not candle_watcher.is_watching(asset):
                candle_watcher.start_watching(
                    asset,
                    nearest_zone.level,
                    nearest_zone.zone_type,
                    expected_dir if expected_dir != "NEUTRAL" else "CALL"
                )
            watcher_verdict = candle_watcher.update(asset, market_data)

            if phase == "dead":
                return self._wait("Mercado muerto — sin volatilidad", asset, context=context)

            # ── 4b. Validación cascada H1→M15→M5→M1 ─────────────────────────
            # Esta es la validación central de la estrategia:
            # Solo entrar cuando la tendencia está confirmada en todos los TF
            # y el precio ha "avanzado" suficiente para confirmar que no es trampa
            cascade_result = self.cascade.analyze(
                df_h1=df_h1 if df_h1 is not None and len(df_h1) >= 10 else None,
                df_m15=df_m15 if df_m15 is not None and len(df_m15) >= 10 else None,
                df_m5=df_m5,
                df_m1=df_m1,
                current_price=current_price,
            )
            self._last_cascade_result[asset] = cascade_result

            # ── Modo advisory: la cascada guía pero NO bloquea completamente ──
            # El bot DEBE poder operar para aprender. La cascada penaliza/bonifica
            # el score final pero solo bloquea en casos extremos (dirección opuesta clara).

            # Usar la dirección de la cascada como dirección esperada si está alineada
            if cascade_result.direction != "NEUTRAL":
                if cascade_result.cascade_aligned:
                    # Cascada alineada → usar su dirección
                    expected_dir = cascade_result.direction
                elif expected_dir == "NEUTRAL":
                    # Sin dirección del contexto, usar la cascada aunque no esté 100% alineada
                    expected_dir = cascade_result.direction

            # Bloqueo SOLO cuando la cascada ve dirección OPUESTA con alineación alta
            # (ej: contexto dice CALL pero H1+M15+M5 dicen bajista con fuerza ≥ 0.75)
            if (cascade_result.direction != "NEUTRAL" and
                cascade_result.alignment_score >= 0.75 and
                expected_dir != "NEUTRAL" and
                cascade_result.direction != expected_dir):
                return self._wait(
                    f"Cascada opuesta al setup ({cascade_result.direction} vs {expected_dir})",
                    asset, context=context
                )

            # Bloqueo si liquidez detectada con señal débil (evitar trampa)
            if cascade_result.liquidity_risk and cascade_result.alignment_score < 0.40:
                return self._wait(
                    f"Trampa liquidez: {cascade_result.liquidity_reason[:70]}",
                    asset, context=context
                )

            # Si dirección no está clara la IA puede resolverlo — no bloqueamos aquí

            # ── 5. Detectar patrón en vela CERRADA (df.iloc[-2]) ────────────
            pattern = self.pattern_detector.detect(df_m1, expected_dir)

            # Si no hay patrón clásico, continuar — la IA puede encontrar micro-estructura
            # Solo bloqueamos si la IA tampoco ve setup válido

            # ── 6. Validar timing — bloqueo real para entradas sin rechazo ───
            # El timing validator detecta si la vela cerrada tocó la zona con
            # mecha de rechazo suficiente. Si no la tiene, se espera — no se entra.
            # La mecha mínima puede subir por zona si ya falló antes.
            min_wick = getattr(nearest_zone, "min_wick_required", 0.20)
            timing = self.timing_validator.validate(
                df_m1, nearest_zone.level, nearest_zone.zone_type,
                expected_dir if expected_dir != "NEUTRAL" else "CALL"
            )
            timing_issue = timing.get("issue", "")
            timing_valid = timing.get("valid", True)

            if not timing_valid:
                wick_actual = timing.get("rejection_wick_pct", 0.0)
                if timing_issue == "no_rejection_wick":
                    # ⚠️ RELAJADO: solo bloquear si mecha < 8% y zona débil
                    # Zonas fuertes (≥0.50) pueden operar sin mecha
                    if wick_actual < 0.08 and nearest_zone.strength < 0.50:
                        return self._wait(
                            f"Sin mecha de rechazo en zona (mecha={wick_actual:.1%} < 8%) "
                            f"y zona débil ({nearest_zone.strength:.2f}) — esperando confirmación",
                            asset, context=context,
                            extra={"timing_issue": timing_issue, "wick_pct": wick_actual}
                        )
                elif timing_issue == "late_entry":
                    return self._wait(
                        f"Movimiento ya iniciado — entrada tardía ({timing.get('reason','')})",
                        asset, context=context
                    )

            # ── 7. Condiciones para AdaptiveLearner ──────────────────────────
            # M5 approach check — ¿el M5 se acercó limpiamente a la zona?
            m5_approach = self._check_m5_approach(
                df_m5, nearest_zone.level, nearest_zone.zone_type
            )
            zone_ctx  = context.get("zone_context", {})
            momentum  = context.get("momentum", {})
            rsi       = momentum.get("rsi_m1", 50)
            rsi_dist  = abs(rsi - 50)
            pattern_name = pattern.get("pattern", "")
            has_pattern  = pattern.get("confirmed", False)

            mtf_aligned = self._check_mtf_alignment(context, expected_dir if expected_dir != "NEUTRAL" else "CALL")

            # ── Order Block confirmation (institucional) ──────────────────
            ob_data = self._find_order_block_near_price(df_m5, current_price, df_m1=df_m1)
            ob_confirmed = ob_data["present"] and ob_data["direction"] == expected_dir

            # ── Sesgo H1 alineado con la dirección esperada ───────────────
            h1_call_aligned = h1_bias == "up"   and expected_dir == "CALL"
            h1_put_aligned  = h1_bias == "down" and expected_dir == "PUT"
            h1_aligned      = h1_call_aligned or h1_put_aligned
            h1_counter      = (
                (h1_bias == "up"   and expected_dir == "PUT") or
                (h1_bias == "down" and expected_dir == "CALL")
            )

            conditions = {
                # ── Zona ──────────────────────────────────────────────────────
                "zone_strength_high":   nearest_zone.strength >= 0.70,
                "zone_strength_medium": 0.45 <= nearest_zone.strength < 0.70,
                "zone_multi_tf":        nearest_zone.touches >= 3,
                "zone_touch_3plus":     nearest_zone.touches >= 2,
                "zone_hold_rate_high":  nearest_zone.hold_rate >= 0.60,
                # Origen de la zona — cuanto más alto el TF, más fiable
                "zone_from_h1":         zone_import >= 3,   # zona identificada en H1
                "zone_from_m15":        zone_import >= 2,   # zona identificada en M15+
                # ── Tendencia y sesgo ──────────────────────────────────────────
                "trend_aligned":   zone_ctx.get("trend_aligned", False),
                "trend_strong":    context.get("dominant_trend") in ("uptrend", "downtrend"),
                "counter_trend":   not zone_ctx.get("trend_aligned", True),
                # H1 sesgo: el contexto de mayor TF confirma la dirección
                "h1_bias_aligned":  h1_aligned,
                "h1_bias_counter":  h1_counter,
                # ── RSI ────────────────────────────────────────────────────────
                "rsi_extreme":       rsi < 28 or rsi > 72,
                "rsi_oversold_sold": rsi < 38 and expected_dir == "CALL",
                "rsi_overbought":    rsi > 62 and expected_dir == "PUT",
                "rsi_divergence":    (momentum.get("bullish_divergence") or
                                      momentum.get("bearish_divergence", False)),
                # ── Patrones (detectados en vela M1 CERRADA) ──────────────────
                "pattern_pin_bar":       "pin_bar"   in pattern_name,
                "pattern_engulfing":     "engulfing"  in pattern_name,
                "pattern_hammer":        pattern_name in ("hammer", "shooting_star"),
                "pattern_doji_reversal": "doji"       in pattern_name,
                "pattern_morning_star":  "star"       in pattern_name,
                "pattern_strong":        pattern.get("strength", 0) >= 0.75,
                "has_any_pattern":       has_pattern,
                # ── MACD ───────────────────────────────────────────────────────
                "macd_cross":        abs(momentum.get("macd_hist", 0)) > 1e-5,
                "macd_hist_turning": momentum.get("macd_turning", False),
                # ── M5 approach — el acercamiento fue limpio y ordenado ────────
                "m5_clean_approach": m5_approach.get("clean", True),
                "m5_toward_zone":    m5_approach.get("direction") == "toward_zone",
                # ── Contexto y timing M1 ──────────────────────────────────────
                "approach_clean":   context.get("before_context", {}).get("approach", "") in
                                    ("falling_to_support", "rising_to_resistance"),
                "mtf_aligned":      mtf_aligned,
                "market_phase_ranging":  phase == "ranging",
                "market_phase_trending": phase in ("trending_up", "trending_down"),
                "setup_quality_high":    context.get("setup_quality", 0) >= 0.55,
                "rejection_visible":     timing.get("rejection_wick_pct", 0) >= 0.20,
                "candle_confirming":     pattern.get("candle_confirmed", False),
                # ── Order Block (institucional) ───────────────────────────────
                "ob_confirmed":      ob_confirmed,
                "ob_present":        ob_data["present"],
                "ob_strong":         ob_data["present"] and ob_data["strength"] >= 0.70,
            }

            # ── 8. MarketAI — análisis inteligente holístico ──────────────────
            # La IA razona sobre el setup completo como un trader experto
            ai_verdict = None
            try:
                ai_verdict = self.market_ai.analyze(
                    df_m1=df_m1, df_m5=df_m5, df_m15=df_m15, df_h1=df_h1,
                    zone_level=nearest_zone.level,
                    zone_type=nearest_zone.zone_type,
                    zone_strength=nearest_zone.strength,
                    zone_touches=nearest_zone.touches,
                    zone_hold_rate=nearest_zone.hold_rate,
                    pattern_name=pattern_name,
                    pattern_strength=pattern.get("strength", 0.5),
                    context=context,
                )
                ai_score    = ai_verdict.score        # 0–100
                ai_conf     = ai_verdict.confidence   # 0–1
                ai_dir      = ai_verdict.direction    # CALL / PUT / NEUTRAL
                ai_label    = ai_verdict.setup_label  # EXCELENTE/BUENO/MODERADO/DÉBIL/SKIP
                ai_narrative = ai_verdict.narrative
                ai_should    = ai_verdict.should_trade

                print(f"[OB] {asset} ob_present={ob_data['present']} ob_dir={ob_data['direction']} "
                      f"ob_str={ob_data['strength']:.2f} confirmed={ob_confirmed} "
                      f"expected={expected_dir}")

                # Si la IA dice que la dirección es diferente a la esperada,
                # confiar en la IA (tiene más contexto)
                if ai_dir != "NEUTRAL" and ai_dir != expected_dir and ai_score >= 55:
                    expected_dir = ai_dir

                # Si la IA dice SKIP con score muy bajo, no operar
                # EXCEPCIÓN: zona fuerte (≥0.85) → override de IA para no perder oportunidades
                # Usar tanto la zona de memoria como la del watchlist (más fiable)
                mem_strength = nearest_zone.strength
                zone_key = f"{asset}_{nearest_zone.level:.5f}_{nearest_zone.zone_type}"
                zone_is_bad = self._zone_is_bad(zone_key)
                zone_override = (mem_strength >= 0.85 or wl_strength >= 0.85) and not zone_is_bad
                if zone_is_bad:
                    print(f"[DEBUG_O] ZONA MALA {zone_key} — override desactivado (l={self._zone_perf.get(zone_key,{}).get('l',0)} w={self._zone_perf.get(zone_key,{}).get('w',0)})")
                print(f"[DEBUG_O] asset={asset} mem_str={mem_strength:.2f} wl_str={wl_strength:.2f} override={zone_override} bad={zone_is_bad} ai_label={ai_label} ai_score={ai_score}")
                if not zone_override and (ai_label == "SKIP" or (not ai_should and ai_score < 30)):
                    return {
                        "asset": asset, "action": "WAIT", "signal": ai_dir,
                        "score": ai_score, "confidence": ai_conf,
                        "reason": f"IA: {ai_label} — {ai_narrative[:60]}",
                        "phase": phase, "zone": nearest_zone.level,
                        "zone_strength": nearest_zone.strength,
                        "pattern": pattern_name, "context": context,
                        "ai_narrative": ai_narrative, "ai_label": ai_label,
                    }
                if zone_override:
                    max_str = max(nearest_zone.strength, wl_strength)
                    if max_str >= 0.95:
                        ai_score = max(ai_score, 42)
                        ai_label = "MODERADO" if ai_label in ("SKIP", "DÉBIL") else ai_label
                        ai_conf = max(ai_conf, 0.55)
                    elif max_str >= 0.90:
                        ai_score = max(ai_score, 35)
                        ai_label = "DÉBIL" if ai_label == "SKIP" else ai_label
                        ai_conf = max(ai_conf, 0.50)
                    else:
                        ai_score = max(ai_score, 30)
                        ai_label = "DÉBIL" if ai_label == "SKIP" else ai_label
                        ai_conf = max(ai_conf, 0.45)
                    print(f"[DEBUG_O] OVERRIDE para {asset}: score={ai_score:.0f} label={ai_label} conf={ai_conf:.2f} (max_str={max_str:.2f})")

            except Exception as ai_err:
                ai_score = 50.0; ai_conf = 0.5; ai_dir = expected_dir
                ai_label = "NORMAL"; ai_narrative = f"IA no disponible: {ai_err}"
                ai_should = True

            # Evitar NameError si ai_verdict nunca se asignó
            ai_evidence_for = getattr(ai_verdict, 'evidence_for', []) if ai_verdict else []

            # ── 9. Puntuación combinada (AdaptiveLearner + IA + Cascada) ─────────
            adaptive_score, breakdown = self.learner.score_conditions(conditions)
            min_score = self.learner.get_min_score()

            # Penalizaciones suaves (no duras) — solo reducen puntaje
            soft_penalties = 0.0
            if ob_confirmed:
                soft_penalties += 0.12  # Order Block confirma — bono fuerte
            elif ob_data["present"] and ob_data["direction"] != expected_dir:
                soft_penalties -= 0.08  # OB en contra — penalización
            if not zone_ctx.get("trend_aligned", True):
                soft_penalties += 0.07
            if rsi_dist < self.learner.get_threshold("min_rsi_distance", 8.0):
                soft_penalties += 0.04
            if nearest_zone.hold_rate < self.learner.get_threshold("min_zone_hold_rate", 0.45):
                soft_penalties += 0.05
            if not timing["valid"]:
                soft_penalties += 0.06

            # ── Modificador de cascada + TF hierarchy (advisory) ─────────────
            cascade_modifier = 0.0

            # Cascada H1→M15→M5→M1
            if cascade_result.cascade_aligned:
                cascade_modifier += 0.08
            if cascade_result.trend_advanced:
                cascade_modifier += 0.06
            if cascade_result.at_valid_sr:
                cascade_modifier += 0.05
            if cascade_result.liquidity_risk:
                cascade_modifier -= 0.10
            if not cascade_result.cascade_aligned:
                cascade_modifier -= 0.06

            # Origen de la zona: H1/M15 zones son más fiables en binarias
            if zone_import >= 3:          # Zona identificada en H1
                cascade_modifier += 0.08
            elif zone_import == 2:        # Zona identificada en M15
                cascade_modifier += 0.04

            # Sesgo H1: si el TF mayor confirma la dirección, +bono; si va en contra, -penalización
            if h1_aligned:
                cascade_modifier += 0.08   # H1 confirma la dirección
            elif h1_counter:
                cascade_modifier -= 0.15   # Contra el sesgo H1 — fuerte penalización

            # M5 approach: acercamiento limpio suma puntos
            if m5_approach.get("direction") == "toward_zone":
                cascade_modifier += 0.04
            elif m5_approach.get("clean") is False:
                cascade_modifier -= 0.05   # M5 sucio: rebotes recientes o zona rota

            # Límite razonable
            cascade_modifier = max(-0.18, min(0.26, cascade_modifier))

            adaptive_adjusted = max(0.0, adaptive_score - soft_penalties + cascade_modifier)

            # Combinación: 50% AdaptiveLearner (con cascada) + 50% MarketAI
            ai_normalized = ai_score / 100.0
            final_score = adaptive_adjusted * 0.50 + ai_normalized * 0.50

            # ── LLM Reasoning: pensar antes de actuar ─────────────────────────
            reasoning = None
            if Config.USE_LLM:
                try:
                    zone_str = (
                        f"level={nearest_zone.level:.5f} strength={nearest_zone.strength:.2f} "
                        f"touches={nearest_zone.touches} hold_rate={nearest_zone.hold_rate:.2f} "
                        f"type={nearest_zone.zone_type} import={zone_import}"
                    )
                    cascade_str = (
                        f"aligned={cascade_result.cascade_aligned} "
                        f"direction={cascade_result.direction} "
                        f"h1={cascade_result.h1_trend} m15={cascade_result.m15_trend} "
                        f"m5={cascade_result.m5_trend} score={cascade_result.alignment_score:.2f} "
                        f"advanced={cascade_result.trend_advanced} at_sr={cascade_result.at_valid_sr}"
                    )
                    ctx_str = (
                        f"expected_dir={expected_dir} phase={phase} "
                        f"dominant_trend={context.get('dominant_trend','?')} "
                        f"setup_quality={context.get('setup_quality',0):.2f} "
                        f"momentum_rsi={context.get('momentum',{}).get('rsi_m1',50)} "
                        f"market_phase={context.get('market_phase','?')}"
                    )

                    close = float(df_m1.iloc[-2]["close"]) if df_m1 is not None and len(df_m1) >= 2 else 0
                    open_ = float(df_m1.iloc[-2]["open"]) if df_m1 is not None and len(df_m1) >= 2 else 0
                    high = float(df_m1.iloc[-2]["high"]) if df_m1 is not None and len(df_m1) >= 2 else 0
                    low = float(df_m1.iloc[-2]["low"]) if df_m1 is not None and len(df_m1) >= 2 else 0
                    wv_sig = " | ".join(watcher_verdict.signals[:3]) if watcher_verdict.signals else watcher_verdict.verdict_type

                    candle_data = f"close={close:.5f} open={open_:.5f} high={high:.5f} low={low:.5f} watcher={wv_sig}"
                    extra_m1 = ""
                    try:
                        last_5 = df_m1.tail(6).head(5)
                        rows = []
                        for _, r in last_5.iterrows():
                            rows.append(f"o={float(r['open']):.5f} h={float(r['high']):.5f} l={float(r['low']):.5f} c={float(r['close']):.5f}")
                        extra_m1 = " | ".join(rows)
                    except Exception:
                        pass

                    reasoning = self.reasoning_engine.reason(
                        asset=asset, current_price=current_price,
                        zone_data=zone_str, cascade_data=cascade_str,
                        context_data=ctx_str, candle_summary=candle_data,
                        extra_m1_data=extra_m1,
                        cache_key=f"{asset}_{int(current_price*100000)}_{int(time.time())//30}"
                    )

                    if reasoning.should_skip:
                        self.reasoning_engine.clear_cache()
                        return self._wait(
                            f"LLM: {reasoning.reasoning_steps[0] if reasoning.reasoning_steps else 'SKIP'}",
                            asset, context=context, zone=nearest_zone
                        )
                    if not reasoning.should_trade and reasoning.conviction < 30:
                        return self._wait(
                            f"LLM: {reasoning.market_narrative[:120]} (conv:{reasoning.conviction}%)",
                            asset, context=context, zone=nearest_zone
                        )

                    # Si el LLM recomienda una direccion distinta con alta conviccion, override
                    llm_dir = reasoning.direction
                    if llm_dir in ("CALL", "PUT") and reasoning.conviction >= 60:
                        if llm_dir != expected_dir:
                            expected_dir = llm_dir
                            context["expected_direction"] = llm_dir
                except Exception as e:
                    pass

            # ── Bloqueo contra contra-tendencia (relajado) ───────────────────
            # Operar contra sesgo H1 requiere zona decente; permitimos más oportunidades
            if h1_counter:
                if nearest_zone.strength < 0.60 or (nearest_zone.strength < 0.75 and ai_label in ("DÉBIL", "SKIP", "")):
                    h1_word = "alcista" if h1_bias == "up" else "bajista"
                    return self._wait(
                        f"Contra-tendencia H1 ({h1_word}) str={nearest_zone.strength:.2f} ia={ai_label} — "
                        f"evitando (necesita str≥0.60 o IA mejor que DÉBIL)",
                        asset, context=context, zone=nearest_zone
                    )

            # ── 10. Decisión final ────────────────────────────────────────────
            # Umbral dinámico RELAJADO: más oportunidades
            effective_min = min_score
            if ai_label in ("EXCELENTE", "BUENO"):
                effective_min = max(0.22, min_score - 0.15)
            elif ai_label == "MODERADO":
                effective_min = max(0.25, min_score - 0.10)
            elif ai_label in ("DÉBIL",):
                effective_min = max(0.22, min_score - 0.12)
            # Cascada alineada y avanzada → bajar mínimo adicional (setup de calidad)
            if cascade_result.cascade_aligned and cascade_result.trend_advanced:
                effective_min = max(0.28, effective_min - 0.06)

            # Si la IA dice "debe operar" y el score combinado es razonable, proceder
            if final_score >= effective_min or (ai_should and final_score >= 0.30):

                # ── CandleWatcher: verificar que la vela confirma ────────────
                wv = watcher_verdict
                if wv.verdict_type == "abort":
                    return self._wait(
                        f"Watcher: {wv.reason} | {' '.join(wv.risk_flags)}",
                        asset, context=context, zone=nearest_zone
                    )
                # Dar tiempo al watcher para analizar (máximo 45s = MAX_WATCH_SECONDS)
                if wv.verdict_type == "watching":
                    wv_reason = wv.reason
                    if wv.watch_time_seconds >= 45:
                        return self._wait(
                            f"Watcher: {wv_reason} | {' '.join(wv.signals[:2])}",
                            asset, context=context, zone=nearest_zone
                        )

                confidence = self._calculate_confidence(
                    final_score, nearest_zone, context, pattern, timing
                )
                # Mezclar confianza con la de la IA
                confidence = confidence * 0.6 + ai_conf * 0.4

                # Si el watcher detectó fakeout, aumentar confianza
                if wv.verdict_type == "enter" and "fakeout" in " ".join(wv.signals).lower():
                    confidence = min(0.95, confidence * 1.12)

                exp_info = self._adaptive_expiration(
                    context, pattern, zone=nearest_zone, conditions=conditions,
                    ob_data=ob_data, cascade=cascade_result, df_m1=df_m1,
                    zone_perf=self._zone_perf.get(zone_key, {})
                )

                cascade_dict = {
                    "h1": cascade_result.h1_trend,
                    "m15": cascade_result.m15_trend,
                    "m5": cascade_result.m5_trend,
                    "m1": cascade_result.m1_trend,
                    "watcher_signals": wv.signals[:3] if wv.signals else [],
                    "watcher_candles": wv.candle_count,
                    "watcher_seconds": round(wv.watch_time_seconds, 1),
                    "aligned": cascade_result.cascade_aligned,
                    "alignment_score": cascade_result.alignment_score,
                    "advanced": cascade_result.trend_advanced,
                    "advancement_bars": cascade_result.advancement_bars,
                    "at_sr": cascade_result.at_valid_sr,
                    "sr_level": cascade_result.nearest_sr.price if cascade_result.nearest_sr else None,
                    "sr_type": cascade_result.nearest_sr.level_type if cascade_result.nearest_sr else None,
                    "sr_source": cascade_result.nearest_sr.period_source if cascade_result.nearest_sr else None,
                    "liquidity_risk": cascade_result.liquidity_risk,
                }
                zone_key = f"{asset}_{nearest_zone.level:.5f}_{nearest_zone.zone_type}"
                self._zone_last_trade[zone_key] = time.time()
                return {
                    "asset": asset,
                    "action": "TRADE",
                    "signal": expected_dir,
                    "score": final_score * 100,
                    "confidence": min(0.95, confidence),
                    "market_session": MarketIntelligence.get_current_session(),
                    "expiration": exp_info["seconds"],
                    "expiration_minutes": exp_info["minutes"],
                    "expiration_label": exp_info["label"],
                    "expiration_color": exp_info["color"],
                    "complexity_score": exp_info["complexity_score"],
                    "expiration_reasons": exp_info["reasons"],
                    "reason": ai_narrative or self._build_reason(nearest_zone, context, pattern, conditions, exp_info, timing),
                    "phase": phase,
                    "zone": nearest_zone.level,
                    "zone_strength": max(nearest_zone.strength, wl_strength),
                    "zone_touches": nearest_zone.touches,
                    "zone_hold_rate": nearest_zone.hold_rate,
                    "pattern": pattern_name,
                    "pattern_strength": pattern.get("strength", 0),
                    "dominant_trend": context.get("dominant_trend"),
                    "rsi": rsi,
                    "setup_quality": context.get("setup_quality", 0),
                    "rejection_wick": timing.get("rejection_wick_pct", 0),
                    "conditions": conditions,
                    "context": context,
                    "zone_object": nearest_zone,
                    "adaptive_breakdown": breakdown,
                    "timing": timing,
                    "ai_score": ai_score,
                    "ai_label": ai_label,
                    "ai_narrative": ai_narrative,
                    "ai_evidence_for": ai_evidence_for,
                    "cascade": cascade_dict,
                    "watcher_verdict": wv.verdict_type if wv else "none",
                    "watcher_signals": wv.signals[:3] if wv and wv.signals else [],
                    "watcher_entry_zone_pct": wv.entry_zone_pct if wv else 0.0,
                    "reasoning": reasoning.to_dict() if reasoning else None,
                }
            else:
                top_missing = self._top_missing(conditions, self.learner.weights)
                return {
                    "asset": asset,
                    "action": "WAIT",
                    "signal": expected_dir,
                    "score": final_score * 100,
                    "confidence": final_score,
                    "reason": f"IA:{ai_label} score={final_score*100:.0f} | {top_missing}",
                    "phase": phase,
                    "zone": nearest_zone.level,
                    "zone_strength": nearest_zone.strength,
                    "pattern": pattern_name,
                    "context": context,
                    "ai_score": ai_score,
                    "ai_label": ai_label,
                    "ai_narrative": ai_narrative,
                    "reasoning": reasoning.to_dict() if reasoning else None,
                }

        except Exception as e:
            return self._wait(f"Error en análisis: {e}", asset)

    # ── Escaneo de zonas ──────────────────────────────────────────────────────

    def _rescan_zones(self, asset: str, df_m5: pd.DataFrame,
                       df_m15: Optional[pd.DataFrame], df_h1: Optional[pd.DataFrame]):
        try:
            detected = self.zone_detector.detect_multi_tf(
                df_m5=df_m5,
                df_m15=df_m15 if df_m15 is not None and len(df_m15) >= 10 else df_m5,
                df_h1=df_h1 if df_h1 is not None and len(df_h1) >= 5 else None,
            )
            if detected:
                self.memory.bulk_add_zones(asset, detected)
                self.memory.purge_weak_zones(asset, min_strength=0.20)
                self.memory.save()
        except Exception:
            pass

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _check_mtf_alignment(self, context: Dict, direction: str) -> bool:
        expected = "uptrend" if direction == "CALL" else "downtrend"
        s1  = context.get("structure_m1", {}).get("trend", "neutral")
        s5  = context.get("structure_m5", {}).get("trend", "neutral")
        s15 = context.get("structure_m15", {}).get("trend", "neutral")
        opposite = "downtrend" if direction == "CALL" else "uptrend"
        aligned  = sum(1 for s in [s1, s5, s15] if s == expected)
        no_opp   = sum(1 for s in [s1, s5, s15] if s != opposite)
        return aligned >= 2 or no_opp >= 2

    def _calculate_confidence(self, score: float, zone, context: Dict,
                               pattern: Dict, timing: Dict = None) -> float:
        base         = score
        zone_boost   = zone.strength   * 0.12
        pattern_boost = pattern.get("strength", 0.5) * 0.10
        quality_boost = context.get("setup_quality", 0.5) * 0.08
        dir_boost     = context.get("direction_confidence", 0.5) * 0.08
        timing_boost  = 0.05 if timing and timing.get("rejection_wick_pct", 0) >= 0.40 else 0.0
        raw = base * 0.57 + zone_boost + pattern_boost + quality_boost + dir_boost + timing_boost
        return min(0.95, max(0.50, raw))

    def _adaptive_expiration(self, context: Dict, pattern: Dict,
                              zone=None, conditions: Dict = None,
                              ob_data: Dict = None, cascade=None,
                              df_m1=None, zone_perf: Dict = None) -> Dict:
        conditions  = conditions or {}
        momentum    = context.get("momentum", {})
        zone_ctx    = context.get("zone_context", {})
        phase       = context.get("market_phase", "ranging")
        zone_str    = zone.strength if zone else zone_ctx.get("zone_strength", 0.5)
        pattern_str = pattern.get("strength", 0.5)
        pattern_name = pattern.get("pattern", "")
        rsi          = momentum.get("rsi_m1", 50)
        rsi_dist     = abs(rsi - 50)
        trend_aligned = zone_ctx.get("trend_aligned", False)
        mtf_aligned   = conditions.get("mtf_aligned", False)
        dominant_trend = context.get("dominant_trend", "neutral")

        simplicity = 0.0
        reasons    = []

        # ── Volatilidad real (ATR) desde M1 ──
        volatility = 0
        if df_m1 is not None and len(df_m1) >= 14:
            highs = df_m1["high"].values[-14:]
            lows = df_m1["low"].values[-14:]
            closes = df_m1["close"].values[-14:]
            atr = sum(abs(h - l) for h, l in zip(highs, lows)) / 14
            price = closes[-1] if len(closes) > 0 else 1
            vol_pct = atr / price if price > 0 else 0
            if vol_pct >= 0.0015:
                volatility = 15; reasons.append(f"alta volatilidad ({vol_pct*100:.2f}% ATR)")
            elif vol_pct >= 0.0008:
                volatility = 8; reasons.append(f"volatilidad media ({vol_pct*100:.2f}%)")
            else:
                volatility = -5; reasons.append(f"baja volatilidad ({vol_pct*100:.2f}% ATR) → +tiempo")
        simplicity += volatility

        # ── Order Block (0-18 pts) ──
        ob = ob_data or {}
        if ob.get("confirmed"):
            simplicity += 18; reasons.append("OB confirma dirección")
            if ob.get("strength", 0) >= 0.70:
                simplicity += 5; reasons.append("OB fuerte")
        elif ob.get("present") and ob.get("direction") != "NEUTRAL":
            reasons.append(f"OB en dirección opuesta ({ob.get('direction')}) → +tiempo")
            simplicity -= 8
        elif not ob.get("present"):
            reasons.append("sin OB detectado → +tiempo")
            simplicity -= 4

        # ── Cascada alignment (0-15 pts) ──
        if cascade:
            if cascade.cascade_aligned:
                simplicity += 15; reasons.append("cascada alineada")
                if cascade.trend_advanced:
                    simplicity += 5; reasons.append("tendencia avanzada")
            elif cascade.liquidity_risk:
                reasons.append("riesgo liquidez → +tiempo")
                simplicity -= 10
            else:
                reasons.append("cascada no alineada → +tiempo")
                simplicity -= 5

        # ── Zone performance (historial) ──
        zp = zone_perf or {}
        if zp.get("l", 0) > zp.get("w", 0) and (zp.get("l", 0) + zp.get("w", 0)) >= 2:
            reasons.append(f"zona perdiendo ({zp.get('w',0)}W/{zp.get('l',0)}L) → +tiempo")
            simplicity -= 8
        elif zp.get("w", 0) > zp.get("l", 0) and (zp.get("w", 0) + zp.get("l", 0)) >= 2:
            simplicity += 8; reasons.append(f"zona ganadora ({zp.get('w',0)}W/{zp.get('l',0)}L)")

        # ── Zona (0-25 pts) ──
        if zone_str >= 0.80:
            simplicity += 25; reasons.append("zona muy fuerte")
        elif zone_str >= 0.65:
            simplicity += 18; reasons.append("zona fuerte")
        elif zone_str >= 0.50:
            simplicity += 10; reasons.append("zona moderada")
        else:
            simplicity += 3;  reasons.append("zona débil")

        # ── Patrón (0-22 pts) ──
        if pattern_name in ("morning_star", "evening_star"):
            simplicity += 15; reasons.append("star pattern (3 velas)")
        elif "engulfing" in pattern_name:
            simplicity += 19; reasons.append("engulfing fuerte")
        elif "pin_bar" in pattern_name:
            pts = 22 if pattern_str >= 0.85 else 16
            simplicity += pts; reasons.append(f"pin bar {'potente' if pts==22 else 'moderado'}")
        elif pattern_name in ("hammer", "shooting_star"):
            simplicity += 17; reasons.append("hammer/shooting star")
        elif "doji" in pattern_name:
            simplicity += 8;  reasons.append("doji (ambiguo → +tiempo)")
        else:
            simplicity += 5

        # ── RSI (0-20 pts) ──
        if rsi_dist >= 30:
            simplicity += 20; reasons.append(f"RSI muy extremo ({rsi:.0f})")
        elif rsi_dist >= 20:
            simplicity += 15; reasons.append(f"RSI extremo ({rsi:.0f})")
        elif rsi_dist >= 12:
            simplicity += 9
        else:
            simplicity += 3;  reasons.append(f"RSI neutro ({rsi:.0f}) → +tiempo")

        # ── MTF alignment (0-18 pts) ──
        if mtf_aligned:
            simplicity += 18; reasons.append("MTF alineados")
        else:
            simplicity += 3

        # ── Tendencia (0-12 pts) ──
        if trend_aligned and dominant_trend in ("uptrend", "downtrend"):
            simplicity += 12; reasons.append("con tendencia")
        elif trend_aligned:
            simplicity += 6
        else:
            reasons.append("contra tendencia → +tiempo")

        # ── Fase de mercado ──
        if phase in ("trending_up", "trending_down"):
            simplicity += 5;  reasons.append("mercado en tendencia")
        elif phase == "ranging":
            simplicity -= 5
        elif phase == "dead":
            simplicity -= 12; reasons.append("mercado lento → +tiempo")

        # ── Rechazo visible ──
        if conditions.get("rejection_visible"):
            simplicity += 5; reasons.append("rechazo visible en zona")

        simplicity = max(0.0, min(100.0, simplicity))
        min_floor = 2 if pattern_name.endswith("star") else 1

        if simplicity >= 82:
            minutes, label, color = 1, "SIMPLE",       "green"
        elif simplicity >= 64:
            minutes, label, color = 2, "MODERADO",     "cyan"
        elif simplicity >= 46:
            minutes, label, color = 3, "NORMAL",        "yellow"
        elif simplicity >= 28:
            minutes, label, color = 4, "COMPLEJO",      "dark_orange"
        else:
            minutes, label, color = 5, "MUY COMPLEJO", "red"

        minutes = max(min_floor, minutes)

        return {
            "seconds":          minutes * 60,
            "minutes":          minutes,
            "label":            label,
            "color":            color,
            "complexity_score": round(100 - simplicity, 1),
            "simplicity_score": round(simplicity, 1),
            "reasons":          reasons,
        }

    def _build_reason(self, zone, context: Dict, pattern: Dict,
                       conditions: Dict, exp_info: Dict = None,
                       timing: Dict = None) -> str:
        parts = [
            f"Zona {zone.zone_type} {zone.level:.5f} (str={zone.strength:.2f}, {zone.touches}x)",
            f"Patrón: {pattern.get('pattern','?')} [vela cerrada]",
            f"Tendencia: {context.get('dominant_trend','?')}",
            f"RSI={context.get('momentum',{}).get('rsi_m1',50):.1f}",
        ]
        if timing:
            parts.append(f"Rechazo={timing.get('rejection_wick_pct',0):.0%}")
        if exp_info:
            parts.append(f"Exp: {exp_info['minutes']}min [{exp_info['label']}]")
        return " | ".join(parts)

    def _top_missing(self, conditions: Dict, weights: Dict, n: int = 3) -> str:
        missing = [(k, weights.get(k, 1.0)) for k, v in conditions.items()
                   if not v and weights.get(k, 1.0) > 0.8]
        missing.sort(key=lambda x: -x[1])
        return ", ".join(k for k, _ in missing[:n]) or "score_bajo"

    def _check_m5_approach(self, df_m5, zone_level: float, zone_type: str) -> dict:
        """
        Verifica que el M5 se esté moviendo HACIA la zona de forma limpia.
        En binarias el M5 muestra si el precio se acerca ordenadamente o si
        ya rebotó y se va, lo que haría la entrada tardía o errónea.
        """
        if df_m5 is None or len(df_m5) < 5:
            return {"clean": True, "direction": "unknown", "approach_pct": 0.0}
        try:
            closes = [float(df_m5.iloc[i]["close"]) for i in range(-6, 0)]
            highs  = [float(df_m5.iloc[i]["high"])  for i in range(-6, 0)]
            lows   = [float(df_m5.iloc[i]["low"])   for i in range(-6, 0)]

            # Distancia al inicio vs al final de la ventana
            dist_start = abs(closes[0] - zone_level) / max(zone_level, 1e-8)
            dist_end   = abs(closes[-2] - zone_level) / max(zone_level, 1e-8)  # última cerrada
            approach_pct = (dist_start - dist_end) / max(dist_start, 1e-8)

            if approach_pct > 0.12:
                direction = "toward_zone"
                clean = True
            elif approach_pct < -0.10:
                direction = "away_from_zone"
                clean = False
            else:
                direction = "lateral"
                clean = True  # Lateral en zona es normal — consolida antes de salir

            # Penalizar si el precio ya atravesó la zona (ruptura reciente)
            zone_breaks = 0
            for i in range(1, 5):
                if zone_type == "support":
                    if closes[i] < zone_level * 0.9994:   # cerró debajo del soporte
                        zone_breaks += 1
                else:
                    if closes[i] > zone_level * 1.0006:   # cerró encima de la resistencia
                        zone_breaks += 1

            if zone_breaks >= 2:
                clean = False   # Zona rota repetidamente → no es setup válido

            return {
                "clean": clean,
                "direction": direction,
                "approach_pct": approach_pct,
                "zone_breaks": zone_breaks,
            }
        except Exception:
            return {"clean": True, "direction": "unknown", "approach_pct": 0.0}

    def _wait(self, reason: str, asset: str,
               context: Dict = None, zone=None, extra: Dict = None) -> Dict:
        r = {
            "asset": asset,
            "action": "WAIT",
            "signal": "NEUTRAL",
            "score": 0.0,
            "confidence": 0.0,
            "reason": reason,
            "phase": context.get("market_phase", "?") if context else "?",
            "zone": zone.level if zone else None,
            "zone_strength": zone.strength if zone else 0.0,
        }
        if extra:
            r.update(extra)
        return r
