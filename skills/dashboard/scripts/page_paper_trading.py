"""Paper Trading Page — equity curve, trade log, risk metrics, win/loss."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import numpy as np


def render() -> None:
    st.title("Paper Trading")

    # Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Value", "€105,230", "+5.23%")
    with c2:
        st.metric("Sharpe Ratio", "1.42")
    with c3:
        st.metric("Max Drawdown", "-6.8%")
    with c4:
        st.metric("Win Rate", "62%")
    with c5:
        st.metric("Profit Factor", "1.85")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Equity Curve vs Benchmarks")
        np.random.seed(42)
        days = 90
        portfolio = [100000]
        spy = [100000]
        btc = [100000]
        for _ in range(days - 1):
            portfolio.append(portfolio[-1] * (1 + np.random.normal(0.0015, 0.01)))
            spy.append(spy[-1] * (1 + np.random.normal(0.0008, 0.012)))
            btc.append(btc[-1] * (1 + np.random.normal(0.001, 0.025)))

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=portfolio, name="Portfolio",
                                 line=dict(color="#00D26A", width=2.5)))
        fig.add_trace(go.Scatter(y=spy, name="SPY",
                                 line=dict(color="#4488FF", width=1.5, dash="dot")))
        fig.add_trace(go.Scatter(y=btc, name="BTC",
                                 line=dict(color="#FFD700", width=1.5, dash="dot")))
        fig.update_layout(height=350, margin=dict(t=10, b=30),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", legend=dict(x=0, y=1), yaxis_title="Value (€)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Win/Loss Distribution")
        np.random.seed(123)
        pnls = np.concatenate([
            np.random.normal(3, 2, 40),   # wins
            np.random.normal(-2, 1.5, 25),  # losses
        ])
        colors = ["#00D26A" if p > 0 else "#FF4444" for p in pnls]
        fig = go.Figure(go.Histogram(
            x=pnls, marker_color="#00D26A",
            nbinsx=30, opacity=0.8,
        ))
        fig.add_vline(x=0, line_color="white", line_width=2)
        fig.update_layout(height=350, margin=dict(t=10, b=30),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", xaxis_title="P&L %", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

    # Trade log
    st.subheader("Recent Trades")
    trades = [
        {"#": 45, "Time": "2025-03-28 14:22", "Asset": "NVDA", "Action": "BUY",
         "Price": 875.50, "Qty": 5, "Score": 85, "AI": False, "P&L": "+3.2%"},
        {"#": 44, "Time": "2025-03-27 10:15", "Asset": "BTC", "Action": "BUY",
         "Price": 62400, "Qty": 0.1, "Score": 78, "AI": True, "P&L": "+1.8%"},
        {"#": 43, "Time": "2025-03-26 16:45", "Asset": "AAPL", "Action": "SELL",
         "Price": 178.20, "Qty": 20, "Score": 42, "AI": False, "P&L": "-1.2%"},
    ]
    st.dataframe(trades, use_container_width=True)

    # Risk Guard status
    st.subheader("Risk Guard Status")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.success("Kill Switch: INACTIVE")
    with r2:
        st.success("Circuit Breaker: OK (0 consecutive losses)")
    with r3:
        st.info("Portfolio VaR(95%, 1d): €2,150")
