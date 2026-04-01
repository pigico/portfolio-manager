"""Backtest Engine — walk-forward simulation on historical data.

No lookahead bias: at each time step, only data available up to that point
is used for scoring. Trades execute through the PaperEngine + RiskGuard pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from loguru import logger

# Add skill paths
_root = Path(__file__).parent.parent.parent.parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists():
        sys.path.insert(0, str(_sp))

from indicators import TechnicalIndicators, Signal
from confluence import ConfluenceScorer
from scorer import CompositeScorer, AssetType, Decision
from paper_engine import PaperEngine
from models import AssetClass, Confidence, TradeProposal, TradeAction
from risk_guard import RiskGuard


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001
    # Scoring weights (can be tuned)
    fundamental_weight: float = 0.35
    technical_weight: float = 0.30
    macro_weight: float = 0.20
    sentiment_weight: float = 0.15
    # Trade thresholds
    buy_threshold: float = 65.0
    strong_buy_threshold: float = 80.0
    sell_threshold: float = 30.0
    reduce_threshold: float = 45.0
    # Position sizing
    base_position_pct: float = 10.0
    max_position_pct: float = 20.0
    # Lookback for indicators
    min_lookback: int = 50


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    asset: str
    config: BacktestConfig
    start_date: str
    end_date: str
    total_return_pct: float
    buy_hold_return_pct: float
    alpha_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    equity_curve: list[float]
    benchmark_curve: list[float]
    dates: list[str]
    trade_log: list[dict]
    daily_returns: list[float]


class BacktestEngine:
    """Walk-forward backtesting engine.

    At each time step t:
    1. Compute technical indicators using data[0:t]
    2. Generate composite score (technical only for backtest, or with fixed macro/fundamental)
    3. Apply decision matrix
    4. Execute through RiskGuard + PaperEngine
    5. Record equity and trades
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        asset: str,
        dates: list[str],
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        asset_type: AssetType = AssetType.STOCKS,
        fundamental_score: float = 50.0,
        macro_score: float = 50.0,
        sentiment_score: float = 50.0,
    ) -> BacktestResult:
        """Run backtest on historical OHLCV data.

        Args:
            asset: Ticker symbol.
            dates: List of date strings.
            opens/highs/lows/closes/volumes: OHLCV arrays.
            asset_type: Asset class for weight selection.
            fundamental_score: Fixed fundamental score (or use dynamic if available).
            macro_score: Fixed macro alignment score.
            sentiment_score: Fixed sentiment score.
        """
        n = len(closes)
        if n < self.config.min_lookback:
            raise ValueError(f"Need at least {self.config.min_lookback} data points, got {n}")

        logger.info(f"Backtest: {asset} | {dates[0]} -> {dates[-1]} | {n} bars")

        # Initialize components
        RiskGuard.reset_singleton()
        import tempfile
        tmp = tempfile.mkdtemp()
        rg = RiskGuard(
            kill_switch_lock_file=f"{tmp}/.kill_switch_bt",
            max_position_pct=self.config.max_position_pct,
        )

        pe = PaperEngine(
            initial_capital=self.config.initial_capital,
            commission_pct=self.config.commission_pct,
        )

        ti = TechnicalIndicators()
        cs_indicator = ConfluenceScorer()
        scorer = CompositeScorer()

        # Tracking
        equity_curve = []
        trade_log: list[dict] = []
        daily_returns: list[float] = []
        prev_equity = self.config.initial_capital

        # Walk-forward loop
        for t in range(self.config.min_lookback, n):
            # Data available up to t (no lookahead)
            c_slice = closes[:t + 1]
            h_slice = highs[:t + 1]
            l_slice = lows[:t + 1]
            v_slice = volumes[:t + 1]
            current_price = closes[t]
            current_date = dates[t]

            # Update mark-to-market
            pe.update_prices({asset: current_price})

            # Compute technical indicators
            indicators = ti.compute_all(c_slice, h_slice, l_slice, v_slice)
            tech_result = cs_indicator.score(indicators)
            technical_score = tech_result.total

            # Composite score
            composite = scorer.score(
                asset=asset,
                asset_type=asset_type,
                fundamental_score=fundamental_score,
                technical_score=technical_score,
                macro_score=macro_score,
                sentiment_score=sentiment_score,
            )

            # Override decision using backtest-specific thresholds
            # (scorer uses hardcoded 65/80, but backtest may need different)
            score = composite.total
            if score >= self.config.strong_buy_threshold:
                bt_decision = "STRONG_BUY"
            elif score >= self.config.buy_threshold:
                bt_decision = "BUY"
            elif score < self.config.sell_threshold:
                bt_decision = "SELL"
            elif score < self.config.reduce_threshold:
                bt_decision = "REDUCE"
            else:
                bt_decision = "HOLD"

            # Decision logic
            action = self._decide_action_bt(bt_decision, asset, pe)

            if action == "BUY":
                size_pct = self.config.base_position_pct
                if bt_decision == "STRONG_BUY":
                    size_pct = min(self.config.max_position_pct, size_pct * 1.5)

                qty = (pe.total_value * size_pct / 100) / current_price
                if qty > 0:
                    proposal = TradeProposal(
                        asset=asset, asset_class=AssetClass(asset_type.value),
                        action=TradeAction.BUY, price=current_price, quantity=qty,
                        score=composite.total, confidence=Confidence.MEDIUM,
                        rationale=f"Backtest signal: {composite.decision.value}",
                    )
                    result = rg.validate_trade(proposal, pe.portfolio_state)
                    if result.approved:
                        trade = pe.execute_buy(
                            asset, AssetClass(asset_type.value),
                            current_price, result.final_quantity,
                            score=composite.total,
                        )
                        trade_log.append({
                            "date": current_date, "action": "BUY",
                            "price": current_price, "qty": result.final_quantity,
                            "score": composite.total, "tech": technical_score,
                        })

            elif action == "SELL":
                if asset in pe.positions:
                    trade = pe.execute_sell(asset, score=composite.total)
                    pnl = pe.positions.get(asset)
                    trade_log.append({
                        "date": current_date, "action": "SELL",
                        "price": current_price, "qty": trade.quantity,
                        "score": composite.total, "tech": technical_score,
                    })
                    # Record win/loss for circuit breaker
                    is_win = trade.price > 0 and trade.quantity > 0
                    rg.record_trade_result(is_win)

            elif action == "REDUCE":
                if asset in pe.positions:
                    half_qty = pe.positions[asset].quantity / 2
                    trade = pe.execute_sell(asset, quantity=half_qty, score=composite.total)
                    trade_log.append({
                        "date": current_date, "action": "REDUCE",
                        "price": current_price, "qty": half_qty,
                        "score": composite.total, "tech": technical_score,
                    })

            # Record equity
            current_equity = pe.total_value
            equity_curve.append(current_equity)

            if prev_equity > 0:
                daily_ret = (current_equity - prev_equity) / prev_equity
                daily_returns.append(daily_ret)
            prev_equity = current_equity

            # Reset daily counters periodically
            if t % 5 == 0:
                pe.reset_daily_counters()

        # Close any remaining position at end
        if asset in pe.positions:
            pe.execute_sell(asset, score=0, rationale="Backtest end — closing position")

        # Calculate metrics
        final_equity = pe.total_value
        total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital * 100
        buy_hold_return = (closes[-1] - closes[self.config.min_lookback]) / closes[self.config.min_lookback] * 100

        # Benchmark curve (buy-and-hold)
        start_price = closes[self.config.min_lookback]
        benchmark_curve = [
            self.config.initial_capital * (closes[t] / start_price)
            for t in range(self.config.min_lookback, n)
        ]

        sharpe = self._calc_sharpe(daily_returns)
        sortino = self._calc_sortino(daily_returns)
        max_dd = self._calc_max_drawdown(equity_curve)
        win_rate, profit_factor = self._calc_trade_stats(trade_log, closes)

        bt_dates = dates[self.config.min_lookback:]

        RiskGuard.reset_singleton()

        logger.info(
            f"Backtest complete: {asset} | Return: {total_return:+.2f}% | "
            f"B&H: {buy_hold_return:+.2f}% | Alpha: {total_return - buy_hold_return:+.2f}% | "
            f"Sharpe: {sharpe:.2f} | MaxDD: {max_dd:.2f}%"
        )

        return BacktestResult(
            asset=asset,
            config=self.config,
            start_date=bt_dates[0] if bt_dates else "",
            end_date=bt_dates[-1] if bt_dates else "",
            total_return_pct=round(total_return, 2),
            buy_hold_return_pct=round(buy_hold_return, 2),
            alpha_pct=round(total_return - buy_hold_return, 2),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            max_drawdown_pct=round(max_dd, 2),
            win_rate=round(win_rate, 3),
            total_trades=len(trade_log),
            profit_factor=round(profit_factor, 3),
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            dates=bt_dates,
            trade_log=trade_log,
            daily_returns=daily_returns,
        )

    def _decide_action_bt(self, decision: str, asset: str, pe: PaperEngine) -> str:
        """Map backtest decision string to trade action."""
        has_position = asset in pe.positions

        if decision in ("STRONG_BUY", "BUY") and not has_position:
            return "BUY"
        elif decision == "SELL" and has_position:
            return "SELL"
        elif decision == "REDUCE" and has_position:
            return "REDUCE"
        return "HOLD"

    def _calc_sharpe(self, returns: list[float], risk_free: float = 0.0) -> float:
        if not returns:
            return 0.0
        arr = np.array(returns)
        excess = arr - risk_free / 252
        if np.std(excess) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(excess) * np.sqrt(252))

    def _calc_sortino(self, returns: list[float], risk_free: float = 0.0) -> float:
        if not returns:
            return 0.0
        arr = np.array(returns)
        excess = arr - risk_free / 252
        downside = arr[arr < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(downside) * np.sqrt(252))

    def _calc_max_drawdown(self, equity: list[float]) -> float:
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = (val - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        return max_dd

    def _calc_trade_stats(
        self, trade_log: list[dict], closes: list[float]
    ) -> tuple[float, float]:
        """Calculate win rate and profit factor from trade pairs."""
        buys: list[dict] = []
        wins = 0
        losses = 0
        total_profit = 0.0
        total_loss = 0.0

        for t in trade_log:
            if t["action"] == "BUY":
                buys.append(t)
            elif t["action"] in ("SELL", "REDUCE") and buys:
                buy = buys.pop(0)
                pnl = (t["price"] - buy["price"]) * buy.get("qty", 1)
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                else:
                    losses += 1
                    total_loss += abs(pnl)

        total = wins + losses
        win_rate = wins / total if total > 0 else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else (
            float("inf") if total_profit > 0 else 0.0
        )
        return win_rate, profit_factor
