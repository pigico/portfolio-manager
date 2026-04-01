# Data Collectors

Event-driven data collection layer. WebSocket-first, REST fallback.

## Scripts
- `websocket_manager.py` — Async WebSocket for Binance + Finnhub
- `base_collector.py` — ABC with retry, rate limiting, caching, fallback chain
- `stock_collector.py` — Alpha Vantage → FMP → yfinance fallback
- `crypto_collector.py` — Binance WS (real-time) + CoinGecko (enrichment)
- `commodity_collector.py` — Alpha Vantage + Twelve Data
- `macro_collector.py` — FRED API (GDP, CPI, PPI, Fed Funds, T10Y2Y, etc.)
- `sentiment_collector.py` — Finnhub news + Alternative.me Fear&Greed
- `polymarket_collector.py` — Prediction market contract prices → implied probabilities
- `divergence_detector.py` — Cross-platform price divergence detection

## Data Sources
| Source | Type | Free Tier |
|--------|------|-----------|
| Binance WS | WebSocket | Unlimited |
| Finnhub WS | WebSocket | Free with key |
| Alpha Vantage | REST | 25 calls/day |
| FMP | REST | 250 calls/day |
| yfinance | REST | Unofficial, no key |
| CoinGecko | REST | 30 calls/min |
| FRED | REST | Unlimited |
| Twelve Data | REST | 800 calls/day |
| Alternative.me | REST | Unlimited |
| Polymarket | REST/WS | Unlimited |

## Caching TTL
- Prices: 5 min
- Fundamentals: 1 hour
- Macro data: 24 hours
