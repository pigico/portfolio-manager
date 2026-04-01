# Composite Scorer

Weighted scoring combining all analyzers into a single 0-100 score.

## Scripts
- `scorer.py` — Weighted composite score per asset
- `screener.py` — New opportunity discovery across universe
- `score_history.py` — Track score evolution over time

## Weights by Asset Class
| Component | Stocks | Crypto | Commodities |
|-----------|--------|--------|-------------|
| Fundamental | 35% | 25% | 25% |
| Technical | 30% | 35% | 25% |
| Macro | 20% | 20% | 30% |
| Sentiment | 15% | 20% | 20% |

## Bonuses (+5 each)
- Momentum: score rising 3+ periods
- Contrarian: Extreme Fear + Fundamentals > 60
- Divergence: cross-platform divergence confirmed

## Decision Matrix
| Score | Decision | Action |
|-------|----------|--------|
| 80-100 | STRONG_BUY | Increase position, max Kelly |
| 65-79 | BUY | Initiate/add, conservative sizing |
| 45-64 | HOLD | Monitor, tighten stops |
| 30-44 | REDUCE | Trim 50% |
| 0-29 | SELL | Exit full position |
