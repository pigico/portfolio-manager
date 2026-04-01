"""Tests for Sprint 5 — Backtesting engine, weight tuner, performance analyzer."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Add paths
_root = Path(__file__).parent.parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists():
        sys.path.insert(0, str(_sp))

from backtest_engine import BacktestEngine, BacktestConfig
from performance_analyzer import PerformanceAnalyzer
from scorer import AssetType


def _make_synthetic_data(n=200, trend=0.001, volatility=0.02, seed=42):
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(seed)
    returns = np.random.normal(trend, volatility, n)
    closes = [100.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    closes = closes[1:]
    highs = [c * (1 + abs(np.random.normal(0, 0.005))) for c in closes]
    lows = [c * (1 - abs(np.random.normal(0, 0.005))) for c in closes]
    opens = [c * (1 + np.random.normal(0, 0.003)) for c in closes]
    volumes = [int(np.random.uniform(1e6, 5e6)) for _ in closes]
    dates = [f"2025-{(i // 30 + 1):02d}-{(i % 28 + 1):02d}" for i in range(n)]
    return dates, opens, highs, lows, closes, volumes


class TestBacktestEngine:
    def test_runs_on_synthetic_data(self):
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(200)
        engine = BacktestEngine(BacktestConfig(
            buy_threshold=55, sell_threshold=40, min_lookback=50,
        ))
        result = engine.run(
            "TEST", dates, opens, highs, lows, closes, volumes,
            fundamental_score=60, macro_score=60, sentiment_score=55,
        )
        assert result.asset == "TEST"
        assert result.start_date != ""
        assert len(result.equity_curve) > 0
        assert len(result.benchmark_curve) > 0
        assert len(result.dates) > 0

    def test_generates_trades(self):
        # Uptrending data should generate at least some buys
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(
            200, trend=0.003, volatility=0.015,
        )
        engine = BacktestEngine(BacktestConfig(
            buy_threshold=52, sell_threshold=45, min_lookback=50,
        ))
        result = engine.run(
            "UPTREND", dates, opens, highs, lows, closes, volumes,
            fundamental_score=60, macro_score=65, sentiment_score=55,
        )
        # Should have at least 1 trade in a strong uptrend
        assert result.total_trades >= 1

    def test_equity_curve_starts_at_initial_capital(self):
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(100)
        config = BacktestConfig(initial_capital=50000, min_lookback=30, buy_threshold=55)
        engine = BacktestEngine(config)
        result = engine.run(
            "TEST", dates, opens, highs, lows, closes, volumes,
            fundamental_score=55, macro_score=55, sentiment_score=50,
        )
        if result.equity_curve:
            assert abs(result.equity_curve[0] - 50000) < 1000

    def test_insufficient_data_raises(self):
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(20)
        engine = BacktestEngine(BacktestConfig(min_lookback=50))
        with pytest.raises(ValueError, match="at least 50"):
            engine.run("TEST", dates, opens, highs, lows, closes, volumes)

    def test_benchmark_curve_matches_buy_hold(self):
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(150)
        engine = BacktestEngine(BacktestConfig(min_lookback=50))
        result = engine.run("TEST", dates, opens, highs, lows, closes, volumes)
        assert len(result.benchmark_curve) == len(result.equity_curve)
        # Benchmark start should be ~initial capital
        assert abs(result.benchmark_curve[0] - 100000) < 5000


class TestPerformanceAnalyzer:
    def test_analyze_positive_returns(self):
        pa = PerformanceAnalyzer()
        equity = [100000 + i * 100 for i in range(200)]
        daily_rets = [0.001] * 199
        report = pa.analyze(equity, equity, daily_rets, [])
        assert report.total_return_pct > 0
        assert report.sharpe_ratio > 0
        assert report.max_drawdown_pct == 0  # No drawdown in monotonic rise

    def test_analyze_with_drawdown(self):
        pa = PerformanceAnalyzer()
        equity = list(range(100000, 110000, 100)) + list(range(110000, 100000, -100))
        daily_rets = [0.001] * 100 + [-0.001] * 100
        report = pa.analyze(equity, equity, daily_rets, [])
        assert report.max_drawdown_pct < 0

    def test_analyze_empty(self):
        pa = PerformanceAnalyzer()
        report = pa.analyze([], [], [], [])
        assert report.total_return_pct == 0

    def test_trade_stats(self):
        pa = PerformanceAnalyzer()
        trade_log = [
            {"action": "BUY", "price": 100, "qty": 10, "date": "2025-01-01"},
            {"action": "SELL", "price": 110, "qty": 10, "date": "2025-02-01"},
            {"action": "BUY", "price": 105, "qty": 10, "date": "2025-03-01"},
            {"action": "SELL", "price": 95, "qty": 10, "date": "2025-04-01"},
        ]
        equity = [100000] * 100
        daily_rets = [0] * 99
        report = pa.analyze(equity, equity, daily_rets, trade_log)
        assert report.win_rate == 0.5
        assert report.avg_win_pct > 0
        assert report.avg_loss_pct < 0

    def test_print_report(self):
        pa = PerformanceAnalyzer()
        equity = [100000 + i * 50 for i in range(100)]
        report = pa.analyze(equity, equity, [0.0005] * 99, [])
        text = pa.print_report(report)
        assert "PERFORMANCE REPORT" in text
        assert "Sharpe" in text


class TestWeightTuner:
    def test_tuner_runs(self):
        from weight_tuner import WeightTuner
        dates, opens, highs, lows, closes, volumes = _make_synthetic_data(150)

        tuner = WeightTuner()
        result = tuner.tune(
            "TEST", dates, opens, highs, lows, closes, volumes,
            fundamental_range=[0.30, 0.40],
            technical_range=[0.30],
            buy_threshold_range=[55],
            sell_threshold_range=[40],
        )
        assert result.iterations >= 2
        assert result.best_config is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
