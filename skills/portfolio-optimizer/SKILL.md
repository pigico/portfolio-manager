# Portfolio Optimizer

Portfolio optimization and trigger-based rebalancing.

## Scripts
- `optimizer.py` — MVO, HRP, Black-Litterman via PyPortfolioOpt
- `rebalancer.py` — 9 trigger conditions for rebalancing

## Optimization Methods
- Mean-Variance: efficient frontier
- Hierarchical Risk Parity (HRP): robust allocation
- Black-Litterman: incorporates views from composite scorer
- Min Volatility: for REDUCE_ONLY or CASH_PRIORITY regimes

## Rebalancing Triggers
1. Drift > 5% from target
2. Score drops below 30 or new asset enters 80+
3. Macro regime change
4. Market posture change
5. Technical trigger (Death Cross, RSI >80 sustained)
6. Cross-platform divergence
7. AI override trigger
8. Risk trigger (drawdown >-10%, position loss >-15%)
9. Calendar (monthly, quarterly)

All rebalancing operations pass through RiskGuard.
