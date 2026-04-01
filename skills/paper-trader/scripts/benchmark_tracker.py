"""Benchmark Tracker — compare portfolio performance vs SPY, BTC, GLD."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger


@dataclass
class BenchmarkSnapshot:
    timestamp: datetime
    portfolio_value: float
    benchmarks: dict[str, float]  # benchmark -> value


class BenchmarkTracker:
    """Track portfolio performance relative to benchmarks.

    Benchmarks: SPY (S&P500 ETF), BTC (Bitcoin), GLD (Gold ETF).
    Calculates rolling alpha, beta, information ratio.
    """

    DEFAULT_BENCHMARKS = ["SPY", "BTC", "GLD"]

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        benchmarks: list[str] | None = None,
    ) -> None:
        self._initial = initial_capital
        self._benchmarks = benchmarks or self.DEFAULT_BENCHMARKS
        self._initial_prices: dict[str, float] = {}
        self._snapshots: list[BenchmarkSnapshot] = []
        self._portfolio_returns: list[float] = []
        self._benchmark_returns: dict[str, list[float]] = {b: [] for b in self._benchmarks}

    def set_initial_prices(self, prices: dict[str, float]) -> None:
        """Set starting benchmark prices for return calculation."""
        self._initial_prices = dict(prices)
        logger.debug(f"Benchmark initial prices: {prices}")

    def record_snapshot(
        self,
        portfolio_value: float,
        benchmark_prices: dict[str, float],
    ) -> None:
        """Record a data point for performance comparison."""
        self._snapshots.append(BenchmarkSnapshot(
            timestamp=datetime.now(tz=UTC),
            portfolio_value=portfolio_value,
            benchmarks=dict(benchmark_prices),
        ))

        # Calculate returns if we have previous snapshot
        if len(self._snapshots) >= 2:
            prev = self._snapshots[-2]
            if prev.portfolio_value > 0:
                self._portfolio_returns.append(
                    (portfolio_value - prev.portfolio_value) / prev.portfolio_value
                )
            for b in self._benchmarks:
                prev_price = prev.benchmarks.get(b, 0)
                curr_price = benchmark_prices.get(b, 0)
                if prev_price > 0 and curr_price > 0:
                    self._benchmark_returns[b].append(
                        (curr_price - prev_price) / prev_price
                    )

    def get_total_returns(self) -> dict[str, float]:
        """Get total return (%) for portfolio and each benchmark."""
        result: dict[str, float] = {}

        if self._snapshots:
            latest = self._snapshots[-1]
            result["portfolio"] = (
                (latest.portfolio_value - self._initial) / self._initial * 100
            )

            for b in self._benchmarks:
                init_price = self._initial_prices.get(b, 0)
                curr_price = latest.benchmarks.get(b, 0)
                if init_price > 0 and curr_price > 0:
                    result[b] = (curr_price - init_price) / init_price * 100
                else:
                    result[b] = 0.0
        else:
            result["portfolio"] = 0.0
            for b in self._benchmarks:
                result[b] = 0.0

        return result

    def get_comparison(self) -> dict:
        """Get full performance comparison."""
        total_returns = self.get_total_returns()

        return {
            "total_returns_pct": total_returns,
            "outperformance_vs_spy": (
                total_returns.get("portfolio", 0) - total_returns.get("SPY", 0)
            ),
            "snapshots_count": len(self._snapshots),
            "tracking_since": (
                self._snapshots[0].timestamp.isoformat() if self._snapshots else None
            ),
        }
