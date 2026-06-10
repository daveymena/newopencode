#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║       EXNOVA ULTRA-SMART BOT v5.0 — CASCADA H1→M15→M5→M1           ║
║  Cascada de tendencia · Una op por ciclo · Evaluación obligatoria    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import sys, os, time, signal, json, threading
from datetime import datetime
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Forzar UTF-8 en stdout/stderr para evitar errores con caracteres Unicode en Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

from config import Config
from data.market_data import MarketDataHandler
from core.advanced_risk_manager import initialize_risk_manager, RiskConfig
from brain.adaptive_learner import get_adaptive_learner
from brain.market_memory import get_market_memory
from brain.trade_evaluator import TradeEvaluator
from brain.pre_trade_evaluator import PreTradeEvaluator
from brain.trade_logger import log_trade as tlog
from brain.zone_watchlist import get_zone_watchlist
from brain.market_intelligence import get_market_intelligence, MarketIntelligence
from engine.intelligent_engine import IntelligentEngine

console = Console(force_terminal=True) if sys.platform == "win32" else Console()

# ─── Estado global ───────────────────────────────────────────────────────────
state = {
    "running": True,
    "balance": 0.0,
    "initial_balance": 0.0,
    "wins": 0,
    "losses": 0,
    "total_pnl": 0.0,
    "trades": [],
    "log": deque(maxlen=22),
    "cycle": 0,
    "start_time": time.time(),
    "last_trade_time": 0,
    "current_asset": "",
    "status": "INICIANDO",
    "active_order": None,
    "consecutive_losses": 0,
    "best_streak": 0,
    "current_streak": 0,
    "last_signal": {},
    "last_diagnosis": [],
    "zones_by_asset": {},
    "learning_summary": "Acumulando datos...",
    "last_zone_info": "",
    # Cascada v5.0
    "cascade_status": {},          # último resultado cascada por activo
    "last_trade_result": None,     # "WIN"/"LOSS"/"DRAW" del último trade
    "last_trade_record": None,     # dict completo del último trade
    "last_trade_diagnosis": None,  # diagnóstico del último trade
    "pre_trade_eval": None,        # última evaluación pre-trade
    "post_trade_phase": False,     # ¿Está en fase de evaluación post-trade?
    "pending_entries": {},         # Entradas pendientes no descartadas por activo
    # Watchlist de zonas estratégicas v5.1
    "watchlist_rows": [],          # filas para el panel de vigilancia
    "watchlist_status": "MAPEANDO",  # estado global del watchlist
}

_raw_assets = Config.get("ASSETS", ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY"])
_raw_assets = _raw_assets if isinstance(_raw_assets, list) else [_raw_assets]
ASSETS = [a.replace("/", "") for a in (_raw_assets or []) if a.strip()]
if not ASSETS:
    ASSETS = ["EURUSD", "GBPUSD", "AUDUSD", "EURJPY"]

INITIAL_BALANCE    = float(Config.get("INITIAL_BALANCE", 10_000.0))
MIN_CONFIDENCE     = float(Config.get("MIN_CONFIDENCE", 0.50))
TRADE_AMOUNT_PCT   = float(Config.get("TRADE_AMOUNT_PCT", 0.02))
COOLDOWN_AFTER_LOSS = int(Config.get("COOLDOWN_AFTER_LOSS", 90))
MIN_BETWEEN_TRADES  = int(Config.get("MIN_BETWEEN_TRADES", 45))
MAX_CONSEC_LOSSES   = int(Config.get("MAX_CONSEC_LOSSES", 6))


# ─── Logging ─────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons  = {"INFO":"●","WIN":"✔","LOSS":"✘","WARN":"⚠","ERROR":"✖",
              "SIGNAL":"▶","WAIT":"◌","LEARN":"◈","ZONE":"◆"}
    colors = {"INFO":"white","WIN":"green","LOSS":"red","WARN":"yellow",
              "ERROR":"bright_red","SIGNAL":"cyan","WAIT":"dim",
              "LEARN":"magenta","ZONE":"blue"}
    icon  = icons.get(level, "●")
    color = colors.get(level, "white")
    state["log"].append(f"[{now}] [{color}]{icon} {msg}[/{color}]")


# ─── Paneles del dashboard ────────────────────────────────────────────────────

def _wr_color(wr): return "green" if wr >= 62 else "yellow" if wr >= 52 else "red"
def _pnl_color(v): return "green" if v >= 0 else "red"


def make_header() -> Panel:
    elapsed = int(time.time() - state["start_time"])
    h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
    total = state["wins"] + state["losses"]
    wr = (state["wins"] / total * 100) if total > 0 else 0
    pnl = state["total_pnl"]
    bal = state["balance"]

    learner = get_adaptive_learner()
    global_wr = learner.get_global_winrate()

    title = Text()
    title.append("EXNOVA SMART BOT v4.0", style="bold cyan")
    title.append("  ·  MODO PRÁCTICA  ·  APRENDIZAJE ACTIVO", style="bold yellow")
    title.append(f"  ·  {h:02d}:{m:02d}:{s:02d}", style="white")

    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(7): grid.add_column(justify="center")

    grid.add_row(
        f"[dim]Balance[/dim]\n[bold white]${bal:,.2f}[/bold white]",
        f"[dim]PnL[/dim]\n[bold {_pnl_color(pnl)}]{'+' if pnl>=0 else ''}${pnl:.2f}[/bold {_pnl_color(pnl)}]",
        f"[dim]Win Rate[/dim]\n[bold {_wr_color(wr)}]{wr:.1f}%[/bold {_wr_color(wr)}]",
        f"[dim]W / L[/dim]\n[bold green]{state['wins']}[/bold green] / [bold red]{state['losses']}[/bold red]",
        f"[dim]Bot WR aprendido[/dim]\n[bold {'green' if global_wr>=0.55 else 'yellow'}]{global_wr:.1%}[/bold {'green' if global_wr>=0.55 else 'yellow'}]",
        f"[dim]Activo[/dim]\n[bold cyan]{state['current_asset'] or '---'}[/bold cyan]",
        f"[dim]Estado[/dim]\n[bold {'green' if state['status']=='OPERANDO' else 'yellow' if state['status']=='ANALIZANDO' else 'dim'}]{state['status']}[/bold {'green' if state['status']=='OPERANDO' else 'yellow' if state['status']=='ANALIZANDO' else 'dim'}]",
    )
    return Panel(grid, title=title, border_style="cyan", padding=(0,1))


def make_signal_panel() -> Panel:
    sig = state.get("last_signal", {})
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim",
                  expand=True, padding=(0,1))
    table.add_column("Activo", width=12)
    table.add_column("Señal", width=7, justify="center")
    table.add_column("Acción", width=8, justify="center")
    table.add_column("Score", width=7, justify="center")
    table.add_column("IA", width=11, justify="center")
    table.add_column("Zona", width=10, justify="center")
    table.add_column("Patrón", width=14)
    table.add_column("Exp.", width=10, justify="center")
    table.add_column("Análisis IA", ratio=1)

    if sig:
        s_dir  = sig.get("signal", "NEUTRAL")
        s_col  = "green" if s_dir == "CALL" else "red" if s_dir == "PUT" else "dim"
        act    = sig.get("action", "WAIT")
        a_col  = "bold green" if act == "TRADE" else "dim"
        score  = sig.get("score", 0)
        sc_col = "green" if score >= 65 else "yellow" if score >= 45 else "red"
        zone_str = f"{sig.get('zone', 0):.5f}" if sig.get("zone") else "---"
        pattern  = sig.get("pattern", "---") or "---"

        # IA info
        ai_label = sig.get("ai_label", "")
        ai_score = sig.get("ai_score", 0)
        ai_colors = {
            "EXCELENTE": "bold green", "BUENO": "green",
            "MODERADO": "yellow", "DÉBIL": "orange1",
            "SKIP": "red", "NORMAL": "dim",
        }
        ai_col = ai_colors.get(ai_label, "dim")
        ai_str = f"[{ai_col}]{ai_label}[/{ai_col}] [dim]{ai_score:.0f}[/dim]" if ai_label else "[dim]---[/dim]"

        # Narrativa IA (truncada para caber)
        narrative = (sig.get("ai_narrative", "") or sig.get("reason", "") or "")[:70]

        # Expiración
        exp_min   = sig.get("expiration_minutes", 0)
        exp_label = sig.get("expiration_label", "")
        exp_color = sig.get("expiration_color", "dim")
        exp_str   = f"[{exp_color}]{exp_min}m {exp_label}[/{exp_color}]" if exp_min > 0 else "[dim]---[/dim]"

        table.add_row(
            sig.get("asset", ""),
            f"[{s_col}]{s_dir}[/{s_col}]",
            f"[{a_col}]{act}[/{a_col}]",
            f"[{sc_col}]{score:.0f}[/{sc_col}]",
            ai_str,
            zone_str,
            f"[cyan]{pattern}[/cyan]",
            exp_str,
            f"[dim]{narrative}[/dim]",
        )
    else:
        table.add_row("[dim]---[/dim]", "", "", "", "", "", "", "", "[dim]Escaneando...[/dim]")

    return Panel(table, title="[bold]Última Señal  ·  Motor IA Activo[/bold]", border_style="magenta", padding=(0,1))


def make_watchlist_panel() -> Panel:
    """
    Panel de vigilancia estratégica — muestra el mapa de zonas H1/M15/M5
    y la proximidad actual del precio a cada nivel clave.
    Estado de cada zona: AT_ZONE 🔴 / APPROACHING 🟡 / WATCHING 🔵 / FAR ⚫
    """
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim",
                  expand=True, padding=(0,1))
    table.add_column("Par",   width=12)
    table.add_column("TF",    width=5,  justify="center")
    table.add_column("Tipo",  width=6,  justify="center")
    table.add_column("Nivel", width=10, justify="right")
    table.add_column("Dist%", width=7,  justify="right")
    table.add_column("Estado",width=12, justify="center")
    table.add_column("H1",    width=5,  justify="center")
    table.add_column("Fuerza",width=7,  justify="center")

    STATUS_ICONS = {
        "at_zone":    ("[bold red]▼ EN ZONA[/bold red]",    "bold red"),
        "approaching":("[bold yellow]→ APROX[/bold yellow]","bold yellow"),
        "watching":   ("[cyan]◉ VIGIL[/cyan]",              "cyan"),
        "far":        ("[dim]· lejos[/dim]",                "dim"),
    }
    H1_COLORS = {"up": "green", "down": "red", "neutral": "dim", "?": "dim"}

    rows = state.get("watchlist_rows", [])
    rows_added = 0
    for row in rows:
        if rows_added >= 10:
            break
        status = row.get("status", "far")
        icon, _ = STATUS_ICONS.get(status, STATUS_ICONS["far"])
        dist = row.get("distance_pct", 1.0)
        dist_col = "red" if dist < 0.0008 else "yellow" if dist < 0.0025 else "dim"
        z_type = row.get("zone_type", "?")
        t_col  = "blue" if z_type == "support" else "red"
        h1b    = row.get("h1_bias", "?")
        h1_col = H1_COLORS.get(h1b, "dim")
        tf_col = "green" if row.get("origin_tf") == "H1" else "yellow" if row.get("origin_tf") == "M15" else "dim"
        str_val = row.get("strength", 0)
        str_col = "green" if str_val >= 0.70 else "yellow" if str_val >= 0.45 else "dim"

        table.add_row(
            row.get("asset", ""),
            f"[{tf_col}]{row.get('origin_tf','?')}[/{tf_col}]",
            f"[{t_col}]{z_type[:4].upper()}[/{t_col}]",
            f"{row.get('level', 0):.5f}",
            f"[{dist_col}]{dist*100:.3f}%[/{dist_col}]",
            icon,
            f"[{h1_col}]{h1b.upper()[:3]}[/{h1_col}]",
            f"[{str_col}]{str_val:.2f}[/{str_col}]",
        )
        rows_added += 1

    if rows_added == 0:
        table.add_row("[dim]---[/dim]","","","","","[dim]Mapeando zonas H1/M15...[/dim]","","")

    wl_status = state.get("watchlist_status", "MAPEANDO")
    status_col = "green" if wl_status == "EN ZONA" else "yellow" if wl_status == "VIGILANDO" else "dim"
    title = (f"[bold]Mapa de Zonas Estratégicas[/bold]  "
             f"[{status_col}]● {wl_status}[/{status_col}]")
    return Panel(table, title=title, border_style="blue", padding=(0,1))


def make_trades_table() -> Panel:
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim",
                  expand=True, padding=(0,1))
    table.add_column("Hora", style="dim", width=8)
    table.add_column("Activo", width=12)
    table.add_column("Dir.", width=6, justify="center")
    table.add_column("$", width=8, justify="right")
    table.add_column("Conf.", width=6, justify="center")
    table.add_column("Patrón", width=14)
    table.add_column("Zona.Str", width=8, justify="center")
    table.add_column("Res.", width=6, justify="center")
    table.add_column("PnL", width=9, justify="right")

    for t in reversed(list(state["trades"])[-10:]):
        d_col = "green" if t["direction"] == "CALL" else "red"
        r_col = "green" if t["result"] == "WIN" else "red" if t["result"] == "LOSS" else "yellow"
        pnl = t.get("pnl", 0)
        pnl_str = f"[{'green' if pnl>=0 else 'red'}]{'+' if pnl>=0 else ''}{pnl:.2f}[/]"
        table.add_row(
            t["time"], t["asset"],
            f"[{d_col}]{t['direction']}[/{d_col}]",
            f"${t['amount']:.2f}",
            f"{t['confidence']*100:.0f}%",
            t.get("pattern", "---") or "---",
            f"{t.get('zone_strength', 0):.2f}",
            f"[{r_col}]{t['result']}[/{r_col}]",
            pnl_str,
        )

    if not state["trades"]:
        table.add_row("[dim]---[/dim]", "[dim]Esperando primera operación...[/dim]", "", "", "", "", "", "", "")

    return Panel(table, title="[bold]Historial de Operaciones[/bold]", border_style="blue", padding=(0,1))


def make_learning_panel() -> Panel:
    learner = get_adaptive_learner()
    m_intel = get_market_intelligence()
    grid = Table.grid(expand=True, padding=(0,1))
    grid.add_column(justify="left")
    grid.add_column(justify="right")

    wr = learner.get_global_winrate()
    grid.add_row("[dim]Trades aprendidos[/dim]", f"[white]{learner.total_trades}[/white]")
    grid.add_row("[dim]WR aprendido[/dim]", f"[{'green' if wr>=0.55 else 'yellow'}]{wr:.1%}[/]")

    # ── Cascada H1→M15→M5→M1 ──────────────────────────────────────────────
    sig = state.get("last_signal", {})
    cascade = sig.get("cascade", state.get("cascade_status", {}).get(
        state.get("current_asset",""), {}
    ))
    if cascade:
        h1  = cascade.get("h1",  "?")
        m15 = cascade.get("m15", "?")
        m5  = cascade.get("m5",  "?")
        m1  = cascade.get("m1",  "?")

        def tf_col(d):
            return "green" if d == "up" else "red" if d == "down" else "dim"

        tf_str = (
            f"[{tf_col(h1)}]H1:{h1[:1].upper()}[/{tf_col(h1)}] "
            f"[{tf_col(m15)}]M15:{m15[:1].upper()}[/{tf_col(m15)}] "
            f"[{tf_col(m5)}]M5:{m5[:1].upper()}[/{tf_col(m5)}] "
            f"[{tf_col(m1)}]M1:{m1[:1].upper()}[/{tf_col(m1)}]"
        )
        aligned = cascade.get("aligned", False)
        advanced = cascade.get("advanced", False)
        at_sr   = cascade.get("at_sr", False)
        grid.add_row("[dim]Cascada TF[/dim]", tf_str)
        grid.add_row(
            "[dim]Alineada/Avanzada/S/R[/dim]",
            f"[{'green' if aligned else 'red'}]{'✔' if aligned else '✗'}[/] "
            f"[{'green' if advanced else 'yellow'}]{'✔' if advanced else '·'}[/] "
            f"[{'green' if at_sr else 'yellow'}]{'✔' if at_sr else '·'}[/]"
        )

    # Post-trade evaluation status
    last_result = state.get("last_trade_result")
    if last_result:
        r_col = "green" if last_result == "WIN" else "red" if last_result == "LOSS" else "yellow"
        grid.add_row("[dim]Último resultado[/dim]", f"[{r_col}]{last_result}[/{r_col}]")

    # Pre-trade eval
    pre = state.get("pre_trade_eval")
    if pre:
        q = getattr(pre, "quality_vs_prev", "")
        q_col = "green" if q in ("MEJOR","PRIMERA") else "yellow" if q == "SIMILAR" else "red"
        grid.add_row("[dim]Setup vs anterior[/dim]", f"[{q_col}]{q}[/{q_col}]")

    # IA del último análisis
    ai_label   = sig.get("ai_label", "")
    ai_score   = sig.get("ai_score", 0)
    ai_colors  = {"EXCELENTE":"green","BUENO":"green","MODERADO":"yellow",
                  "DÉBIL":"orange1","SKIP":"red","NORMAL":"dim"}
    if ai_label:
        ai_col = ai_colors.get(ai_label, "dim")
        grid.add_row("[dim]IA[/dim]",
                     f"[{ai_col}]{ai_label} {ai_score:.0f}[/{ai_col}]")

    top = learner.get_top_conditions(2)
    for c in top:
        name = c["condition"].replace("_", " ")[:18]
        cwr  = c["win_rate"]
        grid.add_row(f"[dim]↑ {name}[/dim]",
                     f"[{'green' if cwr>=0.6 else 'yellow'}]{cwr:.0%}[/]")

    grid.add_row("", "")
    # ── Market Intelligence ──
    m_intel = get_market_intelligence()
    current_session = MarketIntelligence.get_current_session()
    session_data = m_intel.get_session_summary().get(current_session, {})
    s_wr = session_data.get("win_rate", 0)
    s_trades = session_data.get("trades", 0)
    s_cl = session_data.get("consecutive_losses", 0)
    session_str = f"{current_session.upper()} WR:{s_wr:.0%}"
    if s_trades >= 5:
        session_str += f" ({s_trades}t)"
    if s_cl >= 3:
        session_str += f" [red]CL:{s_cl}[/red]"
    grid.add_row("[dim]Sesión[/dim]", f"[cyan]{session_str}[/cyan]")

    grid.add_row("[dim]Umbral zona[/dim]",     f"[cyan]{learner.get_threshold('min_zone_strength'):.2f}[/cyan]")
    grid.add_row("[dim]Min. score[/dim]",      f"[cyan]{learner.get_min_score():.2f}[/cyan]")

    # ── Best hours from MI ──
    best_hours = m_intel.get_best_hours(3)
    if best_hours:
        hours_str = " | ".join(
            f"{h['hour']}({h['win_rate']:.0%})" for h in best_hours
        )
        grid.add_row("[dim]Mejores horas[/dim]", f"[green]{hours_str}[/green]")

    if state.get("last_diagnosis"):
        grid.add_row("", "")
        for line in state["last_diagnosis"][:3]:
            text = Text.from_markup(line)
            grid.add_row(text, "")

    return Panel(grid, title="[bold]Cascada + IA + Aprendizaje[/bold]", border_style="magenta", padding=(0,1))


def make_log_panel() -> Panel:
    text = Text()
    for line in list(state["log"])[-16:]:
        text.append_text(Text.from_markup(line + "\n"))
    return Panel(text, title="[bold]Log[/bold]", border_style="dim", padding=(0,1))


def make_risk_panel() -> Panel:
    total = state["wins"] + state["losses"]
    wr = (state["wins"] / total * 100) if total > 0 else 0
    dd = ((state["initial_balance"] - state["balance"]) / state["initial_balance"] * 100) \
         if state["initial_balance"] > 0 else 0
    dd_col = "red" if dd > 10 else "yellow" if dd > 5 else "green"
    elapsed_h = max((time.time() - state["start_time"]) / 3600, 0.01)
    trades_h = total / elapsed_h
    streak = state["current_streak"]
    streak_str = f"[green]+{streak}[/green]" if streak > 0 else f"[red]{streak}[/red]"

    grid = Table.grid(expand=True, padding=(0,1))
    grid.add_column(justify="left"); grid.add_column(justify="right")
    grid.add_row("[dim]Drawdown[/dim]", f"[{dd_col}]{dd:.2f}%[/{dd_col}]")
    grid.add_row("[dim]Trades totales[/dim]", str(total))
    grid.add_row("[dim]Trades/hora[/dim]", f"{trades_h:.1f}")
    grid.add_row("[dim]Racha[/dim]", streak_str)
    grid.add_row("[dim]Mejor racha[/dim]", f"[green]+{state['best_streak']}[/green]")
    grid.add_row("[dim]Pérd. seguidas[/dim]",
                 f"[{'red' if state['consecutive_losses']>=3 else 'white'}]{state['consecutive_losses']}[/]")
    grid.add_row("[dim]Ciclo[/dim]", str(state["cycle"]))
    return Panel(grid, title="[bold]Riesgo[/bold]", border_style="yellow", padding=(0,1))


def build_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="signal_row", size=5),
        Layout(name="middle"),
        Layout(name="bottom"),
    )
    layout["middle"].split_row(
        Layout(name="watchlist", ratio=3),
        Layout(name="risk", ratio=1),
    )
    layout["bottom"].split_row(
        Layout(name="trades", ratio=3),
        Layout(name="right_col", ratio=2),
    )
    layout["right_col"].split_column(
        Layout(name="learning"),
        Layout(name="log_panel"),
    )
    return layout


def update_layout(layout: Layout):
    layout["header"].update(make_header())
    layout["signal_row"].update(make_signal_panel())
    layout["watchlist"].update(make_watchlist_panel())
    layout["risk"].update(make_risk_panel())
    layout["trades"].update(make_trades_table())
    layout["learning"].update(make_learning_panel())
    layout["log_panel"].update(make_log_panel())


def record_trade(asset, direction, amount, confidence, result, pnl,
                 pattern="", zone_strength=0.0):
    state["trades"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "asset": asset, "direction": direction, "amount": amount,
        "confidence": confidence, "result": result, "pnl": pnl,
        "pattern": pattern, "zone_strength": zone_strength,
    })
    if result == "WIN":
        state["wins"] += 1
        state["consecutive_losses"] = 0
        state["current_streak"] = max(0, state["current_streak"]) + 1
        state["best_streak"] = max(state["best_streak"], state["current_streak"])
    elif result == "LOSS":
        state["losses"] += 1
        state["consecutive_losses"] += 1
        state["current_streak"] = min(0, state["current_streak"]) - 1
    state["total_pnl"] += pnl
    state["balance"] = max(0, state["balance"] + pnl)


# ─── Bucle principal v5.1 — Sistema de dos fases ──────────────────────────────
#
# Fase 1 — MAPA ESTRATÉGICO (cada 30 min):
#   Analiza H1/M15/M5 de cada par y construye el mapa de zonas clave.
#   El bot sabe DÓNDE debería reaccionar el precio ANTES de que llegue.
#
# Fase 2 — MONITOR DE PROXIMIDAD (continuo):
#   Revisa si el precio se está acercando a alguna zona del mapa.
#   FAR (>0.5%)     → heartbeat lento, solo actualizar dashboard
#   APPROACHING     → alerta, preparar análisis
#   AT_ZONE (<0.08%)→ activa análisis M1 completo para detectar entrada
#
# La entrada SOLO se ejecuta cuando:
#   ✔ Zona identificada en H1/M15 (no ruido de M1)
#   ✔ M5 muestra acercamiento limpio y ordenado
#   ✔ M1 (última vela cerrada) muestra mecha de rechazo visible
#   ✔ Cascada H1→M15→M5 alineada con la dirección esperada

def bot_loop(market_data: MarketDataHandler, rm, engine: IntelligentEngine):
    email    = os.getenv("EXNOVA_EMAIL", "")
    password = os.getenv("EXNOVA_PASSWORD", "")
    learner   = get_adaptive_learner()
    memory    = get_market_memory()
    evaluator = TradeEvaluator()
    pre_eval  = PreTradeEvaluator()
    watchlist = get_zone_watchlist()
    m_intel   = get_market_intelligence()

    log("Conectando a Exnova PRACTICE...", "INFO")
    print("Conectando a EXNOVA (PRACTICE)...")
    state["status"] = "CONECTANDO"

    if not market_data.connect(email, password):
        log("ERROR: No se pudo conectar. Verificá credenciales.", "ERROR")
        print("[ERROR] No se pudo conectar. Verificá credenciales.")
        state["status"] = "ERROR"
        return
    else:
        print("[OK] Conectado a EXNOVA (PRACTICE)")

    try:
        balance = market_data.get_balance()
        balance = float(balance) if balance and float(balance) > 0 else INITIAL_BALANCE
    except Exception:
        balance = INITIAL_BALANCE

    state["balance"] = balance
    state["initial_balance"] = balance
    rm.initialize(balance)
    log(f"Conectado. Balance práctica: ${balance:,.2f}", "INFO")
    log(f"Sistema v5.1: mapa estratégico H1/M15 + monitor M1", "INFO")
    log(f"Aprendizaje cargado. {learner.summary()}", "LEARN")

    # ── Fase 1 inicial: mapear zonas para todos los pares ─────────────────────
    state["status"] = "MAPEANDO"
    state["watchlist_status"] = "MAPEANDO"
    log("Construyendo mapa de zonas estratégicas H1/M15/M5...", "ZONE")
    for asset in ASSETS:
        try:
            n = watchlist.refresh_zones(asset, market_data)
            bias = watchlist.get_h1_bias(asset)
            log(f"{asset}: {n} zonas mapeadas | H1 sesgo={bias}", "ZONE")
        except Exception as e:
            log(f"{asset}: error mapeando — {e}", "WARN")
    state["watchlist_rows"] = watchlist.get_dashboard_rows(ASSETS)
    state["status"] = "VIGILANDO"
    state["watchlist_status"] = "VIGILANDO"

    last_reconnect = time.time()
    trade_executed_in_cycle = False

    while state["running"]:
        try:
            state["cycle"] += 1
            now = time.time()

            # ── Reconexión periódica ──────────────────────────────────────────
            if now - last_reconnect > 240:
                if not market_data.is_really_connected():
                    log("Reconectando...", "WARN")
                    market_data.reconnect(email, password)
                last_reconnect = now

            # ── Pausa por pérdidas consecutivas ──────────────────────────────
            if state["consecutive_losses"] >= MAX_CONSEC_LOSSES:
                state["status"] = "PAUSA_RIESGO"
                log(f"PAUSA: {state['consecutive_losses']} pérdidas seguidas. Esperando 5 min.", "WARN")
                time.sleep(300)
                state["consecutive_losses"] = 0
                trade_executed_in_cycle = False
                continue

            # ── Post-trade: evaluar y refrescar zonas ─────────────────────────
            if trade_executed_in_cycle:
                state["post_trade_phase"] = True
                last_diag  = state.get("last_trade_diagnosis")
                result_str = state.get("last_trade_result", "?")
                if isinstance(last_diag, dict):
                    cause = last_diag.get("primary_cause", "desconocida")
                    log(f"Post-trade [{result_str}]: causa = {cause}", "LEARN")

                # Forzar re-mapeo solo del asset operado — más rápido
                traded_asset = state.get("current_asset", "")
                if traded_asset:
                    watchlist.force_refresh(traded_asset)
                    try:
                        engine.force_rescan_zones(traded_asset, market_data)
                    except Exception:
                        pass
                    log(f"Zonas {traded_asset} actualizadas post-trade", "ZONE")
                trade_executed_in_cycle = False
                state["post_trade_phase"] = False
                time.sleep(5)
                continue

            # ── FASE 1: Actualizar mapa si hace >30 min + obtener precios ─────
            for asset in ASSETS:
                try:
                    if watchlist.needs_refresh(asset):
                        n = watchlist.refresh_zones(asset, market_data)
                        bias = watchlist.get_h1_bias(asset)
                        log(f"{asset}: mapa actualizado — {n} zonas | H1={bias}", "ZONE")

                    # Precio actual: solo necesitamos las últimas 3 velas M1
                    df_q = market_data.get_candles(asset, 60, 5)
                    if df_q is not None and len(df_q) >= 2:
                        price = float(df_q.iloc[-2]["close"])   # última vela cerrada
                        watchlist.update_price(asset, price)
                        
                        # ── VALIDACIÓN DINÁMICA DE ZONAS (v5.2) ──────────────────
                        # Detectar rupturas de estructura
                        if watchlist.detect_zone_breakout(asset, price):
                            log(f"{asset}: ruptura detectada — zonas invalidadas", "ZONE")
                        
                        # Filtrar zonas obsoletas o rotas
                        valid_zones = watchlist.filter_valid_zones(asset, price)
                        if len(valid_zones) < watchlist.get_zone_count(asset):
                            removed = watchlist.get_zone_count(asset) - len(valid_zones)
                            log(f"{asset}: {removed} zonas removidas (obsoletas/rotas)", "ZONE")
                except Exception:
                    pass

            state["watchlist_rows"] = watchlist.get_dashboard_rows(ASSETS)

            # ── FASE 2: ¿Hay algún par en zona o acercándose? ─────────────────
            active = watchlist.get_all_active(ASSETS)

            if not active:
                # Ningún par cerca de zona — heartbeat + info de distancias
                state["status"] = "VIGILANDO"
                state["watchlist_status"] = "VIGILANDO"
                if state["cycle"] % 6 == 0:
                    nearest_info = []
                    for a in ASSETS:
                        status_s, zone_n, dist_n = watchlist.get_status(a)
                        if zone_n:
                            nearest_info.append(
                                f"{a[:6]}→{zone_n.origin_tf} {dist_n*100:.2f}%"
                            )
                    log(f"Vigilando | {' | '.join(nearest_info)}", "ZONE")
                print(f"[WATCH] Ciclo {state['cycle']} | {state['status']} | "
                      f"Balance: ${state['balance']:.2f} | Sin zonas activas")
                time.sleep(8)
                continue

            # ── FASE 3: Procesar pares activos ───────────────────────────────
            at_zone_count = sum(
                1 for _, z in active if z.proximity_status == "at_zone"
            )
            state["watchlist_status"] = "EN ZONA" if at_zone_count else "APROXIMANDO"

            print(f"[ANALISIS] {len(active)} zonas activas encontradas")
            for asset, watched_zone in active:
                if trade_executed_in_cycle:
                    break

                prox   = watched_zone.proximity_status
                dist   = watched_zone.current_distance_pct
                h1_bias = watchlist.get_h1_bias(asset)

                state["current_asset"] = asset
                print(f"[ZONA] {asset} {watched_zone.zone_type} {watched_zone.level:.5f} "
                      f"dist={dist*100:.3f}% prox={prox} tf={watched_zone.origin_tf} "
                      f"str={watched_zone.strength:.2f} H1={h1_bias}")

                if prox == "approaching":
                    # Zonas fuertes en APPROACHING también activan análisis M1
                    if watched_zone.strength >= 0.70 or watched_zone.importance >= 2:
                        state["status"] = "ANALIZANDO"
                        print(f"[APROX_FUERTE] {asset} — zona fuerte activa análisis M1")
                    else:
                        if not watched_zone.approach_alerted:
                            log(
                                f"◈ APROX {asset} → [{watched_zone.origin_tf}] "
                                f"{watched_zone.zone_type[:4].upper()} {watched_zone.level:.5f} "
                                f"dist={dist*100:.3f}% | H1={h1_bias}",
                                "ZONE"
                            )
                            watched_zone.approach_alerted = True
                        state["status"] = "VIGILANDO"
                        continue

                # ── prox == "at_zone" → activar análisis M1 completo ──────────
                state["status"] = "ANALIZANDO"
                print(f"[AT_ZONE] {asset} — activando análisis M1 completo")

                if not watched_zone.at_zone_alerted:
                    log(
                        f"▶ EN ZONA [{watched_zone.origin_tf}] {asset} "
                        f"{watched_zone.zone_type.upper()} {watched_zone.level:.5f} "
                        f"| H1={h1_bias} | str={watched_zone.strength:.2f}",
                        "SIGNAL"
                    )
                    watched_zone.at_zone_alerted = True

                # Pasar contexto del watchlist al engine (jerarquía TF)
                signal = engine.analyze(asset, market_data, fe={
                    "watchlist_zone":   watched_zone,
                    "h1_bias":          h1_bias,
                    "zone_origin_tf":   watched_zone.origin_tf,
                    "zone_importance":  watched_zone.importance,
                })

                if not signal:
                    print(f"[AT_ZONE] {asset} — engine.analyze() retornó None")
                    continue

                action     = signal.get("action", "WAIT")
                confidence = signal.get("confidence", 0)
                score      = signal.get("score", 0)
                direction  = signal.get("signal", "?")
                reason     = signal.get("reason", "")[:80]

                print(f"[ANALISIS] {asset} | acción={action} dir={direction} "
                      f"score={score:.0f} conf={confidence:.2f} | {reason}")

                state["last_signal"] = signal
                if "cascade" in signal:
                    state["cascade_status"][asset] = signal["cascade"]

                if action == "TRADE" and confidence >= MIN_CONFIDENCE:
                    print(f"[DBG_EXEC] {asset} action=TRADE conf={confidence:.2f} min_conf={MIN_CONFIDENCE:.2f}")
                    time_since = now - state["last_trade_time"]
                    cooldown_needed = (
                        COOLDOWN_AFTER_LOSS if state["consecutive_losses"] > 0
                        else MIN_BETWEEN_TRADES
                    )
                    if time_since < cooldown_needed:
                        remaining = int(cooldown_needed - time_since)
                        print(f"[DBG_EXEC] {asset} cooldown {remaining}s")
                        log(f"Cooldown: {remaining}s más", "WAIT")
                    elif rm.is_stopped:
                        print(f"[DBG_EXEC] {asset} rm.stopped={rm.is_stopped}")
                        log(f"Risk Manager activo: {rm.stop_reason}", "WARN")
                    else:
                        cascade_obj = engine._last_cascade_result.get(asset)
                        pre_decision = pre_eval.evaluate_entry(
                            last_trade=state.get("last_trade_record"),
                            last_diagnosis=state.get("last_trade_diagnosis"),
                            new_signal=signal,
                            cascade=cascade_obj,
                            recent_trades=state["trades"][-10:],
                        )
                        state["pre_trade_eval"] = pre_decision
                        for reason in pre_decision.reasoning[-3:]:
                            log(f"Pre-eval: {reason}", "LEARN")

                        print(f"[DBG_EXEC] {asset} pre_decision.should_enter={pre_decision.should_enter} new_score={pre_decision.new_setup_score:.0f}")
                        for r in pre_decision.reasoning[-2:]:
                            print(f"[DBG_EXEC] {asset} pre_decision reason: {r}")
                        if pre_decision.should_enter:
                            # ── Market Intelligence validation ──
                            mi_skip, mi_reason = m_intel.should_skip_trade(
                                asset=asset, confidence=confidence,
                                direction=signal.get("signal", "CALL"),
                                expiration_sec=signal.get("expiration", 60)
                            )
                            if mi_skip:
                                log(f"MI: {mi_reason}", "WAIT")
                                pending = state["pending_entries"].get(asset, [])
                                pending.append({
                                    "signal": signal,
                                    "reason": f"MI: {mi_reason}",
                                    "timestamp": now,
                                    "score": pre_decision.new_setup_score,
                                })
                                state["pending_entries"][asset] = pending[-3:]
                                continue

                            # ── Trap warnings ──
                            trap_warnings = m_intel.get_trap_warnings(asset)
                            for tw in trap_warnings[:1]:
                                log(f"⚠ {tw}", "WARN")

                            amount = rm.calculate_position_size(confidence=confidence)
                            if amount > 0:
                                log(
                                    f"Pre-eval: {pre_decision.suggestion} "
                                    f"(score={pre_decision.new_setup_score:.0f})",
                                    "INFO"
                                )
                                execute_trade(
                                    market_data, rm, signal, amount,
                                    learner, memory, evaluator, engine
                                )
                                trade_executed_in_cycle = True
                                log("Una operación por ciclo — evaluando antes de continuar.", "LEARN")
                        else:
                            pending = state["pending_entries"].get(asset, [])
                            wait_reason = pre_decision.suggestion or " | ".join(pre_decision.reasoning[-2:])
                            pending.append({
                                "signal": signal,
                                "reason": wait_reason,
                                "timestamp": now,
                                "score": pre_decision.new_setup_score,
                            })
                            state["pending_entries"][asset] = pending[-3:]
                            log(f"Pre-eval: ESPERAR — {wait_reason[:70]}", "WAIT")

                elif action == "WAIT":
                    reason = signal.get("reason", "")
                    if reason and ("zona" in reason.lower() or "cascada" in reason.lower()
                                   or "mecha" in reason.lower()):
                        log(f"{asset} | {reason[:80]}", "ZONE")
                    elif reason:
                        log(f"{asset} | {reason[:80]}", "WAIT")
                else:
                    log(f"{asset} | Score {score:.0f} | {signal.get('reason','')[:70]}", "WAIT")

            # Sleep adaptativo: monitoreo más frecuente
            if at_zone_count > 0:
                time.sleep(2)   # En zona — revisar cada 2s
            else:
                time.sleep(4)   # Aproximándose — revisión cada 4s

        except KeyboardInterrupt:
            state["running"] = False
            break
        except Exception as e:
            log(f"Error en loop: {e}", "ERROR")
            time.sleep(5)

    log("Bot detenido.", "INFO")
    state["status"] = "DETENIDO"
    memory.save()


def execute_trade(market_data, rm, signal, amount, learner, memory, evaluator, engine):
    asset      = signal["asset"]
    direction  = signal["signal"]
    confidence = signal["confidence"]
    expiration = signal.get("expiration", 60)
    pattern    = signal.get("pattern", "")
    zone_str   = signal.get("zone_strength", 0.0)
    context    = signal.get("context", {})
    conditions = signal.get("conditions", {})
    zone_obj   = signal.get("zone_object")
    m_intel    = get_market_intelligence()

    action_str = "call" if direction == "CALL" else "put"
    duration   = max(3, min(5, expiration // 60))

    exp_min   = signal.get("expiration_minutes", expiration // 60)
    exp_label = signal.get("expiration_label", "NORMAL")
    cplx      = signal.get("complexity_score", 50)
    log(f"ENTRANDO: {asset} {direction} ${amount:.2f} | {pattern} | zona={zone_str:.2f} | conf={confidence*100:.0f}% | {exp_min}min [{exp_label}] cplx={cplx:.0f}", "SIGNAL")
    state["status"] = "OPERANDO"

    print(f"[DBG_EXEC] execute_trade llamado: {asset} {direction} ${amount:.2f} exp={duration}min")
    try:
        check, order_id = market_data.buy(asset, amount, action_str, duration)

        if check:
            log(f"Orden abierta: {direction} ${amount:.2f} exp={duration}min", "INFO")
            print(f"[DBG_EXEC] Orden ABIERTA: {asset} {direction} ${amount:.2f} order_id={order_id}")
            state["active_order"] = order_id
            state["last_trade_time"] = time.time()
            time.sleep(expiration + 8)

            # Verificar resultado
            result, pnl = "DRAW", 0.0
            try:
                result_data = market_data.api.check_win_v4(order_id)
                # Reintentar si no hay respuesta
                if result_data is None or len(result_data) != 2:
                    log("Reintentando verificar resultado...", "WARN")
                    time.sleep(15)
                    result_data = market_data.api.check_win_v4(order_id)
                
                if result_data is not None and len(result_data) == 2:
                    win_status, profit = result_data
                    profit = float(profit) if profit is not None else 0.0
                    
                    if win_status == "win" or profit > 0:
                        pnl, result = profit, "WIN"
                        log(f"WIN +${profit:.2f} | {asset} {direction}", "WIN")
                    elif win_status == "loose" or profit < 0:
                        pnl, result = profit, "LOSS"
                        log(f"LOSS ${profit:.2f} | {asset} {direction}", "LOSS")
                    elif win_status == "equal" or profit == 0:
                        pnl, result = 0.0, "DRAW"
                        log(f"EMPATE | {asset} {direction}", "WARN")
                    else:
                        pnl, result = 0.0, "DRAW"
                        log(f"Resultado desconocido: {win_status} | {asset} {direction}", "WARN")
                else:
                    pnl, result = -amount, "LOSS"
                    log("Sin confirmación — asumiendo pérdida total", "WARN")
            except Exception as e:
                log(f"Error verificando resultado: {e}", "WARN")
                pnl, result = -amount, "LOSS"

            record_trade(asset, direction, amount, confidence, result, pnl, pattern, zone_str)
            if zone_obj:
                engine.record_zone_result(asset, zone_obj.level, zone_obj.zone_type, result == "WIN")
            rm.update_balance(state["balance"], {"profit": pnl})

            # ── Auto-evaluación y aprendizaje ──
            # Capturar velas DESPUÉS del trade para detectar entrada prematura
            df_after = None
            try:
                df_after = market_data.get_candles(asset, 60, 20)
            except Exception:
                pass

            trade_record = {
                "asset": asset, "direction": direction, "amount": amount,
                "confidence": confidence, "result": result, "pnl": pnl,
                "pattern": pattern, "order_id": str(order_id),
                "entry_price": signal.get("zone", 0.0) or amount,
                "expiration_minutes": signal.get("expiration_minutes", duration),
                "cascade": signal.get("cascade", {}),
            }
            diagnosis = evaluator.evaluate(trade_record, context, conditions,
                                           df_m1_after=df_after)
            learner.learn_from_trade(conditions, result, diagnosis)
            state["last_diagnosis"] = evaluator.format_for_display(diagnosis)

            # ── Market Intelligence 24/7 ──
            cascade_obj = signal.get("cascade", {})
            trap_type = ""
            if result == "LOSS":
                pc = diagnosis.get("primary_cause", "") if isinstance(diagnosis, dict) else ""
                if pc == "no_rejection_wick":      trap_type = "fake_breakout"
                elif pc == "premature_entry":      trap_type = "premature_timing"
                elif pc == "counter_trend":        trap_type = "counter_trend_trap"
                elif pc == "bad_market_phase":     trap_type = "low_volatility_reversal"
                elif pc == "zone_too_weak":        trap_type = "weak_zone_failure"
                elif pc == "liquidity_trap":       trap_type = "liquidity_trap"
            m_intel.record_trade(
                asset=asset, direction=direction, won=(result == "WIN"),
                expiration_sec=signal.get("expiration", 60),
                confidence=confidence,
                volatility=context.get("momentum", {}).get("volatility", 0.0),
                pnl=pnl, trap_type=trap_type
            )

            # ── Guardar para evaluación pre-trade del siguiente ciclo ─────────
            state["last_trade_result"]    = result
            state["last_trade_record"]    = trade_record
            state["last_trade_diagnosis"] = diagnosis

            # ── Log detallado de la operación (trade_log.jsonl) ───────────────
            cascade_obj = signal.get("cascade", {})
            zone_level  = zone_obj.level if zone_obj else signal.get("zone", 0.0)
            zone_type   = zone_obj.zone_type if zone_obj else ""
            zone_str_v  = zone_obj.strength if zone_obj else signal.get("zone_strength", 0.0)
            zone_touch  = zone_obj.touches if zone_obj else 0
            tlog(
                asset=asset, direction=direction, amount=amount,
                entry_price=signal.get("entry_price", zone_level),
                expiration_min=duration,
                confidence=confidence, result=result, pnl=pnl,
                zone_level=zone_level, zone_type=zone_type,
                zone_strength=zone_str_v, zone_touches=zone_touch,
                pattern=pattern,
                rsi_value=context.get("momentum", {}).get("rsi_m1", 50.0),
                macd_signal=context.get("macd_signal", ""),
                cascade=cascade_obj if isinstance(cascade_obj, dict) else {},
                ai_score=signal.get("ai_score", 0.0),
                ai_label=signal.get("ai_label", ""),
                final_score=signal.get("score", 0.0),
                conditions=conditions,
                diagnosis=diagnosis if isinstance(diagnosis, dict) else None,
            )

            # Actualizar memoria de zona — con causa de fallo para que la zona aprenda
            if zone_obj:
                reacted = (result == "WIN" and direction == "CALL" and zone_obj.zone_type == "support") or \
                          (result == "WIN" and direction == "PUT" and zone_obj.zone_type == "resistance")
                primary_cause = diagnosis.get("primary_cause", "") if isinstance(diagnosis, dict) else ""
                memory.add_or_update_zone(
                    asset, zone_obj.level, zone_obj.zone_type, reacted,
                    failure_cause=primary_cause if result != "WIN" else ""
                )
                memory.save()

            # Log de aprendizaje con causa específica
            if result == "LOSS":
                cause = diagnosis.get("primary_cause", "desconocida") if isinstance(diagnosis, dict) else "evaluando"
                lesson = (diagnosis.get("lessons") or [""])[0] if isinstance(diagnosis, dict) else ""
                if lesson:
                    log(f"LOSS — causa: {cause} | {lesson}", "LEARN")
                else:
                    log(f"LOSS — evaluando causa: {cause}", "LEARN")
            elif result == "WIN":
                worked = (diagnosis.get("what_worked") or []) if isinstance(diagnosis, dict) else []
                if worked:
                    log(f"WIN — confirmado: {worked[0]}", "LEARN")
                else:
                    log(f"WIN — setup válido confirmado", "LEARN")

        else:
            log(f"Orden rechazada: {order_id}", "ERROR")

    except Exception as e:
        log(f"Error ejecutando trade: {e}", "ERROR")

    state["status"] = "ANALIZANDO"
    state["active_order"] = None


# ─── Entry point ─────────────────────────────────────────────────────────────

def signal_handler(sig, frame):
    state["running"] = False


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Detectar headless (sin TTY) — Docker / EasyPanel
    headless = not sys.stdout.isatty()

    if not headless:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]EXNOVA ULTRA-SMART BOT v5.0 — CASCADA H1→M15→M5→M1[/bold cyan]\n"
            "[dim]Cascada de tendencia · Una op/ciclo · Evaluación obligatoria · Liquidez evitada[/dim]",
            border_style="cyan"
        ))

    risk_config = RiskConfig(
        max_drawdown_daily=0.15,
        max_trades_per_hour=8,
        cooldown_after_loss_seconds=COOLDOWN_AFTER_LOSS,
        min_confidence_threshold=MIN_CONFIDENCE,
        stop_after_consecutive_losses=MAX_CONSEC_LOSSES,
    )
    rm = initialize_risk_manager(INITIAL_BALANCE, risk_config)
    market_data = MarketDataHandler(broker_name="exnova", account_type="PRACTICE")
    engine = IntelligentEngine()

    state["start_time"] = time.time()

    bot_thread = threading.Thread(
        target=bot_loop, args=(market_data, rm, engine), daemon=True
    )
    bot_thread.start()

    if headless:
        # Modo headless (Docker): solo esperar sin UI
        log("Modo headless — sin dashboard visual", "INFO")
        log(f"Assets: {ASSETS} | Balance: ${state['balance']:.2f} | Confianza min: {MIN_CONFIDENCE}", "INFO")
        print(f"[HEADLESS] Balance: ${state['balance']:.2f} | Assets: {ASSETS}")
        print(f"[HEADLESS] Confianza min: {MIN_CONFIDENCE} | Cooldown: {COOLDOWN_AFTER_LOSS}s")
        last_cycle = 0
        while state["running"] or state["status"] not in ("DETENIDO", "ERROR"):
            if state["cycle"] > last_cycle:
                last_cycle = state["cycle"]
                total = state["wins"] + state["losses"]
                wr = (state["wins"] / total * 100) if total > 0 else 0
                log(f"Estado: {state['status']} | Trades: {state['wins']+state['losses']} "
                    f"W:{state['wins']} L:{state['losses']} PnL:${state['total_pnl']:.2f}", "INFO")
                last_log_lines = [ln for ln in list(state["log"])[-3:]]
                print(f"[{state['cycle']}] {state['status']} | "
                      f"T: {total} W:{state['wins']} L:{state['losses']} "
                      f"WR:{wr:.1f}% PnL:${state['total_pnl']:.2f} "
                      f"Activo: {state['current_asset']}")
            time.sleep(5)
    else:
        layout = build_layout()
        with Live(layout, console=console, refresh_per_second=2, screen=True):
            while state["running"] or state["status"] not in ("DETENIDO", "ERROR"):
                update_layout(layout)
                time.sleep(0.5)
            update_layout(layout)
            time.sleep(2)

    total = state["wins"] + state["losses"]
    wr = (state["wins"] / total * 100) if total > 0 else 0
    learner = get_adaptive_learner()
    console.print()
    console.print(Panel(
        f"[bold]Resumen Final[/bold]\n\n"
        f"  Trades: {total}  |  [green]{state['wins']}W[/green] / [red]{state['losses']}L[/red]\n"
        f"  Win Rate: [{'green' if wr>=60 else 'yellow'}]{wr:.1f}%[/]\n"
        f"  PnL: [{'green' if state['total_pnl']>=0 else 'red'}]{'+' if state['total_pnl']>=0 else ''}{state['total_pnl']:.2f}[/]\n"
        f"  Balance final: ${state['balance']:.2f}\n\n"
        f"  [dim]Sistema aprendió de {learner.total_trades} trades. WR aprendido: {learner.get_global_winrate():.1%}[/dim]",
        border_style="cyan", title="[bold cyan]BOT DETENIDO[/bold cyan]"
    ))


if __name__ == "__main__":
    print("Usá 'python console_setup.py' para arrancar el bot con configuración interactiva.")
    print("Ejecutando console_setup.py...")
    import console_setup
    console_setup.run_setup()
