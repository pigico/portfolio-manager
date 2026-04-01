"""Portfolio Page — allocation donut, positions table, equity curve."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go


def render() -> None:
    st.title("Portfolio Overview")

    # Demo data
    total_value = 105_230.50
    cash = 42_000.00
    daily_pnl = 1.23
    drawdown = -3.5
    positions = [
        {"Ticker": "AAPL", "Price": 185.20, "Qty": 50, "P&L%": 5.2, "Score": 72, "Signal": "BUY"},
        {"Ticker": "BTC", "Price": 63500, "Qty": 0.5, "P&L%": 12.1, "Score": 78, "Signal": "BUY"},
        {"Ticker": "ETH", "Price": 3350, "Qty": 5, "P&L%": -2.3, "Score": 55, "Signal": "HOLD"},
        {"Ticker": "GLD", "Price": 192, "Qty": 30, "P&L%": 1.8, "Score": 65, "Signal": "BUY"},
    ]

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Value", f"€{total_value:,.2f}", f"{daily_pnl:+.2f}%")
    with c2:
        st.metric("Cash", f"€{cash:,.2f}", f"{cash/total_value*100:.1f}%")
    with c3:
        st.metric("Positions", len(positions))
    with c4:
        st.metric("Max Drawdown", f"{drawdown:.1f}%")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Asset Allocation")
        labels = ["Stocks", "Crypto", "Commodities", "Cash"]
        values = [15, 30, 15, 40]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.5,
            marker_colors=["#4488FF", "#FFD700", "#FF8C00", "#888888"],
            textinfo="label+percent",
        ))
        fig.update_layout(height=300, margin=dict(t=10, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Equity Curve")
        # Demo equity curve
        import numpy as np
        np.random.seed(42)
        days = list(range(90))
        equity = [100000]
        for _ in days[1:]:
            equity.append(equity[-1] * (1 + np.random.normal(0.001, 0.01)))

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=equity, mode="lines", name="Portfolio",
                                 line=dict(color="#00D26A", width=2)))
        fig.add_hline(y=100000, line_dash="dash", line_color="#888",
                      annotation_text="Start")
        fig.update_layout(height=300, margin=dict(t=10, b=30),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", showlegend=False,
                          yaxis_title="Value (€)")
        st.plotly_chart(fig, use_container_width=True)

    # Positions table
    st.subheader("Open Positions")
    st.dataframe(
        positions,
        use_container_width=True,
        column_config={
            "P&L%": st.column_config.NumberColumn(format="%.2f%%"),
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100),
        },
    )
