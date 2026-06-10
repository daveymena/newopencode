"""
market_intelligence.py — Sistema de aprendizaje continuo 24/7
=============================================================
Clasifica:
  - Horarios de mayor rentabilidad (sesiones Londres, NY, Asia, Overlap)
  - Mejores divisas por sesión y por hora
  - Patrones de expiración óptimos por activo
  - Evolución del ratio acierto/fallo por hora del día

Persiste en data/market_intelligence.json y se refuerza 24/7.
"""

import json
import os
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Constantes de sesiones de mercado ────────────────────────────────────────
# Horas UTC
LONDON_HOURS   = (7, 16)    # 07:00-16:00 UTC
NY_HOURS       = (12, 21)   # 12:00-21:00 UTC
ASIA_HOURS     = (23, 8)    # 23:00-08:00 UTC (pasa medianoche)
OVERLAP_HOURS  = (12, 16)   # 12:00-16:00 UTC (Londres+NY)

MAJOR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF"]

PERSIST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "market_intelligence.json"
)

# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class SessionStats:
    """Rendimiento de una sesión de mercado."""
    session_name: str          # london / ny / asia / overlap / other
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    best_assets: Dict[str, float] = field(default_factory=dict)  # asset → win_rate
    worst_assets: Dict[str, float] = field(default_factory=dict)
    avg_expiration_sec: float = 60.0
    profit_factor: float = 1.0
    consecutive_losses: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_trades, 1)

    def update(self, asset: str, won: bool, expiration_sec: int):
        self.total_trades += 1
        if won:
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1

        # Actualizar ranking del activo
        if asset not in self.best_assets:
            self.best_assets[asset] = 0.0
        old_rate = self.best_assets[asset]
        self.best_assets[asset] = old_rate * 0.85 + (1.0 if won else 0.0) * 0.15

        # Actualizar expiración promedio ponderada
        self.avg_expiration_sec = self.avg_expiration_sec * 0.9 + expiration_sec * 0.1
        self.profit_factor = (self.wins + 1) / max(self.losses, 1)


@dataclass
class HourlyStats:
    """Rendimiento granular por hora del día (UTC)."""
    hour: int  # 0-23
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    assets_traded: Dict[str, int] = field(default_factory=dict)
    best_direction: str = "CALL"
    volatility_avg: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_trades, 1)

    def update(self, asset: str, won: bool, direction: str, volatility: float = 0.0):
        self.total_trades += 1
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.assets_traded[asset] = self.assets_traded.get(asset, 0) + 1
        self.volatility_avg = self.volatility_avg * 0.9 + volatility * 0.1

        # Dirección predominante
        if self.total_trades >= 5:
            call_pct = self._dir_pct("CALL")
            self.best_direction = "CALL" if call_pct >= 0.5 else "PUT"

    def _dir_pct(self, direction: str) -> float:
        return direction == self.best_direction if hasattr(self, 'best_direction') else 0.5


@dataclass
class TrapProfile:
    """Perfil de condiciones que causan pérdidas (trampas)."""
    asset: str
    trap_type: str            # ej: "fake_breakout", "low_volatility_reversal"
    times_detected: int = 0
    pattern_signature: str = ""  # descripción del patrón
    avg_loss: float = 0.0
    last_seen: float = 0.0
    avoid_signal: bool = True  # Si debe evitarse automáticamente

    def update(self, loss_amount: float):
        self.times_detected += 1
        self.avg_loss = self.avg_loss * 0.8 + loss_amount * 0.2
        self.last_seen = time.time()


@dataclass
class AssetProfile:
    """Perfil completo de rendimiento de un activo."""
    asset: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    best_session: str = "unknown"
    best_expiration_sec: int = 60
    last_trade_ts: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    avg_confidence: float = 0.0
    pnl_net: float = 0.0
    is_blocked: bool = False
    block_reason: str = ""

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_trades, 1)

    def record_trade(self, won: bool, confidence: float, expiration_sec: int,
                     session: str, pnl: float):
        self.total_trades += 1
        self.last_trade_ts = time.time()
        if won:
            self.wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        self.avg_confidence = self.avg_confidence * 0.85 + confidence * 0.15
        self.pnl_net += pnl

        # Actualizar mejor sesión
        if session != "unknown":
            self.best_session = session

        # Actualizar mejor expiración (ponderada por éxito)
        if won:
            self.best_expiration_sec = int(
                self.best_expiration_sec * 0.7 + expiration_sec * 0.3
            )

        # Bloquear si racha de pérdidas
        if self.consecutive_losses >= 5:
            self.is_blocked = True
            self.block_reason = f"5+ pérdidas consecutivas"
        elif self.consecutive_losses >= 3 and self.win_rate < 0.3:
            self.is_blocked = True
            self.block_reason = f"Win rate bajo ({self.win_rate:.0%}) con racha negativa"
        else:
            # Desbloquear si recupera
            if self.consecutive_wins >= 3:
                self.is_blocked = False
                self.block_reason = ""


# ── Clase principal ──────────────────────────────────────────────────────────


class MarketIntelligence:
    """
    Sistema de inteligencia que aprende 24/7:
      - Por sesión de mercado
      - Por hora del día
      - Por activo individual
      - Detecta trampas recurrentes
      - Genera recomendaciones de mejora continua
    """

    def __init__(self, persist_path: str = PERSIST_PATH):
        self.persist_path = persist_path
        self.sessions: Dict[str, SessionStats] = {}
        self.hours: Dict[int, HourlyStats] = {}
        self.assets: Dict[str, AssetProfile] = {}
        self.traps: Dict[str, TrapProfile] = {}
        self._total_trades_all: int = 0
        self._total_wins_all: int = 0
        self._last_improvement_ts: float = 0.0

        # Inicializar sesiones
        for s in ["london", "ny", "asia", "overlap", "other"]:
            self.sessions[s] = SessionStats(session_name=s)

        # Inicializar horas
        for h in range(24):
            self.hours[h] = HourlyStats(hour=h)

        self._load()

    # ── Persistencia ──────────────────────────────────────────────────────

    def _load(self):
        try:
            if not os.path.exists(self.persist_path):
                return
            with open(self.persist_path) as f:
                data = json.load(f)

            for s_name, s_data in data.get("sessions", {}).items():
                if s_name in self.sessions:
                    for k, v in s_data.items():
                        if hasattr(self.sessions[s_name], k):
                            setattr(self.sessions[s_name], k, v)

            for h_str, h_data in data.get("hours", {}).items():
                h = int(h_str)
                if h in self.hours:
                    for k, v in h_data.items():
                        if hasattr(self.hours[h], k):
                            setattr(self.hours[h], k, v)

            for a_name, a_data in data.get("assets", {}).items():
                p = AssetProfile(asset=a_name)
                for k, v in a_data.items():
                    if hasattr(p, k):
                        setattr(p, k, v)
                self.assets[a_name] = p

            for t_key, t_data in data.get("traps", {}).items():
                t = TrapProfile(asset=t_data.get("asset", ""), trap_type=t_data.get("trap_type", ""))
                for k, v in t_data.items():
                    if hasattr(t, k):
                        setattr(t, k, v)
                self.traps[t_key] = t

            self._total_trades_all = data.get("total_trades", 0)
            self._total_wins_all = data.get("total_wins", 0)

            logger.info(f"MarketIntelligence cargado: {self._total_trades_all} trades históricos")
        except Exception as e:
            logger.warning(f"Error cargando MarketIntelligence: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            data = {
                "version": "2.0",
                "updated": time.time(),
                "total_trades": self._total_trades_all,
                "total_wins": self._total_wins_all,
                "sessions": {
                    s_name: {k: v for k, v in asdict(s).items() if k != "session_name"}
                    for s_name, s in self.sessions.items()
                },
                "hours": {
                    str(h): {k: v for k, v in asdict(hs).items() if k != "hour"}
                    for h, hs in self.hours.items()
                },
                "assets": {
                    a_name: asdict(ap)
                    for a_name, ap in self.assets.items()
                },
                "traps": {
                    t_key: asdict(tp)
                    for t_key, tp in self.traps.items()
                },
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error guardando MarketIntelligence: {e}")

    # ── Clasificación de sesión ───────────────────────────────────────────

    @staticmethod
    def classify_session(utc_hour: int) -> str:
        """Clasifica la hora UTC en sesión de mercado."""
        if OVERLAP_HOURS[0] <= utc_hour < OVERLAP_HOURS[1]:
            return "overlap"
        if LONDON_HOURS[0] <= utc_hour < LONDON_HOURS[1]:
            return "london"
        if NY_HOURS[0] <= utc_hour < NY_HOURS[1]:
            return "ny"
        if utc_hour >= ASIA_HOURS[0] or utc_hour < ASIA_HOURS[1]:
            return "asia"
        return "other"

    @staticmethod
    def get_current_session() -> str:
        """Devuelve la sesión actual basada en hora UTC."""
        utc_hour = datetime.utcnow().hour
        return MarketIntelligence.classify_session(utc_hour)

    # ── Registro de trade ─────────────────────────────────────────────────

    def record_trade(self, asset: str, direction: str, won: bool,
                     expiration_sec: int, confidence: float,
                     volatility: float = 0.0,
                     pnl: float = 0.0,
                     trap_type: str = ""):
        """
        Registra el resultado de un trade y actualiza todos los modelos.
        """
        utc_hour = datetime.utcnow().hour
        session = self.classify_session(utc_hour)

        self._total_trades_all += 1
        if won:
            self._total_wins_all += 1

        # ── Actualizar sesión ──
        if session in self.sessions:
            self.sessions[session].update(asset, won, expiration_sec)

        # ── Actualizar hora ──
        if utc_hour in self.hours:
            self.hours[utc_hour].update(asset, won, direction, volatility)

        # ── Actualizar activo ──
        if asset not in self.assets:
            self.assets[asset] = AssetProfile(asset=asset)
        self.assets[asset].record_trade(won, confidence, expiration_sec,
                                        session, pnl)

        # ── Registrar trampa si pérdida con patrón conocido ──
        if not won and trap_type:
            trap_key = f"{asset}|{trap_type}"
            if trap_key not in self.traps:
                self.traps[trap_key] = TrapProfile(
                    asset=asset, trap_type=trap_type
                )
            self.traps[trap_key].update(abs(pnl))

        # ── Guardar cada 5 trades ──
        if self._total_trades_all % 5 == 0:
            self.save()

    # ── Mejora continua (learning loop) ───────────────────────────────────

    def get_improvement_suggestions(self) -> List[str]:
        """
        Analiza datos históricos y genera sugerencias concretas.
        """
        suggestions = []

        # ── ¿Hay sesiones con rendimiento muy bajo? ──
        for s_name, s in self.sessions.items():
            if s.total_trades >= 5 and s.win_rate < 0.4:
                suggestions.append(
                    f"Sesión '{s_name}' con win_rate={s.win_rate:.0%} — "
                    f"reducir operaciones o aumentar exigencia"
                )

        # ── ¿Horas que consistentemente pierden? ──
        bad_hours = []
        for h, hs in self.hours.items():
            if hs.total_trades >= 5 and hs.win_rate < 0.35:
                bad_hours.append(f"{h:02d}:00 ({hs.win_rate:.0%})")
        if bad_hours:
            suggestions.append(f"Horas a evitar: {', '.join(bad_hours)}")

        # ── ¿Activos bloqueados? ──
        blocked = [a for a, ap in self.assets.items() if ap.is_blocked]
        if blocked:
            suggestions.append(f"Activos bloqueados temporalmente: {', '.join(blocked)}")

        # ── ¿Trampas recurrentes? ──
        frequent_traps = sorted(
            [t for t in self.traps.values() if t.times_detected >= 3],
            key=lambda t: t.times_detected, reverse=True
        )[:3]
        for t in frequent_traps:
            suggestions.append(
                f"Trampa detectada {t.times_detected}x en {t.asset}: {t.trap_type} "
                f"(pérdida media={t.avg_loss:.2f}) — EVITAR este patrón"
            )

        # ── Mejores activos por sesión actual ──
        current_session = self.get_current_session()
        if current_session in self.sessions:
            s = self.sessions[current_session]
            ranked = sorted(
                s.best_assets.items(), key=lambda x: x[1], reverse=True
            )[:3]
            if ranked:
                pairs_str = ", ".join(f"{a}({r:.0%})" for a, r in ranked)
                suggestions.append(
                    f"Mejores activos en {current_session}: {pairs_str}"
                )

        return suggestions

    def get_asset_rankings(self, top_n: int = 5) -> List[dict]:
        """Ranking global de activos por win rate (mín. 5 trades)."""
        ranked = sorted(
            [ap for ap in self.assets.values() if ap.total_trades >= 5],
            key=lambda ap: ap.win_rate,
            reverse=True
        )
        return [
            {
                "asset": ap.asset,
                "win_rate": ap.win_rate,
                "total": ap.total_trades,
                "best_session": ap.best_session,
                "blocked": ap.is_blocked,
            }
            for ap in ranked[:top_n]
        ]

    def get_best_hours(self, top_n: int = 5) -> List[dict]:
        """Mejores horas del día para operar."""
        ranked = sorted(
            [hs for hs in self.hours.values() if hs.total_trades >= 5],
            key=lambda hs: hs.win_rate,
            reverse=True
        )
        return [
            {
                "hour": f"{hs.hour:02d}:00",
                "win_rate": hs.win_rate,
                "total": hs.total_trades,
                "volatility": round(hs.volatility_avg, 4),
                "best_direction": hs.best_direction,
            }
            for hs in ranked[:top_n]
        ]

    def get_session_summary(self) -> Dict[str, dict]:
        """Resumen de rendimiento por sesión."""
        return {
            s_name: {
                "win_rate": s.win_rate,
                "trades": s.total_trades,
                "wins": s.wins,
                "losses": s.losses,
                "profit_factor": round(s.profit_factor, 2),
                "consecutive_losses": s.consecutive_losses,
            }
            for s_name, s in self.sessions.items()
        }

    # ── Validación previa al trade ────────────────────────────────────────

    def should_skip_trade(self, asset: str, confidence: float,
                          direction: str, expiration_sec: int) -> Tuple[bool, str]:
        """
        Valida condiciones de aprendizaje antes de permitir el trade.
        Retorna (skip, razón).
        """
        # 1. Activo bloqueado por racha de pérdidas
        if asset in self.assets and self.assets[asset].is_blocked:
            return True, self.assets[asset].block_reason

        # 2. Hora actual con bajo rendimiento histórico
        utc_hour = datetime.utcnow().hour
        hs = self.hours.get(utc_hour)
        if hs and hs.total_trades >= 5 and hs.win_rate < 0.30:
            return True, f"Hora {utc_hour}:00 históricamente mala ({hs.win_rate:.0%})"

        # 3. Sesión actual con bajo rendimiento
        session = self.classify_session(utc_hour)
        s = self.sessions.get(session)
        if s and s.total_trades >= 10 and s.win_rate < 0.30:
            return True, f"Sesión {session} con win_rate bajo ({s.win_rate:.0%})"

        # 4. Confianza menor que mínimo requerido por aprendizaje
        if asset in self.assets:
            ap = self.assets[asset]
            min_conf = max(0.55, ap.avg_confidence * 0.8)
            if confidence < min_conf and ap.total_trades >= 5:
                return True, f"Confianza {confidence:.2f} < mín requerida {min_conf:.2f}"

        # 5. Trampa conocida en este activo
        for t_key, t in self.traps.items():
            if t.asset == asset and t.times_detected >= 2:
                # Si es una trampa reciente (última hora)
                if time.time() - t.last_seen < 3600:
                    return True, f"Trampa '{t.trap_type}' detectada hace <1h en {asset}"

        return False, ""

    def get_trap_warnings(self, asset: str) -> List[str]:
        """Advertencias de trampas conocidas para un activo."""
        warnings = []
        for t_key, t in self.traps.items():
            if t.asset == asset and t.times_detected >= 1:
                recency = "reciente" if time.time() - t.last_seen < 7200 else "histórico"
                warnings.append(
                    f"Trampa '{t.trap_type}' detectada {t.times_detected}x "
                    f"({recency}, pérdida media: {t.avg_loss:.1f})"
                )
        return warnings

    # ── Reporte general ───────────────────────────────────────────────────

    def full_report(self) -> str:
        """Genera reporte completo de estado del aprendizaje."""
        lines = []
        lines.append("=" * 60)
        lines.append("MARKET INTELLIGENCE REPORT")
        lines.append(f"Total trades: {self._total_trades_all} | "
                     f"Global WR: {self._total_wins_all/max(self._total_trades_all,1):.0%}")
        lines.append("=" * 60)

        lines.append("\n── SESIONES ──")
        for s_name, s in self.sessions.items():
            if s.total_trades > 0:
                lines.append(
                    f"  {s_name:8s} | {s.total_trades:3d} trades | "
                    f"WR: {s.win_rate:.0%} | PF: {s.profit_factor:.2f} | "
                    f"CL: {s.consecutive_losses}"
                )

        lines.append("\n── MEJORES HORAS ──")
        for h_info in self.get_best_hours(5):
            lines.append(
                f"  {h_info['hour']} | WR: {h_info['win_rate']:.0%} | "
                f"{h_info['total']} trades | dir: {h_info['best_direction']}"
            )

        lines.append("\n── TOP ACTIVOS ──")
        for a_info in self.get_asset_rankings(10):
            flag = " [BLOQUEADO]" if a_info["blocked"] else ""
            lines.append(
                f"  {a_info['asset']:8s} | WR: {a_info['win_rate']:.0%} | "
                f"{a_info['total']:3d} trades | mejor: {a_info['best_session']}{flag}"
            )

        active_traps = [t for t in self.traps.values() if t.times_detected >= 2]
        if active_traps:
            lines.append(f"\n── TRAMPAS DETECTADAS ({len(active_traps)}) ──")
            for t in sorted(active_traps, key=lambda x: x.times_detected, reverse=True)[:5]:
                lines.append(f"  {t.asset} | {t.trap_type} | {t.times_detected}x | pérdida: {t.avg_loss:.1f}")

        lines.append("\n── SUGERENCIAS ──")
        for sug in self.get_improvement_suggestions():
            lines.append(f"  → {sug}")

        lines.append("=" * 60)
        return "\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────────────────

_intelligence: Optional[MarketIntelligence] = None


def get_market_intelligence() -> MarketIntelligence:
    global _intelligence
    if _intelligence is None:
        _intelligence = MarketIntelligence()
    return _intelligence
