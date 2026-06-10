"""
Adaptive Learner — El bot aprende de su propio historial
Actualiza los pesos de cada condición según su historial real de aciertos/fallos.
Persiste el estado de aprendizaje en JSON.
"""
import json
import os
import time
import math
from typing import Dict, List, Optional, Tuple


class AdaptiveLearner:
    """
    Mantiene y actualiza los pesos de cada condición que influye en las entradas.
    Cada peso representa qué tanto confiar en esa condición basado en experiencia real.
    Un peso > 1.0 significa que esa condición ha sido buena predictor → se pondera más.
    Un peso < 1.0 significa que esa condición ha fallado → se le da menos importancia.
    """

    DEFAULT_WEIGHTS = {
        # Zona y posición en el gráfico
        "zone_strength_high": 1.0,      # zona con strength > 0.7
        "zone_strength_medium": 1.0,    # zona con strength 0.5-0.7
        "zone_multi_tf": 1.0,           # zona visible en múltiples TF
        "zone_touch_3plus": 1.0,        # zona con 3+ toques
        "zone_hold_rate_high": 1.0,     # zona con hold rate > 70%
        # Tendencia
        "trend_aligned": 1.0,           # operando a favor de la tendencia
        "trend_strong": 1.0,            # tendencia confirmada en H1+M15
        "counter_trend": 0.7,           # operando contra tendencia (penalizado por defecto)
        # RSI
        "rsi_extreme": 1.0,             # RSI < 25 o > 75
        "rsi_oversold_sold": 1.0,       # RSI < 35
        "rsi_overbought": 1.0,          # RSI > 65
        "rsi_divergence": 1.0,          # divergencia RSI/precio
        # Patrones de vela
        "pattern_pin_bar": 1.0,
        "pattern_engulfing": 1.0,
        "pattern_hammer": 1.0,
        "pattern_doji_reversal": 1.0,
        "pattern_morning_star": 1.0,
        "pattern_strong": 1.0,          # cualquier patrón fuerte
        "has_any_pattern": 1.0,         # existe al menos un patrón reconocido
        # MACD
        "macd_cross": 1.0,
        "macd_hist_turning": 1.0,
        # Contexto
        "approach_clean": 1.0,          # precio llegó limpiamente a la zona
        "mtf_aligned": 1.0,             # M1+M5+M15 alineados
        "market_phase_ranging": 1.0,    # mercado en rango (bueno para reversiones)
        "market_phase_trending": 1.0,   # mercado en tendencia
        "setup_quality_high": 1.0,      # setup_quality > 0.7
        "rejection_visible": 1.0,       # vela de rechazo visible en zona
        "candle_confirming": 1.0,       # vela M1 confirma dirección
    }

    DEFAULT_THRESHOLDS = {
        "min_zone_strength": 0.25,      # más relajado: más zonas válidas
        "min_rsi_distance": 10.0,       # menos exigente en RSI
        "min_zone_hold_rate": 0.35,     # más permisivo
        "min_setup_quality": 0.38,
        "min_score_to_trade": 0.45,     # menor umbral para más operaciones
    }

    # Thresholds cuando el bot tiene pocos datos (< 15 trades)
    BOOTSTRAP_THRESHOLDS = {
        "min_zone_strength": 0.20,
        "min_rsi_distance": 8.0,
        "min_zone_hold_rate": 0.30,
        "min_setup_quality": 0.30,
        "min_score_to_trade": 0.35,
    }

    def __init__(self, persist_path: str = "brain/adaptive_state.json"):
        self.persist_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", persist_path
        )
        self.weights: Dict[str, float] = dict(self.DEFAULT_WEIGHTS)
        self.thresholds: Dict[str, float] = dict(self.DEFAULT_THRESHOLDS)
        self.condition_stats: Dict[str, Dict] = {
            k: {"wins": 0, "losses": 0, "total": 0}
            for k in self.DEFAULT_WEIGHTS
        }
        self.learning_rate = 0.08       # qué tan rápido aprende (0.05-0.15)
        self.min_weight = 0.3
        self.max_weight = 2.5
        self.total_trades = 0
        self.total_wins = 0
        self._load()

    # ── Puntuación adaptativa ─────────────────────────────────────────────────

    def score_conditions(self, conditions: Dict[str, bool]) -> Tuple[float, Dict]:
        """
        Recibe un dict de condiciones {nombre: True/False} y devuelve:
        - score: float 0-1 ponderado por los pesos aprendidos
        - breakdown: contribución de cada condición activa
        """
        total_weight = 0.0
        weighted_score = 0.0
        breakdown = {}

        for cond_name, is_active in conditions.items():
            weight = self.weights.get(cond_name, 1.0)
            total_weight += weight
            contribution = weight if is_active else 0.0
            weighted_score += contribution
            if is_active:
                breakdown[cond_name] = {
                    "weight": weight,
                    "win_rate": self._win_rate(cond_name),
                }

        if total_weight == 0:
            return 0.0, {}

        score = weighted_score / total_weight
        return score, breakdown

    def _win_rate(self, cond_name: str) -> float:
        stats = self.condition_stats.get(cond_name, {})
        total = stats.get("total", 0)
        wins = stats.get("wins", 0)
        return wins / total if total > 0 else 0.5

    # ── Aprendizaje post-trade ────────────────────────────────────────────────

    def learn_from_trade(self, conditions_at_entry: Dict[str, bool],
                          result: str, diagnosis: Dict = None):
        """
        Actualiza los pesos basándose en el resultado de una operación.
        result: 'WIN' o 'LOSS'
        conditions_at_entry: las condiciones que estaban activas al entrar
        diagnosis: por qué se cree que falló (del TradeEvaluator)
        """
        is_win = result == "WIN"
        self.total_trades += 1
        if is_win:
            self.total_wins += 1

        for cond_name, was_active in conditions_at_entry.items():
            if not was_active:
                continue

            # Actualizar estadísticas
            if cond_name not in self.condition_stats:
                self.condition_stats[cond_name] = {"wins": 0, "losses": 0, "total": 0}
            self.condition_stats[cond_name]["total"] += 1
            if is_win:
                self.condition_stats[cond_name]["wins"] += 1
            else:
                self.condition_stats[cond_name]["losses"] += 1

            # Actualizar peso usando Bayesian update simplificado
            current_weight = self.weights.get(cond_name, 1.0)
            stats = self.condition_stats[cond_name]
            if stats["total"] >= 3:
                wr = stats["wins"] / stats["total"]
                # Si win rate es bueno → aumentar peso; si es malo → reducir
                target = wr * 2.0  # rango 0-2 (baseline=1.0 si wr=50%)
                delta = (target - current_weight) * self.learning_rate
                new_weight = current_weight + delta
                self.weights[cond_name] = max(self.min_weight, min(self.max_weight, new_weight))

        # Ajustar thresholds si el diagnóstico indica causa específica
        if diagnosis and not is_win:
            self._adjust_thresholds_from_diagnosis(diagnosis)

        self._save()

    def _adjust_thresholds_from_diagnosis(self, diagnosis: Dict):
        """Ajusta thresholds mínimos basado en el diagnóstico de fallo."""
        cause = diagnosis.get("primary_cause", "")

        if cause == "zone_too_weak":
            self.thresholds["min_zone_strength"] = min(
                self.thresholds["min_zone_strength"] + 0.03, 0.75
            )
        elif cause == "poor_setup_quality":
            self.thresholds["min_setup_quality"] = min(
                self.thresholds["min_setup_quality"] + 0.03, 0.80
            )
        elif cause == "rsi_not_extreme":
            self.thresholds["min_rsi_distance"] = min(
                self.thresholds["min_rsi_distance"] + 1.0, 25.0
            )
        elif cause == "zone_broke":
            self.thresholds["min_zone_hold_rate"] = min(
                self.thresholds["min_zone_hold_rate"] + 0.02, 0.80
            )
        elif cause == "no_rejection_wick":
            # Sin mecha de rechazo → requerir mecha mínima visible
            self.thresholds["min_rejection_wick"] = min(
                self.thresholds.get("min_rejection_wick", 0.20) + 0.04, 0.45
            )
        elif cause == "premature_entry":
            # Entrada antes de cerrar la vela → subir threshold de calidad
            self.thresholds["min_setup_quality"] = min(
                self.thresholds.get("min_setup_quality", 0.45) + 0.03, 0.80
            )
        elif cause in ("counter_trend", "cascade_misaligned"):
            # Operó contra la tendencia — aumentar score mínimo
            self.thresholds["min_score_to_trade"] = min(
                self.thresholds.get("min_score_to_trade", 0.52) + 0.02, 0.70
            )
        elif cause == "liquidity_trap":
            # Trampa de liquidez — requerir mayor distancia a zona
            self.thresholds["min_zone_hold_rate"] = min(
                self.thresholds.get("min_zone_hold_rate", 0.40) + 0.03, 0.80
            )

    def get_min_score(self) -> float:
        """
        Retorna el umbral mínimo de score para operar.
        Modo bootstrap (< 15 trades): usa thresholds reducidos para que el bot
        pueda acumular datos de aprendizaje antes de volverse más selectivo.
        """
        if self.total_trades < 15:
            return self.BOOTSTRAP_THRESHOLDS.get("min_score_to_trade", 0.45)
        return self.thresholds.get("min_score_to_trade", 0.52)

    def get_threshold(self, name: str, default: float = 0.5) -> float:
        """
        Retorna un threshold específico. En bootstrap usa valores reducidos.
        """
        if self.total_trades < 15 and name in self.BOOTSTRAP_THRESHOLDS:
            return self.BOOTSTRAP_THRESHOLDS[name]
        return self.thresholds.get(name, default)

    def get_top_conditions(self, n: int = 5) -> List[Dict]:
        """Las condiciones más predictivas según el historial."""
        result = []
        for cond, stats in self.condition_stats.items():
            if stats["total"] >= 3:
                wr = stats["wins"] / stats["total"]
                result.append({
                    "condition": cond,
                    "win_rate": wr,
                    "total": stats["total"],
                    "weight": self.weights.get(cond, 1.0),
                })
        return sorted(result, key=lambda x: x["win_rate"], reverse=True)[:n]

    def get_global_winrate(self) -> float:
        return self.total_wins / self.total_trades if self.total_trades > 0 else 0.0

    def summary(self) -> str:
        wr = self.get_global_winrate()
        top = self.get_top_conditions(3)
        top_str = ", ".join([f"{c['condition']}({c['win_rate']:.0%})" for c in top])
        return (f"Trades={self.total_trades} WR={wr:.1%} | "
                f"Top: {top_str if top_str else 'acumulando datos...'}")

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            data = {
                "weights": self.weights,
                "thresholds": self.thresholds,
                "condition_stats": self.condition_stats,
                "total_trades": self.total_trades,
                "total_wins": self.total_wins,
                "last_updated": time.time(),
            }
            tmp = self.persist_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.persist_path)
        except Exception as e:
            import sys
            print(f"[AdaptiveLearner] ERROR guardando estado: {e}", file=sys.stderr)

    def _load(self):
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)
            if "weights" in data:
                self.weights.update(data["weights"])
            if "thresholds" in data:
                self.thresholds.update(data["thresholds"])
            if "condition_stats" in data:
                self.condition_stats.update(data["condition_stats"])
            self.total_trades = data.get("total_trades", 0)
            self.total_wins = data.get("total_wins", 0)
        except Exception:
            pass


# Singleton
_learner: Optional[AdaptiveLearner] = None


def get_adaptive_learner() -> AdaptiveLearner:
    global _learner
    if _learner is None:
        _learner = AdaptiveLearner()
    return _learner
