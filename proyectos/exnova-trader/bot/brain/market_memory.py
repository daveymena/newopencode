"""
Market Memory — Memoria persistente del mercado
Registra zonas donde el precio ha reaccionado, cuántas veces y con qué fuerza.
Cada vez que el precio toca una zona y reacciona (o rompe), se actualiza el registro.
"""
import json
import os
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field


@dataclass
class Zone:
    level: float
    asset: str
    zone_type: str          # 'support', 'resistance', 'both'
    touches: int = 1
    holds: int = 0
    breaks: int = 0
    strength: float = 0.5
    last_touch_ts: float = 0.0
    first_seen_ts: float = 0.0
    avg_reaction_pips: float = 0.0
    notes: List[str] = field(default_factory=list)
    # Aprendizaje por zona: qué mecha mínima necesita esta zona específica
    min_wick_required: float = 0.20   # sube cuando falla por no_rejection_wick
    no_wick_failures: int = 0         # cuántas veces falló por falta de mecha

    @property
    def hold_rate(self) -> float:
        if self.touches == 0:
            return 0.0
        return self.holds / self.touches

    def recalculate_strength(self):
        """
        Fuerza de zona 0-1 basada en:
        - Número de toques (más = más fuerte, hasta 6)
        - Tasa de hold (0-1)
        - Recencia (decae si hace mucho que no se toca)
        - Reacción promedio en pips
        """
        touch_score = min(self.touches / 6.0, 1.0)
        hold_score = self.hold_rate
        age_hours = (time.time() - self.last_touch_ts) / 3600
        recency_score = max(0.0, 1.0 - age_hours / 48.0)  # decae en 48h
        pip_score = min(self.avg_reaction_pips / 20.0, 1.0) if self.avg_reaction_pips > 0 else 0.3

        self.strength = (
            touch_score * 0.30 +
            hold_score * 0.35 +
            recency_score * 0.20 +
            pip_score * 0.15
        )
        return self.strength


class MarketMemory:
    def __init__(self, persist_path: str = "brain/learning_state.json"):
        self.persist_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", persist_path
        )
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        self.zones: Dict[str, List[Zone]] = {}
        self.trade_history: List[dict] = []
        self._load()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)
            for asset, zone_list in data.get("zones", {}).items():
                self.zones[asset] = []
                for zd in zone_list:
                    z = Zone(**{k: v for k, v in zd.items() if k in Zone.__dataclass_fields__})
                    self.zones[asset].append(z)
            self.trade_history = data.get("trade_history", [])
        except Exception:
            pass

    def save(self):
        try:
            data = {
                "version": "4.0",
                "updated": time.time(),
                "zones": {
                    asset: [asdict(z) for z in zones]
                    for asset, zones in self.zones.items()
                },
                "trade_history": self.trade_history[-200:],
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ── Gestión de zonas ──────────────────────────────────────────────────────

    def add_or_update_zone(self, asset: str, level: float, zone_type: str,
                            reacted: bool, reaction_pips: float = 0.0,
                            failure_cause: str = ""):
        """
        Registra que el precio tocó un nivel.
        reacted=True si aguantó (hold), False si rompió.
        failure_cause: si hubo pérdida, la causa (ej 'no_rejection_wick')
        """
        if asset not in self.zones:
            self.zones[asset] = []

        existing = self._find_nearby_zone(asset, level, tolerance_pct=0.0015)
        if existing:
            existing.touches += 1
            existing.last_touch_ts = time.time()
            if reacted:
                existing.holds += 1
            else:
                existing.breaks += 1
            if reaction_pips > 0:
                existing.avg_reaction_pips = (existing.avg_reaction_pips * 0.7 + reaction_pips * 0.3)
            # Aprender: si falló por falta de mecha, subir el mínimo para esta zona
            if failure_cause == "no_rejection_wick":
                existing.no_wick_failures += 1
                existing.min_wick_required = min(
                    existing.min_wick_required + 0.05, 0.45
                )
            existing.recalculate_strength()
        else:
            z = Zone(
                level=level,
                asset=asset,
                zone_type=zone_type,
                touches=1,
                holds=1 if reacted else 0,
                breaks=0 if reacted else 1,
                last_touch_ts=time.time(),
                first_seen_ts=time.time(),
                avg_reaction_pips=reaction_pips,
            )
            z.recalculate_strength()
            self.zones[asset].append(z)

    def bulk_add_zones(self, asset: str, detected_zones: List[dict]):
        """Recibe zonas detectadas desde el historial de velas y las integra sin duplicar."""
        for zd in detected_zones:
            self.add_or_update_zone(
                asset=asset,
                level=zd["level"],
                zone_type=zd.get("type", "both"),
                reacted=True,
                reaction_pips=zd.get("avg_reaction_pips", 5.0),
            )
            # Actualizar touches con el conteo histórico
            existing = self._find_nearby_zone(asset, zd["level"])
            if existing:
                existing.touches = max(existing.touches, zd.get("touches", 1))
                existing.holds = max(existing.holds, zd.get("holds", 0))
                existing.recalculate_strength()

    def get_zones_near_price(self, asset: str, price: float,
                              tolerance_pct: float = 0.002,
                              min_strength: float = 0.35) -> List[Zone]:
        """Devuelve zonas activas cercanas al precio actual, ordenadas por fuerza."""
        if asset not in self.zones:
            return []
        nearby = []
        for z in self.zones[asset]:
            distance_pct = abs(z.level - price) / price
            if distance_pct <= tolerance_pct and z.strength >= min_strength:
                nearby.append((distance_pct, z))
        nearby.sort(key=lambda x: (x[0], -x[1].strength))
        return [z for _, z in nearby]

    def get_nearest_strong_zone(self, asset: str, price: float,
                                 tolerance_pct: float = 0.003) -> Optional[Zone]:
        """La zona más cercana y fuerte al precio actual."""
        candidates = self.get_zones_near_price(asset, price, tolerance_pct, min_strength=0.4)
        if not candidates:
            return None
        return max(candidates, key=lambda z: z.strength)

    def get_all_zones(self, asset: str, min_strength: float = 0.3) -> List[Zone]:
        return sorted(
            [z for z in self.zones.get(asset, []) if z.strength >= min_strength],
            key=lambda z: z.strength,
            reverse=True,
        )

    def purge_weak_zones(self, asset: str, min_strength: float = 0.2):
        if asset in self.zones:
            self.zones[asset] = [z for z in self.zones[asset] if z.strength >= min_strength]

    # ── Historial de trades ───────────────────────────────────────────────────

    def record_trade_result(self, trade: dict):
        self.trade_history.append(trade)
        self.save()

    def get_recent_trades(self, n: int = 50) -> List[dict]:
        return self.trade_history[-n:]

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _find_nearby_zone(self, asset: str, level: float,
                           tolerance_pct: float = 0.0015) -> Optional[Zone]:
        for z in self.zones.get(asset, []):
            if abs(z.level - level) / max(level, 0.0001) <= tolerance_pct:
                return z
        return None

    def get_zone_context(self, asset: str, price: float) -> dict:
        """Resumen del contexto de zonas para el precio actual."""
        above = [z for z in self.get_all_zones(asset) if z.level > price]
        below = [z for z in self.get_all_zones(asset) if z.level <= price]
        nearest_above = min(above, key=lambda z: z.level - price) if above else None
        nearest_below = max(below, key=lambda z: price - z.level) if below else None

        dist_above = (nearest_above.level - price) / price if nearest_above else 1.0
        dist_below = (price - nearest_below.level) / price if nearest_below else 1.0

        bias = "neutral"
        if nearest_below and nearest_above:
            if nearest_below.strength > nearest_above.strength * 1.3:
                bias = "bullish"
            elif nearest_above.strength > nearest_below.strength * 1.3:
                bias = "bearish"

        return {
            "nearest_support": nearest_below,
            "nearest_resistance": nearest_above,
            "dist_to_support_pct": dist_below,
            "dist_to_resistance_pct": dist_above,
            "bias": bias,
            "zone_count": len(self.get_all_zones(asset)),
        }


# Singleton
_memory: Optional[MarketMemory] = None


def get_market_memory() -> MarketMemory:
    global _memory
    if _memory is None:
        _memory = MarketMemory()
    return _memory
