"""Async WebSocket Manager — persistent connections to Binance + Finnhub.

Event-driven price updates with automatic reconnection and heartbeat.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

from loguru import logger

try:
    import websockets
    from websockets.asyncio.client import connect as ws_connect
except ImportError:
    websockets = None  # type: ignore[assignment]
    ws_connect = None  # type: ignore[assignment]


class PriceUpdate:
    """A single price update from a WebSocket feed."""

    __slots__ = ("symbol", "price", "volume", "timestamp", "source")

    def __init__(
        self,
        symbol: str,
        price: float,
        volume: float,
        timestamp: datetime,
        source: str,
    ) -> None:
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.timestamp = timestamp
        self.source = source


class AsyncWebSocketManager:
    """Manages persistent WebSocket connections to multiple exchanges.

    Features:
    - Thread-safe price buffer (dict)
    - Automatic reconnection with exponential backoff
    - Heartbeat check every 30 seconds
    - Fallback flag when disconnected > 60s
    - Subscriber callbacks for real-time events
    """

    # Binance streams (no API key needed)
    BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"
    # Finnhub WebSocket (requires API key)
    FINNHUB_WS_URL = "wss://ws.finnhub.io"

    # Default crypto symbols to track
    DEFAULT_CRYPTO_SYMBOLS = [
        "btcusdt", "ethusdt", "solusdt", "bnbusdt", "xrpusdt",
        "adausdt", "avaxusdt", "dotusdt", "maticusdt", "linkusdt",
        "dogeusdt", "shibusdt", "atomusdt", "ltcusdt", "uniusdt",
        "nearusdt", "aptusdt", "opusdt", "arbusdt", "suiusdt",
    ]

    def __init__(
        self,
        finnhub_api_key: str = "",
        crypto_symbols: list[str] | None = None,
        stock_symbols: list[str] | None = None,
        heartbeat_interval: float = 30.0,
        fallback_timeout: float = 60.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        self._finnhub_key = finnhub_api_key
        self._crypto_symbols = crypto_symbols or self.DEFAULT_CRYPTO_SYMBOLS
        self._stock_symbols = stock_symbols or []
        self._heartbeat_interval = heartbeat_interval
        self._fallback_timeout = fallback_timeout
        self._max_reconnect_delay = max_reconnect_delay

        # Price buffer — thread-safe via asyncio
        self._prices: dict[str, PriceUpdate] = {}
        self._last_message_time: dict[str, float] = defaultdict(float)

        # Connection state
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._subscribers: list[Callable[[PriceUpdate], Coroutine[Any, Any, None]]] = []

        # Fallback flags
        self._binance_connected = False
        self._finnhub_connected = False

    @property
    def prices(self) -> dict[str, PriceUpdate]:
        """Current price buffer snapshot."""
        return dict(self._prices)

    @property
    def needs_rest_fallback(self) -> dict[str, bool]:
        """Whether each source needs REST fallback."""
        now = time.time()
        return {
            "binance": (
                not self._binance_connected
                or (now - self._last_message_time.get("binance", 0)) > self._fallback_timeout
            ),
            "finnhub": (
                not self._finnhub_connected
                or (now - self._last_message_time.get("finnhub", 0)) > self._fallback_timeout
            ),
        }

    def get_price(self, symbol: str) -> float | None:
        """Get latest price for a symbol."""
        update = self._prices.get(symbol.upper())
        if update:
            return update.price
        # Try lowercase (binance format)
        update = self._prices.get(symbol.lower())
        return update.price if update else None

    def subscribe(
        self, callback: Callable[[PriceUpdate], Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async callback for price updates."""
        self._subscribers.append(callback)

    async def start(self) -> None:
        """Start all WebSocket connections."""
        if websockets is None:
            logger.error("websockets package not installed — WebSocket manager disabled.")
            return

        self._running = True
        logger.info("WebSocket manager starting...")

        # Launch Binance streams
        if self._crypto_symbols:
            task = asyncio.create_task(self._run_binance())
            self._tasks.append(task)

        # Launch Finnhub stream
        if self._finnhub_key and self._stock_symbols:
            task = asyncio.create_task(self._run_finnhub())
            self._tasks.append(task)

        # Launch heartbeat monitor
        task = asyncio.create_task(self._heartbeat_monitor())
        self._tasks.append(task)

        logger.info(
            f"WebSocket manager started — "
            f"tracking {len(self._crypto_symbols)} crypto, "
            f"{len(self._stock_symbols)} stocks."
        )

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("WebSocket manager stopped.")

    # ── Binance ──────────────────────────────────────────

    def _build_binance_url(self) -> str:
        """Build combined Binance stream URL."""
        streams = "/".join(f"{s}@trade" for s in self._crypto_symbols)
        return f"{self.BINANCE_WS_BASE}/{streams}"

    async def _run_binance(self) -> None:
        """Binance WebSocket connection with auto-reconnect."""
        reconnect_delay = 1.0

        while self._running:
            try:
                url = self._build_binance_url()
                logger.info(f"Connecting to Binance WebSocket...")

                async with ws_connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self._binance_connected = True
                    reconnect_delay = 1.0
                    logger.info("Binance WebSocket connected.")

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw_msg)
                            await self._handle_binance_message(msg)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.debug(f"Binance message parse error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._binance_connected = False
                logger.warning(
                    f"Binance WebSocket disconnected: {e}. "
                    f"Reconnecting in {reconnect_delay:.0f}s..."
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)

        self._binance_connected = False

    async def _handle_binance_message(self, msg: dict) -> None:
        """Process a Binance trade message."""
        symbol = msg.get("s", "").upper()
        price = float(msg.get("p", 0))
        volume = float(msg.get("q", 0))
        ts_ms = msg.get("T", 0)

        if not symbol or price <= 0:
            return

        update = PriceUpdate(
            symbol=symbol,
            price=price,
            volume=volume,
            timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
            source="binance",
        )
        self._prices[symbol] = update
        self._last_message_time["binance"] = time.time()

        for cb in self._subscribers:
            try:
                await cb(update)
            except Exception as e:
                logger.debug(f"Subscriber error: {e}")

    # ── Finnhub ──────────────────────────────────────────

    async def _run_finnhub(self) -> None:
        """Finnhub WebSocket connection with auto-reconnect."""
        reconnect_delay = 1.0

        while self._running:
            try:
                url = f"{self.FINNHUB_WS_URL}?token={self._finnhub_key}"
                logger.info("Connecting to Finnhub WebSocket...")

                async with ws_connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self._finnhub_connected = True
                    reconnect_delay = 1.0
                    logger.info("Finnhub WebSocket connected.")

                    # Subscribe to stock symbols
                    for symbol in self._stock_symbols:
                        sub_msg = json.dumps({"type": "subscribe", "symbol": symbol})
                        await ws.send(sub_msg)

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw_msg)
                            await self._handle_finnhub_message(msg)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.debug(f"Finnhub message parse error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._finnhub_connected = False
                logger.warning(
                    f"Finnhub WebSocket disconnected: {e}. "
                    f"Reconnecting in {reconnect_delay:.0f}s..."
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)

        self._finnhub_connected = False

    async def _handle_finnhub_message(self, msg: dict) -> None:
        """Process a Finnhub trade message."""
        if msg.get("type") != "trade":
            return

        for trade in msg.get("data", []):
            symbol = trade.get("s", "").upper()
            price = float(trade.get("p", 0))
            volume = float(trade.get("v", 0))
            ts_ms = trade.get("t", 0)

            if not symbol or price <= 0:
                continue

            update = PriceUpdate(
                symbol=symbol,
                price=price,
                volume=volume,
                timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
                source="finnhub",
            )
            self._prices[symbol] = update
            self._last_message_time["finnhub"] = time.time()

            for cb in self._subscribers:
                try:
                    await cb(update)
                except Exception as e:
                    logger.debug(f"Subscriber error: {e}")

    # ── Heartbeat ────────────────────────────────────────

    async def _heartbeat_monitor(self) -> None:
        """Periodic check that connections are alive."""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                now = time.time()
                for source in ("binance", "finnhub"):
                    last = self._last_message_time.get(source, 0)
                    if last > 0 and (now - last) > self._fallback_timeout:
                        logger.warning(
                            f"{source} silent for >{self._fallback_timeout}s — "
                            "REST fallback may be needed."
                        )
            except asyncio.CancelledError:
                break

    def get_status(self) -> dict:
        """Return WebSocket manager status."""
        return {
            "running": self._running,
            "binance_connected": self._binance_connected,
            "finnhub_connected": self._finnhub_connected,
            "tracked_symbols": len(self._prices),
            "needs_fallback": self.needs_rest_fallback,
        }
