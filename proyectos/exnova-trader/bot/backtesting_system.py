"""
Backtesting System - Sistema de Paper Trading y Backtesting
Permite validar estrategias sin riesgo con datos histricos y en tiempo real
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from collections import defaultdict


class TradeResult(Enum):
    """Resultado de una operacin"""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    PENDING = "PENDING"


@dataclass
class BacktestTrade:
    """Operacin en backtesting"""
    id: str
    asset: str
    direction: str  # "call" o "put"
    entry_time: datetime
    entry_price: float
    amount: float
    expiration_seconds: int
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    result: TradeResult = TradeResult.PENDING
    pnl: float = 0.0
    payout_percent: float = 85.0  # Payout tpico en Exnova
    score: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class BacktestStats:
    """Estadsticas de backtesting"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    pending_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_profit: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_consecutive_wins: int = 0
    current_consecutive_losses: int = 0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    recovery_factor: float = 0.0
    avg_trade_duration: float = 0.0
    total_commissions: float = 0.0


class BacktestingSystem:
    """
    Sistema de Backtesting y Paper Trading

    Caractersticas:
    - Backtesting histrico con datos de velas
    - Paper trading en tiempo real
    - Mtricas profesionales (Sharpe, Drawdown, Recovery)
    - Anlisis por activo, hora, da
    - Exportacin de resultados
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        payout_percent: float = 85.0,
        commission_percent: float = 0.0
    ):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.peak_balance = initial_balance
        self.payout_percent = payout_percent
        self.commission_percent = commission_percent

        # Trades
        self.trades: List[BacktestTrade] = []
        self.pending_trades: List[BacktestTrade] = []

        # Estadsticas
        self.stats = BacktestStats()

        # Balance histrico para drawdown
        self.balance_history: List[Tuple[datetime, float]] = []

        # Configuracin
        self.config = {
            'default_expiration': 300,  # 5 minutos
            'min_score_to_trade': 65,
            'position_size_pct': 0.02,  # 2% por operacin
        }

    def run_backtest(
        self,
        df: pd.DataFrame,
        scoring_engine,
        asset: str = "EUR/USD",
        initial_balance: Optional[float] = None
    ) -> BacktestStats:
        """
        Ejecutar backtest con datos histricos

        Args:
            df: DataFrame con velas histricas (debe tener columnas: timestamp, open, high, low, close)
            scoring_engine: Motor de scoring para generar seales
            asset: Nombre del activo
            initial_balance: Balance inicial (opcional)

        Returns:
            BacktestStats con estadsticas completas
        """
        if initial_balance:
            self.initial_balance = initial_balance
            self.current_balance = initial_balance
            self.peak_balance = initial_balance

        self.trades = []
        self.pending_trades = []
        self.balance_history = [(df.iloc[0]['timestamp'], self.initial_balance)]

        print(f" Ejecutando backtest en {asset}...")
        print(f"  Datos: {len(df)} velas")
        print(f"  Periodo: {df['timestamp'].min()} a {df['timestamp'].max()}")
        print(f"  Balance inicial: ${self.initial_balance:.2f}")

        # Iterar sobre velas (dejando suficientes para calcular indicadores)
        for i in range(50, len(df) - 1):
            # Verificar trades pendientes
            self._check_pending_trades(df.iloc[i])

            if not self.pending_trades:  # Solo operar si no hay trades pendientes
                # Generar seal
                signal = self._generate_signal(
                    df.iloc[:i+1].copy(),
                    scoring_engine,
                    asset
                )

                if signal and signal.get('should_trade'):
                    self._execute_backtest_trade(
                        signal=signal,
                        entry_time=df.iloc[i]['timestamp'],
                        entry_price=df.iloc[i]['close'],
                        asset=asset
                    )

        # Esperar a que cierren todos los trades pendientes
        if self.pending_trades:
            last_row = df.iloc[-1]
            self._check_pending_trades(last_row, force_close=True)

        # Calcular estadsticas finales
        self._calculate_stats()

        return self.stats

    def _generate_signal(
        self,
        df: pd.DataFrame,
        scoring_engine,
        asset: str
    ) -> Optional[Dict]:
        """Generar seal de trading"""
        try:
            # Calcular scoring
            result = scoring_engine.score(
                df=df,
                current_price=df['close'].iloc[-1],
                asset=asset
            )

            if result.recommendation == "TRADE" and result.confidence >= self.config['min_score_to_trade']:
                return {
                    'signal': result.signal_type.value,
                    'score': result.total_score,
                    'confidence': result.confidence,
                    'reasons': result.reasons_to_trade,
                }

        except Exception as e:
            pass

        return None

    def _execute_backtest_trade(
        self,
        signal: Dict,
        entry_time: datetime,
        entry_price: float,
        asset: str
    ):
        """Ejecutar operacin en backtest"""
        # Calcular tamao de posicin
        position_size = self.current_balance * self.config['position_size_pct']

        # Crear trade
        trade = BacktestTrade(
            id=f"BT_{len(self.trades) + 1:04d}",
            asset=asset,
            direction="call" if signal['signal'] == "CALL" else "put",
            entry_time=entry_time,
            entry_price=entry_price,
            amount=position_size,
            expiration_seconds=self.config['default_expiration'],
            score=signal['score'],
            confidence=signal['confidence'],
            reasons=signal.get('reasons', []),
        )

        self.pending_trades.append(trade)
        print(f"   {entry_time}: {trade.direction.upper()} en {entry_price:.5f} (${position_size:.2f})")

    def _check_pending_trades(
        self,
        current_candle: pd.Series,
        force_close: bool = False
    ):
        """Verificar y cerrar trades pendientes"""
        current_time = current_candle['timestamp']
        current_price = current_candle['close']

        trades_to_remove = []

        for trade in self.pending_trades:
            # Verificar si expir
            expiry_time = trade.entry_time + timedelta(seconds=trade.expiration_seconds)

            if current_time >= expiry_time or force_close:
                # Calcular resultado
                if trade.direction == "call":
                    price_change = (current_price - trade.entry_price) / trade.entry_price
                else:
                    price_change = (trade.entry_price - current_price) / trade.entry_price

                # Determinar resultado (umbral pequeo para breakeven)
                if price_change > 0.0001:  # Gan
                    trade.result = TradeResult.WIN
                    trade.pnl = trade.amount * (self.payout_percent / 100)
                elif price_change < -0.0001:  # Perdi
                    trade.result = TradeResult.LOSS
                    trade.pnl = -trade.amount
                else:  # Breakeven
                    trade.result = TradeResult.BREAKEVEN
                    trade.pnl = 0.0

                trade.exit_time = current_time
                trade.exit_price = current_price

                # Actualizar balance
                self.current_balance += trade.pnl
                self.balance_history.append((current_time, self.current_balance))

                if self.current_balance > self.peak_balance:
                    self.peak_balance = self.current_balance

                trades_to_remove.append(trade)
                self.trades.append(trade)

                # Log
                emoji = "" if trade.result == TradeResult.WIN else "" if trade.result == TradeResult.LOSS else ""
                print(f"    {emoji} {trade.id}: {trade.result.value} | PnL: ${trade.pnl:+.2f} | Balance: ${self.current_balance:.2f}")

        # Remover trades cerrados
        for trade in trades_to_remove:
            self.pending_trades.remove(trade)

    def _calculate_stats(self):
        """Calcular estadsticas completas"""
        if not self.trades:
            return

        # Conteos bsicos
        self.stats.total_trades = len(self.trades)
        self.stats.winning_trades = sum(1 for t in self.trades if t.result == TradeResult.WIN)
        self.stats.losing_trades = sum(1 for t in self.trades if t.result == TradeResult.LOSS)
        self.stats.breakeven_trades = sum(1 for t in self.trades if t.result == TradeResult.BREAKEVEN)

        # PnL
        all_pnls = [t.pnl for t in self.trades]
        wins = [p for p in all_pnls if p > 0]
        losses = [p for p in all_pnls if p < 0]

        self.stats.total_profit = sum(wins) if wins else 0
        self.stats.total_loss = abs(sum(losses)) if losses else 0
        self.stats.net_profit = sum(all_pnls)

        # Win rate
        if self.stats.total_trades > 0:
            self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades

        # Profit factor
        if self.stats.total_loss > 0:
            self.stats.profit_factor = self.stats.total_profit / self.stats.total_loss
        else:
            self.stats.profit_factor = float('inf') if self.stats.total_profit > 0 else 0

        # Promedios
        self.stats.avg_win = np.mean(wins) if wins else 0
        self.stats.avg_loss = np.mean(losses) if losses else 0
        self.stats.max_win = max(wins) if wins else 0
        self.stats.max_loss = min(losses) if losses else 0

        # Rachas consecutivas
        self._calculate_streaks()

        # Drawdown mximo
        self._calculate_max_drawdown()

        # Sharpe ratio (simplificado)
        if all_pnls and len(all_pnls) > 1:
            returns = np.diff([self.initial_balance] + [self.initial_balance + sum(all_pnls[:i+1]) for i in range(len(all_pnls))])
            if np.std(returns) > 0:
                self.stats.sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)  # Anualizado

        # Recovery factor
        if self.stats.max_drawdown > 0:
            self.stats.recovery_factor = self.stats.net_profit / self.stats.max_drawdown

        # Duracin promedio
        durations = [
            (t.exit_time - t.entry_time).total_seconds()
            for t in self.trades
            if t.exit_time
        ]
        self.stats.avg_trade_duration = np.mean(durations) if durations else 0

    def _calculate_streaks(self):
        """Calcular rachas consecutivas"""
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in self.trades:
            if trade.result == TradeResult.WIN:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.result == TradeResult.LOSS:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        self.stats.max_consecutive_wins = max_wins
        self.stats.max_consecutive_losses = max_losses

    def _calculate_max_drawdown(self):
        """Calcular drawdown mximo"""
        if not self.balance_history:
            return

        peak = self.initial_balance
        max_dd = 0
        max_dd_percent = 0

        for time, balance in self.balance_history:
            if balance > peak:
                peak = balance

            dd = peak - balance
            dd_percent = dd / peak if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_percent = dd_percent

        self.stats.max_drawdown = max_dd
        self.stats.max_drawdown_percent = max_dd_percent

    def get_report(self) -> str:
        """Generar reporte de texto"""
        r = self.stats

        report = []
        report.append("=" * 70)
        report.append("REPORTE DE BACKTESTING")
        report.append("=" * 70)
        report.append(f"Balance Inicial: ${self.initial_balance:.2f}")
        report.append(f"Balance Final: ${self.current_balance:.2f}")
        report.append(f"PnL Neto: ${r.net_profit:+.2f} ({r.net_profit/self.initial_balance*100:+.2f}%)")
        report.append(f"Pico de Balance: ${self.peak_balance:.2f}")
        report.append("")
        report.append("ESTADSTICAS DE TRADING:")
        report.append(f"  Total Trades: {r.total_trades}")
        report.append(f"  Ganadoras: {r.winning_trades} ({r.win_rate*100:.1f}%)")
        report.append(f"  Perdedoras: {r.losing_trades}")
        report.append(f"  Breakeven: {r.breakeven_trades}")
        report.append("")
        report.append("MTRICAS DE RENDIMIENTO:")
        report.append(f"  Profit Factor: {r.profit_factor:.2f}")
        report.append(f"  Avg Win: ${r.avg_win:+.2f}")
        report.append(f"  Avg Loss: ${r.avg_loss:+.2f}")
        report.append(f"  Max Win: ${r.max_win:+.2f}")
        report.append(f"  Max Loss: ${r.max_loss:+.2f}")
        report.append("")
        report.append("RACHAS:")
        report.append(f"  Mx Victorias Consecutivas: {r.max_consecutive_wins}")
        report.append(f"  Mx Derrotas Consecutivas: {r.max_consecutive_losses}")
        report.append("")
        report.append("RIESGO:")
        report.append(f"  Max Drawdown: ${r.max_drawdown:.2f} ({r.max_drawdown_percent*100:.2f}%)")
        report.append(f"  Sharpe Ratio: {r.sharpe_ratio:.2f}")
        report.append(f"  Recovery Factor: {r.recovery_factor:.2f}")
        report.append("")
        report.append(f"  Duracin Promedio Trade: {r.avg_trade_duration:.1f}s")
        report.append("=" * 70)

        return "\n".join(report)

    def export_trades(self, filepath: str):
        """Exportar trades a CSV"""
        if not self.trades:
            print(" No hay trades para exportar")
            return

        data = []
        for trade in self.trades:
            data.append({
                'id': trade.id,
                'asset': trade.asset,
                'direction': trade.direction,
                'entry_time': trade.entry_time.isoformat(),
                'entry_price': trade.entry_price,
                'exit_time': trade.exit_time.isoformat() if trade.exit_time else '',
                'exit_price': trade.exit_price or '',
                'result': trade.result.value,
                'pnl': trade.pnl,
                'amount': trade.amount,
                'score': trade.score,
                'confidence': trade.confidence,
                'reasons': '; '.join(trade.reasons),
            })

        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        print(f" Trades exportados a {filepath}")

    def export_stats(self, filepath: str):
        """Exportar estadsticas a JSON"""
        stats_dict = {
            'initial_balance': self.initial_balance,
            'final_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'stats': {
                'total_trades': self.stats.total_trades,
                'win_rate': self.stats.win_rate,
                'profit_factor': self.stats.profit_factor,
                'net_profit': self.stats.net_profit,
                'total_profit': self.stats.total_profit,
                'total_loss': self.stats.total_loss,
                'avg_win': self.stats.avg_win,
                'avg_loss': self.stats.avg_loss,
                'max_drawdown': self.stats.max_drawdown,
                'max_drawdown_percent': self.stats.max_drawdown_percent,
                'sharpe_ratio': self.stats.sharpe_ratio,
                'recovery_factor': self.stats.recovery_factor,
            }
        }

        with open(filepath, 'w') as f:
            json.dump(stats_dict, f, indent=2)
        print(f" Estadsticas exportadas a {filepath}")


class PaperTrader(BacktestingSystem):
    """
    Paper Trader - Backtesting en tiempo real

    Opera con datos en tiempo real sin dinero real
    para validar la estrategia en condiciones reales
    """

    def __init__(self, initial_balance: float = 10000.0):
        super().__init__(initial_balance)
        self.real_time_mode = True
        self.on_trade_callback: Optional[callable] = None

    def on_trade_executed(self, callback: callable):
        """Registrar callback para cuando se ejecuta un trade"""
        self.on_trade_callback = callback

    def execute_paper_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        score: float,
        confidence: float,
        reasons: List[str] = None
    ) -> BacktestTrade:
        """
        Ejecutar operacin en papel

        Args:
            asset: Par de trading
            direction: "call" o "put"
            amount: Monto a operar
            score: Score de la seal
            confidence: Confianza de la seal
            reasons: Razones para la operacin

        Returns:
            BacktestTrade creado
        """
        trade = BacktestTrade(
            id=f"PT_{len(self.trades) + 1:04d}",
            asset=asset,
            direction=direction,
            entry_time=datetime.now(),
            entry_price=0.0,  # Se actualiza cuando se conoce el precio
            amount=amount,
            expiration_seconds=self.config['default_expiration'],
            score=score,
            confidence=confidence,
            reasons=reasons or [],
        )

        self.pending_trades.append(trade)
        print(f" PAPER TRADE: {trade.id} | {asset} | {direction.upper()} | ${amount:.2f}")

        return trade

    def update_paper_trade_result(
        self,
        trade_id: str,
        result: TradeResult,
        pnl: float,
        exit_price: float
    ):
        """Actualizar resultado de paper trade"""
        for trade in self.pending_trades:
            if trade.id == trade_id:
                trade.result = result
                trade.pnl = pnl
                trade.exit_price = exit_price
                trade.exit_time = datetime.now()

                # Mover a trades cerrados
                self.pending_trades.remove(trade)
                self.trades.append(trade)

                # Actualizar balance
                self.current_balance += pnl
                if self.current_balance > self.peak_balance:
                    self.peak_balance = self.current_balance

                self.balance_history.append((datetime.now(), self.current_balance))

                # Callback
                if self.on_trade_callback:
                    self.on_trade_callback(trade)

                print(f"  {'' if result == TradeResult.WIN else ''} {trade_id}: {result.value} | PnL: ${pnl:+.2f}")
                return True

        print(f" Trade {trade_id} no encontrado")
        return False


# Singleton
_paper_trader: Optional[PaperTrader] = None


def get_paper_trader(initial_balance: float = 10000.0) -> PaperTrader:
    """Obtener instancia singleton del Paper Trader"""
    global _paper_trader
    if _paper_trader is None:
        _paper_trader = PaperTrader(initial_balance)
    return _paper_trader
