"""Portfolio Page — manage positions, track P&L with live prices."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from portfolio_manager import (
    load_portfolio, save_portfolio, add_position, remove_position,
    update_capital, get_portfolio_with_live_prices,
)
from live_data import get_stock_price, get_crypto_price


def render() -> None:
    st.title("Portfolio")

    # Load and enrich
    raw_portfolio = load_portfolio()

    # ── Sidebar: Add/Remove positions ────────────────────
    with st.sidebar:
        st.markdown("---")
        st.subheader("Manage Portfolio")

        # Add position
        with st.expander("Add Position", expanded=False):
            new_ticker = st.text_input("Ticker", placeholder="AAPL, BTC-USD, GLD...").upper().strip()
            new_class = st.selectbox("Asset Class", ["stocks", "crypto", "commodities", "etf"])
            new_qty = st.number_input("Quantity", min_value=0.0001, value=1.0, step=1.0, format="%.4f")

            # Auto-fill price
            auto_price = 0.0
            if new_ticker:
                is_crypto = "-USD" in new_ticker
                if is_crypto:
                    pd = get_crypto_price(new_ticker.replace("-USD", ""))
                else:
                    pd = get_stock_price(new_ticker)
                if pd:
                    auto_price = pd["price"]

            new_price = st.number_input("Entry Price", min_value=0.01, value=max(0.01, auto_price), format="%.2f")
            total_cost = new_qty * new_price
            st.caption(f"Total cost: {raw_portfolio.get('currency', 'EUR')} {total_cost:,.2f}")

            if st.button("Buy", type="primary", use_container_width=True):
                if new_ticker and new_qty > 0 and new_price > 0:
                    if total_cost <= raw_portfolio["cash"]:
                        raw_portfolio = add_position(raw_portfolio, new_ticker, new_qty, new_price, new_class)
                        st.success(f"Bought {new_qty} {new_ticker} @ {new_price:.2f}")
                        st.rerun()
                    else:
                        st.error(f"Not enough cash (have {raw_portfolio['cash']:,.2f})")

        # Remove position
        if raw_portfolio["positions"]:
            with st.expander("Sell Position", expanded=False):
                sell_ticker = st.selectbox("Select position", list(raw_portfolio["positions"].keys()))
                if sell_ticker:
                    pos = raw_portfolio["positions"][sell_ticker]
                    st.caption(f"Holding: {pos['quantity']} @ {pos['entry_price']:.2f}")

                    sell_qty = st.number_input("Sell quantity", min_value=0.0001,
                                               max_value=float(pos["quantity"]),
                                               value=float(pos["quantity"]), format="%.4f")

                    # Current price
                    is_crypto = "-USD" in sell_ticker
                    if is_crypto:
                        pd = get_crypto_price(sell_ticker.replace("-USD", ""))
                    else:
                        pd = get_stock_price(sell_ticker)
                    sell_price = pd["price"] if pd else pos["entry_price"]
                    sell_price_input = st.number_input("Sell Price", value=sell_price, format="%.2f")

                    if st.button("Sell", type="secondary", use_container_width=True):
                        raw_portfolio = remove_position(raw_portfolio, sell_ticker, sell_qty, sell_price_input)
                        st.success(f"Sold {sell_qty} {sell_ticker} @ {sell_price_input:.2f}")
                        st.rerun()

        # Reset capital
        with st.expander("Settings", expanded=False):
            new_cap = st.number_input("Starting Capital", value=raw_portfolio["initial_capital"], step=1000.0)
            if st.button("Reset Portfolio"):
                raw_portfolio = update_capital(raw_portfolio, new_cap)
                st.success(f"Portfolio reset to {new_cap:,.2f}")
                st.rerun()

    # ── Main content ─────────────────────────────────────
    with st.spinner("Fetching live prices..."):
        portfolio = get_portfolio_with_live_prices(raw_portfolio)

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pnl_delta = f"{portfolio['total_return_pct']:+.2f}%"
        st.metric("Total Value", f"{portfolio['total_value']:,.2f}", pnl_delta)
    with c2:
        st.metric("Cash", f"{portfolio['cash']:,.2f}", f"{portfolio['cash_pct']:.1f}%")
    with c3:
        pnl_color = "normal" if portfolio["total_pnl"] >= 0 else "inverse"
        st.metric("P&L", f"{portfolio['total_pnl']:+,.2f}", f"{portfolio['total_pnl_pct']:+.2f}%",
                  delta_color=pnl_color)
    with c4:
        st.metric("Positions", portfolio["position_count"])

    if not portfolio["positions"]:
        st.info("Portfolio vuoto. Usa il menu laterale per aggiungere posizioni.")
        st.markdown("""
        **Come iniziare:**
        1. Espandi **'Add Position'** nel menu a sinistra
        2. Inserisci il ticker (es. `AAPL`, `BTC-USD`, `GLD`)
        3. Il prezzo si auto-compila dal mercato
        4. Scegli la quantita' e clicca **Buy**
        """)
        return

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Allocation")
        # By asset class
        class_values = {}
        for p in portfolio["positions"]:
            cls = p["asset_class"]
            class_values[cls] = class_values.get(cls, 0) + p["market_value"]
        class_values["cash"] = portfolio["cash"]

        colors_map = {"stocks": "#4488FF", "crypto": "#FFD700", "commodities": "#FF8C00",
                      "etf": "#AA44FF", "cash": "#888888"}
        fig = go.Figure(go.Pie(
            labels=list(class_values.keys()),
            values=list(class_values.values()),
            hole=0.5,
            marker_colors=[colors_map.get(k, "#666") for k in class_values],
            textinfo="label+percent",
        ))
        fig.update_layout(height=300, margin=dict(t=10, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("P&L per Position")
        tickers = [p["ticker"] for p in portfolio["positions"]]
        pnls = [p["pnl_pct"] for p in portfolio["positions"]]
        colors = ["#00D26A" if v >= 0 else "#FF4444" for v in pnls]

        fig = go.Figure(go.Bar(
            x=tickers, y=pnls, marker_color=colors,
            text=[f"{v:+.1f}%" for v in pnls], textposition="outside",
        ))
        fig.update_layout(height=300, margin=dict(t=10, b=30),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", showlegend=False, yaxis_title="P&L %")
        st.plotly_chart(fig, use_container_width=True)

    # Positions table
    st.subheader("Open Positions")
    table_data = []
    for p in sorted(portfolio["positions"], key=lambda x: -x["market_value"]):
        table_data.append({
            "Ticker": p["ticker"],
            "Class": p["asset_class"],
            "Qty": p["quantity"],
            "Entry": p["entry_price"],
            "Current": p["current_price"],
            "Value": p["market_value"],
            "P&L": p["pnl"],
            "P&L %": p["pnl_pct"],
            "Weight %": p["weight_pct"],
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        column_config={
            "Entry": st.column_config.NumberColumn(format="$%.2f"),
            "Current": st.column_config.NumberColumn(format="$%.2f"),
            "Value": st.column_config.NumberColumn(format="$%.2f"),
            "P&L": st.column_config.NumberColumn(format="$%.2f"),
            "P&L %": st.column_config.NumberColumn(format="%.2f%%"),
            "Weight %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
        },
    )

    # Transaction history
    if portfolio["history"]:
        with st.expander(f"Transaction History ({len(portfolio['history'])} trades)"):
            for h in reversed(portfolio["history"][-20:]):
                emoji = "BUY" if h["action"] == "BUY" else "SELL"
                st.text(f"{h['timestamp'][:16]} | {emoji} {h['quantity']:.4f} {h['ticker']} @ ${h['price']:,.2f}")
