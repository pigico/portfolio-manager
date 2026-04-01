"""Send a live daily report to Telegram with real data from all APIs."""

import asyncio
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists():
        sys.path.insert(0, str(_sp))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")

from stock_collector import StockCollector
from crypto_collector import CryptoCollector
from macro_collector import MacroCollector
from sentiment_collector import SentimentCollector
from indicators import TechnicalIndicators
from confluence import ConfluenceScorer
from regime_detector import RegimeDetector
from posture_analyzer import PostureAnalyzer
from bubble_detector import BubbleDetector
from scorer import CompositeScorer, AssetType
from stock_fundamentals import StockFundamentals
from crypto_fundamentals import CryptoFundamentals
import yfinance as yf

print("Collecting data from all APIs...")

# Collect
sc = StockCollector(alpha_vantage_key="52G1TEAV6K9594VM")
cc = CryptoCollector()
mc = MacroCollector(fred_api_key="26b5ca6380dd335a38b153823bbf6b7b")
sent = SentimentCollector(finnhub_key="d76erh9r01qm4b7u0sd0d76erh9r01qm4b7u0sdg")

aapl = sc.collect("AAPL")
btc = cc.collect("BTC")
eth = cc.collect("ETH")

vix_d = mc.collect_series("VIXCLS", limit=1)
spread_d = mc.collect_series("T10Y2Y", limit=1)
gdp = mc.collect_series("GDP", limit=12)
cpi = mc.collect_series("CPIAUCSL", limit=12)
vix = vix_d["latest_value"] if vix_d else 20
spread_val = spread_d["latest_value"] if spread_d else 0

fg = sent.collect_fear_greed_crypto()
fg_val = fg["value"] if fg else 50
fg_class = fg["classification"] if fg else "N/A"

# Regime
rd = RegimeDetector()
regime = rd.detect(
    gdp_observations=gdp["observations"] if gdp else None,
    cpi_observations=cpi["observations"] if cpi else None,
    yield_spread_10y2y=spread_val,
)

# Posture
bd = BubbleDetector()
bubble = bd.analyze(shiller_cape=33, vix=vix, put_call_ratio=0.8)
pa = PostureAnalyzer()
posture = pa.analyze(
    regime=regime.regime, regime_confidence=regime.confidence,
    bubble_score=bubble.total_score, vix=vix,
    fear_greed_value=fg_val, pct_above_sma200=55, pct_rsi_above_50=50,
)

# AAPL analysis
hist = sc.collect_historical("AAPL", period="1y")
ti = TechnicalIndicators()
aapl_tech_score = 50.0
if hist and len(hist) > 50:
    closes = [d["close"] for d in hist]
    highs = [d["high"] for d in hist]
    lows = [d["low"] for d in hist]
    vols = [d["volume"] for d in hist]
    indicators = ti.compute_all(closes, highs, lows, vols)
    tech_result = ConfluenceScorer().score(indicators)
    aapl_tech_score = tech_result.total

info = yf.Ticker("AAPL").info
sf = StockFundamentals()
aapl_fund = sf.analyze({
    "pe_ratio": info.get("trailingPE"), "pb_ratio": info.get("priceToBook"),
    "roe": info.get("returnOnEquity"), "debt_to_equity": info.get("debtToEquity"),
    "ev_ebitda": info.get("enterpriseToEbitda"), "dividend_yield": info.get("dividendYield"),
    "fcf_yield": (info.get("freeCashflow", 0) or 0) / (info.get("marketCap", 1) or 1),
})

recs = sent.collect_analyst_recommendations("AAPL")
analyst = 50
if recs:
    total_r = recs["strong_buy"] + recs["buy"] + recs["hold"] + recs["sell"] + recs["strong_sell"]
    if total_r > 0:
        analyst = int((recs["strong_buy"] + recs["buy"]) / total_r * 100)

cs = CompositeScorer()
macro_s = 70 if regime.regime == "Goldilocks" else 50
aapl_composite = cs.score(
    "AAPL", AssetType.STOCKS,
    fundamental_score=aapl_fund.total, technical_score=aapl_tech_score,
    macro_score=macro_s, sentiment_score=analyst,
    fear_greed_extreme_fear=(fg_val < 15),
)

# BTC analysis
btc_data = cc.collect_market_data("BTC")
cf = CryptoFundamentals()
btc_fund = cf.analyze(btc_data) if btc_data else None
btc_fund_score = btc_fund.total if btc_fund else 50

btc_composite = cs.score(
    "BTC", AssetType.CRYPTO,
    fundamental_score=btc_fund_score, technical_score=50,
    macro_score=60, sentiment_score=fg_val,
    fear_greed_extreme_fear=(fg_val < 15),
)

# Analysts string
recs_str = ""
if recs:
    recs_str = f"{recs['strong_buy']}SB {recs['buy']}B {recs['hold']}H {recs['sell']}S"

# Build message
aapl_price = aapl["price"] if aapl else 0
btc_price = btc["price"] if btc else 0
eth_price = eth["price"] if eth else 0

msg = (
    f"*DAILY REPORT - 1 Apr 2026*\n\n"
    f"*Macro*\n"
    f"  Regime: {regime.regime} ({regime.confidence:.0%})\n"
    f"  VIX: {vix} | Spread: {spread_val}%\n"
    f"  Fear & Greed: {fg_val} ({fg_class})\n"
    f"  Bubble: {bubble.total_score}/15 ({bubble.classification})\n\n"
    f"*Market Posture*\n"
    f"  {posture.posture.value}\n"
    f"  Ceiling: {posture.exposure_ceiling:.0f}%\n\n"
    f"*Prices*\n"
    f"  AAPL: ${aapl_price:,.2f}\n"
    f"  BTC:  ${btc_price:,.0f}\n"
    f"  ETH:  ${eth_price:,.2f}\n\n"
    f"*Scores*\n"
    f"  AAPL: {aapl_composite.total}/100 -> {aapl_composite.decision.value}\n"
    f"    Fund={aapl_fund.total:.0f} Tech={aapl_tech_score:.0f} Macro={macro_s} Sent={analyst}\n"
    f"  BTC: {btc_composite.total}/100 -> {btc_composite.decision.value}\n"
    f"    Fund={btc_fund_score:.0f} Tech=50 Macro=60 Sent={fg_val}\n\n"
    f"*Analysts (Finnhub)*\n"
    f"  AAPL: {recs_str}"
)

print("Sending to Telegram...")

async def send():
    from telegram import Bot
    bot = Bot(token="8646805942:AAHAX1xXl2ay4xUFbaUKzBieA0IiAfa_yRQ")
    await bot.send_message(chat_id=858644168, text=msg)
    print("Daily report sent!")

asyncio.run(send())
