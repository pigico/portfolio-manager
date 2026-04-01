"""Analysis Page — LIVE candlestick, indicators, radar chart, fundamentals."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from live_data import (
    get_technical_analysis, get_fundamental_score,
    get_analyst_recommendations, get_stock_price,
)


def render() -> None:
    st.title("Asset Analysis")

    ticker = st.selectbox("Select Asset", ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "AMZN", "META", "JPM"])

    # Fetch live price
    price_data = get_stock_price(ticker)
    if price_data:
        st.metric(f"{ticker} Price", f"${price_data['price']:,.2f}",
                  f"{price_data.get('change_pct', 0):+.2f}%")

    with st.spinner(f"Analyzing {ticker} with live data..."):
        tech = get_technical_analysis(ticker)
        fund = get_fundamental_score(ticker)
        recs = get_analyst_recommendations(ticker)

    if not tech:
        st.warning(f"Insufficient historical data for {ticker}")
        return

    # Candlestick chart
    st.subheader(f"{ticker} - Price Chart (1 Year)")
    closes = tech["closes"]
    highs = tech["highs"]
    lows = tech["lows"]
    volumes = tech["volumes"]
    dates = tech["dates"]
    n = len(closes)

    # Compute overlays
    sma20 = [np.mean(closes[max(0, i-20):i+1]) for i in range(n)]
    sma50 = [np.mean(closes[max(0, i-50):i+1]) for i in range(n)]
    std20 = [np.std(closes[max(0, i-20):i+1]) if i >= 20 else 0 for i in range(n)]
    bb_upper = [m + 2*s for m, s in zip(sma20, std20)]
    bb_lower = [m - 2*s for m, s in zip(sma20, std20)]

    # RSI
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses_arr = np.where(deltas < 0, -deltas, 0)
    rsi_vals = [50] * 14
    for i in range(14, len(closes)):
        ag = np.mean(gains[max(0,i-14):i])
        al = np.mean(losses_arr[max(0,i-14):i])
        rsi_vals.append(100 - 100/(1 + ag/(al+1e-10)))

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(
        x=dates, open=[closes[i]*0.999 for i in range(n)],  # Approximate opens
        high=highs, low=lows, close=closes,
        increasing_line_color="#00D26A", decreasing_line_color="#FF4444",
        name="Price",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=sma20, mode="lines", name="SMA20",
                             line=dict(color="#FFD700", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=sma50, mode="lines", name="SMA50",
                             line=dict(color="#FF8C00", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=bb_upper, mode="lines", name="BB+",
                             line=dict(color="#666", dash="dot", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=bb_lower, mode="lines", name="BB-",
                             line=dict(color="#666", dash="dot", width=1),
                             fill="tonexty", fillcolor="rgba(100,100,100,0.1)"), row=1, col=1)

    fig.add_trace(go.Scatter(x=dates, y=rsi_vals, mode="lines", name="RSI",
                             line=dict(color="#FFD700", width=1.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#FF4444", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#00D26A", row=2, col=1)

    vol_colors = ["#00D26A" if i == 0 or closes[i] >= closes[i-1] else "#FF4444" for i in range(n)]
    fig.add_trace(go.Bar(x=dates, y=volumes, marker_color=vol_colors, name="Volume"), row=3, col=1)

    fig.update_layout(height=600, margin=dict(t=10, b=30),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="white", showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Indicators table
    st.subheader("Technical Indicators (Live)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Tech Score", f"{tech['score']}/100")
    with c2:
        st.metric("Confluence", tech["confluence"])
    with c3:
        direction_color = "#00D26A" if tech["direction"] == "BULLISH" else "#FF4444" if tech["direction"] == "BEARISH" else "#888"
        st.markdown(f"**Direction:** <span style='color:{direction_color}'>{tech['direction']}</span> ({tech['bullish']}B/{tech['bearish']}S/{tech['neutral']}N)", unsafe_allow_html=True)

    for name, signal, detail in tech["signals"]:
        sig_color = "#00D26A" if signal == "BULLISH" else "#FF4444" if signal == "BEARISH" else "#888"
        st.markdown(f"<span style='color:{sig_color}'>**{name}**</span>: {detail}", unsafe_allow_html=True)

    st.markdown("---")

    # Score breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Score Radar")
        fund_score = fund["score"] if fund else 50
        analyst_score = 50
        if recs:
            total_r = recs["strong_buy"] + recs["buy"] + recs["hold"] + recs["sell"] + recs["strong_sell"]
            if total_r > 0:
                analyst_score = int((recs["strong_buy"] + recs["buy"]) / total_r * 100)

        categories = ["Fundamental", "Technical", "Macro", "Sentiment"]
        values = [fund_score, tech["score"], 60, analyst_score]
        fig = go.Figure(go.Scatterpolar(
            r=values + [values[0]], theta=categories + [categories[0]],
            fill="toself", fillcolor="rgba(0,210,106,0.2)", line_color="#00D26A",
        ))
        fig.update_layout(polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#333"),
            angularaxis=dict(gridcolor="#333"),
        ), height=350, margin=dict(t=30, b=30),
            paper_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Fundamentals")
        if fund:
            st.write(f"**Score:** {fund['score']}/100 | **Moat:** {fund['moat']}")
            for k, v in sorted(fund["breakdown"].items(), key=lambda x: -x[1]):
                bar_pct = min(100, max(0, int(v)))
                st.progress(bar_pct, text=f"{k}: {v:.0f}")
        else:
            st.info("Fundamental data not available")

        if recs:
            st.subheader("Analyst Consensus")
            st.write(f"**{recs['strong_buy']}** Strong Buy | **{recs['buy']}** Buy | **{recs['hold']}** Hold | **{recs['sell']}** Sell")

    st.caption("Data: yfinance (OHLCV), Finnhub (analysts)")
