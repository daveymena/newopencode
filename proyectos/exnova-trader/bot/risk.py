class RiskManager:
    def __init__(self, capital_per_trade, stop_loss_pct, take_profit_pct, max_martingale_steps=3):
        self.base_capital = capital_per_trade
        self.current_trade_amount = capital_per_trade
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.wins = 0
        
        # Martingala DESHABILITADA para mayor estabilidad
        self.martingale_step = 0
        self.max_martingale_steps = 0  # 0 = Sin martingala
        self.martingale_multiplier = 2.0

    def can_trade(self, current_balance):
        """Verifica si se puede operar según las reglas de riesgo."""
        # Verificar Stop Loss diario
        if self.daily_pnl <= -(current_balance * self.stop_loss_pct):
            print(f"Stop Loss diario alcanzado: {self.daily_pnl:.2f}")
            return False
        
        # Verificar Take Profit diario
        if self.daily_pnl >= (current_balance * self.take_profit_pct):
            print(f"Take Profit diario alcanzado: {self.daily_pnl:.2f}")
            return False
            
        return True

    def update_trade_result(self, profit_amount, analysis_result=None):
        """
        Actualiza el PnL diario y ajusta el monto de la siguiente operación (Martingala).
        analysis_result: Dict del TradeAnalyzer (opcional).
        """
        self.daily_pnl += profit_amount
        self.total_trades += 1
        
        if profit_amount > 0:
            self.wins += 1
            # Ganada: Resetear Martingala
            self.reset_martingale()
        else:
            # Perdida: Evaluar Martingala
            if analysis_result and analysis_result.get("should_martingale", False):
                if self.martingale_step < self.max_martingale_steps:
                    self.martingale_step += 1
                    self.current_trade_amount = self.base_capital * (self.martingale_multiplier ** self.martingale_step)
                    print(f"⚠️ Aplicando Martingala Nivel {self.martingale_step}: ${self.current_trade_amount:.2f}")
                else:
                    print("🛑 Límite de Martingala alcanzado. Reseteando.")
                    self.reset_martingale()
            else:
                print("🚫 Martingala cancelada por análisis de riesgo.")
                self.reset_martingale()

    def reset_martingale(self):
        self.martingale_step = 0
        self.current_trade_amount = self.base_capital

    def get_trade_amount(self):
        """Devuelve el monto a invertir en la operación."""
        return self.current_trade_amount

    def reset_daily_stats(self):
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.wins = 0
        self.reset_martingale()
