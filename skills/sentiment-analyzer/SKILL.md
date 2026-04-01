# Sentiment Analyzer

Sentiment and alternative data analysis.

## Scripts
- `news_sentiment.py` — Finnhub NLP sentiment per ticker
- `fear_greed.py` — Alternative.me (crypto) + CNN style (stocks)
- `prediction_market_sentiment.py` — Polymarket implied probabilities as signal

## Signals
- News NLP: bullish/bearish per ticker
- Fear & Greed: CONTRARIAN (extreme fear = buy, extreme greed = sell)
- 13F Flows: smart money tracking (45-day lag)
- Insider Trading: cluster buying = bullish
- Short Interest: >20% = squeeze potential
- Prediction Markets: divergence >10% from model = high-value signal

## Output
`SentimentScore(total=0-100, breakdown=dict, contrarian_signal=bool)`
