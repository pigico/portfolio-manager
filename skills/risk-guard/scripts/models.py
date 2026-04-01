"""Shared data models for the Risk Guard module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    STRONG_BUY = "STRONG_BUY"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


class AssetClass(str, Enum):
    STOCKS = "stocks"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    CASH = "cash"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class TradeProposal:
    """A proposed trade that must be validated by RiskGuard."""
    asset: str
    asset_class: AssetClass
    action: TradeAction
    price: float
    quantity: float
    score: float
    confidence: Confidence
    rationale: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def notional_value(self) -> float:
        return self.price * self.quantity


@dataclass
class TradeResult:
    """Result of RiskGuard validation."""
    approved: bool
    proposal: TradeProposal
    adjusted_quantity: Optional[float] = None
    rejection_reason: Optional[str] = None
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    kelly_size_pct: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def final_quantity(self) -> float:
        if self.adjusted_quantity is not None:
            return self.adjusted_quantity
        return self.proposal.quantity


@dataclass
class PortfolioState:
    """Current state of the portfolio."""
    total_value: float
    cash: float
    positions: dict[str, PositionInfo] = field(default_factory=dict)
    peak_value: float = 0.0
    daily_start_value: float = 0.0
    daily_trades: int = 0
    daily_new_positions: int = 0

    @property
    def cash_pct(self) -> float:
        if self.total_value == 0:
            return 100.0
        return (self.cash / self.total_value) * 100.0

    @property
    def drawdown_pct(self) -> float:
        if self.peak_value == 0:
            return 0.0
        return ((self.total_value - self.peak_value) / self.peak_value) * 100.0

    @property
    def daily_pnl_pct(self) -> float:
        if self.daily_start_value == 0:
            return 0.0
        return ((self.total_value - self.daily_start_value) / self.daily_start_value) * 100.0


@dataclass
class PositionInfo:
    """Info about a single position."""
    asset: str
    asset_class: AssetClass
    quantity: float
    entry_price: float
    current_price: float
    peak_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100.0

    @property
    def drawdown_from_peak_pct(self) -> float:
        if self.peak_price == 0:
            return 0.0
        return ((self.current_price - self.peak_price) / self.peak_price) * 100.0
