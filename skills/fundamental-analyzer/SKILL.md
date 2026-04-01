# Fundamental Analyzer

Buffett/Munger/Graham style fundamental analysis per asset class.

## Scripts
- `stock_fundamentals.py` — 12 indicators → score 0-100
- `crypto_fundamentals.py` — On-chain + network metrics → score 0-100
- `commodity_fundamentals.py` — Futures curve, seasonals, USD correlation

## Stock Indicators (weighted)
P/E (12%), Shiller CAPE (8%), P/B (8%), P/S (5%), EV/EBITDA (8%), ROE (10%), ROIC (10%), FCF Yield (12%), D/E (8%), EPS Growth 5yr (10%), Dividend (5%), Piotroski F-Score (4%)

## Crypto Indicators
NVT, MVRV, Active Addresses, Hash Rate, TVL, Supply on Exchanges, Stablecoin Supply Ratio, Stock-to-Flow (BTC)

## Output
`FundamentalScore(total=0-100, breakdown=dict, economic_moat=str, rationale=str)`
