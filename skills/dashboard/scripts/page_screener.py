"""Screener Page — scan custom ticker lists with live scores."""

from __future__ import annotations

import streamlit as st
from live_data import (
    get_stock_price, get_crypto_price, get_technical_analysis,
    get_fundamental_score, get_analyst_recommendations,
)


DEFAULT_STOCKS = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, JPM, V, JNJ"
DEFAULT_CRYPTO = "BTC-USD, ETH-USD, SOL-USD, BNB-USD, XRP-USD, ADA-USD"
DEFAULT_ETFS = "SPY, QQQ, GLD, SLV, TLT, XLE, XLF"


def render() -> None:
    st.title("Screener")
    st.caption("Scan any list of tickers for investment opportunities")

    # Input
    tab_stocks, tab_crypto, tab_etf, tab_custom = st.tabs(
        ["Stocks", "Crypto", "ETFs/Commodities", "Custom List"]
    )

    with tab_stocks:
        stock_input = st.text_area("Stock tickers (comma-separated)", DEFAULT_STOCKS, height=68)
    with tab_crypto:
        crypto_input = st.text_area("Crypto tickers (comma-separated)", DEFAULT_CRYPTO, height=68)
        st.caption("Use Yahoo format: BTC-USD, ETH-USD, SOL-USD")
    with tab_etf:
        etf_input = st.text_area("ETF/Commodity tickers", DEFAULT_ETFS, height=68)
    with tab_custom:
        custom_input = st.text_area("Your custom list (comma-separated)", "", height=68)
        st.caption("Mix stocks, crypto, ETFs — e.g. AAPL, BTC-USD, GLD, PLTR")

    col1, col2 = st.columns([1, 3])
    with col1:
        min_score = st.number_input("Min Score", 0, 100, 0)
    with col2:
        scan_button = st.button("Scan Now", type="primary", use_container_width=True)

    if not scan_button:
        st.info("Configure your ticker list above and click 'Scan Now' to analyze.")
        return

    # Collect all tickers from active tab
    all_tickers_raw = stock_input + "," + crypto_input + "," + etf_input
    if custom_input.strip():
        all_tickers_raw = custom_input
    tickers = [t.strip().upper() for t in all_tickers_raw.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))  # Deduplicate preserving order

    if not tickers:
        st.warning("No tickers to scan.")
        return

    st.markdown("---")
    st.subheader(f"Scanning {len(tickers)} assets...")

    progress = st.progress(0)
    results = []

    for i, ticker in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Analyzing {ticker}...")

        try:
            # Get price
            is_crypto = "-USD" in ticker
            if is_crypto:
                symbol = ticker.replace("-USD", "")
                price_data = get_crypto_price(symbol)
                price = price_data["price"] if price_data else 0
                change = price_data.get("change_24h_pct", 0) if price_data else 0
            else:
                price_data = get_stock_price(ticker)
                price = price_data["price"] if price_data else 0
                change = price_data.get("change_pct", 0) if price_data else 0

            if price == 0:
                continue

            # Technical score
            tech = get_technical_analysis(ticker)
            tech_score = tech["score"] if tech else 50
            tech_direction = tech["direction"] if tech else "N/A"
            confluence = tech["confluence"] if tech else "N/A"

            # Fundamental score (stocks only)
            fund = get_fundamental_score(ticker) if not is_crypto else None
            fund_score = fund["score"] if fund else 50
            moat = fund["moat"] if fund else "-"

            # Analyst recs (stocks only)
            recs = get_analyst_recommendations(ticker) if not is_crypto else None
            analyst_pct = 50
            analyst_str = "-"
            if recs:
                total_r = recs["strong_buy"] + recs["buy"] + recs["hold"] + recs["sell"] + recs["strong_sell"]
                if total_r > 0:
                    analyst_pct = int((recs["strong_buy"] + recs["buy"]) / total_r * 100)
                    analyst_str = f"{recs['strong_buy']}SB {recs['buy']}B {recs['hold']}H {recs['sell']}S"

            # Simple composite (quick estimate)
            composite = fund_score * 0.35 + tech_score * 0.30 + 55 * 0.20 + analyst_pct * 0.15

            # Decision
            if composite >= 80:
                decision = "STRONG BUY"
            elif composite >= 65:
                decision = "BUY"
            elif composite >= 45:
                decision = "HOLD"
            elif composite >= 30:
                decision = "REDUCE"
            else:
                decision = "SELL"

            results.append({
                "Ticker": ticker,
                "Price": price,
                "Change %": round(change, 2),
                "Score": round(composite, 1),
                "Decision": decision,
                "Tech": round(tech_score, 1),
                "Fund": round(fund_score, 1),
                "Direction": tech_direction,
                "Confluence": confluence,
                "Moat": moat,
                "Analysts": analyst_str,
            })
        except Exception as e:
            st.caption(f"Skipped {ticker}: {e}")

    progress.empty()

    if not results:
        st.warning("No results found.")
        return

    # Sort by score
    results.sort(key=lambda r: r["Score"], reverse=True)

    # Filter by min score
    if min_score > 0:
        results = [r for r in results if r["Score"] >= min_score]

    # Display
    st.subheader(f"Results: {len(results)} assets")

    # Top 3 highlights
    if results:
        cols = st.columns(min(3, len(results)))
        for i, col in enumerate(cols):
            if i < len(results):
                r = results[i]
                with col:
                    color = "#00D26A" if r["Score"] >= 65 else "#FFD700" if r["Score"] >= 45 else "#FF4444"
                    st.markdown(f"### <span style='color:{color}'>{r['Ticker']}</span>", unsafe_allow_html=True)
                    st.metric("Score", f"{r['Score']}/100", r["Decision"])
                    st.caption(f"Tech: {r['Tech']} | Fund: {r['Fund']} | {r['Direction']}")

    st.markdown("---")

    # Full table
    st.dataframe(
        results,
        use_container_width=True,
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Tech": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Fund": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Change %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.caption("Data: yfinance (prices, fundamentals), Finnhub (analysts), CoinGecko (crypto)")
