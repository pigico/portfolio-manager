"""Portfolio Manager — persistent portfolio state with live price updates.

Saves portfolio to data/portfolio.json. Tracks positions, cash, P&L.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st
from loguru import logger


PORTFOLIO_FILE = Path(__file__).parent.parent.parent.parent / "data" / "portfolio.json"


def _default_portfolio() -> dict:
    return {
        "initial_capital": 100000.0,
        "cash": 100000.0,
        "currency": "EUR",
        "positions": {},
        "history": [],
        "created_at": datetime.now(tz=UTC).isoformat(),
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }


def load_portfolio() -> dict:
    """Load portfolio from disk."""
    if PORTFOLIO_FILE.exists():
        try:
            with open(PORTFOLIO_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return _default_portfolio()


def save_portfolio(portfolio: dict) -> None:
    """Save portfolio to disk."""
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    portfolio["updated_at"] = datetime.now(tz=UTC).isoformat()
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def add_position(
    portfolio: dict, ticker: str, quantity: float,
    entry_price: float, asset_class: str = "stocks",
) -> dict:
    """Add or increase a position."""
    ticker = ticker.upper()
    cost = quantity * entry_price

    if cost > portfolio["cash"]:
        return portfolio  # Not enough cash

    if ticker in portfolio["positions"]:
        pos = portfolio["positions"][ticker]
        total_qty = pos["quantity"] + quantity
        avg_price = (pos["entry_price"] * pos["quantity"] + entry_price * quantity) / total_qty
        pos["quantity"] = total_qty
        pos["entry_price"] = round(avg_price, 4)
    else:
        portfolio["positions"][ticker] = {
            "ticker": ticker,
            "quantity": quantity,
            "entry_price": round(entry_price, 4),
            "asset_class": asset_class,
            "added_at": datetime.now(tz=UTC).isoformat(),
        }

    portfolio["cash"] = round(portfolio["cash"] - cost, 2)
    portfolio["history"].append({
        "action": "BUY",
        "ticker": ticker,
        "quantity": quantity,
        "price": entry_price,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })

    save_portfolio(portfolio)
    return portfolio


def remove_position(
    portfolio: dict, ticker: str, quantity: float | None = None, sell_price: float = 0,
) -> dict:
    """Remove or reduce a position."""
    ticker = ticker.upper()
    if ticker not in portfolio["positions"]:
        return portfolio

    pos = portfolio["positions"][ticker]
    sell_qty = quantity if quantity is not None else pos["quantity"]
    sell_qty = min(sell_qty, pos["quantity"])

    proceeds = sell_qty * sell_price
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)

    if sell_qty >= pos["quantity"]:
        del portfolio["positions"][ticker]
    else:
        pos["quantity"] = round(pos["quantity"] - sell_qty, 6)

    portfolio["history"].append({
        "action": "SELL",
        "ticker": ticker,
        "quantity": sell_qty,
        "price": sell_price,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })

    save_portfolio(portfolio)
    return portfolio


def update_capital(portfolio: dict, new_capital: float) -> dict:
    """Reset portfolio with new starting capital."""
    portfolio["initial_capital"] = new_capital
    portfolio["cash"] = new_capital
    portfolio["positions"] = {}
    portfolio["history"] = []
    save_portfolio(portfolio)
    return portfolio


def get_portfolio_with_live_prices(portfolio: dict) -> dict:
    """Enrich portfolio with live prices and P&L."""
    from live_data import get_stock_price, get_crypto_price

    enriched_positions = []
    total_invested = 0
    total_current = 0

    for ticker, pos in portfolio["positions"].items():
        is_crypto = "-USD" in ticker
        if is_crypto:
            symbol = ticker.replace("-USD", "")
            price_data = get_crypto_price(symbol)
        else:
            price_data = get_stock_price(ticker)

        current_price = price_data["price"] if price_data else pos["entry_price"]
        market_value = pos["quantity"] * current_price
        cost_basis = pos["quantity"] * pos["entry_price"]
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

        total_invested += cost_basis
        total_current += market_value

        enriched_positions.append({
            "ticker": ticker,
            "asset_class": pos.get("asset_class", "stocks"),
            "quantity": pos["quantity"],
            "entry_price": pos["entry_price"],
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "weight_pct": 0,  # Calculated below
        })

    total_value = portfolio["cash"] + total_current
    for p in enriched_positions:
        p["weight_pct"] = round(p["market_value"] / total_value * 100, 1) if total_value > 0 else 0

    return {
        "total_value": round(total_value, 2),
        "cash": portfolio["cash"],
        "cash_pct": round(portfolio["cash"] / total_value * 100, 1) if total_value > 0 else 100,
        "invested": round(total_current, 2),
        "total_pnl": round(total_current - total_invested, 2),
        "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested > 0 else 0,
        "initial_capital": portfolio["initial_capital"],
        "total_return_pct": round((total_value - portfolio["initial_capital"]) / portfolio["initial_capital"] * 100, 2),
        "positions": enriched_positions,
        "position_count": len(enriched_positions),
        "history": portfolio.get("history", []),
    }
