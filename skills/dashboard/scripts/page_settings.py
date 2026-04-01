"""Settings Page — config UI for portfolio, alerts, API keys, risk parameters."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.title("Settings")

    tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "Risk", "API Keys", "Alerts"])

    with tab1:
        st.subheader("Portfolio Configuration")
        st.number_input("Initial Capital (€)", value=100000, step=1000)
        st.slider("Target Stocks %", 0, 100, 40)
        st.slider("Target Crypto %", 0, 100, 30)
        st.slider("Target Commodities %", 0, 100, 15)
        st.slider("Target Cash %", 0, 100, 15)

    with tab2:
        st.subheader("Risk Parameters")
        st.error("Kill Switch cannot be disabled. It activates at -40% drawdown and requires manual reset.")
        st.number_input("Max Position Size %", value=20, min_value=1, max_value=50)
        st.number_input("Max Asset Class %", value=60, min_value=10, max_value=100)
        st.number_input("Min Cash Reserve %", value=5, min_value=0, max_value=50)
        st.number_input("Daily Loss Limit %", value=-15, min_value=-50, max_value=0)
        st.number_input("Max Trades Per Day", value=20, min_value=1, max_value=100)
        st.number_input("Trailing Stop %", value=-8, min_value=-50, max_value=0)

        st.subheader("Circuit Breaker")
        st.info("3 consecutive losses = 1h pause | 5 = 4h | 8 = 24h")

        st.subheader("AI Override")
        ai_enabled = st.checkbox("Enable AI Override", value=True)
        if ai_enabled:
            st.number_input("Max Override Points", value=20, min_value=5, max_value=30)

    with tab3:
        st.subheader("API Keys")
        st.text_input("Alpha Vantage", type="password", placeholder="Your API key")
        st.text_input("FMP", type="password", placeholder="Your API key")
        st.text_input("Finnhub", type="password", placeholder="Your API key")
        st.text_input("FRED", type="password", placeholder="Your API key")
        st.text_input("Anthropic", type="password", placeholder="Your API key")
        st.text_input("Telegram Bot Token", type="password", placeholder="Your bot token")
        st.text_input("Telegram Chat ID", placeholder="Your chat ID")
        st.caption("Keys are stored in .env file and never transmitted.")

    with tab4:
        st.subheader("Alert Configuration")
        st.checkbox("Buy Signal Alerts (score > 65)", value=True)
        st.checkbox("Sell Signal Alerts (score < 30)", value=True)
        st.checkbox("Risk Warnings", value=True)
        st.checkbox("Rebalance Suggestions", value=True)
        st.checkbox("Macro Regime Changes", value=True)
        st.checkbox("AI Override Notifications", value=True)
        st.checkbox("Daily Summary (8:00 + 18:00 CET)", value=True)
        st.checkbox("Screener Alerts (score > 80)", value=True)
        st.checkbox("Divergence Alerts", value=True)
        st.checkbox("Require Confirmation Before Paper Execution", value=True)
