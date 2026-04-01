"""Macro Page — LIVE data from FRED API."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from live_data import get_fred_series, get_market_posture, get_fear_greed


def render() -> None:
    st.title("Macro Dashboard")
    st.caption("Live data from FRED, Alternative.me")

    with st.spinner("Fetching macro data from FRED..."):
        posture_data = get_market_posture()
        vix_series = get_fred_series("VIXCLS", limit=90)
        spread_series = get_fred_series("T10Y2Y", limit=90)
        cpi_series = get_fred_series("CPIAUCSL", limit=24)
        fed_funds = get_fred_series("FEDFUNDS", limit=24)
        unrate = get_fred_series("UNRATE", limit=24)

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Regime", posture_data["regime"],
                  f"{posture_data['regime_confidence']:.0%} conf")
    with c2:
        if cpi_series and cpi_series["observations"]:
            latest_cpi = cpi_series["observations"][0]["value"]
            prev_cpi = cpi_series["observations"][1]["value"] if len(cpi_series["observations"]) > 1 else latest_cpi
            st.metric("CPI", f"{latest_cpi:.1f}", f"{latest_cpi - prev_cpi:+.1f}")
    with c3:
        if fed_funds:
            st.metric("Fed Funds Rate", f"{fed_funds['latest_value']:.2f}%")
    with c4:
        if unrate:
            st.metric("Unemployment", f"{unrate['latest_value']:.1f}%")

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("VIX - Fear Gauge (live)")
        if vix_series and vix_series["observations"]:
            obs = list(reversed(vix_series["observations"]))
            dates = [o["date"] for o in obs]
            values = [o["value"] for o in obs]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=values, mode="lines",
                                     line=dict(color="#FFD700", width=2), fill="tozeroy",
                                     fillcolor="rgba(255,215,0,0.1)"))
            fig.add_hline(y=30, line_dash="dash", line_color="#FF4444",
                          annotation_text="Fear zone")
            fig.add_hline(y=20, line_dash="dash", line_color="#888",
                          annotation_text="Normal")
            fig.update_layout(height=300, margin=dict(t=10, b=30),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="white", showlegend=False, yaxis_title="VIX")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Yield Curve 10Y-2Y (live)")
        if spread_series and spread_series["observations"]:
            obs = list(reversed(spread_series["observations"]))
            dates = [o["date"] for o in obs]
            values = [o["value"] for o in obs]
            colors = ["#00D26A" if v > 0 else "#FF4444" for v in values]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=dates, y=values, marker_color=colors))
            fig.add_hline(y=0, line_color="white", line_width=2)
            fig.update_layout(height=300, margin=dict(t=10, b=30),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="white", showlegend=False, yaxis_title="Spread %")
            st.plotly_chart(fig, use_container_width=True)

    # CPI + Fed Funds
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("CPI (live)")
        if cpi_series and cpi_series["observations"]:
            obs = list(reversed(cpi_series["observations"]))
            dates = [o["date"] for o in obs]
            values = [o["value"] for o in obs]
            fig = go.Figure(go.Scatter(x=dates, y=values, mode="lines+markers",
                                       line=dict(color="#FF8C00", width=2)))
            fig.update_layout(height=250, margin=dict(t=10, b=30),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="white", showlegend=False, yaxis_title="CPI Index")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Fed Funds Rate (live)")
        if fed_funds and fed_funds["observations"]:
            obs = list(reversed(fed_funds["observations"]))
            dates = [o["date"] for o in obs]
            values = [o["value"] for o in obs]
            fig = go.Figure(go.Scatter(x=dates, y=values, mode="lines+markers",
                                       line=dict(color="#4488FF", width=2)))
            fig.update_layout(height=250, margin=dict(t=10, b=30),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="white", showlegend=False, yaxis_title="Rate %")
            st.plotly_chart(fig, use_container_width=True)

    # Fear & Greed history
    st.subheader("Crypto Fear & Greed Index (live)")
    fg = get_fear_greed()
    if fg:
        c1, c2 = st.columns([1, 3])
        with c1:
            val = fg["value"]
            color = "#FF4444" if val < 25 else "#FF8C00" if val < 45 else "#FFD700" if val < 55 else "#00D26A"
            st.markdown(f"### <span style='color:{color}'>{val} - {fg['classification']}</span>",
                        unsafe_allow_html=True)
        with c2:
            if fg.get("history"):
                hist_vals = list(reversed([h["value"] for h in fg["history"]]))
                fig = go.Figure(go.Scatter(y=hist_vals, mode="lines",
                                           line=dict(color="#FFD700", width=2)))
                fig.add_hline(y=25, line_dash="dash", line_color="#FF4444")
                fig.add_hline(y=75, line_dash="dash", line_color="#00D26A")
                fig.update_layout(height=150, margin=dict(t=5, b=5, l=30, r=10),
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="white", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    st.caption("Data sources: FRED API (all macro), Alternative.me (Fear & Greed)")
