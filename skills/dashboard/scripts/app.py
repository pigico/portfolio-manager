"""Streamlit Dashboard — main entry point.

Dark theme, accent green #00D26A / red #FF4444. Auto-refresh 60s.
Run with: streamlit run skills/dashboard/scripts/app.py
"""

from __future__ import annotations

import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Portfolio Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme CSS
st.markdown("""
<style>
    .stMetric [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .positive { color: #00D26A; }
    .negative { color: #FF4444; }
    .neutral { color: #888888; }
    div[data-testid="stSidebar"] { background-color: #1a1a2e; }
</style>
""", unsafe_allow_html=True)

# Auto-refresh
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60_000, key="auto_refresh")
except ImportError:
    pass

# Sidebar navigation
st.sidebar.title("Portfolio Manager")
st.sidebar.markdown("---")

PAGES = {
    "Market Posture": "page_market_posture",
    "Portfolio": "page_portfolio",
    "Analysis": "page_analysis",
    "Screener": "page_screener",
    "Macro": "page_macro",
    "Paper Trading": "page_paper_trading",
    "Settings": "page_settings",
}

selected = st.sidebar.radio("Navigation", list(PAGES.keys()), index=0)

st.sidebar.markdown("---")
st.sidebar.caption("v2.0 — Skills-Based Architecture")

# Route to selected page
page_module = PAGES[selected]

if page_module == "page_market_posture":
    from page_market_posture import render
    render()
elif page_module == "page_portfolio":
    from page_portfolio import render
    render()
elif page_module == "page_analysis":
    from page_analysis import render
    render()
elif page_module == "page_screener":
    from page_screener import render
    render()
elif page_module == "page_macro":
    from page_macro import render
    render()
elif page_module == "page_paper_trading":
    from page_paper_trading import render
    render()
elif page_module == "page_settings":
    from page_settings import render
    render()
