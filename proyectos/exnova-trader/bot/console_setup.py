#!/usr/bin/env python3
"""
Console Setup — Configuración interactiva del bot
Primero conecta, luego trae el balance, después pedís las órdenes.
"""
import os
import sys
import json
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(os.path.dirname(BOT_DIR), ".env")
CONFIG_PATH = os.path.join(BOT_DIR, "bot_config.json")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, FloatPrompt, Confirm
from rich.text import Text
from rich import box
from rich.spinner import Spinner
from rich.live import Live
from data.market_data import MarketDataHandler

console = Console()

ALL_ASSETS = [
    "EURUSD-OTC", "GBPUSD-OTC", "AUDUSD-OTC", "EURJPY-OTC",
    "USDJPY-OTC", "GBPJPY-OTC", "USDCAD-OTC", "NZDUSD-OTC",
    "USDCHF-OTC", "EURGBP-OTC", "AUDJPY-OTC", "CADJPY-OTC",
    "CHFJPY-OTC", "EURCHF-OTC", "GBPCHF-OTC", "GBPAUD-OTC",
    "GBPNZD-OTC", "NZDCAD-OTC", "NZDJPY-OTC", "USDNOK-OTC",
    "USDSEK-OTC",
]

ASSET_SHORT = {
    "EURUSD-OTC": "EUR/USD", "GBPUSD-OTC": "GBP/USD",
    "AUDUSD-OTC": "AUD/USD", "EURJPY-OTC": "EUR/JPY",
    "USDJPY-OTC": "USD/JPY", "GBPJPY-OTC": "GBP/JPY",
    "USDCAD-OTC": "USD/CAD", "NZDUSD-OTC": "NZD/USD",
    "USDCHF-OTC": "USD/CHF", "EURGBP-OTC": "EUR/GBP",
    "AUDJPY-OTC": "AUD/JPY", "CADJPY-OTC": "CAD/JPY",
    "CHFJPY-OTC": "CHF/JPY", "EURCHF-OTC": "EUR/CHF",
    "GBPCHF-OTC": "GBP/CHF", "GBPAUD-OTC": "GBP/AUD",
    "GBPNZD-OTC": "GBP/NZD", "NZDCAD-OTC": "NZD/CAD",
    "NZDJPY-OTC": "NZD/JPY", "USDNOK-OTC": "USD/NOK",
    "USDSEK-OTC": "USD/SEK",
}


def show_header():
    console.clear()
    header = Panel(
        Text.from_markup(
            "[bold cyan]⚡ EXNOVA TRADING BOT[/bold cyan]\n"
            "[dim]Configuración guiada — Conectá primero, configurá después[/dim]"
        ),
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(header)


def show_assets_menu(available_assets=None):
    items = available_assets if available_assets else ALL_ASSETS
    console.print("[bold]Divisas disponibles:[/bold]\n")
    cols = 3
    for i in range(0, len(items), cols):
        row = []
        for j in range(cols):
            if i + j < len(items):
                code = items[i + j]
                name = ASSET_SHORT.get(code, code.replace("-OTC", ""))
                row.append(f"  [cyan]{i+j+1:2d}.[/cyan]  {name:<10}")
        console.print("".join(row))
    console.print()


def run_setup():
    show_header()

    console.print("[bold]Paso 1 — Ingresá tus credenciales:[/bold]\n")

    # Auto-detectar desde .env si ya hay credenciales guardadas
    env_email = os.getenv("EXNOVA_EMAIL", "")
    env_pass = os.getenv("EXNOVA_PASSWORD", "")
    if env_email and env_pass:
        email = env_email
        password = env_pass
        console.print(f"  [dim]Usando credenciales guardadas: {email}[/dim]\n")
    else:
        email = Prompt.ask("  [bold cyan]Correo Electrónico[/bold cyan]")
        password = Prompt.ask("  [bold cyan]Contraseña[/bold cyan]", password=True)

    console.print()
    console.print("  [bold]Tipo de cuenta:[/bold]")
    console.print("    [cyan]1.[/cyan]  Práctica (Demo)")
    console.print("    [cyan]2.[/cyan]  Real\n")
    account_type = Prompt.ask("  [bold]Opción[/bold]", choices=["1", "2"], default="1")
    account_type = "REAL" if account_type == "2" else "PRACTICE"

    # ── Conectar ──
    console.print()
    status = Panel("  [yellow]⏳ Conectando a EXNOVA...[/yellow]", border_style="yellow")
    console.print(status)
    with console.status("[bold yellow]Conectando al broker...[/bold yellow]", spinner="dots"):
        market = MarketDataHandler(broker_name="exnova", account_type=account_type)
        connected = market.connect(email, password)

    if not connected:
        console.print("\n  [bold red]❌ No se pudo conectar. Verificá tus credenciales e intentá de nuevo.[/bold red]")
        if Confirm.ask("\n  [yellow]¿Reintentar?[/yellow]", default=True):
            run_setup()
        return

    # ── Balance ──
    raw_balance = market.get_balance()
    try:
        balance = float(raw_balance) if raw_balance and float(raw_balance) > 0 else 0
    except Exception:
        balance = 0
    market.disconnect()

    if balance <= 0:
        console.print("\n  [yellow]⚠ No se pudo obtener el balance automáticamente.[/yellow]")
        balance = FloatPrompt.ask("  [bold]Ingresá tu balance manualmente ($)[/bold]", default=10000.0)

    console.print(f"\n  [green]✅ Conectado. Balance: [bold]${balance:,.2f}[/bold][/green]")

    # ── Opciones ──
    console.print()
    console.print("[bold]Paso 2 — Elegí la configuración de trading:[/bold]\n")

    # Monto por operación
    console.print("  [bold]Monto por operación:[/bold]")
    console.print("    [cyan]1.[/cyan]  $0.50     [cyan]2.[/cyan]  $1.00     [cyan]3.[/cyan]  $2.00")
    console.print("    [cyan]4.[/cyan]  $5.00     [cyan]5.[/cyan]  $10.00    [cyan]6.[/cyan]  Otro\n")
    amount_choice = Prompt.ask("  [bold]Opción[/bold]", choices=["1", "2", "3", "4", "5", "6"], default="2")
    amount = {"1": 0.5, "2": 1.0, "3": 2.0, "4": 5.0, "5": 10.0}.get(amount_choice)
    if amount is None:
        amount = FloatPrompt.ask("    [dim]Monto personalizado ($)[/dim]", default=1.0)

    # Expiración
    console.print()
    console.print("  [bold]Expiración base:[/bold]")
    console.print("    [cyan]1.[/cyan]  1 min  —  Escalpado")
    console.print("    [cyan]2.[/cyan]  2 min  —  Corto plazo")
    console.print("    [cyan]3.[/cyan]  3 min  —  Normal")
    console.print("    [cyan]4.[/cyan]  5 min  —  Largo plazo\n")
    expiration = Prompt.ask("  [bold]Opción[/bold]", choices=["1", "2", "3", "4"], default="3")
    expiration = int(expiration)

    # Divisas
    console.print()
    console.print("  [bold]Divisas a analizar:[/bold]")
    show_assets_menu()
    console.print("  [dim]Ingresá los números separados por coma (ej: 1,2,3) o 'all' para todas.[/dim]\n")
    assets_input = Prompt.ask("  [bold]Divisas[/bold]", default="1,2")
    assets_input = assets_input.strip().lower()

    if assets_input in ("all", "todas", "todos"):
        assets = ALL_ASSETS[:]
    else:
        selected = set()
        for part in assets_input.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(ALL_ASSETS):
                    selected.add(ALL_ASSETS[idx])
        assets = sorted(selected) if selected else ["EURUSD-OTC", "GBPUSD-OTC"]

    # ── Resumen ──
    console.clear()
    show_header()
    console.print("[bold green]✅ Todo listo — Resumen:[/bold green]\n")

    table = Table(box=box.SIMPLE, padding=(0, 2))
    table.add_column("Opción", style="bold cyan")
    table.add_column("Valor", style="white")
    table.add_row("Cuenta", "🧪 Práctica (Demo)" if account_type == "PRACTICE" else "💰 Real")
    table.add_row("Balance", f"${balance:,.2f}")
    table.add_row("Monto/Op.", f"${amount:.2f}")
    table.add_row("Expiración", f"{expiration} min")
    table.add_row("Divisas", ", ".join(assets))

    console.print(table)
    console.print(Panel("[dim]💡 La IA ajusta la expiración según la complejidad de la señal (2-5 min)[/dim]", border_style="dim"))

    if not Confirm.ask("\n[bold yellow]¿Iniciar el bot con esta configuración?[/bold yellow]", default=True):
        console.print("[red]❌ Cancelado.[/red]")
        return

    guardar_config(email, password, account_type, balance, amount, expiration, assets)

    console.clear()
    byline = Text()
    byline.append("\n  EXNOVA ULTRA-SMART BOT v5.0\n", style="bold cyan")
    byline.append("  CASCADA H1→M15→M5→M1\n", style="cyan")
    byline.append(f"\n  Balance: ", style="white")
    byline.append(f"${balance:,.2f}", style="green")
    byline.append(f"  |  Capital: ", style="white")
    byline.append(f"${amount:.2f}", style="green")
    byline.append(f"  |  Exp: ", style="white")
    byline.append(f"{expiration}min", style="green")
    byline.append("\n" + "─" * 50 + "\n", style="dim")
    console.print(Panel(byline, border_style="cyan"))

    lanzar_bot()


def guardar_config(email, password, account_type, balance, amount, expiration, assets):
    env_lines = [
        f'EXNOVA_EMAIL={email}',
        f'EXNOVA_PASSWORD={password}',
        f'ACCOUNT_TYPE={account_type}',
        f'CAPITAL_PER_TRADE={amount}',
        f'INITIAL_BALANCE={balance}',
        f'EXPIRATION_TIME={expiration * 60}',
        f'BROKER_NAME=exnova',
        f'BROKER=exnova',
        f'DEFAULT_ASSET={assets[0] if assets else "EURUSD-OTC"}',
        f'USE_LLM=true',
        f'OPENROUTER_API_KEY=',
        f'OPENROUTER_MODEL=',
        f'NVIDIA_NIM_BRIDGE_URL=',
        f'NVIDIA_NIM_BRIDGE_API_KEY=',
        f'NVIDIA_NIM_BRIDGE_MODEL=',
        f'GITHUB_TOKEN=',
        f'GITHUB_MODEL=',
    ]
    env_dir = os.path.dirname(ENV_PATH)
    os.makedirs(env_dir, exist_ok=True)
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(env_lines) + '\n')

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        cfg = {}
    cfg['assets'] = assets
    cfg['risk'] = cfg.get('risk', {})
    cfg['risk']['position_size_pct'] = round(amount / max(balance, 1), 4)
    cfg['backtest_settings'] = cfg.get('backtest_settings', {})
    cfg['backtest_settings']['initial_balance'] = balance
    cfg['expiration_seconds'] = expiration * 60
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    os.environ['EXNOVA_EMAIL'] = email
    os.environ['EXNOVA_PASSWORD'] = password
    os.environ['ACCOUNT_TYPE'] = account_type
    os.environ['CAPITAL_PER_TRADE'] = str(amount)
    os.environ['EXPIRATION_TIME'] = str(expiration * 60)


def lanzar_bot():
    try:
        from main import main
        main()
    except KeyboardInterrupt:
        console.print("\n\n[bold red]⏹ Bot detenido por el usuario.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        run_setup()
    except KeyboardInterrupt:
        console.print("\n\n[red]Cancelado.[/red]")
        sys.exit(0)
