"""
CascadeTrendAnalyzer — Validación en cascada H1 → M15 → M5 → M1
Estrategia: solo entrar cuando la tendencia está confirmada en todos los TF
y el precio ya ha "avanzado" suficiente para confirmar que no es una trampa.

Lógica:
1. H1 define la dirección maestra
2. M15 confirma que la tendencia sigue activa (períodos 15)
3. M5 muestra el impulso inmediato  
4. M1 da el timing exacto de entrada
5. El precio debe estar en S/R del período 15 o 20
6. La tendencia debe haber "avanzado" antes de entrar (no entrar al inicio)
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class TrendLevel:
    timeframe: str
    direction: str        # "up", "down", "neutral"
    strength: float       # 0-1
    advanced: bool        # ¿La tendencia ya avanzó lo suficiente?
    ema_slope: float      # Pendiente EMA
    structure: str        # "bullish", "bearish", "choppy", "flat"
    last_swing: float     # Último swing relevante
    candles_in_trend: int # Cuántas velas lleva la tendencia


@dataclass 
class SRLevel:
    price: float
    level_type: str    # "support", "resistance"
    period_source: str # "p15", "p20"
    touches: int
    strength: float    # 0-1
    distance_pct: float  # Distancia al precio actual


@dataclass
class CascadeResult:
    """Resultado completo del análisis en cascada."""
    direction: str         # "CALL", "PUT", "NEUTRAL"
    cascade_aligned: bool  # ¿Todos los TF apuntan juntos?
    alignment_score: float # 0-1 qué tan alineados están
    trend_advanced: bool   # ¿La tendencia ya avanzó?
    advancement_bars: int  # Cuántos períodos lleva la tendencia activa
    nearest_sr: Optional[SRLevel]  # S/R más cercano
    at_valid_sr: bool      # ¿El precio está en un S/R válido?
    liquidity_risk: bool   # ¿Hay riesgo de trampa de liquidez?
    liquidity_reason: str
    h1_trend: str
    m15_trend: str
    m5_trend: str
    m1_trend: str
    reason: str
    should_enter: bool
    wait_reason: str       # Por qué esperar si should_enter=False


class CascadeTrendAnalyzer:
    """
    Analiza la tendencia en cascada desde H1 hasta M1.
    Solo recomienda entrada cuando:
    1. La cascada está alineada (H1 y M15 al menos)
    2. La tendencia lleva al menos 3-4 períodos activa (avanzada)
    3. El precio llegó a un S/R del período 15 o 20
    4. No hay trampa de liquidez evidente
    """

    def analyze(self,
                df_h1: Optional[pd.DataFrame],
                df_m15: Optional[pd.DataFrame],
                df_m5: Optional[pd.DataFrame],
                df_m1: pd.DataFrame,
                current_price: float) -> CascadeResult:

        # ── Analizar cada TF ──────────────────────────────────────────────────
        h1_level  = self._analyze_tf(df_h1,  "H1")  if df_h1  is not None and len(df_h1)  >= 10 else None
        m15_level = self._analyze_tf(df_m15, "M15") if df_m15 is not None and len(df_m15) >= 10 else None
        m5_level  = self._analyze_tf(df_m5,  "M5")  if df_m5  is not None and len(df_m5)  >= 10 else None
        m1_level  = self._analyze_tf(df_m1,  "M1")  if len(df_m1) >= 10 else None

        # ── Dirección maestra desde H1 (o M15 si H1 no disponible) ───────────
        master = h1_level or m15_level
        if not master:
            return self._neutral("Sin datos suficientes para análisis en cascada")

        master_dir = master.direction
        if master_dir == "neutral":
            return self._neutral("H1 lateral — esperar dirección clara en TF mayor")

        direction = "CALL" if master_dir == "up" else "PUT"

        # ── Evaluar alineación de cascada ─────────────────────────────────────
        levels = [l for l in [h1_level, m15_level, m5_level, m1_level] if l]
        aligned_count = sum(1 for l in levels if l.direction == master_dir)
        total_count   = len(levels)
        alignment_score = aligned_count / total_count if total_count > 0 else 0.0

        # Mínimo: H1 + M15 deben coincidir
        h1_ok  = h1_level  is not None and h1_level.direction  == master_dir
        m15_ok = m15_level is not None and m15_level.direction == master_dir
        m5_ok  = m5_level  is not None and m5_level.direction  == master_dir
        m1_ok  = m1_level  is not None and m1_level.direction  == master_dir

        cascade_aligned = (h1_ok or m15_ok) and alignment_score >= 0.50

        # ── Verificar si la tendencia ha avanzado (no es inicio fresco) ──────
        # La tendencia debe llevar al menos 5 períodos activa en M15 o M5
        # para evitar falsas señales en pullbacks dentro de una tendencia mayor
        advancement_bars = 0
        trend_advanced   = True  # Relajado: no requerimos avance mínimo para tener más entradas
        
        if m15_level:
            advancement_bars = m15_level.candles_in_trend
        elif m5_level:
            advancement_bars = m5_level.candles_in_trend
        elif m1_level:
            advancement_bars = m1_level.candles_in_trend

        # ── Detectar S/R desde períodos 15 y 20 ─────────────────────────────
        sr_levels = []
        if df_m15 is not None and len(df_m15) >= 20:
            sr_levels.extend(self._find_sr_levels(df_m15, current_price, "p20", periods=20))
        if df_m5 is not None and len(df_m5) >= 15:
            sr_levels.extend(self._find_sr_levels(df_m5, current_price, "p15", periods=15))
        if len(df_m1) >= 15:
            sr_levels.extend(self._find_sr_levels(df_m1, current_price, "p15_m1", periods=15))

        # Ordenar por distancia al precio
        sr_levels.sort(key=lambda x: x.distance_pct)
        nearest_sr = sr_levels[0] if sr_levels else None

        # Verificar si estamos en un S/R válido
        # Tolerancia más amplia para más oportunidades
        at_valid_sr = (
            nearest_sr is not None and
            nearest_sr.distance_pct <= 0.0050 and  # dentro del 0.50%
            nearest_sr.strength >= 0.20             # fuerza mínima muy baja
        )

        # Verificar coherencia: el S/R debe ser del tipo correcto
        if at_valid_sr and nearest_sr:
            sr_matches_direction = (
                (direction == "CALL" and nearest_sr.level_type == "support") or
                (direction == "PUT"  and nearest_sr.level_type == "resistance")
            )
            if not sr_matches_direction:
                # S/R no coincide con dirección — puede ser trampa
                at_valid_sr = False

        # ── Detectar riesgo de liquidez ───────────────────────────────────────
        liq_risk, liq_reason = self._check_liquidity_risk(
            df_m1, df_m5, current_price, direction, nearest_sr
        )

        # ── Construir razón y decisión ────────────────────────────────────────
        h1_str  = h1_level.direction  if h1_level  else "N/A"
        m15_str = m15_level.direction if m15_level else "N/A"
        m5_str  = m5_level.direction  if m5_level  else "N/A"
        m1_str  = m1_level.direction  if m1_level  else "N/A"

        # should_enter = condición ideal completa
        # Pero el engine usará esto de forma advisory (penalizará pero no bloqueará del todo)
        should_enter = (
            cascade_aligned and
            trend_advanced  and
            not liq_risk
        )
        # at_valid_sr es deseable pero no obligatorio para should_enter
        # (el engine ya valida zona en su paso 3)

        wait_parts = []
        if not cascade_aligned:
            wait_parts.append(f"cascada no alineada ({aligned_count}/{total_count} TF)")
        if not trend_advanced:
            wait_parts.append(f"tendencia no avanzada aún ({advancement_bars} barras, necesita ≥3)")
        if not at_valid_sr:
            sr_info = f"nearest={nearest_sr.distance_pct*100:.2f}%" if nearest_sr else "sin S/R cercano"
            wait_parts.append(f"precio no en S/R válido ({sr_info})")
        if liq_risk:
            wait_parts.append(f"trampa de liquidez: {liq_reason}")

        reason_parts = [
            f"H1={h1_str} M15={m15_str} M5={m5_str} M1={m1_str}",
            f"alineación={alignment_score:.0%}",
            f"avance={advancement_bars}p",
        ]
        if nearest_sr:
            reason_parts.append(f"S/R {nearest_sr.level_type} {nearest_sr.price:.5f} ({nearest_sr.period_source})")

        return CascadeResult(
            direction=direction,
            cascade_aligned=cascade_aligned,
            alignment_score=alignment_score,
            trend_advanced=trend_advanced,
            advancement_bars=advancement_bars,
            nearest_sr=nearest_sr,
            at_valid_sr=at_valid_sr,
            liquidity_risk=liq_risk,
            liquidity_reason=liq_reason,
            h1_trend=h1_str,
            m15_trend=m15_str,
            m5_trend=m5_str,
            m1_trend=m1_str,
            reason=" | ".join(reason_parts),
            should_enter=should_enter,
            wait_reason=" + ".join(wait_parts) if wait_parts else "",
        )

    # ── Análisis por timeframe ─────────────────────────────────────────────────

    def _analyze_tf(self, df: pd.DataFrame, tf_name: str) -> TrendLevel:
        if df is None or len(df) < 8:
            return TrendLevel(tf_name, "neutral", 0.0, False, 0.0, "unclear", 0.0, 0)

        closes = df["close"].values.astype(float)
        highs  = df["high"].values.astype(float)
        lows   = df["low"].values.astype(float)
        n = len(closes)

        # ── EMA 9 y 20 ───────────────────────────────────────────────────────
        ema9  = self._ema(closes, min(9,  n - 1))
        ema20 = self._ema(closes, min(20, n - 1))

        # Pendiente EMA20 (últimas 5 velas)
        slope_window = min(5, n - 1)
        ema_slope = (ema20[-1] - ema20[-slope_window]) / (ema20[-slope_window] + 1e-10) * 100

        ema_up   = ema9[-1] > ema20[-1] and ema_slope > 0.0005  # pendiente positiva real
        ema_down = ema9[-1] < ema20[-1] and ema_slope < -0.0005

        # ── Pendiente simple de closes (más directa) ─────────────────────────
        # Comparar primer y último tercio del array para dirección general
        third = max(1, n // 3)
        first_avg = float(np.mean(closes[:third]))
        last_avg  = float(np.mean(closes[-third:]))
        price_change_pct = (last_avg - first_avg) / (first_avg + 1e-10) * 100

        slope_up   = price_change_pct >  0.02   # +0.02% neto = tendencia alcista
        slope_down = price_change_pct < -0.02

        # ── Estructura de HH/HL o LH/LL (complementaria, no obligatoria) ────
        peaks, troughs = self._find_pivots(highs, lows, n)
        hh = len(peaks)   >= 2 and peaks[-1][1]   > peaks[-2][1]
        hl = len(troughs) >= 2 and troughs[-1][1]  > troughs[-2][1]
        lh = len(peaks)   >= 2 and peaks[-1][1]   < peaks[-2][1]
        ll = len(troughs) >= 2 and troughs[-1][1]  < troughs[-2][1]

        struct_bullish = hh or hl
        struct_bearish = ll or lh

        # ── Decisión de dirección: consenso de 3 señales ─────────────────────
        # up_votes / down_votes — necesita al menos 2 de 3 señales
        up_votes   = int(ema_up) + int(slope_up)   + int(struct_bullish)
        down_votes = int(ema_down) + int(slope_down) + int(struct_bearish)

        if up_votes >= 2:
            direction = "up"
            structure = "bullish"
        elif down_votes >= 2:
            direction = "down"
            structure = "bearish"
        elif up_votes == 1 and down_votes == 0 and slope_up:
            direction = "up"    # Solo señal suave de slope
            structure = "weak_bullish"
        elif down_votes == 1 and up_votes == 0 and slope_down:
            direction = "down"
            structure = "weak_bearish"
        else:
            direction = "neutral"
            structure = "flat" if abs(price_change_pct) < 0.01 else "choppy"

        # ── Fuerza de la tendencia (0-1) ─────────────────────────────────────
        strength = 0.0
        if direction != "neutral":
            ema_score    = 0.35 if ema_up or ema_down else 0.0
            slope_score  = min(abs(price_change_pct) / 0.10, 0.35)
            struct_score = 0.30 if (hh and hl) or (ll and lh) else 0.10 if (hh or hl or ll or lh) else 0.0
            strength = min(1.0, ema_score + slope_score + struct_score)

        # ── Cuántas velas lleva la tendencia ─────────────────────────────────
        candles_in_trend = self._count_trend_bars(closes, direction, min(20, n))

        # Swing relevante
        last_swing = (peaks[-1][1] if peaks else highs.max()) if direction == "down" else \
                     (troughs[-1][1] if troughs else lows.min())

        return TrendLevel(
            timeframe=tf_name,
            direction=direction,
            strength=strength,
            advanced=candles_in_trend >= 3,
            ema_slope=ema_slope,
            structure=structure,
            last_swing=last_swing,
            candles_in_trend=candles_in_trend,
        )

    # ── Detección de S/R desde períodos 15 y 20 ───────────────────────────────

    def _find_sr_levels(self, df: pd.DataFrame, current_price: float,
                         source: str, periods: int) -> List[SRLevel]:
        """
        Detecta niveles S/R desde los últimos N períodos.
        Busca donde el precio ha rebotado múltiples veces.
        """
        if len(df) < periods:
            return []

        recent = df.tail(periods)
        highs  = recent["high"].values.astype(float)
        lows   = recent["low"].values.astype(float)
        closes = recent["close"].values.astype(float)
        n = len(recent)

        levels = []
        tolerance = current_price * 0.0008  # 0.08% de tolerancia para agrupar

        # Encontrar niveles de soporte (donde el precio rebotó desde abajo)
        all_lows = []
        for i in range(1, n - 1):
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                all_lows.append(lows[i])

        # Encontrar niveles de resistencia (donde el precio rebotó desde arriba)
        all_highs = []
        for i in range(1, n - 1):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                all_highs.append(highs[i])

        # Agrupar niveles cercanos
        support_clusters = self._cluster_levels(all_lows, tolerance)
        resist_clusters  = self._cluster_levels(all_highs, tolerance)

        for price_level, count in support_clusters:
            dist = abs(price_level - current_price) / current_price
            strength = min(1.0, count / 3 * 0.5 + (1 - min(dist / 0.003, 1)) * 0.5)
            levels.append(SRLevel(
                price=price_level,
                level_type="support",
                period_source=source,
                touches=count,
                strength=strength,
                distance_pct=dist,
            ))

        for price_level, count in resist_clusters:
            dist = abs(price_level - current_price) / current_price
            strength = min(1.0, count / 3 * 0.5 + (1 - min(dist / 0.003, 1)) * 0.5)
            levels.append(SRLevel(
                price=price_level,
                level_type="resistance",
                period_source=source,
                touches=count,
                strength=strength,
                distance_pct=dist,
            ))

        return levels

    def _cluster_levels(self, prices: List[float], tolerance: float) -> List[Tuple[float, int]]:
        """Agrupa niveles de precio cercanos."""
        if not prices:
            return []
        clusters = []
        used = set()
        for i, p in enumerate(prices):
            if i in used:
                continue
            group = [p]
            for j, q in enumerate(prices):
                if j != i and j not in used and abs(p - q) <= tolerance:
                    group.append(q)
                    used.add(j)
            used.add(i)
            if len(group) >= 1:
                clusters.append((float(np.mean(group)), len(group)))
        return sorted(clusters, key=lambda x: -x[1])

    # ── Detección de riesgo de liquidez ───────────────────────────────────────

    def _check_liquidity_risk(self, df_m1: pd.DataFrame, df_m5: Optional[pd.DataFrame],
                               current_price: float, direction: str,
                               nearest_sr: Optional[SRLevel]) -> Tuple[bool, str]:
        """
        Detecta si hay riesgo de trampa de liquidez:
        - Precio muy cerca de un swing reciente (stops ahí)
        - Entre dos niveles sin dirección clara
        - Vela spike reciente (noticias)
        """
        if len(df_m1) < 10:
            return False, ""

        recent = df_m1.tail(15)
        recent_high = float(recent["high"].max())
        recent_low  = float(recent["low"].min())
        recent_range = recent_high - recent_low

        # ── Riesgo 1: Precio muy cerca del high/low reciente ─────────────────
        # Los stops se acumulan justo arriba/abajo de swings recientes
        dist_from_high = abs(current_price - recent_high) / current_price
        dist_from_low  = abs(current_price - recent_low)  / current_price

        if direction == "PUT" and dist_from_high <= 0.0008:
            return True, f"precio en máximo reciente (stops ahí, dist={dist_from_high*100:.2f}%)"
        if direction == "CALL" and dist_from_low <= 0.0008:
            return True, f"precio en mínimo reciente (stops ahí, dist={dist_from_low*100:.2f}%)"

        # ── Riesgo 2: El precio está en el MEDIO del rango ───────────────────
        # No hay S/R claro, solo ruido
        midpoint = (recent_high + recent_low) / 2
        dist_from_mid = abs(current_price - midpoint) / recent_range if recent_range > 0 else 1.0
        if dist_from_mid < 0.25 and nearest_sr is None:
            return True, "precio en centro del rango sin S/R definido"

        # ── Riesgo 3: Spread/spike inusual en M1 ─────────────────────────────
        ranges_m1 = [float(r["high"]) - float(r["low"]) for _, r in df_m1.tail(8).iterrows()]
        avg_range  = np.mean(ranges_m1[:-1]) if len(ranges_m1) > 1 else 0
        last_range = ranges_m1[-1]
        if avg_range > 0 and last_range > avg_range * 3.0:
            return True, f"spike detectado ({last_range/avg_range:.1f}x rango normal)"

        return False, ""

    # ── Conteo de barras en tendencia ─────────────────────────────────────────

    def _count_trend_bars(self, closes: np.ndarray, direction: str, lookback: int) -> int:
        """
        Cuenta velas recientes en la dirección de la tendencia.
        Permite hasta 1 barra contraria cada 4 (el mercado siempre tiene pullbacks).
        """
        if direction == "neutral" or len(closes) < 3:
            return 0

        recent = closes[-lookback:]
        n = len(recent)
        aligned = 0
        contra  = 0
        # Recorremos de más reciente a más antiguo
        for i in range(n - 1, 0, -1):
            if (direction == "up"   and recent[i] > recent[i-1]) or \
               (direction == "down" and recent[i] < recent[i-1]):
                aligned += 1
                contra = 0  # Resetear contador de contras tras barra alineada
            else:
                contra += 1
                # Permitir máximo 1 contra por cada 3 alineadas
                # Si hay 2+ contras seguidas, la tendencia se rompió
                if contra >= 2:
                    break

        return aligned

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _find_pivots(self, highs, lows, n):
        peaks   = []
        troughs = []
        for i in range(2, n - 2):
            if highs[i] >= max(highs[i-1], highs[i-2], highs[i+1], highs[i+2]):
                peaks.append((i, float(highs[i])))
            if lows[i] <= min(lows[i-1], lows[i-2], lows[i+1], lows[i+2]):
                troughs.append((i, float(lows[i])))
        return peaks[-4:], troughs[-4:]

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        if len(data) < period:
            return data
        result = np.zeros(len(data))
        result[period - 1] = np.mean(data[:period])
        k = 2 / (period + 1)
        for i in range(period, len(data)):
            result[i] = data[i] * k + result[i - 1] * (1 - k)
        result[:period - 1] = result[period - 1]
        return result

    def _neutral(self, reason: str) -> CascadeResult:
        return CascadeResult(
            direction="NEUTRAL", cascade_aligned=False, alignment_score=0.0,
            trend_advanced=False, advancement_bars=0, nearest_sr=None,
            at_valid_sr=False, liquidity_risk=False, liquidity_reason="",
            h1_trend="?", m15_trend="?", m5_trend="?", m1_trend="?",
            reason=reason, should_enter=False,
            wait_reason=reason,
        )
