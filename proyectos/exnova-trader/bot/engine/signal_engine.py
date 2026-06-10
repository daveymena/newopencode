"""
Motor de Señales Mejorado v3.0
Combina múltiples estrategias con filtros estrictos para alta precisión
"""
import pandas as pd
import numpy as np
import ta
from typing import Optional, Dict
from datetime import datetime


class SignalEngine:
    """
    Motor unificado de señales con filtros en cascada:
    1. Tendencia Multi-Timeframe (H1 > M15 > M5 > M1)
    2. Indicadores técnicos alineados (RSI + MACD + BB + EMA)
    3. Patrones de velas japonesas (hammer, engulfing, doji, pin bar)
    4. Zonas de soporte/resistencia dinámicas
    5. Filtro de volatilidad (evitar movimientos erráticos)
    6. Score final ponderado >= 68% para operar
    """

    def __init__(self, scoring_engine=None):
        self.scoring_engine = scoring_engine
        self.MIN_SCORE = 68.0
        self.MIN_CANDLES = 60

    # ─── ENTRADA PRINCIPAL ────────────────────────────────────────────────────
    def analyze(self, asset: str, market_data, feature_engineer) -> Optional[Dict]:
        try:
            import time as _time
            now = _time.time()

            # Obtener velas en múltiples timeframes
            df_m1  = market_data.get_candles(asset, 60,      100, now)
            df_m5  = market_data.get_candles(asset, 300,     60,  now)
            df_m15 = market_data.get_candles(asset, 900,     40,  now)

            if df_m1 is None or len(df_m1) < self.MIN_CANDLES:
                return None
            if df_m5 is None or len(df_m5) < 20:
                df_m5 = None
            if df_m15 is None or len(df_m15) < 15:
                df_m15 = None

            # Calcular indicadores en M1
            df_m1 = self._add_indicators(df_m1)
            if df_m1 is None or len(df_m1) < 30:
                return None

            # Calcular en M5 y M15 si disponibles
            if df_m5 is not None:
                df_m5 = self._add_indicators(df_m5)
            if df_m15 is not None:
                df_m15 = self._add_indicators(df_m15)

            # Correr análisis completo
            return self._full_analysis(asset, df_m1, df_m5, df_m15)

        except Exception as e:
            return None

    # ─── ANÁLISIS COMPLETO ────────────────────────────────────────────────────
    def _full_analysis(self, asset: str, df: pd.DataFrame,
                       df_m5: Optional[pd.DataFrame],
                       df_m15: Optional[pd.DataFrame]) -> Dict:

        scores = {}
        reasons = []
        warnings = []

        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(last["close"])

        # ── 1. FILTRO DE VOLATILIDAD (eliminar mercados erráticos) ──
        atr = float(last.get("atr", 0))
        atr_pct = atr / price if price > 0 else 0
        if atr_pct > 0.004:   # volatilidad > 0.4% → skip
            warnings.append("Volatilidad extrema")
            scores["volatility"] = 20
        elif atr_pct < 0.0002:  # mercado muerto → skip
            warnings.append("Sin volatilidad")
            scores["volatility"] = 30
        else:
            scores["volatility"] = 80
            reasons.append(f"Volatilidad adecuada ({atr_pct*100:.3f}%)")

        # ── 2. TENDENCIA M1 (EMAs) ──
        ema9  = float(last.get("ema_9",  price))
        ema21 = float(last.get("ema_21", price))
        ema50 = float(last.get("ema_50", price))
        trend_m1 = "UP" if ema9 > ema21 > ema50 else "DOWN" if ema9 < ema21 < ema50 else "NEUTRAL"
        if trend_m1 == "NEUTRAL":
            scores["trend_m1"] = 45
        else:
            scores["trend_m1"] = 75
            reasons.append(f"Tendencia M1: {trend_m1}")

        # ── 3. TENDENCIA M5 ──
        trend_m5 = "NEUTRAL"
        if df_m5 is not None and len(df_m5) > 5:
            l5 = df_m5.iloc[-1]
            e9_5  = float(l5.get("ema_9",  0))
            e21_5 = float(l5.get("ema_21", 0))
            if e9_5 > e21_5:
                trend_m5 = "UP"
            elif e9_5 < e21_5:
                trend_m5 = "DOWN"
            scores["trend_m5"] = 80 if trend_m5 != "NEUTRAL" else 45
            if trend_m5 != "NEUTRAL":
                reasons.append(f"Tendencia M5: {trend_m5}")

        # ── 4. TENDENCIA M15 ──
        trend_m15 = "NEUTRAL"
        if df_m15 is not None and len(df_m15) > 5:
            l15 = df_m15.iloc[-1]
            e9_15  = float(l15.get("ema_9",  0))
            e21_15 = float(l15.get("ema_21", 0))
            if e9_15 > e21_15:
                trend_m15 = "UP"
            elif e9_15 < e21_15:
                trend_m15 = "DOWN"
            scores["trend_m15"] = 85 if trend_m15 != "NEUTRAL" else 40
            if trend_m15 != "NEUTRAL":
                reasons.append(f"Tendencia M15: {trend_m15}")

        # ── 5. ALINEACIÓN MULTI-TIMEFRAME ──
        active_trends = [t for t in [trend_m1, trend_m5, trend_m15] if t != "NEUTRAL"]
        if len(active_trends) >= 2 and len(set(active_trends)) == 1:
            # Todos alineados en la misma dirección
            scores["mtf_align"] = 95
            reasons.append(f"MTF alineado: {active_trends[0]}")
            master_direction = active_trends[0]
        elif len(set(active_trends)) > 1:
            # Tendencias contradictorias → señal débil
            scores["mtf_align"] = 25
            warnings.append("MTF contradictorio")
            master_direction = "NEUTRAL"
        else:
            scores["mtf_align"] = 50
            master_direction = trend_m1

        # ── 6. RSI ──
        rsi = float(last.get("rsi", 50))
        rsi_prev = float(prev.get("rsi", 50))
        rsi_score, rsi_signal = self._score_rsi(rsi, rsi_prev)
        scores["rsi"] = rsi_score
        if rsi_score >= 70:
            reasons.append(f"RSI {rsi_signal} ({rsi:.1f})")

        # ── 7. MACD ──
        macd     = float(last.get("macd", 0))
        macd_sig = float(last.get("macd_signal", 0))
        macd_prv = float(prev.get("macd", 0))
        macd_s_p = float(prev.get("macd_signal", 0))
        macd_score, macd_signal_dir = self._score_macd(macd, macd_sig, macd_prv, macd_s_p)
        scores["macd"] = macd_score
        if macd_score >= 70:
            reasons.append(f"MACD cruce {macd_signal_dir}")

        # ── 8. BOLLINGER BANDS ──
        bb_high = float(last.get("bb_high", price * 1.002))
        bb_low  = float(last.get("bb_low",  price * 0.998))
        bb_mid  = (bb_high + bb_low) / 2
        bb_score, bb_signal = self._score_bollinger(price, bb_high, bb_low, bb_mid)
        scores["bollinger"] = bb_score
        if bb_score >= 70:
            reasons.append(f"BB {bb_signal}")

        # ── 9. PATRONES DE VELAS ──
        pattern_score, pattern_signal, pattern_name = self._detect_candle_patterns(df)
        scores["patterns"] = pattern_score
        if pattern_score >= 70:
            reasons.append(f"Patrón: {pattern_name}")

        # ── 10. SOPORTE / RESISTENCIA ──
        sr_score, sr_signal, sr_detail = self._score_support_resistance(df, price)
        scores["support_resistance"] = sr_score
        if sr_score >= 70:
            reasons.append(sr_detail)

        # ── 11. MOMENTUM ──
        momentum_score, momentum_signal = self._score_momentum(df)
        scores["momentum"] = momentum_score
        if momentum_score >= 65:
            reasons.append(f"Momentum {momentum_signal}")

        # ─── CÁLCULO DEL SCORE FINAL PONDERADO ──────────────────────────────
        weights = {
            "volatility":        0.08,
            "trend_m1":          0.10,
            "trend_m5":          0.12,
            "trend_m15":         0.10,
            "mtf_align":         0.15,
            "rsi":               0.12,
            "macd":              0.10,
            "bollinger":         0.08,
            "patterns":          0.07,
            "support_resistance":0.05,
            "momentum":          0.03,
        }

        total_weight = sum(weights[k] for k in scores if k in weights)
        total_score = sum(scores[k] * weights.get(k, 0) for k in scores if k in weights)
        final_score = (total_score / total_weight * 100) / 100 if total_weight > 0 else 0

        # ─── DETERMINAR SEÑAL DE TRADING ────────────────────────────────────
        direction_votes = {
            "CALL": 0.0,
            "PUT":  0.0,
        }

        # Votar según cada indicador
        if rsi_signal == "OVERSOLD":      direction_votes["CALL"] += 2.0
        if rsi_signal == "OVERBOUGHT":    direction_votes["PUT"]  += 2.0
        if macd_signal_dir == "BULLISH":  direction_votes["CALL"] += 1.5
        if macd_signal_dir == "BEARISH":  direction_votes["PUT"]  += 1.5
        if bb_signal == "AT_LOW":         direction_votes["CALL"] += 1.5
        if bb_signal == "AT_HIGH":        direction_votes["PUT"]  += 1.5
        if pattern_signal == "CALL":      direction_votes["CALL"] += 2.0
        if pattern_signal == "PUT":       direction_votes["PUT"]  += 2.0
        if sr_signal == "CALL":           direction_votes["CALL"] += 1.5
        if sr_signal == "PUT":            direction_votes["PUT"]  += 1.5
        if master_direction == "UP":      direction_votes["CALL"] += 1.0
        if master_direction == "DOWN":    direction_votes["PUT"]  += 1.0
        if momentum_signal == "CALL":     direction_votes["CALL"] += 1.0
        if momentum_signal == "PUT":      direction_votes["PUT"]  += 1.0

        call_votes = direction_votes["CALL"]
        put_votes  = direction_votes["PUT"]
        total_votes = call_votes + put_votes

        if total_votes > 0:
            call_pct = call_votes / total_votes
            put_pct  = put_votes  / total_votes
        else:
            call_pct = put_pct = 0.5

        # Señal final: debe haber consenso claro (>= 60% de votos)
        if call_pct >= 0.60:
            final_signal = "CALL"
            signal_confidence = call_pct
        elif put_pct >= 0.60:
            final_signal = "PUT"
            signal_confidence = put_pct
        else:
            final_signal = "NEUTRAL"
            signal_confidence = 0.5

        # Confianza combinada = score * consenso de señal
        confidence = final_score * signal_confidence

        # Decidir acción
        action = "TRADE" if (final_score >= self.MIN_SCORE / 100 and
                              confidence >= 0.60 and
                              final_signal != "NEUTRAL" and
                              scores.get("volatility", 0) >= 50 and
                              scores.get("mtf_align", 0) >= 40) else "WAIT"

        # Expiración adaptativa según alineación MTF
        if len(active_trends) >= 3 and len(set(active_trends)) == 1:
            expiration = 60   # 1 min si todos alineados
        elif len(active_trends) >= 2:
            expiration = 120  # 2 min alineación parcial
        else:
            expiration = 180  # 3 min si solo M1

        return {
            "asset":      asset,
            "signal":     final_signal,
            "action":     action,
            "confidence": round(confidence, 3),
            "score":      round(final_score * 100, 1),
            "scores":     scores,
            "reasons":    reasons,
            "warnings":   warnings,
            "expiration": expiration,
            "phase":      master_direction,
            "timestamp":  datetime.now().strftime("%H:%M:%S"),
        }

    # ─── INDICADORES TÉCNICOS ─────────────────────────────────────────────────
    def _add_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        try:
            if df is None or len(df) < 20:
                return None
            df = df.copy()

            # RSI
            df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

            # MACD
            macd_ind = ta.trend.MACD(df["close"])
            df["macd"]        = macd_ind.macd()
            df["macd_signal"] = macd_ind.macd_signal()

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
            df["bb_high"] = bb.bollinger_hband()
            df["bb_low"]  = bb.bollinger_lband()
            df["bb_mid"]  = bb.bollinger_mavg()

            # EMAs
            df["ema_9"]  = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
            df["ema_21"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
            df["ema_50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()

            # ATR
            df["atr"] = ta.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=14
            ).average_true_range()

            # ADX
            adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
            df["adx"] = adx.adx()

            # ROC (rate of change)
            df["roc"] = df["close"].pct_change(5) * 100

            df.dropna(subset=["rsi", "macd", "ema_9", "ema_21"], inplace=True)
            return df if len(df) >= 10 else None

        except Exception:
            return None

    # ─── SCORING DE INDICADORES ───────────────────────────────────────────────
    def _score_rsi(self, rsi: float, rsi_prev: float):
        if rsi < 25:
            return 95, "OVERSOLD"
        elif rsi < 30 and rsi > rsi_prev:     # sobreventa + giro
            return 90, "OVERSOLD"
        elif rsi < 35 and rsi > rsi_prev:
            return 75, "OVERSOLD"
        elif rsi > 75:
            return 95, "OVERBOUGHT"
        elif rsi > 70 and rsi < rsi_prev:     # sobrecompra + giro
            return 90, "OVERBOUGHT"
        elif rsi > 65 and rsi < rsi_prev:
            return 75, "OVERBOUGHT"
        elif 40 <= rsi <= 60:                 # zona neutra
            return 40, "NEUTRAL"
        else:
            return 55, "NEUTRAL"

    def _score_macd(self, macd, macd_sig, macd_prv, macd_s_p):
        # Cruce alcista (MACD cruza arriba de señal)
        if macd > macd_sig and macd_prv <= macd_s_p:
            return 92, "BULLISH"
        # Cruce bajista
        elif macd < macd_sig and macd_prv >= macd_s_p:
            return 92, "BEARISH"
        # MACD positivo y creciendo
        elif macd > macd_sig and macd > macd_prv:
            return 70, "BULLISH"
        # MACD negativo y cayendo
        elif macd < macd_sig and macd < macd_prv:
            return 70, "BEARISH"
        else:
            return 45, "NEUTRAL"

    def _score_bollinger(self, price, bb_high, bb_low, bb_mid):
        bb_range = bb_high - bb_low
        if bb_range <= 0:
            return 50, "NEUTRAL"
        pct_pos = (price - bb_low) / bb_range

        if pct_pos <= 0.05:         # tocando banda inferior
            return 92, "AT_LOW"
        elif pct_pos <= 0.15:       # cerca de banda inferior
            return 80, "AT_LOW"
        elif pct_pos >= 0.95:       # tocando banda superior
            return 92, "AT_HIGH"
        elif pct_pos >= 0.85:       # cerca de banda superior
            return 80, "AT_HIGH"
        elif 0.45 <= pct_pos <= 0.55:  # zona central (sin señal)
            return 40, "NEUTRAL"
        else:
            return 55, "NEUTRAL"

    def _detect_candle_patterns(self, df: pd.DataFrame):
        """Detecta patrones de velas con confirmación"""
        if len(df) < 4:
            return 50, "NEUTRAL", "Ninguno"

        c0 = df.iloc[-1]   # vela actual
        c1 = df.iloc[-2]   # anterior
        c2 = df.iloc[-3]   # 2 atrás

        o0, h0, l0, cl0 = float(c0["open"]), float(c0["high"]), float(c0["low"]), float(c0["close"])
        o1, h1, l1, cl1 = float(c1["open"]), float(c1["high"]), float(c1["low"]), float(c1["close"])
        o2, h2, l2, cl2 = float(c2["open"]), float(c2["high"]), float(c2["low"]), float(c2["close"])

        body0  = abs(cl0 - o0)
        body1  = abs(cl1 - o1)
        range0 = h0 - l0
        range1 = h1 - l1

        lower_wick0 = min(o0, cl0) - l0
        upper_wick0 = h0 - max(o0, cl0)
        lower_wick1 = min(o1, cl1) - l1
        upper_wick1 = h1 - max(o1, cl1)

        is_bull0 = cl0 > o0
        is_bear0 = cl0 < o0
        is_bull1 = cl1 > o1
        is_bear1 = cl1 < o1

        # ── HAMMER (alcista) ──
        if (is_bull0 and
            lower_wick0 > 2 * body0 and
            upper_wick0 < body0 * 0.5 and
            range0 > 0):
            return 88, "CALL", "Hammer"

        # ── SHOOTING STAR (bajista) ──
        if (is_bear0 and
            upper_wick0 > 2 * body0 and
            lower_wick0 < body0 * 0.5 and
            range0 > 0):
            return 88, "PUT", "Shooting Star"

        # ── PIN BAR ALCISTA (mecha inferior larga) ──
        if (lower_wick0 > 2.5 * body0 and
            lower_wick0 > upper_wick0 * 2 and
            range0 > 0):
            return 85, "CALL", "Pin Bar Alcista"

        # ── PIN BAR BAJISTA (mecha superior larga) ──
        if (upper_wick0 > 2.5 * body0 and
            upper_wick0 > lower_wick0 * 2 and
            range0 > 0):
            return 85, "PUT", "Pin Bar Bajista"

        # ── BULLISH ENGULFING ──
        if (is_bull0 and is_bear1 and
            o0 <= cl1 and cl0 >= o1 and
            body0 > body1 * 1.0):
            return 90, "CALL", "Engulfing Alcista"

        # ── BEARISH ENGULFING ──
        if (is_bear0 and is_bull1 and
            o0 >= cl1 and cl0 <= o1 and
            body0 > body1 * 1.0):
            return 90, "PUT", "Engulfing Bajista"

        # ── MORNING STAR (3 velas alcistas) ──
        if (is_bear2 := cl2 < o2) and body0 > 0:
            if (abs(cl1 - o1) < body0 * 0.5 and   # doji/pequeña en medio
                is_bull0 and
                cl0 > (o2 + cl2) / 2):
                return 87, "CALL", "Morning Star"

        # ── EVENING STAR (3 velas bajistas) ──
        if (is_bull2 := cl2 > o2) and body0 > 0:
            if (abs(cl1 - o1) < body0 * 0.5 and
                is_bear0 and
                cl0 < (o2 + cl2) / 2):
                return 87, "PUT", "Evening Star"

        # ── DOJI (indecisión) ──
        if range0 > 0 and body0 / range0 < 0.1:
            return 40, "NEUTRAL", "Doji"

        return 50, "NEUTRAL", "Sin Patrón"

    def _score_support_resistance(self, df: pd.DataFrame, price: float):
        """Detecta zonas S/R dinámicas y evalúa posición del precio"""
        window = min(50, len(df))
        recent = df.tail(window)

        pivots_high = []
        pivots_low  = []

        for i in range(2, len(recent) - 2):
            h = float(recent["high"].iloc[i])
            l = float(recent["low"].iloc[i])
            # Pivot high
            if (h > float(recent["high"].iloc[i-1]) and
                h > float(recent["high"].iloc[i-2]) and
                h > float(recent["high"].iloc[i+1]) and
                h > float(recent["high"].iloc[i+2])):
                pivots_high.append(h)
            # Pivot low
            if (l < float(recent["low"].iloc[i-1]) and
                l < float(recent["low"].iloc[i-2]) and
                l < float(recent["low"].iloc[i+1]) and
                l < float(recent["low"].iloc[i+2])):
                pivots_low.append(l)

        if not pivots_high and not pivots_low:
            return 50, "NEUTRAL", "Sin niveles S/R"

        tolerance = price * 0.002  # 0.2% de tolerancia

        # Cerca de soporte → señal CALL
        for sup in pivots_low:
            if abs(price - sup) <= tolerance:
                return 88, "CALL", f"En zona soporte ({sup:.5f})"

        # Cerca de resistencia → señal PUT
        for res in pivots_high:
            if abs(price - res) <= tolerance:
                return 88, "PUT", f"En zona resistencia ({res:.5f})"

        # Lejos de niveles → zona limpia
        return 60, "NEUTRAL", "Entre niveles S/R"

    def _score_momentum(self, df: pd.DataFrame):
        """Evalúa el momentum del precio con ROC y pendiente de EMA"""
        if len(df) < 10:
            return 50, "NEUTRAL"

        # Rate of Change de 5 velas
        roc = float(df["roc"].iloc[-1]) if "roc" in df.columns else 0
        # Pendiente EMA9 (últimas 3 velas)
        if "ema_9" in df.columns and len(df) >= 3:
            ema_slope = (float(df["ema_9"].iloc[-1]) - float(df["ema_9"].iloc[-3])) / float(df["ema_9"].iloc[-3]) * 100
        else:
            ema_slope = 0

        if roc > 0.05 and ema_slope > 0.01:
            return 78, "CALL"
        elif roc < -0.05 and ema_slope < -0.01:
            return 78, "PUT"
        elif abs(roc) < 0.01:
            return 40, "NEUTRAL"
        else:
            return 55, "NEUTRAL"
