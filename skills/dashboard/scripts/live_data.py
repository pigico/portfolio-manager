"""Live Data Loader — shared module that fetches real data for all dashboard pages.

Uses st.cache_data to avoid re-fetching on every Streamlit rerun.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add all skill paths
_root = Path(__file__).parent.parent.parent.parent
for _skill in (_root / "skills").iterdir():
    _sp = _skill / "scripts"
    if _sp.exists():
        if str(_sp) not in sys.path:
            sys.path.insert(0, str(_sp))

# Load env
from dotenv import load_dotenv
import os
load_dotenv(_root / ".env")

FRED_KEY = os.getenv("FRED_API_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
AV_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


@st.cache_data(ttl=60)  # Cache 1 min
def get_stock_price(ticker: str) -> dict | None:
    from stock_collector import StockCollector
    sc = StockCollector(alpha_vantage_key=AV_KEY)
    return sc.collect(ticker)


@st.cache_data(ttl=60)
def get_crypto_price(symbol: str) -> dict | None:
    from crypto_collector import CryptoCollector
    return CryptoCollector().collect(symbol)


@st.cache_data(ttl=60)
def get_crypto_market_data(symbol: str) -> dict | None:
    from crypto_collector import CryptoCollector
    return CryptoCollector().collect_market_data(symbol)


@st.cache_data(ttl=300)  # 5 min (historical data changes less frequently)
def get_stock_history(ticker: str, period: str = "1y") -> list[dict] | None:
    from stock_collector import StockCollector
    sc = StockCollector(alpha_vantage_key=AV_KEY)
    return sc.collect_historical(ticker, period=period)


@st.cache_data(ttl=3600)
def get_fred_series(series_id: str, limit: int = 60) -> dict | None:
    from macro_collector import MacroCollector
    mc = MacroCollector(fred_api_key=FRED_KEY)
    return mc.collect_series(series_id, limit=limit)


@st.cache_data(ttl=120)  # 2 min
def get_fear_greed() -> dict | None:
    from sentiment_collector import SentimentCollector
    return SentimentCollector().collect_fear_greed_crypto()


@st.cache_data(ttl=3600)
def get_analyst_recommendations(ticker: str) -> dict | None:
    from sentiment_collector import SentimentCollector
    sc = SentimentCollector(finnhub_key=FINNHUB_KEY)
    return sc.collect_analyst_recommendations(ticker)


@st.cache_data(ttl=3600)
def get_macro_regime() -> dict:
    """Compute live macro regime from FRED data."""
    from regime_detector import RegimeDetector

    gdp = get_fred_series("GDP", limit=12)
    cpi = get_fred_series("CPIAUCSL", limit=12)
    spread = get_fred_series("T10Y2Y", limit=1)

    rd = RegimeDetector()
    regime = rd.detect(
        gdp_observations=gdp["observations"] if gdp else None,
        cpi_observations=cpi["observations"] if cpi else None,
        yield_spread_10y2y=spread["latest_value"] if spread else None,
    )
    return {
        "regime": regime.regime,
        "confidence": regime.confidence,
        "weights": regime.recommended_weights,
    }


@st.cache_data(ttl=120)  # 2 min
def get_market_posture() -> dict:
    """Compute live market posture."""
    from posture_analyzer import PostureAnalyzer
    from bubble_detector import BubbleDetector

    vix_d = get_fred_series("VIXCLS", limit=1)
    vix = vix_d["latest_value"] if vix_d else 20

    fg = get_fear_greed()
    fg_val = fg["value"] if fg else 50

    regime_data = get_macro_regime()

    bd = BubbleDetector()
    bubble = bd.analyze(shiller_cape=33, vix=vix, put_call_ratio=0.8)

    pa = PostureAnalyzer()
    posture = pa.analyze(
        regime=regime_data["regime"],
        regime_confidence=regime_data["confidence"],
        bubble_score=bubble.total_score,
        vix=vix,
        fear_greed_value=fg_val,
        pct_above_sma200=55,
        pct_rsi_above_50=50,
    )
    return {
        "posture": posture.posture.value,
        "ceiling": posture.exposure_ceiling,
        "confidence": posture.confidence,
        "allocation": posture.recommended_allocation,
        "components": posture.components,
        "bubble_score": bubble.total_score,
        "bubble_class": bubble.classification,
        "vix": vix,
        "fear_greed": fg_val,
        "fear_greed_class": fg["classification"] if fg else "N/A",
        "regime": regime_data["regime"],
        "regime_confidence": regime_data["confidence"],
    }


@st.cache_data(ttl=120)  # 2 min
def get_technical_analysis(ticker: str) -> dict | None:
    """Run full technical analysis on a ticker."""
    from indicators import TechnicalIndicators
    from confluence import ConfluenceScorer

    hist = get_stock_history(ticker, "1y")
    if not hist or len(hist) < 50:
        return None

    closes = [d["close"] for d in hist]
    highs = [d["high"] for d in hist]
    lows = [d["low"] for d in hist]
    volumes = [d["volume"] for d in hist]

    ti = TechnicalIndicators()
    indicators = ti.compute_all(closes, highs, lows, volumes)
    score = ConfluenceScorer().score(indicators)

    return {
        "score": score.total,
        "confluence": score.confluence_level,
        "direction": score.dominant_direction.value,
        "bullish": score.bullish_count,
        "bearish": score.bearish_count,
        "neutral": score.neutral_count,
        "signals": [(i.name, i.signal.value, i.detail) for i in score.signals],
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
        "dates": [d["date"] for d in hist],
    }


@st.cache_data(ttl=3600)
def get_fundamental_score(ticker: str) -> dict | None:
    """Compute fundamental score using yfinance data."""
    from stock_fundamentals import StockFundamentals
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        data = {
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "dividend_yield": info.get("dividendYield"),
            "fcf_yield": (info.get("freeCashflow", 0) or 0) / (info.get("marketCap", 1) or 1),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
        }
        sf = StockFundamentals()
        result = sf.analyze(data)
        return {
            "score": result.total,
            "moat": result.economic_moat,
            "breakdown": result.breakdown,
            "rationale": result.rationale,
        }
    except Exception:
        return None
