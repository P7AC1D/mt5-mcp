"""Async wrapper for MetaTrader 5 API.

The MT5 Python API is synchronous, so all calls are wrapped with
asyncio.to_thread() to prevent blocking the event loop.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import MetaTrader5 as mt5

from .config import MT5Settings

logger = logging.getLogger(__name__)


class MT5Error(Exception):
    """Exception raised for MT5 API errors."""

    def __init__(self, message: str, error_code: int | None = None):
        self.error_code = error_code
        super().__init__(message)


class MT5Client:
    """Async client wrapper for MetaTrader 5 API."""

    def __init__(self, settings: MT5Settings | None = None):
        self.settings = settings or MT5Settings()
        self._initialized = False
        self._selected_symbols: set[str] = set()

    async def initialize(self, path_override: str | None = None) -> bool:
        """Initialize connection to MT5 terminal."""
        kwargs = self.settings.get_init_kwargs()
        if path_override:
            kwargs["path"] = path_override

        def _init():
            if kwargs:
                return mt5.initialize(**kwargs)
            return mt5.initialize()

        result = await asyncio.to_thread(_init)
        if not result:
            error = await self.get_last_error()
            raise MT5Error(f"MT5 initialization failed: {error}", error[0] if error else None)

        self._initialized = True
        logger.info("MT5 initialized successfully")
        return True

    async def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        await asyncio.to_thread(mt5.shutdown)
        self._initialized = False
        self._selected_symbols.clear()
        logger.info("MT5 shutdown complete")

    async def get_last_error(self) -> tuple[int, str]:
        """Get last MT5 error."""
        return await asyncio.to_thread(mt5.last_error)

    def _check_initialized(self) -> None:
        """Ensure MT5 is initialized."""
        if not self._initialized:
            raise MT5Error("MT5 not initialized. Call initialize() first.")

    async def _ensure_symbol_selected(self, symbol: str) -> None:
        """Ensure a symbol is selected in MarketWatch (auto-select if needed)."""
        if symbol in self._selected_symbols:
            return

        def _select():
            info = mt5.symbol_info(symbol)
            if info is None:
                return False, f"Symbol {symbol} not found"
            if not info.visible:
                if not mt5.symbol_select(symbol, True):
                    return False, f"Failed to select symbol {symbol}"
            return True, None

        success, error = await asyncio.to_thread(_select)
        if not success:
            raise MT5Error(error)
        self._selected_symbols.add(symbol)

    # -------------------------------------------------------------------------
    # Terminal Info
    # -------------------------------------------------------------------------

    async def get_terminal_info(self) -> dict[str, Any]:
        """Get MT5 terminal information."""
        self._check_initialized()
        info = await asyncio.to_thread(mt5.terminal_info)
        if info is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get terminal info: {error}")
        return info._asdict()

    async def get_version(self) -> tuple[int, int, str]:
        """Get MT5 terminal version."""
        self._check_initialized()
        return await asyncio.to_thread(mt5.version)

    # -------------------------------------------------------------------------
    # Account
    # -------------------------------------------------------------------------

    async def get_account_info(self) -> dict[str, Any]:
        """Get trading account information."""
        self._check_initialized()
        info = await asyncio.to_thread(mt5.account_info)
        if info is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get account info: {error}")
        return info._asdict()

    # -------------------------------------------------------------------------
    # Symbols
    # -------------------------------------------------------------------------

    async def get_symbols_total(self) -> int:
        """Get total number of symbols."""
        self._check_initialized()
        return await asyncio.to_thread(mt5.symbols_total)

    async def get_symbols(self, group: str | None = None) -> list[dict[str, Any]]:
        """Get list of available symbols."""
        self._check_initialized()

        def _get():
            if group:
                symbols = mt5.symbols_get(group=group)
            else:
                symbols = mt5.symbols_get()
            return symbols

        symbols = await asyncio.to_thread(_get)
        if symbols is None:
            return []
        return [s._asdict() for s in symbols]

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Get symbol specification."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        info = await asyncio.to_thread(mt5.symbol_info, symbol)
        if info is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get symbol info for {symbol}: {error}")
        return info._asdict()

    async def get_symbol_tick(self, symbol: str) -> dict[str, Any]:
        """Get current tick for a symbol."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
        if tick is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get tick for {symbol}: {error}")
        return tick._asdict()

    # -------------------------------------------------------------------------
    # Market Data - OHLC Bars
    # -------------------------------------------------------------------------

    async def get_ohlc_bars(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> list[dict[str, Any]]:
        """Get OHLC bars from a starting position."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        rates = await asyncio.to_thread(
            mt5.copy_rates_from_pos, symbol, timeframe, start_pos, count
        )
        if rates is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get OHLC bars: {error}")
        return [
            {
                "time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "tick_volume": int(r[5]),
                "spread": int(r[6]),
                "real_volume": int(r[7]),
            }
            for r in rates
        ]

    async def get_ohlc_bars_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        """Get OHLC bars for a date range."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        rates = await asyncio.to_thread(
            mt5.copy_rates_range, symbol, timeframe, date_from, date_to
        )
        if rates is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get OHLC bars range: {error}")
        return [
            {
                "time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "tick_volume": int(r[5]),
                "spread": int(r[6]),
                "real_volume": int(r[7]),
            }
            for r in rates
        ]

    # -------------------------------------------------------------------------
    # Market Data - Ticks
    # -------------------------------------------------------------------------

    async def get_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int = mt5.COPY_TICKS_ALL,
    ) -> list[dict[str, Any]]:
        """Get tick data for a date range."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        ticks = await asyncio.to_thread(
            mt5.copy_ticks_range, symbol, date_from, date_to, flags
        )
        if ticks is None:
            error = await self.get_last_error()
            raise MT5Error(f"Failed to get ticks range: {error}")
        return [
            {
                "time": int(t[0]),
                "bid": float(t[1]),
                "ask": float(t[2]),
                "last": float(t[3]),
                "volume": int(t[4]),
                "time_msc": int(t[5]),
                "flags": int(t[6]),
                "volume_real": float(t[7]),
            }
            for t in ticks
        ]

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------

    async def get_positions_total(self) -> int:
        """Get total number of open positions."""
        self._check_initialized()
        return await asyncio.to_thread(mt5.positions_total)

    async def get_positions(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get open positions."""
        self._check_initialized()

        def _get():
            if ticket:
                return mt5.positions_get(ticket=ticket)
            if symbol:
                return mt5.positions_get(symbol=symbol)
            return mt5.positions_get()

        positions = await asyncio.to_thread(_get)
        if positions is None:
            return []
        return [p._asdict() for p in positions]

    # -------------------------------------------------------------------------
    # Orders
    # -------------------------------------------------------------------------

    async def get_orders_total(self) -> int:
        """Get total number of pending orders."""
        self._check_initialized()
        return await asyncio.to_thread(mt5.orders_total)

    async def get_orders(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get pending orders."""
        self._check_initialized()

        def _get():
            if ticket:
                return mt5.orders_get(ticket=ticket)
            if symbol:
                return mt5.orders_get(symbol=symbol)
            return mt5.orders_get()

        orders = await asyncio.to_thread(_get)
        if orders is None:
            return []
        return [o._asdict() for o in orders]

    async def calculate_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate required margin for an order."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        margin = await asyncio.to_thread(
            mt5.order_calc_margin, action, symbol, volume, price
        )
        return margin

    async def calculate_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate potential profit/loss for a trade."""
        self._check_initialized()
        await self._ensure_symbol_selected(symbol)

        profit = await asyncio.to_thread(
            mt5.order_calc_profit, action, symbol, volume, price_open, price_close
        )
        return profit

    async def check_order(self, request: dict[str, Any]) -> dict[str, Any]:
        """Check if an order can be placed."""
        self._check_initialized()

        result = await asyncio.to_thread(mt5.order_check, request)
        if result is None:
            error = await self.get_last_error()
            raise MT5Error(f"Order check failed: {error}")
        return result._asdict()

    async def send_order(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a trading order."""
        self._check_initialized()

        logger.warning(f"Sending order: {request}")
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None:
            error = await self.get_last_error()
            raise MT5Error(f"Order send failed: {error}")

        result_dict = result._asdict()
        logger.info(f"Order result: retcode={result_dict.get('retcode')}, order={result_dict.get('order')}")
        return result_dict

    # -------------------------------------------------------------------------
    # History
    # -------------------------------------------------------------------------

    async def get_history_orders_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int:
        """Get total number of historical orders."""
        self._check_initialized()
        return await asyncio.to_thread(
            mt5.history_orders_total, date_from, date_to
        )

    async def get_history_orders(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get historical orders."""
        self._check_initialized()

        def _get():
            if ticket:
                return mt5.history_orders_get(ticket=ticket)
            if position:
                return mt5.history_orders_get(position=position)
            if symbol:
                return mt5.history_orders_get(date_from, date_to, group=f"*{symbol}*")
            return mt5.history_orders_get(date_from, date_to)

        orders = await asyncio.to_thread(_get)
        if orders is None:
            return []
        return [o._asdict() for o in orders]

    async def get_history_deals_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int:
        """Get total number of historical deals."""
        self._check_initialized()
        return await asyncio.to_thread(
            mt5.history_deals_total, date_from, date_to
        )

    async def get_history_deals(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get historical deals/trades."""
        self._check_initialized()

        def _get():
            if ticket:
                return mt5.history_deals_get(ticket=ticket)
            if position:
                return mt5.history_deals_get(position=position)
            if symbol:
                return mt5.history_deals_get(date_from, date_to, group=f"*{symbol}*")
            return mt5.history_deals_get(date_from, date_to)

        deals = await asyncio.to_thread(_get)
        if deals is None:
            return []
        return [d._asdict() for d in deals]
