"""Base Collector — Abstract base class with retry, rate limiting, caching.

All data collectors inherit from this class.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from loguru import logger


class RateLimiter:
    """Simple token-bucket rate limiter per provider."""

    def __init__(self, calls_per_period: int, period_seconds: float = 60.0) -> None:
        self._max_calls = calls_per_period
        self._period = period_seconds
        self._calls: list[float] = []

    def acquire(self) -> bool:
        """Try to acquire a rate limit token. Returns True if allowed."""
        now = time.time()
        # Remove expired entries
        self._calls = [t for t in self._calls if now - t < self._period]
        if len(self._calls) >= self._max_calls:
            return False
        self._calls.append(now)
        return True

    async def wait_and_acquire(self) -> None:
        """Wait until a token is available, then acquire."""
        while not self.acquire():
            await asyncio.sleep(0.5)


class SimpleCache:
    """In-memory cache with TTL. Falls back when Redis unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.time() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store value with TTL."""
        self._store[key] = (value, time.time() + ttl_seconds)

    def clear(self) -> None:
        self._store.clear()


# Global cache instance
_cache = SimpleCache()

# Rate limiters per provider
_rate_limiters: dict[str, RateLimiter] = {
    "alpha_vantage": RateLimiter(25, 86400),     # 25/day
    "fmp": RateLimiter(250, 86400),              # 250/day
    "finnhub": RateLimiter(60, 60),              # 60/min
    "coingecko": RateLimiter(30, 60),            # 30/min
    "fred": RateLimiter(120, 60),                # generous
    "twelve_data": RateLimiter(800, 86400),      # 800/day
    "alternative_me": RateLimiter(60, 60),       # generous
    "polymarket": RateLimiter(60, 60),           # generous
    "yfinance": RateLimiter(30, 60),             # conservative
}


def rate_limit(provider: str):
    """Decorator to apply rate limiting for a provider."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            limiter = _rate_limiters.get(provider)
            if limiter and not limiter.acquire():
                logger.warning(f"Rate limit hit for {provider} — skipping call.")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


def cache_key(prefix: str, *args) -> str:
    """Generate a cache key from prefix and arguments."""
    raw = f"{prefix}:" + ":".join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()


class BaseCollector(ABC):
    """Abstract base class for all data collectors.

    Provides:
    - Retry logic (3 attempts, exponential backoff)
    - Rate limiting per provider
    - Caching with configurable TTL
    - Fallback chain support
    - Consistent logging
    """

    PROVIDER: str = "unknown"
    DEFAULT_TTL: float = 300.0  # 5 minutes

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "PortfolioManager/2.0"})

    def _fetch_with_retry(
        self,
        url: str,
        params: dict | None = None,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        timeout: float = 30.0,
    ) -> dict | list | None:
        """HTTP GET with retry and exponential backoff.

        Returns parsed JSON or None on failure.
        """
        # Check rate limit
        limiter = _rate_limiters.get(self.PROVIDER)
        if limiter and not limiter.acquire():
            logger.warning(f"Rate limit hit for {self.PROVIDER}")
            return None

        for attempt in range(1, max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                logger.debug(f"[{self.PROVIDER}] GET {url} — OK (attempt {attempt})")
                return data
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 403:
                    logger.error(f"[{self.PROVIDER}] 403 Forbidden — endpoint may require premium tier.")
                    return None
                if status == 429:
                    wait = backoff_base ** attempt * 2
                    logger.warning(f"[{self.PROVIDER}] 429 Rate Limited — waiting {wait:.0f}s")
                    time.sleep(wait)
                elif status >= 500:
                    wait = backoff_base ** attempt
                    logger.warning(f"[{self.PROVIDER}] {status} Server Error — retry in {wait:.0f}s")
                    time.sleep(wait)
                else:
                    logger.error(f"[{self.PROVIDER}] HTTP {status}: {e}")
                    return None
            except requests.exceptions.ConnectionError as e:
                wait = backoff_base ** attempt
                logger.warning(f"[{self.PROVIDER}] Connection error — retry in {wait:.0f}s: {e}")
                time.sleep(wait)
            except requests.exceptions.Timeout:
                wait = backoff_base ** attempt
                logger.warning(f"[{self.PROVIDER}] Timeout — retry in {wait:.0f}s")
                time.sleep(wait)
            except json.JSONDecodeError:
                logger.error(f"[{self.PROVIDER}] Invalid JSON response from {url}")
                return None
            except Exception as e:
                logger.error(f"[{self.PROVIDER}] Unexpected error: {e}")
                return None

        logger.error(f"[{self.PROVIDER}] All {max_retries} retries exhausted for {url}")
        return None

    def _get_cached(self, key: str) -> Any | None:
        """Retrieve from cache."""
        return _cache.get(key)

    def _set_cached(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store in cache."""
        _cache.set(key, value, ttl or self.DEFAULT_TTL)

    @abstractmethod
    def collect(self, symbol: str) -> dict | None:
        """Collect data for a symbol. Must be implemented by subclasses."""
        ...
