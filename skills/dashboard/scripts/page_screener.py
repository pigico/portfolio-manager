"""Screener Page — sortable table with filters and drill-down."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.title("Screener")
    st.caption("Discover new investment opportunities")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        asset_class = st.selectbox("Asset Class", ["All", "Stocks", "Crypto", "Commodities"])
    with col2:
        min_score = st.slider("Minimum Score", 0, 100, 65)
    with col3:
        sort_by = st.selectbox("Sort By", ["Score", "P&L %", "Volume"])

    # Demo screener data
    data = [
        {"Ticker": "NVDA", "Class": "Stocks", "Score": 88, "Decision": "STRONG BUY",
         "Catalyst": "AI demand surge", "AI Rec": True},
        {"Ticker": "SOL", "Class": "Crypto", "Score": 82, "Decision": "STRONG BUY",
         "Catalyst": "DeFi TVL growing", "AI Rec": True},
        {"Ticker": "MSFT", "Class": "Stocks", "Score": 76, "Decision": "BUY",
         "Catalyst": "Cloud growth", "AI Rec": False},
        {"Ticker": "ETH", "Class": "Crypto", "Score": 73, "Decision": "BUY",
         "Catalyst": "ETF inflows", "AI Rec": False},
        {"Ticker": "GLD", "Class": "Commodities", "Score": 71, "Decision": "BUY",
         "Catalyst": "Rate cut expectations", "AI Rec": True},
        {"Ticker": "AAPL", "Class": "Stocks", "Score": 68, "Decision": "BUY",
         "Catalyst": "Services revenue", "AI Rec": False},
        {"Ticker": "BTC", "Class": "Crypto", "Score": 65, "Decision": "BUY",
         "Catalyst": "Halving cycle", "AI Rec": False},
    ]

    # Apply filters
    if asset_class != "All":
        data = [d for d in data if d["Class"] == asset_class]
    data = [d for d in data if d["Score"] >= min_score]

    if not data:
        st.info("No assets match your criteria.")
        return

    st.dataframe(
        data,
        use_container_width=True,
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "AI Rec": st.column_config.CheckboxColumn("AI Recommended"),
        },
    )

    st.caption(f"Showing {len(data)} candidates above score {min_score}")
