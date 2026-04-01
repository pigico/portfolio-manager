"""Real backtest — run the full pipeline on 1 year of AAPL + BTC data."""

from __future__ import annotations

import sys
from pathlib import Path

# Add all skill paths
_root = Path(__file__).parent.parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists():
        sys.path.insert(0, str(_sp))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")


def run_backtest(ticker: str, period: str = "1y", asset_type_str: str = "stocks"):
    """Run a full backtest on real historical data."""
    import yfinance as yf
    from backtest_engine import BacktestEngine, BacktestConfig
    from scorer import AssetType
    from performance_analyzer import PerformanceAnalyzer

    print(f"\n{'='*60}")
    print(f"  BACKTEST: {ticker} ({period})")
    print(f"{'='*60}")

    # Fetch real data
    print(f"  Fetching data from yfinance...")
    data = yf.Ticker(ticker).history(period=period)
    if data.empty:
        print(f"  ERROR: No data for {ticker}")
        return None

    dates = [str(d.date()) for d in data.index]
    opens = data["Open"].tolist()
    highs = data["High"].tolist()
    lows = data["Low"].tolist()
    closes = data["Close"].tolist()
    volumes = data["Volume"].tolist()

    print(f"  Data: {len(closes)} bars | {dates[0]} -> {dates[-1]}")
    print(f"  Price: ${closes[0]:.2f} -> ${closes[-1]:.2f}")

    # Configure and run backtest
    config = BacktestConfig(
        initial_capital=100_000,
        commission_pct=0.001,
        buy_threshold=55,       # Lowered for backtest — tech-only scores hover 45-65
        sell_threshold=40,
        base_position_pct=10,
        max_position_pct=20,
        min_lookback=50,
    )

    asset_type = AssetType(asset_type_str)
    engine = BacktestEngine(config)

    print(f"  Running walk-forward backtest...")
    result = engine.run(
        asset=ticker, dates=dates,
        opens=opens, highs=highs, lows=lows,
        closes=closes, volumes=volumes,
        asset_type=asset_type,
        fundamental_score=55,  # Slightly above neutral
        macro_score=60,
        sentiment_score=50,
    )

    # Detailed performance
    analyzer = PerformanceAnalyzer()
    report = analyzer.analyze(
        equity_curve=result.equity_curve,
        benchmark_curve=result.benchmark_curve,
        daily_returns=result.daily_returns,
        trade_log=result.trade_log,
    )
    analyzer.print_report(report)

    # Trade log summary
    if result.trade_log:
        print(f"\n  Trade Log ({len(result.trade_log)} trades):")
        for t in result.trade_log[:15]:
            print(f"    {t['date']} | {t['action']:<8} | ${t['price']:>10,.2f} | "
                  f"score={t['score']:.1f} | tech={t.get('tech', 0):.1f}")
        if len(result.trade_log) > 15:
            print(f"    ... and {len(result.trade_log) - 15} more trades")
    else:
        print(f"\n  No trades generated (scores may not have crossed thresholds)")

    return result


def main():
    print("\n" + "=" * 60)
    print("  PORTFOLIO MANAGER - HISTORICAL BACKTEST")
    print("=" * 60)

    # Backtest AAPL (stocks)
    aapl_result = run_backtest("AAPL", "1y", "stocks")

    # Backtest BTC (crypto)
    btc_result = run_backtest("BTC-USD", "1y", "crypto")

    # Backtest MSFT (stocks)
    msft_result = run_backtest("MSFT", "1y", "stocks")

    # Summary comparison
    print(f"\n{'='*60}")
    print(f"  COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Asset':<10} {'Return':>10} {'B&H':>10} {'Alpha':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>7}")
    print(f"  {'-'*65}")

    for name, r in [("AAPL", aapl_result), ("BTC-USD", btc_result), ("MSFT", msft_result)]:
        if r:
            print(f"  {name:<10} {r.total_return_pct:>+9.2f}% {r.buy_hold_return_pct:>+9.2f}% "
                  f"{r.alpha_pct:>+9.2f}% {r.sharpe_ratio:>7.3f} {r.max_drawdown_pct:>7.2f}% {r.total_trades:>6}")

    print()


if __name__ == "__main__":
    main()
