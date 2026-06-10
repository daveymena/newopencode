"""
Zone Watchlist — Mapa Estratégico de Zonas Clave v1.0

Filosofía (binarias ≠ forex):
  • H1   → sesgo general del mercado (SOLO contexto, NO entrada)
  • M15  → zonas donde el precio DEBERÍA reaccionar (el mapa)
  • M5   → confirma acercamiento limpio y ordenado a la zona
  • M1   → única vela que define la ENTRADA (rechazo visible)

El bot NO entra a ciegas. Primero mapea los niveles estratégicos,
espera que el precio llegue, luego activa el análisis M1 detallado.

Estados de proximidad:
  FAR         > 0.50%  del nivel  → bot duerme, no analiza
  WATCHING    0.25-0.50%          → bot alerta, nota en dashboard
  APPROACHING 0.08-0.25%          → análisis M5 activo, preparar entrada
  AT_ZONE     < 0.08%             → análisis M1 completo, buscar rechazo
"""
import time
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from brain.zone_detector import ZoneDetector


# ── Umbrales de proximidad ─────────────────────────────────────────────────────
DIST_AT_ZONE     = 0.0012   # <0.12%   → EN zona → análisis M1 completo
DIST_APPROACHING = 0.0035   # <0.35%   → acercándose → preparar análisis
DIST_WATCHING    = 0.0065   # <0.65%   → vigilando → nota en dashboard
# > 0.50%  → lejos → solo heartbeat


@dataclass
class WatchedZone:
    asset: str
    level: float
    zone_type: str       # "support" / "resistance"
    origin_tf: str       # "H1" / "M15" / "M5"
    importance: int      # 3=H1, 2=M15, 1=M5
    strength: float
    hold_rate: float
    touches: int
    reaction_pips: float
    first_added: float
    last_updated: float

    # Estado calculado en tiempo real
    current_distance_pct: float = 1.0
    proximity_status: str = "far"   # "far" / "watching" / "approaching" / "at_zone"

    # Alerta única por ciclo de acercamiento
    approach_alerted: bool = False
    at_zone_alerted: bool  = False

    @property
    def label(self) -> str:
        return f"[{self.origin_tf}] {self.level:.5f} {self.zone_type[:4].upper()}"

    @property
    def is_h1_or_m15(self) -> bool:
        return self.importance >= 2


class ZoneWatchlist:
    """
    Mapa estratégico de zonas clave por par.
    • Se actualiza desde H1 / M15 / M5 cada 30 minutos.
    • Provee detección rápida de proximidad sin coste de API.
    • Dirección del H1 se almacena para filtrar entradas.
    """

    REFRESH_INTERVAL = 300   # 5 minutos (reducido de 30 para detectar cambios de estructura)

    def __init__(self):
        self._zones: Dict[str, List[WatchedZone]] = {}
        self._last_refresh: Dict[str, float] = {}
        self._h1_bias: Dict[str, str] = {}          # asset → "up" / "down" / "neutral"
        self._price_cache: Dict[str, Tuple[float, float]] = {}  # (price, ts)

    # ── Actualización del mapa ─────────────────────────────────────────────────

    def needs_refresh(self, asset: str) -> bool:
        return time.time() - self._last_refresh.get(asset, 0) > self.REFRESH_INTERVAL

    def force_refresh(self, asset: str):
        """Fuerza el refresh en el próximo ciclo."""
        self._last_refresh[asset] = 0

    def refresh_zones(self, asset: str, market_data) -> int:
        """
        Reconstruye el mapa de zonas desde H1/M15/M5.
        También calcula el sesgo H1.
        Retorna cuántas zonas se mapearon.
        """
        detector = ZoneDetector()

        try:
            df_h1  = market_data.get_candles(asset, 3600, 80)   # 80 velas H1 ≈ 3 días
            df_m15 = market_data.get_candles(asset, 900,  96)   # 96 velas M15 ≈ 24h
            df_m5  = market_data.get_candles(asset, 300,  72)   # 72 velas M5  ≈ 6h
        except Exception:
            return 0

        new_zones: List[WatchedZone] = []

        # ── Zonas H1 (importancia 3) ───────────────────────────────────────────
        if df_h1 is not None and len(df_h1) >= 20:
            self._h1_bias[asset] = self._calc_h1_bias(df_h1)
            for zd in detector.detect_from_candles(df_h1, asset):
                if zd["strength"] >= 0.30:
                    new_zones.append(WatchedZone(
                        asset=asset, level=zd["level"], zone_type=zd["type"],
                        origin_tf="H1", importance=3,
                        strength=zd["strength"], hold_rate=zd.get("hold_rate", 0.5),
                        touches=zd["touches"],
                        reaction_pips=zd.get("avg_reaction_pips", 5.0),
                        first_added=time.time(), last_updated=time.time(),
                    ))

        # ── Zonas M15 (importancia 2) ──────────────────────────────────────────
        if df_m15 is not None and len(df_m15) >= 20:
            for zd in detector.detect_from_candles(df_m15, asset):
                if zd["strength"] >= 0.38:
                    overlap = self._find_overlap(new_zones, zd["level"], asset)
                    if overlap:
                        # Reforzar zona H1 con confirmación M15
                        overlap.importance = max(overlap.importance, 3)
                        overlap.strength   = min(1.0, overlap.strength + 0.05)
                        overlap.hold_rate  = max(overlap.hold_rate, zd.get("hold_rate", 0.5))
                    else:
                        new_zones.append(WatchedZone(
                            asset=asset, level=zd["level"], zone_type=zd["type"],
                            origin_tf="M15", importance=2,
                            strength=zd["strength"], hold_rate=zd.get("hold_rate", 0.5),
                            touches=zd["touches"],
                            reaction_pips=zd.get("avg_reaction_pips", 5.0),
                            first_added=time.time(), last_updated=time.time(),
                        ))

        # ── Zonas M5 (importancia 1 — solo sin equivalente en TF superior) ────
        if df_m5 is not None and len(df_m5) >= 20:
            for zd in detector.detect_from_candles(df_m5, asset):
                if zd["strength"] >= 0.55:   # más exigente: M5 solo si es muy fuerte
                    overlap = self._find_overlap(new_zones, zd["level"], asset)
                    if not overlap:
                        new_zones.append(WatchedZone(
                            asset=asset, level=zd["level"], zone_type=zd["type"],
                            origin_tf="M5", importance=1,
                            strength=zd["strength"], hold_rate=zd.get("hold_rate", 0.5),
                            touches=zd["touches"],
                            reaction_pips=zd.get("avg_reaction_pips", 5.0),
                            first_added=time.time(), last_updated=time.time(),
                        ))

        # Ordenar por importancia y fuerza, guardar máx 14 por par
        new_zones.sort(key=lambda z: (-z.importance, -z.strength))
        self._zones[asset] = new_zones[:14]
        self._last_refresh[asset] = time.time()

        return len(self._zones[asset])

    # ── Actualización de precio y proximidad ───────────────────────────────────

    def update_price(self, asset: str, price: float):
        """
        Actualiza el caché de precio y recalcula el estado de proximidad
        para todas las zonas de este par. Muy rápido — sin llamadas API.
        """
        if price <= 0:
            return
        self._price_cache[asset] = (price, time.time())

        for z in self._zones.get(asset, []):
            dist = abs(z.level - price) / price
            z.current_distance_pct = dist

            old_status = z.proximity_status
            if dist <= DIST_AT_ZONE:
                z.proximity_status = "at_zone"
            elif dist <= DIST_APPROACHING:
                z.proximity_status = "approaching"
            elif dist <= DIST_WATCHING:
                z.proximity_status = "watching"
            else:
                z.proximity_status = "far"

            # Resetear alertas cuando el precio se aleja de nuevo
            if z.proximity_status == "far" and old_status != "far":
                z.approach_alerted = False
                z.at_zone_alerted  = False

    def get_nearest_zone(self, asset: str) -> Optional[WatchedZone]:
        """La zona más cercana al precio actual para este par."""
        zones = self._zones.get(asset, [])
        if not zones:
            return None
        return min(zones, key=lambda z: z.current_distance_pct)

    def get_status(self, asset: str) -> Tuple[str, Optional[WatchedZone], float]:
        """
        Retorna el estado más urgente para este par.
        ("far"|"watching"|"approaching"|"at_zone", zona_más_cercana, distancia_pct)
        """
        nearest = self.get_nearest_zone(asset)
        if nearest is None:
            return ("far", None, 1.0)
        return (nearest.proximity_status, nearest, nearest.current_distance_pct)

    def get_at_zone(self, asset: str) -> List[WatchedZone]:
        """Zonas de este par donde el precio está ahora mismo."""
        return [z for z in self._zones.get(asset, []) if z.proximity_status == "at_zone"]

    def get_approaching(self, asset: str) -> List[WatchedZone]:
        """Zonas de este par donde el precio se está acercando."""
        return [z for z in self._zones.get(asset, [])
                if z.proximity_status in ("approaching", "at_zone")]

    def get_h1_bias(self, asset: str) -> str:
        """Sesgo del H1 del par: 'up' / 'down' / 'neutral'."""
        return self._h1_bias.get(asset, "neutral")

    def get_all_active(self, assets: List[str]) -> List[Tuple[str, WatchedZone]]:
        """
        Todos los pares con zonas en estado approaching o at_zone.
        Ordenados: at_zone primero, luego approaching; dentro de cada grupo por importancia.
        """
        result = []
        for asset in assets:
            for z in self._zones.get(asset, []):
                if z.proximity_status in ("approaching", "at_zone"):
                    result.append((asset, z))
        result.sort(key=lambda x: (
            0 if x[1].proximity_status == "at_zone" else 1,
            -x[1].importance,
            x[1].current_distance_pct,
        ))
        return result

    def get_zone_count(self, asset: str) -> int:
        """Retorna la cantidad total de zonas para un par."""
        return len(self._zones.get(asset, []))

    def get_dashboard_rows(self, assets: List[str]) -> List[dict]:
        """Filas para el panel de vigilancia del dashboard."""
        rows = []
        for asset in assets:
            zones = sorted(
                self._zones.get(asset, []),
                key=lambda z: z.current_distance_pct,
            )
            price, _ = self._price_cache.get(asset, (0.0, 0))
            for z in zones[:3]:
                rows.append({
                    "asset": asset,
                    "level": z.level,
                    "zone_type": z.zone_type,
                    "origin_tf": z.origin_tf,
                    "importance": z.importance,
                    "strength": z.strength,
                    "distance_pct": z.current_distance_pct,
                    "status": z.proximity_status,
                    "price": price,
                    "h1_bias": self._h1_bias.get(asset, "?"),
                })
        return rows

    # ── Utilidades internas ────────────────────────────────────────────────────

    def _find_overlap(self, zones: List[WatchedZone], level: float,
                       asset: str, tol: float = 0.0018) -> Optional[WatchedZone]:
        for z in zones:
            if z.asset == asset and abs(z.level - level) / max(level, 1e-6) <= tol:
                return z
        return None

    def _calc_h1_bias(self, df_h1) -> str:
        """
        Sesgo del H1 basado en las últimas 20 velas:
        • EMA-fast > EMA-slow → up
        • EMA-fast < EMA-slow → down
        • Otherwise → neutral
        """
        try:
            closes = df_h1["close"].astype(float).values
            if len(closes) < 20:
                return "neutral"
            ema8  = self._ema(closes, 8)
            ema21 = self._ema(closes, 21)
            diff  = ema8[-1] - ema21[-1]
            threshold = closes[-1] * 0.0003   # 0.03% mínimo para confirmar sesgo
            if diff > threshold:
                return "up"
            elif diff < -threshold:
                return "down"
            return "neutral"
        except Exception:
            return "neutral"

    @staticmethod
    def _ema(closes, period: int):
        k = 2 / (period + 1)
        ema = [closes[0]]
        for p in closes[1:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema

    # ── Validación Dinámica de Zonas (v5.2) ────────────────────────────────────

    def is_zone_still_valid(self, zone: WatchedZone, current_price: float) -> bool:
        if time.time() - zone.first_added > 1500:
            return False
        if zone.zone_type == "support" and current_price < zone.level * 0.9998:
            return False
        if zone.zone_type == "resistance" and current_price > zone.level * 1.0002:
            return False
        current_bias = self._h1_bias.get(zone.asset, "neutral")
        if zone.origin_tf == "H1" and current_bias != "neutral":
            if zone.zone_type == "support" and current_bias == "up":
                return False
            if zone.zone_type == "resistance" and current_bias == "down":
                return False
        return True

    def filter_valid_zones(self, asset: str, current_price: float) -> List[WatchedZone]:
        valid = [z for z in self._zones.get(asset, [])
                 if self.is_zone_still_valid(z, current_price)]
        self._zones[asset] = valid
        return valid

    def detect_zone_breakout(self, asset: str, current_price: float) -> bool:
        zones_copy = list(self._zones.get(asset, []))
        for zone in zones_copy:
            if zone.zone_type == "support" and current_price < zone.level * 0.9995:
                self._zones[asset] = [
                    z for z in self._zones[asset]
                    if not (z.zone_type == "support" and z.level <= zone.level)
                ]
                return True
            elif zone.zone_type == "resistance" and current_price > zone.level * 1.0005:
                self._zones[asset] = [
                    z for z in self._zones[asset]
                    if not (z.zone_type == "resistance" and z.level >= zone.level)
                ]
                return True
        return False


# ── Singleton ──────────────────────────────────────────────────────────────────
_watchlist: Optional[ZoneWatchlist] = None


def get_zone_watchlist() -> ZoneWatchlist:
    global _watchlist
    if _watchlist is None:
        _watchlist = ZoneWatchlist()
    return _watchlist


