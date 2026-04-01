"""Trade Log — full audit trail for every paper trade."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


class TradeLog:
    """Persistent trade log with CSV and JSON export."""

    def __init__(self, log_dir: Path | str = "data/trades") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict] = []

    def log_trade(
        self,
        trade_id: int,
        asset: str,
        action: str,
        price: float,
        quantity: float,
        commission: float,
        score: float,
        ai_override: bool,
        rationale: str,
        risk_guard_result: str,
        portfolio_value: float,
    ) -> None:
        """Log a trade with full details."""
        entry = {
            "trade_id": trade_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "asset": asset,
            "action": action,
            "price": round(price, 4),
            "quantity": round(quantity, 6),
            "commission": round(commission, 4),
            "notional": round(price * quantity, 2),
            "score": round(score, 1),
            "ai_override": ai_override,
            "rationale": rationale[:200],
            "risk_guard": risk_guard_result,
            "portfolio_value": round(portfolio_value, 2),
        }
        self._entries.append(entry)
        logger.debug(f"Trade logged: #{trade_id} {action} {quantity:.4f} {asset} @ {price:.2f}")

    def get_entries(self, last_n: int | None = None) -> list[dict]:
        if last_n:
            return self._entries[-last_n:]
        return list(self._entries)

    def export_csv(self, filename: str = "trade_log.csv") -> Path:
        """Export trade log to CSV."""
        path = self._log_dir / filename
        if not self._entries:
            return path

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._entries[0].keys())
            writer.writeheader()
            writer.writerows(self._entries)

        logger.info(f"Trade log exported to {path} ({len(self._entries)} entries)")
        return path

    def export_json(self, filename: str = "trade_log.json") -> Path:
        """Export trade log to JSON."""
        path = self._log_dir / filename
        with open(path, "w") as f:
            json.dump(self._entries, f, indent=2)
        return path
