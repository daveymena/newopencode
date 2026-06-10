"""
Candle Watcher — Seguimiento de vela M1 en tiempo real
Observa cómo se forma la vela, detecta reacciones, trampas, y decide
el punto más favorable para entrar SIN precipitarse.
"""
import time
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field


@dataclass
class CandleSnapshot:
    """Estado de una vela en formación en un momento dado."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    age_seconds: float
    body: float = 0.0
    full_range: float = 0.0
    upper_wick: float = 0.0
    lower_wick: float = 0.0
    wick_dominant: str = "none"       # "upper", "lower", "both", "none"
    direction: str = "neutral"         # "up", "down", "neutral"
    zone_touched: bool = False
    faked_out: bool = False            # ¿Rompió la zona y volvió?


@dataclass
class CandleVerdict:
    """
    Veredicto final del watcher después de analizar velas recientes.
    """
    confirmed: bool = False
    verdict_type: str = "waiting"      # "enter", "wait", "abort", "watching"
    entry_price: float = 0.0
    entry_zone_pct: float = 0.0        # A qué % de la zona entramos
    reason: str = ""
    signals: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    candle_count: int = 0
    watch_time_seconds: float = 0.0


class CandleWatcher:
    """
    Observa la vela M1 en formación cuando el precio está en zona.
    No permite entrar hasta que ve evidencia clara de:
    - Rechazo en la zona (mecha visible)
    - Falso breakout detectado (trampa de liquidez)
    - La vela actual confirma dirección con cuerpo
    - El setup tomó forma (no es entrada prematura)

    Si el precio está indeciso o absorbiendo, espera o aborta.
    """

    MIN_WATCH_SECONDS = 8        # Mínimo 8s observando antes de decidir
    MAX_WATCH_SECONDS = 40       # Máximo 40s — si no decide, aborta
    FAKEOUT_TOLERANCE = 0.0006   # 0.06% por debajo/encima de zona = posible fakeout
    REJECTION_WICK_MIN = 0.15    # 15% del rango debe ser mecha de rechazo
    CONFIRM_BODY_MIN = 0.25      # 25% del rango debe ser cuerpo en dirección correcta

    def __init__(self):
        self._watch_state: Dict[str, dict] = {}

    def start_watching(self, asset: str, zone_level: float, zone_type: str,
                       direction: str) -> dict:
        """Inicia monitoreo de la vela actual para este activo."""
        state = {
            "asset": asset,
            "zone_level": zone_level,
            "zone_type": zone_type,
            "direction": direction,
            "start_time": time.time(),
            "first_snapshot": None,
            "last_snapshot": None,
            "snapshots": [],
            "zone_touched": False,
            "max_penetration": 0.0,       # Máxima penetración dentro de la zona
            "fakeout_penetration": 0.0,   # Penetración pasajera (trampa)
            "fakeout_detected": False,
            "fakeout_reversal_started": False,
            "best_entry_point": 0.0,
            "entry_confidence": 0.0,
            "verdict": None,
            "candles_before": [],          # Velas cerradas anteriores (confirmación)
            "current_candle_open": 0.0,
        }
        self._watch_state[asset] = state
        return state

    def stop_watching(self, asset: str):
        """Detiene monitoreo y limpia estado."""
        self._watch_state.pop(asset, None)

    def update(self, asset: str, market_data) -> CandleVerdict:
        """
        Actualiza el watcher con el estado actual del mercado.
        Llámese cada ~3 segundos cuando el asset está en zona.
        Retorna CandleVerdict con el estado actual.
        """
        state = self._watch_state.get(asset)
        if not state:
            return CandleVerdict(verdict_type="not_watching")

        try:
            df = market_data.get_candles(asset, 60, 5)
            if df is None or len(df) < 3:
                return CandleVerdict(verdict_type="no_data")

            # Última vela cerrada (confirmación de comportamiento)
            last_closed = df.iloc[-2]
            # Vela actual (en formación)
            current = df.iloc[-1]

            co = float(current["open"])
            ch = float(current["high"])
            cl = float(current["low"])
            cc = float(current["close"])

            state["current_candle_open"] = co
            age = time.time() - state["start_time"]

            snapshot = CandleSnapshot(
                timestamp=time.time(),
                open=co, high=ch, low=cl, close=cc,
                age_seconds=age,
            )
            self._update_snapshot_metrics(snapshot, state["zone_level"], state["zone_type"])
            state["snapshots"].append(snapshot)
            state["last_snapshot"] = snapshot
            if state["first_snapshot"] is None:
                state["first_snapshot"] = snapshot

            if not state.get("candles_before") and len(df) >= 4:
                # Guardar velas cerradas previas para contexto
                for i in range(-5, -1):
                    row = df.iloc[i]
                    state["candles_before"].append({
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                    })

            # ── Análisis ──
            verdict = self._analyze(state, snapshot, last_closed, df)

            if verdict.verdict_type in ("enter", "abort"):
                self.stop_watching(asset)

            return verdict

        except Exception:
            return CandleVerdict(verdict_type="error")

    def _update_snapshot_metrics(self, snap: CandleSnapshot,
                                 zone_level: float, zone_type: str):
        """Calcula métricas de la vela en formación."""
        snap.body = abs(snap.close - snap.open)
        snap.full_range = snap.high - snap.low if snap.high > snap.low else 1e-8
        snap.upper_wick = snap.high - max(snap.open, snap.close)
        snap.lower_wick = min(snap.open, snap.close) - snap.low
        snap.direction = "up" if snap.close > snap.open else "down" if snap.close < snap.open else "neutral"

        if snap.full_range > 0:
            uw_pct = snap.upper_wick / snap.full_range
            lw_pct = snap.lower_wick / snap.full_range
            if uw_pct >= 0.55 and lw_pct < 0.30:
                snap.wick_dominant = "upper"
            elif lw_pct >= 0.55 and uw_pct < 0.30:
                snap.wick_dominant = "lower"
            elif uw_pct >= 0.35 and lw_pct >= 0.35:
                snap.wick_dominant = "both"
            else:
                snap.wick_dominant = "none"

        # ¿Tocó la zona?
        tol = zone_level * 0.0008
        if zone_type == "support":
            snap.zone_touched = snap.low <= zone_level + tol
        else:
            snap.zone_touched = snap.high >= zone_level - tol

    def _analyze(self, state: dict, snap: CandleSnapshot,
                 last_closed: pd.Series, df) -> CandleVerdict:
        """Análisis completo del estado actual de la vela."""
        asset = state["asset"]
        direction = state["direction"]
        zone_level = state["zone_level"]
        zone_type = state["zone_type"]
        elapsed = time.time() - state["start_time"]

        signals = []
        risks = []

        # ── 1. Verificar que la vela tocó la zona ──
        if snap.zone_touched:
            state["zone_touched"] = True
            signals.append("zona tocada")

            # Calcular penetración
            if zone_type == "support":
                penetration = max(0, (zone_level - snap.low) / zone_level)
            else:
                penetration = max(0, (snap.high - zone_level) / zone_level)
            state["max_penetration"] = max(state["max_penetration"], penetration)

            # ── 2. Detectar fakeout (trampa de liquidez) ──
            tol = zone_level * self.FAKEOUT_TOLERANCE
            fakeout_occurred = False

            if zone_type == "support":
                if snap.low < zone_level - tol:
                    state["fakeout_penetration"] = max(
                        state["fakeout_penetration"],
                        (zone_level - snap.low) / zone_level
                    )
                    if not state["fakeout_detected"]:
                        state["fakeout_detected"] = True
                        signals.append("fakeout detectado — barrido de stops")
                        fakeout_occurred = True
                    if snap.close > zone_level:
                        state["fakeout_reversal_started"] = True
                        signals.append("fakeout revertido — precio de vuelta sobre zona")
            else:
                if snap.high > zone_level + tol:
                    state["fakeout_penetration"] = max(
                        state["fakeout_penetration"],
                        (snap.high - zone_level) / zone_level
                    )
                    if not state["fakeout_detected"]:
                        state["fakeout_detected"] = True
                        signals.append("fakeout detectado — barrido de stops")
                        fakeout_occurred = True
                    if snap.close < zone_level:
                        state["fakeout_reversal_started"] = True
                        signals.append("fakeout revertido — precio de vuelta bajo zona")

            # ── 3. Detectar mecha de rechazo ──
            rejection_wick = self._detect_rejection_wick(snap, zone_type, direction)
            if rejection_wick > self.REJECTION_WICK_MIN:
                signals.append(f"mecha de rechazo: {rejection_wick:.0%}")
                # Mejor punto de entrada: cerca del final de la mecha
                if zone_type == "support":
                    entry = snap.low + (max(snap.open, snap.close) - snap.low) * 0.15
                else:
                    entry = snap.high - (snap.high - min(snap.open, snap.close)) * 0.15
                state["best_entry_point"] = entry
                state["entry_confidence"] = min(1.0, rejection_wick * 1.5)

            # ── 4. Detectar absorción (peligro) ──
            if self._detect_absorption(snap, zone_type, direction):
                risks.append("absorción en zona — precio indeciso")
                state["entry_confidence"] = max(0.1, state["entry_confidence"] - 0.2)

            # ── 5. Verificar dirección del cuerpo ──
            if snap.full_range > 0:
                body_dir_pct = snap.body / snap.full_range if snap.body > 0 else 0
                if (direction == "CALL" and snap.direction == "up" and body_dir_pct >= self.CONFIRM_BODY_MIN) or \
                   (direction == "PUT" and snap.direction == "down" and body_dir_pct >= self.CONFIRM_BODY_MIN):
                    signals.append(f"cuerpo confirma dirección ({snap.direction})")
                    if state["best_entry_point"] == 0:
                        state["best_entry_point"] = snap.close
                    if state["entry_confidence"] == 0:
                        state["entry_confidence"] = 0.5

            # ── 6. Velas cerradas anteriores confirman ──
            prev_confirmation = self._check_previous_candles(state, direction, zone_type)
            if prev_confirmation:
                signals.append("velas anteriores confirman rechazo")
                state["entry_confidence"] = min(1.0, state["entry_confidence"] + 0.15)

        # ── Decisión ──
        watch_duration = elapsed
        state["watch_time_seconds"] = watch_duration

        # ENTER: condiciones cumplidas
        if (snap.zone_touched and
                watch_duration >= self.MIN_WATCH_SECONDS and
                state["entry_confidence"] >= 0.30):

            fakeout_confirm = (state["fakeout_detected"] and state["fakeout_reversal_started"])

            if state["entry_confidence"] >= 0.40 or fakeout_confirm:
                entry_px = state["best_entry_point"] if state["best_entry_point"] > 0 else snap.close
                zone_dist = abs(entry_px - zone_level) / zone_level if zone_level > 0 else 0
                return CandleVerdict(
                    confirmed=True,
                    verdict_type="enter",
                    entry_price=entry_px,
                    entry_zone_pct=zone_dist,
                    reason="Setup confirmado por vela en formación",
                    signals=signals,
                    risk_flags=risks,
                    candle_count=len(state["snapshots"]),
                    watch_time_seconds=watch_duration,
                )

        # ABORT: pasó demasiado tiempo o absorción sin rumbo
        if watch_duration >= self.MAX_WATCH_SECONDS:
            if state["entry_confidence"] < 0.30:
                return CandleVerdict(
                    verdict_type="abort",
                    reason="Tiempo agotado sin confirmación clara",
                    signals=signals, risk_flags=risks,
                    watch_time_seconds=watch_duration,
                )
            else:
                entry_px = state["best_entry_point"] if state["best_entry_point"] > 0 else snap.close
                zone_dist = abs(entry_px - zone_level) / zone_level if zone_level > 0 else 0
                return CandleVerdict(
                    confirmed=True,
                    verdict_type="enter",
                    entry_price=entry_px,
                    entry_zone_pct=zone_dist,
                    reason="Tiempo máximo — entrando con confianza parcial",
                    signals=signals, risk_flags=risks,
                    candle_count=len(state["snapshots"]),
                    watch_time_seconds=watch_duration,
                )

        # WATCHING: todavía observando
        return CandleVerdict(
            verdict_type="watching",
            reason=f"Observando vela... {watch_duration:.0f}s",
            signals=signals, risk_flags=risks,
            candle_count=len(state["snapshots"]),
            watch_time_seconds=watch_duration,
        )

    def _detect_rejection_wick(self, snap: CandleSnapshot,
                                zone_type: str, direction: str) -> float:
        """
        Detecta mecha de rechazo en el lado de la zona.
        Retorna 0-1 qué tan fuerte es el rechazo.
        """
        if snap.full_range <= 0:
            return 0.0

        if zone_type == "support" and direction == "CALL":
            wick_pct = snap.lower_wick / snap.full_range
            if wick_pct >= 0.20:
                return min(1.0, wick_pct + 0.1)
        elif zone_type == "resistance" and direction == "PUT":
            wick_pct = snap.upper_wick / snap.full_range
            if wick_pct >= 0.20:
                return min(1.0, wick_pct + 0.1)

        return 0.0

    def _detect_absorption(self, snap: CandleSnapshot,
                            zone_type: str, direction: str) -> bool:
        """
        Detecta si el precio está siendo absorbido en la zona:
        - Sin mecha dominante
        - Cuerpo pequeño (vela indecisa)
        - Sin dirección clara
        """
        if snap.body == 0 or snap.full_range <= 0:
            return True

        body_pct = snap.body / snap.full_range
        if body_pct > 0.60 and snap.wick_dominant == "none":
            return True

        uw_pct = snap.upper_wick / snap.full_range
        lw_pct = snap.lower_wick / snap.full_range
        if uw_pct >= 0.30 and lw_pct >= 0.30:
            return True

        return False

    def _check_previous_candles(self, state: dict, direction: str,
                                 zone_type: str) -> bool:
        """Verifica si las últimas velas cerradas confirman rechazo en zona."""
        candles = state.get("candles_before", [])
        if len(candles) < 2:
            return False

        # Al menos 1 vela cerrada debe mostrar rechazo
        for c in candles[-3:]:
            if zone_type == "support":
                if c["low"] >= state["zone_level"] * 0.9995:
                    return True
            else:
                if c["high"] <= state["zone_level"] * 1.0005:
                    return True
        return False

    def get_state(self, asset: str) -> Optional[dict]:
        """Estado actual del watcher para un activo."""
        return self._watch_state.get(asset)

    def is_watching(self, asset: str) -> bool:
        return asset in self._watch_state


# ── Singleton ──
_watcher: Optional[CandleWatcher] = None


def get_candle_watcher() -> CandleWatcher:
    global _watcher
    if _watcher is None:
        _watcher = CandleWatcher()
    return _watcher
