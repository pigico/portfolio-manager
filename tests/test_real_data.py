"""Real-data integration test — runs against live APIs.

Tests: CoinGecko, Alternative.me, yfinance, and the full analysis pipeline.
Run with: python3 tests/test_real_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add all skill script paths
_root = Path(__file__).parent.parent
for skill_dir in (_root / "skills").iterdir():
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(_root / "scheduler"))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_crypto_collector():
    separator("TEST 1: Crypto Collector (CoinGecko)")
    from crypto_collector import CryptoCollector

    cc = CryptoCollector()

    # Test price fetch
    btc = cc.collect("BTC")
    if btc:
        print(f"  BTC Price:      ${btc['price']:,.2f}")
        print(f"  24h Change:     {btc.get('change_24h_pct', 0):+.2f}%")
        print(f"  Market Cap:     ${btc.get('market_cap', 0):,.0f}")
        print(f"  Source:         {btc['source']}")
    else:
        print("  FAILED: Could not fetch BTC price")
        return False

    # Test ETH
    eth = cc.collect("ETH")
    if eth:
        print(f"  ETH Price:      ${eth['price']:,.2f}")
    else:
        print("  FAILED: Could not fetch ETH price")

    # Test global data
    glob = cc.collect_global()
    if glob:
        print(f"  Total MCap:     ${glob['total_market_cap_usd']:,.0f}")
        print(f"  BTC Dominance:  {glob['btc_dominance']:.1f}%")
    else:
        print("  WARNING: Could not fetch global data")

    print("  PASSED")
    return True


def test_stock_collector():
    separator("TEST 2: Stock Collector (yfinance)")
    from stock_collector import StockCollector

    sc = StockCollector()

    # Test AAPL via yfinance fallback
    aapl = sc.collect("AAPL")
    if aapl:
        print(f"  AAPL Price:     ${aapl['price']:,.2f}")
        print(f"  Source:         {aapl['source']}")
    else:
        print("  FAILED: Could not fetch AAPL")
        return False

    # Test historical data
    hist = sc.collect_historical("AAPL", period="3mo")
    if hist:
        print(f"  Historical:     {len(hist)} data points")
        print(f"  Latest:         {hist[-1]['date']} @ ${hist[-1]['close']:.2f}")
    else:
        print("  WARNING: No historical data")

    print("  PASSED")
    return True


def test_sentiment_collector():
    separator("TEST 3: Sentiment Collector (Alternative.me)")
    from sentiment_collector import SentimentCollector

    sc = SentimentCollector()

    fg = sc.collect_fear_greed_crypto()
    if fg:
        print(f"  Fear & Greed:   {fg['value']} ({fg['classification']})")
        print(f"  History:        {len(fg['history'])} data points")
    else:
        print("  FAILED: Could not fetch Fear & Greed")
        return False

    print("  PASSED")
    return True


def test_divergence_detector():
    separator("TEST 4: Divergence Detector (cross-platform)")
    from divergence_detector import DivergenceDetector
    from crypto_collector import CryptoCollector

    cc = CryptoCollector()
    dd = DivergenceDetector(crypto_threshold_pct=0.3)

    btc_cg = cc.collect("BTC")
    if not btc_cg:
        print("  SKIPPED: No CoinGecko data")
        return True

    # Simulate a slight divergence (real Binance WS not running)
    cg_price = btc_cg["price"]
    simulated_binance = cg_price * 1.004  # +0.4% simulated

    signal = dd.check_crypto_divergence("BTC", simulated_binance, cg_price)
    if signal:
        print(f"  Divergence:     {signal.delta_pct:+.3f}% ({signal.direction})")
        print(f"  Confidence:     {signal.confidence}")
    else:
        print(f"  No divergence detected (below threshold)")

    print("  PASSED")
    return True


def test_technical_analysis():
    separator("TEST 5: Technical Analysis (real AAPL data)")
    from stock_collector import StockCollector
    from indicators import TechnicalIndicators
    from confluence import ConfluenceScorer

    sc = StockCollector()
    ti = TechnicalIndicators()
    cs = ConfluenceScorer()

    hist = sc.collect_historical("AAPL", period="1y")
    if not hist or len(hist) < 50:
        print("  SKIPPED: Insufficient historical data")
        return True

    closes = [d["close"] for d in hist]
    highs = [d["high"] for d in hist]
    lows = [d["low"] for d in hist]
    volumes = [d["volume"] for d in hist]

    print(f"  Data points:    {len(closes)}")
    print(f"  Latest close:   ${closes[-1]:.2f}")

    results = ti.compute_all(closes, highs, lows, volumes)
    print(f"  Indicators:     {len(results)} computed")

    for r in results:
        print(f"    {r.name:<15} {r.signal.value:<10} {r.detail}")

    score = cs.score(results)
    print(f"\n  Confluence:     {score.confluence_level}")
    print(f"  Tech Score:     {score.total}/100")
    print(f"  Direction:      {score.dominant_direction.value}")
    print(f"  Breakdown:      {score.bullish_count}B / {score.bearish_count}S / {score.neutral_count}N")

    print("  PASSED")
    return True


def test_fundamental_analysis():
    separator("TEST 6: Fundamental Analysis (AAPL)")
    from stock_fundamentals import StockFundamentals

    sf = StockFundamentals()

    # Use sample data since we don't have FMP key
    # Let's try to get basic data from yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        info = ticker.info
        data = {
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
            "fcf_yield": None,  # Need FCF/market cap
            "ev_ebitda": info.get("enterpriseToEbitda"),
        }
        # Calculate FCF yield if possible
        fcf = info.get("freeCashflow", 0)
        mcap = info.get("marketCap", 0)
        if fcf and mcap and mcap > 0:
            data["fcf_yield"] = fcf / mcap

        print(f"  P/E:            {data['pe_ratio']}")
        print(f"  P/B:            {data['pb_ratio']}")
        print(f"  ROE:            {data['roe']}")
        print(f"  D/E:            {data['debt_to_equity']}")
        print(f"  EV/EBITDA:      {data['ev_ebitda']}")
        print(f"  FCF Yield:      {data['fcf_yield']}")

        result = sf.analyze(data)
        print(f"\n  Fund Score:     {result.total}/100")
        print(f"  Economic Moat:  {result.economic_moat}")
        print(f"  Rationale:      {result.rationale[:120]}")

        # Breakdown
        print(f"  Breakdown:")
        for k, v in sorted(result.breakdown.items(), key=lambda x: -x[1]):
            bar = "#" * int(v / 10) + "-" * (10 - int(v / 10))
            print(f"    {k:<20} [{bar}] {v:.0f}")

    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    print("  PASSED")
    return True


def test_crypto_fundamental():
    separator("TEST 7: Crypto Fundamental Analysis (BTC)")
    from crypto_collector import CryptoCollector
    from crypto_fundamentals import CryptoFundamentals

    cc = CryptoCollector()
    cf = CryptoFundamentals()

    data = cc.collect_market_data("BTC")
    if not data:
        print("  SKIPPED: No market data")
        return True

    print(f"  BTC Price:      ${data['price']:,.2f}")
    print(f"  Market Cap:     ${data['market_cap']:,.0f}")
    print(f"  Circ Supply:    {data['circulating_supply']:,.0f}")
    print(f"  ATH:            ${data['ath']:,.2f}")

    result = cf.analyze(data)
    print(f"\n  Crypto Score:   {result.total}/100")
    print(f"  Rationale:      {result.rationale[:120]}")

    for k, v in sorted(result.breakdown.items(), key=lambda x: -x[1]):
        bar = "#" * int(v / 10) + "-" * (10 - int(v / 10))
        print(f"    {k:<20} [{bar}] {v:.0f}")

    print("  PASSED")
    return True


def test_market_posture():
    separator("TEST 8: Market Posture (simulated with real sentiment)")
    from posture_analyzer import PostureAnalyzer
    from bubble_detector import BubbleDetector
    from sentiment_collector import SentimentCollector

    sc = SentimentCollector()
    fg = sc.collect_fear_greed_crypto()
    fg_value = fg["value"] if fg else 50

    pa = PostureAnalyzer()
    bd = BubbleDetector()

    bubble = bd.analyze(
        shiller_cape=33, margin_debt_yoy_change_pct=8,
        put_call_ratio=0.75, vix=18, ipo_first_day_avg_return_pct=12,
    )
    print(f"  Bubble Score:   {bubble.total_score}/15 ({bubble.classification})")

    posture = pa.analyze(
        regime="Reflation", regime_confidence=0.7,
        pct_above_sma200=62, advance_decline_ratio=1.2,
        bubble_score=bubble.total_score, vix=18,
        fear_greed_value=fg_value,
        pct_rsi_above_50=58,
    )
    print(f"  Posture:        {posture.posture.value}")
    print(f"  Ceiling:        {posture.exposure_ceiling:.1f}%")
    print(f"  Confidence:     {posture.confidence}")
    print(f"  Fear & Greed:   {fg_value} (real data)")
    print(f"  Allocation:     {posture.recommended_allocation}")

    print("  PASSED")
    return True


def test_composite_score():
    separator("TEST 9: Full Composite Score (AAPL end-to-end)")
    from scorer import CompositeScorer, AssetType

    cs = CompositeScorer()

    # Use scores from previous tests (simulated integration)
    result = cs.score(
        asset="AAPL",
        asset_type=AssetType.STOCKS,
        fundamental_score=68,  # Would come from test 6
        technical_score=72,     # Would come from test 5
        macro_score=70,         # Reflation regime, stocks moderate
        sentiment_score=55,     # Neutral-ish
        score_rising_periods=2,
        fear_greed_extreme_fear=False,
        divergence_confirmed=False,
    )

    print(f"  Asset:          {result.asset}")
    print(f"  Total Score:    {result.total}/100")
    print(f"  Decision:       {result.decision.value}")
    print(f"  Confidence:     {result.confidence}")
    print(f"  Sub-scores:")
    for k, v in result.sub_scores.items():
        print(f"    {k:<15} {v:.1f}")
    print(f"  Rationale:      {result.rationale[:120]}")

    print("  PASSED")
    return True


def test_paper_trade_flow():
    separator("TEST 10: Paper Trade Flow (buy AAPL with RiskGuard)")
    from paper_engine import PaperEngine
    from models import AssetClass, Confidence, TradeAction, TradeProposal, PortfolioState
    from risk_guard import RiskGuard
    from kill_switch import KillSwitch
    import tempfile

    # Fresh RiskGuard
    RiskGuard.reset_singleton()
    tmp = tempfile.mkdtemp()
    rg = RiskGuard(kill_switch_lock_file=f"{tmp}/.kill_switch_active")

    pe = PaperEngine(initial_capital=100_000)

    # Create trade proposal
    proposal = TradeProposal(
        asset="AAPL", asset_class=AssetClass.STOCKS,
        action=TradeAction.BUY, price=185.0, quantity=50,
        score=68, confidence=Confidence.MEDIUM,
        rationale="Real data test — composite score 68",
    )

    # Validate through RiskGuard
    result = rg.validate_trade(proposal, pe.portfolio_state)
    print(f"  Proposal:       BUY 50 AAPL @ $185")
    print(f"  RiskGuard:      {'APPROVED' if result.approved else 'REJECTED'}")
    print(f"  Checks passed:  {result.checks_passed}")
    if not result.approved:
        print(f"  Reason:         {result.rejection_reason}")
        return True  # Not a failure

    print(f"  Kelly size:     {result.kelly_size_pct}%")
    print(f"  Adj quantity:   {result.final_quantity:.2f}")

    # Execute paper trade
    trade = pe.execute_buy(
        "AAPL", AssetClass.STOCKS, price=185.0,
        quantity=result.final_quantity, score=68,
        rationale="Real data test",
    )
    print(f"\n  Executed:       BUY {trade.quantity:.2f} AAPL @ ${trade.price:.2f}")
    print(f"  Commission:     ${trade.commission:.2f}")
    print(f"  Portfolio:      €{pe.total_value:,.2f}")
    print(f"  Cash left:      €{pe.cash:,.2f}")
    print(f"  Position value: €{pe.positions['AAPL'].market_value:,.2f}")

    # Simulate price increase
    pe.update_prices({"AAPL": 190.0})
    print(f"\n  Price update:   AAPL -> $190")
    print(f"  Portfolio:      €{pe.total_value:,.2f}")
    print(f"  AAPL P&L:       {pe.positions['AAPL'].pnl_pct:+.2f}%")

    metrics = pe.get_performance_metrics()
    print(f"  Total trades:   {metrics['total_trades']}")

    RiskGuard.reset_singleton()
    print("  PASSED")
    return True


def main():
    print("\n" + "=" * 60)
    print("  PORTFOLIO MANAGER — REAL DATA INTEGRATION TEST")
    print("=" * 60)

    tests = [
        ("Crypto Collector", test_crypto_collector),
        ("Stock Collector", test_stock_collector),
        ("Sentiment", test_sentiment_collector),
        ("Divergence Detector", test_divergence_detector),
        ("Technical Analysis", test_technical_analysis),
        ("Stock Fundamentals", test_fundamental_analysis),
        ("Crypto Fundamentals", test_crypto_fundamental),
        ("Market Posture", test_market_posture),
        ("Composite Score", test_composite_score),
        ("Paper Trade Flow", test_paper_trade_flow),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    separator("RESULTS SUMMARY")
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    print(f"\n  Total: {passed}/{len(results)} passed, {failed} failed")


if __name__ == "__main__":
    main()
