# Market Posture — RUNS FIRST

Meta-layer answering: "How much total capital should I commit NOW?"

## Scripts
- `posture_analyzer.py` — Exposure ceiling (0-100%) weighted calculation
- `breadth_analyzer.py` — McClellan Oscillator, % above SMA50/200, A/D line
- `bubble_detector.py` — Minsky/Kindleberger framework (0-15 score)

## Components & Weights
| Component | Weight | Source |
|-----------|--------|--------|
| Macro Regime Score | 25% | regime_detector.py |
| Market Breadth Health | 20% | % above SMA200, A/D ratio |
| Bubble Risk Score | 20% | CAPE, margin debt, Put/Call, VIX, IPO vol |
| Volatility Regime | 15% | VIX level + term structure |
| Sentiment Extremes | 10% | Fear & Greed (CONTRARIAN) |
| Momentum Breadth | 10% | % assets with RSI > 50 |

## Output: Exposure Ceiling
| Ceiling | Posture | Action |
|---------|---------|--------|
| 80-100% | NEW_ENTRY_ALLOWED | New investments OK |
| 50-79% | SELECTIVE_ENTRY | Only score > 75 |
| 20-49% | REDUCE_ONLY | Trim positions, no new buys |
| 0-19% | CASH_PRIORITY | Maximize cash, hedging only |
