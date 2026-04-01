# Risk Guard — CORE (Wraps ALL Operations)

The heart of the system. Every trade must pass through RiskGuard.

## Scripts
- `risk_guard.py` — Master gatekeeper singleton, 10-check validation pipeline
- `position_sizer.py` — Kelly Criterion (1/4 fractional), capped at 20%
- `circuit_breaker.py` — 3 losses → 1h pause, 5 → 4h, 8 → 24h
- `kill_switch.py` — Hard stop at -40% drawdown, manual reset only
- `correlation_checker.py` — Max 0.7 correlation between positions
- `models.py` — Shared data models (TradeProposal, PortfolioState, etc.)

## Validation Pipeline (in order)
1. Kill switch status
2. Circuit breaker status
3. Daily loss limit (-15%)
4. Daily trade count (max 20)
5. Position size (max 20%)
6. Asset class allocation (max 60%)
7. Cash reserve (min 5%)
8. Correlation check (< 0.7)
9. Portfolio heat vs exposure_ceiling
10. Kelly sizing calculation

## Immutable Rules
- Kill switch CANNOT be disabled programmatically
- Circuit breaker CANNOT be bypassed
- SELL trades bypass checks 3-10 but NOT kill switch or circuit breaker
