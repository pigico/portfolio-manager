# Technical Analyzer

Quantitative technical analysis with confluence scoring.

## Scripts
- `indicators.py` — RSI, MACD, BB, SMA, EMA, ADX, OBV, ATR, Stochastic, Ichimoku, VWAP
- `patterns.py` — Chart pattern detection
- `confluence.py` — Multi-indicator alignment scoring

## Confluence Scoring
- 1 aligned = +1 (weak)
- 2-3 aligned = +3 (moderate)
- 4+ aligned = +5 (strong)
- MACD + RSI + BB aligned = +8 (high-confidence)

## Output
`TechnicalScore(total=0-100, confluence_level=str, dominant_signals=list, chart_data=dict)`
