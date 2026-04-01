"""Paper Trading Engine — simulated execution with realistic friction.

All trades MUST be approved by RiskGuard before execution.
Tracks full portfolio state with mark-to-market.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

# Add risk-guard to path for imports
_rg_path = Path(__file__).parent.parent.parent / "risk-guard" / "scripts"
sys.path.insert(0, str(_rg_path))

from models import AssetClass, PortfolioState, PositionInfo


@dataclass
class PaperTrade:
    """Record of an executed paper trade."""
    trade_id: int
    asset: str
    asset_class: AssetClass
    action: str
    price: float
    quantity: float
    commission: float
    slippage: float
    net_cost: float
    score_at_time: float
    ai_override: bool
    rationale: str
    risk_guard_result: str  # "approved" or rejection reason
    portfolio_value_after: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class PaperEngine:
    """Simulated trading engine with commissions and slippage.

    Config:
    - Commission: 0.1% per trade
    - Slippage: 0.05% stocks, 0.10% crypto, 0.02% commodities
    - All trades must pass RiskGuard
    """

    SLIPPAGE = {
        AssetClass.STOCKS: 0.0005,
        AssetClass.CRYPTO: 0.0010,
        AssetClass.COMMODITIES: 0.0002,
    }

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_pct: float = 0.001,
    ) -> None:
        self._commission_pct = commission_pct
        self._trade_counter = 0

        # Portfolio state
        self.cash = initial_capital
        self.positions: dict[str, PositionInfo] = {}
        self.peak_value = initial_capital
        self.daily_start_value = initial_capital
        self.daily_trades = 0
        self.daily_new_positions = 0
        self._trades: list[PaperTrade] = []

    @property
    def total_value(self) -> float:
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    @property
    def portfolio_state(self) -> PortfolioState:
        return PortfolioState(
            total_value=self.total_value,
            cash=self.cash,
            positions=dict(self.positions),
            peak_value=self.peak_value,
            daily_start_value=self.daily_start_value,
            daily_trades=self.daily_trades,
            daily_new_positions=self.daily_new_positions,
        )

    @property
    def trades(self) -> list[PaperTrade]:
        return list(self._trades)

    def execute_buy(
        self,
        asset: str,
        asset_class: AssetClass,
        price: float,
        quantity: float,
        score: float = 0,
        ai_override: bool = False,
        rationale: str = "",
    ) -> PaperTrade:
        """Execute a paper BUY order with slippage and commission.

        Returns the trade record.
        """
        slippage_pct = self.SLIPPAGE.get(asset_class, 0.0005)
        exec_price = price * (1 + slippage_pct)  # Buy at slightly higher
        commission = exec_price * quantity * self._commission_pct
        total_cost = exec_price * quantity + commission

        if total_cost > self.cash:
            # Adjust quantity to fit available cash
            max_affordable = self.cash / (exec_price * (1 + self._commission_pct))
            quantity = max(0, max_affordable)
            total_cost = exec_price * quantity + exec_price * quantity * self._commission_pct
            commission = exec_price * quantity * self._commission_pct

        if quantity <= 0:
            logger.warning(f"Cannot buy {asset}: insufficient cash.")
            return self._make_trade(
                asset, asset_class, "BUY", price, 0, 0, 0, 0,
                score, ai_override, rationale, "rejected: no cash",
            )

        self.cash -= total_cost

        # Update or create position
        if asset in self.positions:
            pos = self.positions[asset]
            total_qty = pos.quantity + quantity
            avg_price = (pos.entry_price * pos.quantity + exec_price * quantity) / total_qty
            pos.quantity = total_qty
            pos.entry_price = avg_price
            pos.current_price = exec_price
            pos.peak_price = max(pos.peak_price, exec_price)
        else:
            self.positions[asset] = PositionInfo(
                asset=asset, asset_class=asset_class,
                quantity=quantity, entry_price=exec_price,
                current_price=exec_price, peak_price=exec_price,
            )
            self.daily_new_positions += 1

        self.daily_trades += 1
        self._update_peak()

        trade = self._make_trade(
            asset, asset_class, "BUY", exec_price, quantity,
            commission, slippage_pct * price * quantity,
            total_cost, score, ai_override, rationale, "approved",
        )
        logger.info(
            f"PAPER BUY: {quantity:.4f} {asset} @ {exec_price:.2f} "
            f"(cost={total_cost:.2f}, commission={commission:.2f})"
        )
        return trade

    def execute_sell(
        self,
        asset: str,
        quantity: float | None = None,
        score: float = 0,
        ai_override: bool = False,
        rationale: str = "",
    ) -> PaperTrade:
        """Execute a paper SELL order. None quantity = sell all."""
        if asset not in self.positions:
            logger.warning(f"Cannot sell {asset}: no position.")
            return self._make_trade(
                asset, AssetClass.STOCKS, "SELL", 0, 0, 0, 0, 0,
                score, ai_override, rationale, "rejected: no position",
            )

        pos = self.positions[asset]
        sell_qty = quantity if quantity is not None else pos.quantity
        sell_qty = min(sell_qty, pos.quantity)

        slippage_pct = self.SLIPPAGE.get(pos.asset_class, 0.0005)
        exec_price = pos.current_price * (1 - slippage_pct)  # Sell at slightly lower
        commission = exec_price * sell_qty * self._commission_pct
        proceeds = exec_price * sell_qty - commission

        self.cash += proceeds

        if sell_qty >= pos.quantity:
            del self.positions[asset]
        else:
            pos.quantity -= sell_qty

        self.daily_trades += 1
        self._update_peak()

        trade = self._make_trade(
            asset, pos.asset_class, "SELL", exec_price, sell_qty,
            commission, slippage_pct * pos.current_price * sell_qty,
            proceeds, score, ai_override, rationale, "approved",
        )
        logger.info(
            f"PAPER SELL: {sell_qty:.4f} {asset} @ {exec_price:.2f} "
            f"(proceeds={proceeds:.2f})"
        )
        return trade

    def update_prices(self, prices: dict[str, float]) -> None:
        """Mark-to-market all positions with latest prices."""
        for asset, price in prices.items():
            if asset in self.positions:
                pos = self.positions[asset]
                pos.current_price = price
                pos.peak_price = max(pos.peak_price, price)
        self._update_peak()

    def reset_daily_counters(self) -> None:
        """Reset daily counters (called at start of each trading day)."""
        self.daily_start_value = self.total_value
        self.daily_trades = 0
        self.daily_new_positions = 0

    def close_all_positions(self) -> list[PaperTrade]:
        """Close all positions (used by kill switch)."""
        trades = []
        for asset in list(self.positions.keys()):
            trade = self.execute_sell(asset, rationale="KILL SWITCH — closing all positions")
            trades.append(trade)
        return trades

    def get_performance_metrics(self) -> dict:
        """Calculate key performance metrics."""
        if not self._trades:
            return {"total_trades": 0}

        buy_trades = [t for t in self._trades if t.action == "BUY" and t.quantity > 0]
        sell_trades = [t for t in self._trades if t.action == "SELL" and t.quantity > 0]

        # Simple PnL per closed position
        wins = 0
        losses = 0
        total_pnl = 0.0

        for sell in sell_trades:
            # Find matching buy
            for buy in buy_trades:
                if buy.asset == sell.asset:
                    pnl = (sell.price - buy.price) * sell.quantity
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1
                    break

        total_closed = wins + losses
        win_rate = wins / total_closed if total_closed > 0 else 0

        return {
            "total_value": self.total_value,
            "cash": self.cash,
            "positions_count": len(self.positions),
            "total_trades": len(self._trades),
            "drawdown_pct": self.portfolio_state.drawdown_pct,
            "win_rate": round(win_rate, 3),
            "wins": wins,
            "losses": losses,
            "daily_pnl_pct": self.portfolio_state.daily_pnl_pct,
        }

    def _update_peak(self) -> None:
        tv = self.total_value
        if tv > self.peak_value:
            self.peak_value = tv

    def _make_trade(
        self, asset, asset_class, action, price, quantity,
        commission, slippage, net_cost, score, ai_override, rationale, rg_result,
    ) -> PaperTrade:
        self._trade_counter += 1
        trade = PaperTrade(
            trade_id=self._trade_counter,
            asset=asset, asset_class=asset_class, action=action,
            price=price, quantity=quantity, commission=commission,
            slippage=slippage, net_cost=net_cost, score_at_time=score,
            ai_override=ai_override, rationale=rationale,
            risk_guard_result=rg_result,
            portfolio_value_after=self.total_value,
        )
        self._trades.append(trade)
        return trade
