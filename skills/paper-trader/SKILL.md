# Paper Trader

Simulated execution engine with full audit trail.

## Scripts
- `paper_engine.py` — Simulated execution, mark-to-market
- `trade_log.py` — Full audit trail for every trade
- `benchmark_tracker.py` — Compare performance vs SPY, BTC, GLD

## Configuration
- Initial capital: €100,000 (configurable)
- Commission: 0.1% per trade
- Slippage: 0.05% stocks, 0.10% crypto, 0.02% commodities

## Metrics
Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor, Avg Win/Loss, Calmar Ratio

## Rules
- Executes ONLY trades approved by RiskGuard
- Mark-to-market using WebSocket prices (real-time)
- Full audit trail: timestamp, asset, action, price, qty, score, AI override, rationale
