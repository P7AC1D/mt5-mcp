"""Synchronous adapter. Only the dedicated owner thread may call this module."""

import logging
from collections.abc import Sized
from datetime import datetime
from typing import Any

from . import constants
from .config import MT5Settings
from .errors import MT5Error

logger = logging.getLogger(__name__)


class _NativeClient:
    """Native operations confined to one owner, including compound tool calls."""

    def __init__(self, settings: MT5Settings, api: Any):
        self.api = api
        self.account_identity = None
        self.account_generation = 0
        self.settings = settings
        self._initialized = False
        self._selected_symbols: set[str] = set()

    def initialize(self, path_override: str | None = None) -> bool:
        """Initialize connection to MT5 terminal."""
        self._initialized = False
        self.account_generation += 1
        kwargs = self.settings.get_init_kwargs()
        if path_override:
            kwargs["path"] = path_override

        def _init():
            if kwargs:
                return self._call("initialize", **kwargs)
            return self._call("initialize")

        result = _init()
        if not result:
            error = self.get_last_error()
            raise MT5Error(f"MT5 initialization failed: {error}", error[0] if error else None)
        self._initialized = False
        self._selected_symbols.clear()
        self._pin_account()
        self._initialized = True
        logger.info("MT5 initialized successfully")
        return True

    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        if self.api is not None:
            self._call("shutdown")
        self._initialized = False
        self._selected_symbols.clear()
        logger.info("MT5 shutdown complete")

    def get_last_error(self) -> tuple[int, str]:
        """Get last MT5 error."""
        return self._call("last_error")

    def _check_initialized(self) -> None:
        """Ensure MT5 is initialized."""
        if not self._initialized:
            raise MT5Error("MT5 not initialized. Call initialize() first.")

    def _ensure_symbol_selected(self, symbol: str) -> None:
        """Ensure a symbol is selected in MarketWatch (auto-select if needed)."""
        if symbol in self._selected_symbols:
            return

        def _select():
            info = self._call("symbol_info", symbol)
            if info is None:
                return (False, f"Symbol {symbol} not found")
            if not info.visible:
                if not self._call("symbol_select", symbol, True):
                    return (False, f"Failed to select symbol {symbol}")
            return (True, None)

        success, error = _select()
        if not success:
            raise MT5Error(error or "Symbol selection failed")
        self._selected_symbols.add(symbol)

    def get_terminal_info(self) -> dict[str, Any]:
        """Get MT5 terminal information."""
        self._check_initialized()
        info = self._call("terminal_info")
        if info is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get terminal info: {error}")
        return info._asdict()

    def get_version(self) -> tuple[int, int, str]:
        """Get MT5 terminal version."""
        self._check_initialized()
        return self._call("version")

    def get_account_info(self) -> dict[str, Any]:
        """Get trading account information."""
        self._check_initialized()
        info = self._call("account_info")
        if info is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get account info: {error}")
        return info._asdict()

    def get_symbols_total(self) -> int:
        """Get total number of symbols."""
        self._check_initialized()
        return self._call("symbols_total")

    def get_symbols(self, group: str | None = None) -> list[dict[str, Any]]:
        """Get list of available symbols."""
        self._check_initialized()

        def _get():
            if group:
                symbols = self._call("symbols_get", group=group)
            else:
                symbols = self._call("symbols_get")
            return symbols

        symbols = _get()
        if symbols is None:
            raise MT5Error("symbols_get failed")
        return [s._asdict() for s in symbols]

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Get symbol specification."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        info = self._call("symbol_info", symbol)
        if info is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get symbol info for {symbol}: {error}")
        return info._asdict()

    def get_symbol_tick(self, symbol: str) -> dict[str, Any]:
        """Get current tick for a symbol."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        tick = self._call("symbol_info_tick", symbol)
        if tick is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get tick for {symbol}: {error}")
        return tick._asdict()

    def get_ohlc_bars(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Get OHLC bars from a starting position."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        rates = self._call("copy_rates_from_pos", symbol, timeframe, start_pos, count)
        if rates is None:
            error = self.get_last_error()
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

    def get_ohlc_bars_range(
        self, symbol: str, timeframe: int, date_from: datetime, date_to: datetime
    ) -> list[dict[str, Any]]:
        """Get OHLC bars for a date range."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        rates = self._call("copy_rates_range", symbol, timeframe, date_from, date_to)
        if rates is None:
            error = self.get_last_error()
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

    def get_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int = constants.COPY_TICKS_ALL,
    ) -> list[dict[str, Any]]:
        """Get tick data for a date range."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        ticks = self._call("copy_ticks_range", symbol, date_from, date_to, flags)
        if ticks is None:
            error = self.get_last_error()
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

    def get_positions_total(self) -> int:
        """Get total number of open positions."""
        self._check_initialized()
        return self._call("positions_total")

    def get_positions(
        self, symbol: str | None = None, ticket: int | None = None
    ) -> list[dict[str, Any]]:
        """Get open positions."""
        self._check_initialized()

        def _get():
            if ticket:
                return self._call("positions_get", ticket=ticket)
            if symbol:
                return self._call("positions_get", symbol=symbol)
            return self._call("positions_get")

        positions = _get()
        if positions is None:
            raise MT5Error("positions_get failed")
        return [p._asdict() for p in positions]

    def get_orders_total(self) -> int:
        """Get total number of pending orders."""
        self._check_initialized()
        return self._call("orders_total")

    def get_orders(
        self, symbol: str | None = None, ticket: int | None = None
    ) -> list[dict[str, Any]]:
        """Get pending orders."""
        self._check_initialized()

        def _get():
            if ticket:
                return self._call("orders_get", ticket=ticket)
            if symbol:
                return self._call("orders_get", symbol=symbol)
            return self._call("orders_get")

        orders = _get()
        if orders is None:
            raise MT5Error("orders_get failed")
        return [o._asdict() for o in orders]

    def calculate_margin(
        self, action: int, symbol: str, volume: float, price: float
    ) -> float | None:
        """Calculate required margin for an order."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        margin = self._call("order_calc_margin", action, symbol, volume, price)
        return margin

    def calculate_profit(
        self, action: int, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        """Calculate potential profit/loss for a trade."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        profit = self._call("order_calc_profit", action, symbol, volume, price_open, price_close)
        return profit

    def check_order(self, request: dict[str, Any]) -> dict[str, Any]:
        """Check if an order can be placed."""
        self._check_initialized()
        result = self._call("order_check", request)
        if result is None:
            error = self.get_last_error()
            raise MT5Error(f"Order check failed: {error}")
        return result._asdict()

    def send_order(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send once, with a last-moment account check. Never replay on error."""
        self._check_initialized()
        self.verify_account()
        logger.info("Submitting native trading request")
        result = self._call("order_send", request)
        if result is None:
            error = self.get_last_error()
            raise MT5Error(f"Order send failed: {error}")
        result_dict = result._asdict()
        logger.info(
            f"Order result: retcode={result_dict.get('retcode')}, order={result_dict.get('order')}"
        )
        return result_dict

    def login(self, login: int, password: str, server: str, timeout: int | None = None) -> bool:
        """Explicit, exclusive account administration; disabled by default."""
        self._check_initialized()
        if not self.settings.allow_account_switch:
            raise MT5Error(
                "Account switching is disabled; use a separate terminal per account.",
                kind="forbidden",
            )
        if self.settings.expected_login is not None and login != self.settings.expected_login:
            raise MT5Error(
                "Requested account differs from configured account.", kind="account_mismatch"
            )
        if self.settings.expected_server is not None and server != self.settings.expected_server:
            raise MT5Error(
                "Requested broker differs from configured account.", kind="account_mismatch"
            )

        def _login():
            kwargs = {"login": login, "password": password, "server": server}
            if timeout is not None:
                kwargs["timeout"] = timeout
            return self._call("login", **kwargs)

        self._initialized = False
        self.account_generation += 1
        result = _login()
        if not result:
            error = self.get_last_error()
            raise MT5Error(f"Login failed: {error}")
        self._initialized = False
        self._selected_symbols.clear()
        self._pin_account(required_identity=(login, server))
        self._initialized = True
        return True

    def get_ohlc_bars_from(
        self, symbol: str, timeframe: int, date_from: datetime, count: int
    ) -> list[dict[str, Any]]:
        """Get OHLC bars from a starting date."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        rates = self._call("copy_rates_from", symbol, timeframe, date_from, count)
        if rates is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get OHLC bars from date: {error}")
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

    def get_ticks_from(
        self, symbol: str, date_from: datetime, count: int, flags: int = constants.COPY_TICKS_ALL
    ) -> list[dict[str, Any]]:
        """Get tick data from a starting date."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        ticks = self._call("copy_ticks_from", symbol, date_from, count, flags)
        if ticks is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get ticks from date: {error}")
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

    def market_book_add(self, symbol: str) -> bool:
        """Subscribe to Market Depth (DOM) updates for a symbol."""
        self._check_initialized()
        self._ensure_symbol_selected(symbol)
        result = self._call("market_book_add", symbol)
        if not result:
            error = self.get_last_error()
            raise MT5Error(f"Failed to subscribe to market depth for {symbol}: {error}")
        return True

    def market_book_get(self, symbol: str) -> list[dict[str, Any]]:
        """Get Market Depth (DOM) entries for a symbol."""
        self._check_initialized()
        entries = self._call("market_book_get", symbol)
        if entries is None:
            error = self.get_last_error()
            raise MT5Error(f"Failed to get market depth for {symbol}: {error}")
        return [e._asdict() for e in entries]

    def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from Market Depth (DOM) updates for a symbol."""
        self._check_initialized()
        result = self._call("market_book_release", symbol)
        if not result:
            error = self.get_last_error()
            raise MT5Error(f"Failed to unsubscribe from market depth for {symbol}: {error}")
        return True

    def select_symbol(self, symbol: str, enable: bool = True) -> bool:
        """Add or remove a symbol from the MarketWatch window."""
        self._check_initialized()
        result = self._call("symbol_select", symbol, enable)
        if not result:
            error = self.get_last_error()
            action = "select" if enable else "deselect"
            raise MT5Error(f"Failed to {action} symbol {symbol}: {error}")
        if enable:
            self._selected_symbols.add(symbol)
        else:
            self._selected_symbols.discard(symbol)
        return True

    def get_history_orders_total(self, date_from: datetime, date_to: datetime) -> int:
        """Get total number of historical orders."""
        self._check_initialized()
        return self._call("history_orders_total", date_from, date_to)

    def get_history_orders(
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
                return self._call("history_orders_get", ticket=ticket)
            if position:
                return self._call("history_orders_get", position=position)
            if symbol:
                return self._call("history_orders_get", date_from, date_to, group=f"*{symbol}*")
            return self._call("history_orders_get", date_from, date_to)

        orders = _get()
        if orders is None:
            raise MT5Error("orders_get failed")
        return [o._asdict() for o in orders]

    def get_history_deals_total(self, date_from: datetime, date_to: datetime) -> int:
        """Get total number of historical deals."""
        self._check_initialized()
        return self._call("history_deals_total", date_from, date_to)

    def get_history_deals(
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
                return self._call("history_deals_get", ticket=ticket)
            if position:
                return self._call("history_deals_get", position=position)
            if symbol:
                return self._call("history_deals_get", date_from, date_to, group=f"*{symbol}*")
            return self._call("history_deals_get", date_from, date_to)

        deals = _get()
        if deals is None:
            raise MT5Error("history_deals_get failed")
        return [d._asdict() for d in deals]

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if self.api is None:
            raise MT5Error(
                "MetaTrader5 requires Windows x86-64 and a configured terminal.",
                kind="platform_unavailable",
            )
        try:
            result = getattr(self.api, name)(*args, **kwargs)
        except Exception:
            if name == "order_send":
                raise MT5Error(
                    "Native order submission raised an exception; outcome is unknown. Reconcile before retrying.",
                    kind="uncertain_trade",
                    outcome_unknown=True,
                ) from None
            raise

        if name not in {"shutdown", "last_error"} and (result is None or result is False):
            code, detail = self.api.last_error()
            # Capture last_error on this same owner thread before another native call.
            raise MT5Error(
                f"MT5 {name} failed: {detail}"
                + (
                    ". Submission outcome is unknown; reconcile before retrying."
                    if name == "order_send"
                    else ""
                ),
                error_code=code,
                outcome_unknown=name == "order_send",
            )
        if name.endswith("_total") and isinstance(result, int) and result < 0:
            code, detail = self.api.last_error()
            raise MT5Error(
                f"MT5 {name} failed: {detail}"
                + (
                    ". Submission outcome is unknown; reconcile before retrying."
                    if name == "order_send"
                    else ""
                ),
                error_code=code,
                outcome_unknown=name == "order_send",
            )
        if name in {
            "symbols_get",
            "positions_get",
            "orders_get",
            "history_orders_get",
            "history_deals_get",
            "copy_rates_from_pos",
            "copy_rates_from",
            "copy_rates_range",
            "copy_ticks_from",
            "copy_ticks_range",
        }:
            if not isinstance(result, Sized):
                raise MT5Error("Unexpected native collection result", kind="invalid_native_result")
            if len(result) > self.settings.max_rows:
                raise MT5Error(
                    "Result exceeds MT5_MAX_ROWS; request a smaller range.", kind="result_too_large"
                )
        return result

    def _pin_account(self, required_identity: tuple[int, str] | None = None) -> None:
        info = self._call("account_info")
        if self.settings.expected_login is not None and info.login != self.settings.expected_login:
            raise MT5Error(
                "Connected account differs from MT5_EXPECTED_LOGIN.", kind="account_mismatch"
            )
        if (
            self.settings.expected_server is not None
            and info.server != self.settings.expected_server
        ):
            raise MT5Error(
                "Connected broker differs from MT5_EXPECTED_SERVER.", kind="account_mismatch"
            )

        if required_identity is not None and required_identity != (info.login, info.server):
            raise MT5Error(
                "Terminal did not remain on the requested login and broker.",
                kind="account_mismatch",
            )
        self.account_identity = (info.login, info.server)
        self.account_generation += 1

    def verify_account(self) -> None:
        self._check_initialized()
        info = self._call("account_info")
        if self.account_identity != (info.login, info.server):
            raise MT5Error(
                "Terminal account changed outside this server. Restore it or restart deliberately.",
                kind="account_mismatch",
            )
