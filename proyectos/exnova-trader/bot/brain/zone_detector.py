"""
Zone Detector — Detecta zonas de soporte/resistencia desde datos históricos reales
Analiza el gráfico completo para encontrar niveles donde el precio reaccionó múltiples veces.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple


class ZoneDetector:
    def __init__(self, cluster_tolerance_pct: float = 0.0012):
        self.cluster_tol = cluster_tolerance_pct

    def detect_from_candles(self, df: pd.DataFrame, asset: str = "") -> List[Dict]:
        """
        Detecta zonas desde un DataFrame de velas.
        Devuelve lista de zonas con: level, type, touches, holds, avg_reaction_pips, strength
        """
        if len(df) < 20:
            return []

        df = df.copy()
        pivots = self._find_pivots(df)
        highs = [p for p in pivots if p["type"] == "high"]
        lows = [p for p in pivots if p["type"] == "low"]

        resistance_zones = self._cluster_levels(highs, "resistance")
        support_zones = self._cluster_levels(lows, "support")
        all_zones = resistance_zones + support_zones

        # Calcular reacción promedio y tasa de hold
        current_price = float(df["close"].iloc[-1])
        price_range = float(df["high"].max() - df["low"].min())

        for z in all_zones:
            z["avg_reaction_pips"] = self._estimate_reaction_pips(df, z["level"], z["type"])
            z["holds"], z["breaks"] = self._count_holds_breaks(df, z["level"], z["type"])
            touches = z["holds"] + z["breaks"]
            z["touches"] = max(touches, z.get("raw_touches", 1))
            z["hold_rate"] = z["holds"] / z["touches"] if z["touches"] > 0 else 0.5
            z["distance_pct"] = abs(z["level"] - current_price) / current_price if current_price > 0 else 1.0
            z["strength"] = self._zone_strength(z)

        # Ordenar por fuerza descendente
        all_zones.sort(key=lambda z: z["strength"], reverse=True)
        return [z for z in all_zones if z["strength"] >= 0.25]

    def detect_multi_tf(self, df_m5: pd.DataFrame, df_m15: pd.DataFrame,
                         df_h1: pd.DataFrame = None) -> List[Dict]:
        """
        Detección multi-timeframe: zonas que aparecen en múltiples TF valen más.
        """
        zones_m5 = self.detect_from_candles(df_m5)
        zones_m15 = self.detect_from_candles(df_m15)
        zones_h1 = self.detect_from_candles(df_h1) if df_h1 is not None and len(df_h1) >= 10 else []

        combined = []
        for z in zones_h1:
            z["tf_score"] = 3.0
            combined.append(z)

        for z in zones_m15:
            overlap = self._find_overlap(z, combined)
            if overlap:
                overlap["tf_score"] = overlap.get("tf_score", 1.0) + 2.0
                overlap["touches"] = max(overlap["touches"], z["touches"])
                overlap["holds"] = max(overlap["holds"], z["holds"])
                overlap["strength"] = max(overlap["strength"], z["strength"])
            else:
                z["tf_score"] = 2.0
                combined.append(z)

        for z in zones_m5:
            overlap = self._find_overlap(z, combined)
            if overlap:
                overlap["tf_score"] = overlap.get("tf_score", 1.0) + 1.0
                overlap["touches"] = max(overlap["touches"], z["touches"])
            else:
                z["tf_score"] = 1.0
                combined.append(z)

        # Reforzar fuerza con tf_score
        for z in combined:
            tf_boost = min((z.get("tf_score", 1.0) - 1.0) * 0.1, 0.3)
            z["strength"] = min(z["strength"] + tf_boost, 1.0)
            z["multi_tf"] = z.get("tf_score", 1.0) >= 2.0

        combined.sort(key=lambda z: z["strength"], reverse=True)
        return combined

    # ── Detección de pivots ───────────────────────────────────────────────────

    def _find_pivots(self, df: pd.DataFrame, left: int = 3, right: int = 3) -> List[Dict]:
        """Encuentra pivot highs y lows en el dataframe."""
        pivots = []
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        n = len(df)

        for i in range(left, n - right):
            # Pivot high
            is_high = all(highs[i] >= highs[i - j] for j in range(1, left + 1)) and \
                      all(highs[i] >= highs[i + j] for j in range(1, right + 1))
            if is_high:
                pivots.append({
                    "type": "high",
                    "level": float(highs[i]),
                    "idx": i,
                })
            # Pivot low
            is_low = all(lows[i] <= lows[i - j] for j in range(1, left + 1)) and \
                     all(lows[i] <= lows[i + j] for j in range(1, right + 1))
            if is_low:
                pivots.append({
                    "type": "low",
                    "level": float(lows[i]),
                    "idx": i,
                })

        return pivots

    def _cluster_levels(self, pivots: List[Dict], zone_type: str) -> List[Dict]:
        """Agrupa pivots cercanos en una sola zona."""
        if not pivots:
            return []

        pivots_sorted = sorted(pivots, key=lambda p: p["level"])
        clusters = []
        current_cluster = [pivots_sorted[0]]

        for p in pivots_sorted[1:]:
            ref_level = current_cluster[0]["level"]
            if abs(p["level"] - ref_level) / max(ref_level, 0.0001) <= self.cluster_tol:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)

        zones = []
        for cluster in clusters:
            avg_level = float(np.mean([p["level"] for p in cluster]))
            zones.append({
                "level": avg_level,
                "type": zone_type,
                "raw_touches": len(cluster),
                "touches": len(cluster),
                "holds": 0,
                "breaks": 0,
                "hold_rate": 0.5,
                "strength": 0.5,
                "avg_reaction_pips": 0.0,
                "distance_pct": 0.0,
                "multi_tf": False,
                "tf_score": 1.0,
            })

        return zones

    # ── Análisis de reacciones históricas ─────────────────────────────────────

    def _estimate_reaction_pips(self, df: pd.DataFrame, level: float, zone_type: str) -> float:
        """Cuántos pips en promedio rebota el precio desde esta zona."""
        reactions = []
        tol = level * self.cluster_tol * 2
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        n = len(df)

        lookahead = 5
        for i in range(1, n - 3):
            end = min(i + lookahead, n)
            if end - i < 2:
                continue
            if zone_type == "support":
                if abs(lows[i] - level) <= tol:
                    max_after = float(np.max(highs[i:end]))
                    reaction = (max_after - lows[i]) / level * 10000
                    if reaction > 0:
                        reactions.append(reaction)
            else:
                if abs(highs[i] - level) <= tol:
                    min_after = float(np.min(lows[i:end]))
                    reaction = (highs[i] - min_after) / level * 10000
                    if reaction > 0:
                        reactions.append(reaction)

        return float(np.mean(reactions)) if reactions else 5.0

    def _count_holds_breaks(self, df: pd.DataFrame, level: float,
                             zone_type: str) -> Tuple[int, int]:
        """Cuenta cuántas veces el precio aguantó (hold) y cuántas rompió (break) la zona."""
        holds = 0
        breaks = 0
        tol = level * self.cluster_tol * 2
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        n = len(df)

        for i in range(1, n - 3):
            look_idx = min(i + 2, n - 1)
            if zone_type == "support":
                if abs(lows[i] - level) <= tol:
                    if closes[look_idx] > level:
                        holds += 1
                    else:
                        breaks += 1
            else:
                if abs(highs[i] - level) <= tol:
                    if closes[look_idx] < level:
                        holds += 1
                    else:
                        breaks += 1

        return holds, breaks

    def _zone_strength(self, z: Dict) -> float:
        touch_score = min(z["touches"] / 5.0, 1.0)
        hold_score = z.get("hold_rate", 0.5)
        pip_score = min(z.get("avg_reaction_pips", 0) / 20.0, 1.0)
        dist_score = max(0.0, 1.0 - z.get("distance_pct", 0) / 0.01)
        return (
            touch_score * 0.35 +
            hold_score * 0.35 +
            pip_score * 0.15 +
            dist_score * 0.15
        )

    def _find_overlap(self, zone: Dict, existing: List[Dict]) -> Dict:
        for z in existing:
            if z["type"] == zone["type"]:
                lvl = z["level"]
                if lvl > 0 and abs(lvl - zone["level"]) / lvl <= self.cluster_tol * 2:
                    return z
        return None
