"""
Trade Logger — Registro detallado de cada operación.
Guarda en brain/trade_log.jsonl (una línea JSON por trade).
Permite revisar exactamente por qué se ganó o perdió cada entrada.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional


_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain", "trade_log.jsonl")
_SUMMARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain", "trade_summary.json")


def log_trade(
    asset: str,
    direction: str,
    amount: float,
    entry_price: float,
    expiration_min: int,
    confidence: float,
    result: str,
    pnl: float,
    # Señales al momento de entrar
    zone_level: float = 0.0,
    zone_type: str = "",
    zone_strength: float = 0.0,
    zone_touches: int = 0,
    pattern: str = "",
    rsi_value: float = 50.0,
    macd_signal: str = "",
    cascade: Optional[Dict] = None,
    ai_score: float = 0.0,
    ai_label: str = "",
    final_score: float = 0.0,
    conditions: Optional[Dict] = None,
    # Diagnóstico post-trade
    diagnosis: Optional[Dict] = None,
):
    """
    Registra una operación completa con todo el contexto disponible.
    Escribe una línea al archivo trade_log.jsonl.
    """
    ts = time.time()
    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    # Determinar causa principal de pérdida de forma legible
    cause_readable = _readable_cause(diagnosis, result, conditions or {})

    record = {
        "ts": ts,
        "datetime": dt,
        "asset": asset,
        "direction": direction,
        "amount": amount,
        "entry_price": round(entry_price, 6),
        "expiration_min": expiration_min,
        "confidence": round(confidence, 3),
        "result": result,
        "pnl": round(pnl, 2),
        # Contexto de la zona
        "zone": {
            "level": round(zone_level, 6),
            "type": zone_type,
            "strength": round(zone_strength, 3),
            "touches": zone_touches,
            "distance_pct": round(abs(entry_price - zone_level) / entry_price * 100, 4) if entry_price else 0,
        },
        # Señales técnicas
        "signals": {
            "pattern": pattern,
            "rsi": round(rsi_value, 1),
            "macd": macd_signal,
            "ai_score": round(ai_score, 1),
            "ai_label": ai_label,
            "final_score": round(final_score, 3),
        },
        # Cascada H1→M15→M5→M1
        "cascade": cascade or {},
        # Condiciones activas al entrar
        "active_conditions": [k for k, v in (conditions or {}).items() if v],
        # Diagnóstico
        "diagnosis": {
            "primary_cause": diagnosis.get("primary_cause", "desconocida") if diagnosis else "sin_diagnostico",
            "cause_readable": cause_readable,
            "lessons": diagnosis.get("lessons", []) if diagnosis else [],
            "what_worked": diagnosis.get("what_worked", []) if diagnosis else [],
            "early_entry": diagnosis.get("early_entry", False) if diagnosis else False,
            "zone_held": diagnosis.get("zone_held", None) if diagnosis else None,
        },
    }

    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _update_summary(result, pnl, cause_readable, asset, direction)
    except Exception as e:
        import sys
        print(f"[TradeLogger] ERROR: {e}", file=sys.stderr)

    return record


def _readable_cause(diagnosis: Optional[Dict], result: str, conditions: Dict) -> str:
    """Convierte el código de causa en texto legible."""
    if result == "WIN":
        if diagnosis and diagnosis.get("what_worked"):
            return "WIN: " + diagnosis["what_worked"][0]
        return "WIN: setup válido confirmado"

    if not diagnosis:
        return "LOSS: sin diagnóstico disponible"

    cause = diagnosis.get("primary_cause", "")
    cause_map = {
        "zone_too_weak": "zona débil — el precio la rompió sin dificultad",
        "early_entry": "entrada prematura — vela sin cerrar confirmación",
        "zone_broke": "zona rompió bajo presión — no era S/R real",
        "counter_trend": "en contra de la tendencia dominante",
        "no_pattern": "sin patrón de vela — entrada sin señal técnica",
        "poor_setup_quality": "calidad del setup baja — señales débiles o contradictorias",
        "rsi_not_extreme": "RSI no en zona extrema — sin divergencia visible",
        "cascade_misaligned": "cascada desalineada — timeframes no confirman dirección",
        "liquidity_trap": "trampa de liquidez — precio barrió stops antes de revertir",
        "low_confidence": "confianza baja al entrar — setup marginal",
        "no_rejection_wick": "sin mecha de rechazo en zona — precio no confirmó reversión",
        "premature_entry": "entrada prematura — impulso no completado en la zona",
        "unknown": "causa indeterminada — acumulando datos",
    }
    prefix = "WIN" if result == "WIN" else ("DRAW" if result == "DRAW" else "LOSS")
    description = cause_map.get(cause, cause or "causa no identificada")
    return f"{prefix}: {description}"


def _update_summary(result: str, pnl: float, cause: str, asset: str, direction: str):
    """Actualiza el resumen acumulado de trades."""
    summary = {"total": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "loss_causes": {}, "last_10": []}
    if os.path.exists(_SUMMARY_PATH):
        try:
            with open(_SUMMARY_PATH) as f:
                summary = json.load(f)
        except Exception:
            pass

    summary["total"] = summary.get("total", 0) + 1
    summary["total_pnl"] = round(summary.get("total_pnl", 0.0) + pnl, 2)
    if result == "WIN":
        summary["wins"] = summary.get("wins", 0) + 1
    else:
        summary["losses"] = summary.get("losses", 0) + 1
        # Acumular causas de pérdida
        causes = summary.get("loss_causes", {})
        short_cause = cause.split(":")[1].strip()[:40] if ":" in cause else cause[:40]
        causes[short_cause] = causes.get(short_cause, 0) + 1
        summary["loss_causes"] = causes

    # Últimos 10 trades
    last10 = summary.get("last_10", [])
    last10.append({"result": result, "pnl": pnl, "asset": asset, "dir": direction, "cause": cause[:60]})
    summary["last_10"] = last10[-10:]

    wr = summary["wins"] / summary["total"] * 100 if summary["total"] > 0 else 0
    summary["win_rate_pct"] = round(wr, 1)

    try:
        with open(_SUMMARY_PATH, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_summary() -> Dict:
    """Devuelve el resumen acumulado de trades."""
    if not os.path.exists(_SUMMARY_PATH):
        return {"total": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "win_rate_pct": 0.0}
    try:
        with open(_SUMMARY_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_last_trades(n: int = 20) -> list:
    """Devuelve los últimos N trades del log detallado."""
    if not os.path.exists(_LOG_PATH):
        return []
    try:
        lines = []
        with open(_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except Exception:
                        pass
        return lines[-n:]
    except Exception:
        return []


def print_last_trades(n: int = 10):
    """Imprime en consola los últimos trades con diagnóstico."""
    trades = get_last_trades(n)
    if not trades:
        print("Sin trades registrados aún.")
        return

    print(f"\n{'='*70}")
    print(f"  HISTORIAL DETALLADO — últimos {len(trades)} trades")
    print(f"{'='*70}")
    for t in trades:
        icon = "✓" if t["result"] == "WIN" else "✗"
        pnl_str = f"+${t['pnl']:.2f}" if t["pnl"] >= 0 else f"-${abs(t['pnl']):.2f}"
        print(f"\n[{icon}] {t['datetime']}  {t['asset']} {t['direction']}  {pnl_str}")
        print(f"    Zona: {t['zone']['type']} @ {t['zone']['level']:.5f}  "
              f"strength={t['zone']['strength']:.2f}  dist={t['zone']['distance_pct']:.3f}%")
        print(f"    Señales: patrón={t['signals']['pattern'] or 'ninguno'}  "
              f"RSI={t['signals']['rsi']:.0f}  IA={t['signals']['ai_label']}({t['signals']['ai_score']:.0f})")
        cascade = t.get("cascade", {})
        if cascade:
            print(f"    Cascada: H1={cascade.get('h1','?')} M15={cascade.get('m15','?')} "
                  f"M5={cascade.get('m5','?')} alineada={cascade.get('aligned','?')}")
        print(f"    → {t['diagnosis']['cause_readable']}")
        if t["diagnosis"].get("lessons"):
            print(f"    Lección: {t['diagnosis']['lessons'][0]}")
    print(f"\n{'='*70}\n")
