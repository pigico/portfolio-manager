"""Performance Analyzer — detailed metrics and risk analysis for backtest results."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from loguru import logger


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis."""
    # Returns
    total_return_pct: float
    annualized_return_pct: float
    buy_hold_return_pct: float
    alpha_pct: float
    # Risk
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_days: int
    volatility_annual_pct: float
    downside_deviation_pct: float
    var_95_pct: float
    # Trading
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    avg_holding_days: float
    # Consistency
    positive_months_pct: float
    best_month_pct: float
    worst_month_pct: float


class PerformanceAnalyzer:
    """Analyze backtest results in depth."""

    def analyze(
        self,
        equity_curve: list[float],
        benchmark_curve: list[float],
        daily_returns: list[float],
        trade_log: list[dict],
        trading_days: int = 252,
    ) -> PerformanceReport:
        """Generate comprehensive performance report."""
        if not equity_curve or not daily_returns:
            return self._empty_report()

        arr = np.array(daily_returns)
        eq = np.array(equity_curve)

        # Returns
        total_return = (eq[-1] - eq[0]) / eq[0] * 100
        years = len(daily_returns) / trading_days
        ann_return = ((1 + total_return / 100) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0

        bh_return = 0.0
        if benchmark_curve:
            bh_return = (benchmark_curve[-1] - benchmark_curve[0]) / benchmark_curve[0] * 100

        # Volatility
        vol = float(np.std(arr) * np.sqrt(trading_days) * 100) if len(arr) > 1 else 0

        # Downside deviation
        neg = arr[arr < 0]
        downside_dev = float(np.std(neg) * np.sqrt(trading_days) * 100) if len(neg) > 0 else 0

        # Sharpe / Sortino / Calmar
        sharpe = float(np.mean(arr) / np.std(arr) * np.sqrt(trading_days)) if np.std(arr) > 0 else 0
        sortino = float(np.mean(arr) / np.std(neg) * np.sqrt(trading_days)) if len(neg) > 0 and np.std(neg) > 0 else 0

        max_dd, max_dd_dur = self._max_drawdown_with_duration(eq)
        calmar = ann_return / abs(max_dd) if max_dd != 0 else 0

        # VaR 95%
        var_95 = float(np.percentile(arr, 5) * 100) if len(arr) > 20 else 0

        # Trade statistics
        win_rate, pf, avg_win, avg_loss, best, worst = self._trade_stats(trade_log)

        # Monthly returns
        pos_months, best_month, worst_month = self._monthly_stats(daily_returns, trading_days)

        return PerformanceReport(
            total_return_pct=round(total_return, 2),
            annualized_return_pct=round(ann_return, 2),
            buy_hold_return_pct=round(bh_return, 2),
            alpha_pct=round(total_return - bh_return, 2),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            calmar_ratio=round(calmar, 3),
            max_drawdown_pct=round(max_dd, 2),
            max_drawdown_duration_days=max_dd_dur,
            volatility_annual_pct=round(vol, 2),
            downside_deviation_pct=round(downside_dev, 2),
            var_95_pct=round(var_95, 3),
            total_trades=len(trade_log),
            win_rate=round(win_rate, 3),
            profit_factor=round(pf, 3),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            best_trade_pct=round(best, 2),
            worst_trade_pct=round(worst, 2),
            avg_holding_days=0,  # Would need entry/exit dates
            positive_months_pct=round(pos_months, 1),
            best_month_pct=round(best_month, 2),
            worst_month_pct=round(worst_month, 2),
        )

    def _max_drawdown_with_duration(self, equity: np.ndarray) -> tuple[float, int]:
        peak = equity[0]
        max_dd = 0.0
        dd_start = 0
        max_dur = 0
        cur_dur = 0

        for i, val in enumerate(equity):
            if val > peak:
                peak = val
                cur_dur = 0
            else:
                cur_dur += 1
            dd = (val - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
                max_dur = max(max_dur, cur_dur)

        return max_dd, max_dur

    def _trade_stats(self, trade_log: list[dict]) -> tuple[float, float, float, float, float, float]:
        buys = []
        pnls = []
        for t in trade_log:
            if t["action"] == "BUY":
                buys.append(t)
            elif t["action"] in ("SELL", "REDUCE") and buys:
                buy = buys.pop(0)
                pnl_pct = (t["price"] - buy["price"]) / buy["price"] * 100
                pnls.append(pnl_pct)

        if not pnls:
            return 0, 0, 0, 0, 0, 0

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls)
        avg_win = float(np.mean(wins)) if wins else 0
        avg_loss = float(np.mean(losses)) if losses else 0
        total_win = sum(wins)
        total_loss = abs(sum(losses))
        pf = total_win / total_loss if total_loss > 0 else (float("inf") if total_win > 0 else 0)
        best = max(pnls) if pnls else 0
        worst = min(pnls) if pnls else 0
        return win_rate, pf, avg_win, avg_loss, best, worst

    def _monthly_stats(self, daily_returns: list[float], td: int) -> tuple[float, float, float]:
        if len(daily_returns) < 20:
            return 0, 0, 0
        # Approximate monthly returns (21 trading days)
        monthly = []
        for i in range(0, len(daily_returns) - 20, 21):
            chunk = daily_returns[i:i + 21]
            monthly_ret = (np.prod([1 + r for r in chunk]) - 1) * 100
            monthly.append(monthly_ret)
        if not monthly:
            return 0, 0, 0
        pos = sum(1 for m in monthly if m > 0) / len(monthly) * 100
        return pos, max(monthly), min(monthly)

    def _empty_report(self) -> PerformanceReport:
        return PerformanceReport(
            total_return_pct=0, annualized_return_pct=0, buy_hold_return_pct=0,
            alpha_pct=0, sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
            max_drawdown_pct=0, max_drawdown_duration_days=0,
            volatility_annual_pct=0, downside_deviation_pct=0, var_95_pct=0,
            total_trades=0, win_rate=0, profit_factor=0,
            avg_win_pct=0, avg_loss_pct=0, best_trade_pct=0, worst_trade_pct=0,
            avg_holding_days=0, positive_months_pct=0, best_month_pct=0, worst_month_pct=0,
        )

    def print_report(self, report: PerformanceReport) -> str:
        """Format report as readable text."""
        lines = [
            "=" * 50,
            "  PERFORMANCE REPORT",
            "=" * 50,
            f"  Total Return:      {report.total_return_pct:+.2f}%",
            f"  Annualized:        {report.annualized_return_pct:+.2f}%",
            f"  Buy & Hold:        {report.buy_hold_return_pct:+.2f}%",
            f"  Alpha:             {report.alpha_pct:+.2f}%",
            "",
            f"  Sharpe Ratio:      {report.sharpe_ratio:.3f}",
            f"  Sortino Ratio:     {report.sortino_ratio:.3f}",
            f"  Calmar Ratio:      {report.calmar_ratio:.3f}",
            f"  Max Drawdown:      {report.max_drawdown_pct:.2f}%",
            f"  DD Duration:       {report.max_drawdown_duration_days} days",
            f"  Annual Vol:        {report.volatility_annual_pct:.2f}%",
            f"  VaR(95%):          {report.var_95_pct:.3f}%",
            "",
            f"  Total Trades:      {report.total_trades}",
            f"  Win Rate:          {report.win_rate:.1%}",
            f"  Profit Factor:     {report.profit_factor:.3f}",
            f"  Avg Win:           {report.avg_win_pct:+.2f}%",
            f"  Avg Loss:          {report.avg_loss_pct:+.2f}%",
            f"  Best Trade:        {report.best_trade_pct:+.2f}%",
            f"  Worst Trade:       {report.worst_trade_pct:+.2f}%",
            "",
            f"  Positive Months:   {report.positive_months_pct:.0f}%",
            f"  Best Month:        {report.best_month_pct:+.2f}%",
            f"  Worst Month:       {report.worst_month_pct:+.2f}%",
            "=" * 50,
        ]
        text = "\n".join(lines)
        print(text)
        return text
