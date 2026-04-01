"""Market Posture Page — LIVE data from FRED, CoinGecko, Alternative.me."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from live_data import get_market_posture, get_crypto_price, get_stock_price


def render() -> None:
    st.title("Market Posture")
    st.caption("Live data - How much capital should be deployed NOW?")

    with st.spinner("Loading live data from FRED, CoinGecko, Finnhub..."):
        data = get_market_posture()

    posture = data["posture"]
    ceiling = data["ceiling"]
    regime = data["regime"]
    confidence = data["confidence"]
    vix = data["vix"]
    fg = data["fear_greed"]
    fg_class = data["fear_greed_class"]
    allocation = data["allocation"]
    components = data["components"]
    bubble_score = data["bubble_score"]
    bubble_class = data["bubble_class"]

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    _colors = {
        "NEW_ENTRY_ALLOWED": "#00D26A", "SELECTIVE_ENTRY": "#FFD700",
        "REDUCE_ONLY": "#FF8C00", "CASH_PRIORITY": "#FF4444",
    }
    with c1:
        color = _colors.get(posture, "#888")
        st.markdown(f"### <span style='color:{color}'>{posture.replace('_', ' ')}</span>",
                    unsafe_allow_html=True)
        st.caption("Current Posture")
    with c2:
        st.metric("Exposure Ceiling", f"{ceiling:.0f}%")
    with c3:
        st.metric("Macro Regime", regime, f"{confidence} conf")
    with c4:
        st.metric("VIX", f"{vix:.1f}", "Elevated" if vix > 25 else "Normal")

    # Second row
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        fg_color = "#FF4444" if fg < 25 else "#FFD700" if fg < 50 else "#00D26A"
        st.metric("Fear & Greed", f"{fg}", fg_class)
    with c6:
        st.metric("Bubble Risk", f"{bubble_score}/15", bubble_class)
    with c7:
        btc = get_crypto_price("BTC")
        if btc:
            st.metric("BTC", f"${btc['price']:,.0f}", f"{btc.get('change_24h_pct', 0):+.1f}%")
    with c8:
        eth = get_crypto_price("ETH")
        if eth:
            st.metric("ETH", f"${eth['price']:,.0f}", f"{eth.get('change_24h_pct', 0):+.1f}%")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Exposure Gauge")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ceiling,
            title={"text": "Exposure Ceiling %"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#00D26A" if ceiling >= 50 else "#FF4444"},
                "steps": [
                    {"range": [0, 20], "color": "#FF4444"},
                    {"range": [20, 50], "color": "#FF8C00"},
                    {"range": [50, 80], "color": "#FFD700"},
                    {"range": [80, 100], "color": "#00D26A"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 3},
                    "thickness": 0.8, "value": ceiling,
                },
            },
        ))
        fig.update_layout(height=300, margin=dict(t=40, b=0, l=30, r=30),
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Recommended Allocation")
        colors = ["#4488FF", "#FFD700", "#FF8C00", "#888888"]
        fig = go.Figure(go.Pie(
            labels=list(allocation.keys()),
            values=list(allocation.values()),
            hole=0.45, marker_colors=colors,
            textinfo="label+percent",
        ))
        fig.update_layout(height=300, margin=dict(t=20, b=0),
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Components
    st.subheader("Posture Components (live)")
    for name, score in components.items():
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.progress(min(100, max(0, int(score))), text=name.replace("_", " ").title())
        with col_b:
            st.write(f"**{score:.0f}**/100")

    st.caption("Data sources: FRED (GDP, CPI, VIX, Yield Curve), Alternative.me (Fear & Greed), CoinGecko (crypto prices)")
