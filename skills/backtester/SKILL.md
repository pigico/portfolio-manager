# Backtester

Historical backtesting and strategy validation.

## Scripts
- `backtest_engine.py` — Run composite scoring pipeline on historical data, simulate trades
- `weight_tuner.py` — Grid search / optimization of scoring weights and thresholds
- `override_validator.py` — Validate AI override quality on historical events
- `performance_analyzer.py` — Sharpe, Sortino, max DD, rolling alpha/beta, drawdown analysis

## Workflow
1. Load historical OHLCV + macro data
2. Walk-forward: compute scores at each time step (no lookahead)
3. Generate trade signals from decision matrix
4. Execute through paper engine with RiskGuard
5. Compare vs buy-and-hold benchmarks

## Output
- Equity curve, trade log, risk metrics
- Weight sensitivity analysis
- AI override hit rate on known events
