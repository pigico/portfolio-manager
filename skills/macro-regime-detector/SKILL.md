# Macro Regime Detector — Dalio 4-Quadrant

Detects current economic regime using FRED macro data.

## Scripts
- `regime_detector.py` — GDP/CPI trend analysis → 4-quadrant classification
- `macro_signals.py` — Yield curve, VIX spike, junk bond spread, Buffett Indicator

## Regimes
| Regime | Indicators | Favored Assets |
|--------|-----------|----------------|
| Goldilocks (GDP↑ CPI↓) | GDP rising, CPI falling | Growth stocks, Tech |
| Reflation (GDP↑ CPI↑) | GDP rising, CPI rising | Commodities, TIPS, Value |
| Deflation (GDP↓ CPI↓) | GDP falling, CPI falling | Long bonds, Defensives |
| Stagflation (GDP↓ CPI↑) | GDP falling, CPI rising | Gold, Cash, BTC |

## FRED Series
GDP, CPIAUCSL, PPIACO, FEDFUNDS, T10Y2Y, BAMLH0A0HYM2, ICSA, M2SL, ISM PMI

## Output
`MacroRegime(regime, confidence, previous_regime, transition_probability, recommended_asset_class_weights)`
