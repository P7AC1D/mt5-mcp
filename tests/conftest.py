"""Pytest configuration and fixtures for MT5 MCP Server tests."""

from collections import namedtuple
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from mcp_server_mt5.config import MT5Settings
from mcp_server_mt5.mt5_client import MT5Client


# Named tuples to simulate MT5 API responses
AccountInfo = namedtuple(
    "AccountInfo",
    [
        "login", "name", "server", "currency", "balance", "equity",
        "profit", "margin", "margin_free", "margin_level", "leverage",
        "trade_mode", "limit_orders", "trade_allowed", "trade_expert",
    ],
)

SymbolInfo = namedtuple(
    "SymbolInfo",
    [
        "name", "description", "path", "visible", "spread", "digits",
        "trade_mode", "currency_base", "currency_profit", "currency_margin",
        "point", "trade_tick_size", "trade_tick_value", "volume_min",
        "volume_max", "volume_step", "spread_float", "margin_initial",
        "margin_maintenance", "session_open", "session_close",
    ],
)

TickInfo = namedtuple(
    "TickInfo",
    ["time", "bid", "ask", "last", "volume", "time_msc", "flags", "volume_real"],
)

PositionInfo = namedtuple(
    "PositionInfo",
    [
        "ticket", "symbol", "type", "volume", "price_open", "price_current",
        "sl", "tp", "profit", "swap", "commission", "time", "comment", "magic",
    ],
)

OrderInfo = namedtuple(
    "OrderInfo",
    [
        "ticket", "symbol", "type", "volume_initial", "volume_current",
        "price_open", "price_current", "sl", "tp", "time_setup",
        "time_expiration", "comment", "magic",
    ],
)

OrderCheckResult = namedtuple(
    "OrderCheckResult",
    [
        "retcode", "balance", "equity", "margin", "margin_free",
        "margin_level", "comment", "request",
    ],
)

OrderSendResult = namedtuple(
    "OrderSendResult",
    [
        "retcode", "order", "deal", "volume", "price",
        "bid", "ask", "comment", "request_id",
    ],
)


@pytest.fixture
def mock_account_info():
    """Sample account info response."""
    return AccountInfo(
        login=12345678,
        name="Test Account",
        server="TestServer-Demo",
        currency="USD",
        balance=10000.0,
        equity=10500.0,
        profit=500.0,
        margin=1000.0,
        margin_free=9500.0,
        margin_level=1050.0,
        leverage=100,
        trade_mode=0,
        limit_orders=200,
        trade_allowed=True,
        trade_expert=True,
    )


@pytest.fixture
def mock_symbol_info():
    """Sample symbol info response."""
    return SymbolInfo(
        name="EURUSD",
        description="Euro vs US Dollar",
        path="Forex\\EURUSD",
        visible=True,
        spread=10,
        digits=5,
        trade_mode=0,
        currency_base="EUR",
        currency_profit="USD",
        currency_margin="EUR",
        point=0.00001,
        trade_tick_size=0.00001,
        trade_tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        spread_float=True,
        margin_initial=0,
        margin_maintenance=0,
        session_open=0,
        session_close=86400,
    )


@pytest.fixture
def mock_tick():
    """Sample tick response."""
    return TickInfo(
        time=int(datetime.now().timestamp()),
        bid=1.10000,
        ask=1.10010,
        last=1.10005,
        volume=100,
        time_msc=int(datetime.now().timestamp() * 1000),
        flags=0,
        volume_real=100.0,
    )


@pytest.fixture
def mock_position():
    """Sample position response."""
    return PositionInfo(
        ticket=123456,
        symbol="EURUSD",
        type=0,  # BUY
        volume=0.1,
        price_open=1.09500,
        price_current=1.10000,
        sl=1.09000,
        tp=1.11000,
        profit=50.0,
        swap=-0.5,
        commission=-0.7,
        time=int(datetime.now().timestamp()),
        comment="Test position",
        magic=0,
    )


@pytest.fixture
def mock_settings():
    """Test MT5 settings."""
    return MT5Settings(
        login=12345678,
        password="test_password",
        server="TestServer-Demo",
        path=None,
    )


@pytest_asyncio.fixture
async def mock_mt5_client(mock_settings):
    """Create MT5 client with mocked MT5 module."""
    with patch("mcp_server_mt5.mt5_client.mt5") as mock_mt5:
        # Setup default mocks
        mock_mt5.initialize.return_value = True
        mock_mt5.shutdown.return_value = None
        mock_mt5.last_error.return_value = (0, "No error")

        client = MT5Client(mock_settings)
        await client.initialize()

        yield client, mock_mt5

        await client.shutdown()


@pytest.fixture
def mock_mt5_module():
    """Provide a mock MT5 module for unit tests."""
    with patch("mcp_server_mt5.mt5_client.mt5") as mock_mt5:
        mock_mt5.initialize.return_value = True
        mock_mt5.shutdown.return_value = None
        mock_mt5.last_error.return_value = (0, "No error")
        
        # Timeframe constants
        mock_mt5.TIMEFRAME_M1 = 1
        mock_mt5.TIMEFRAME_M5 = 5
        mock_mt5.TIMEFRAME_M15 = 15
        mock_mt5.TIMEFRAME_M30 = 30
        mock_mt5.TIMEFRAME_H1 = 16385
        mock_mt5.TIMEFRAME_H4 = 16388
        mock_mt5.TIMEFRAME_D1 = 16408
        mock_mt5.TIMEFRAME_W1 = 32769
        mock_mt5.TIMEFRAME_MN1 = 49153
        
        # Order type constants
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.ORDER_TYPE_BUY_LIMIT = 2
        mock_mt5.ORDER_TYPE_SELL_LIMIT = 3
        mock_mt5.ORDER_TYPE_BUY_STOP = 4
        mock_mt5.ORDER_TYPE_SELL_STOP = 5
        
        # Trade action constants
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.TRADE_ACTION_PENDING = 5
        mock_mt5.TRADE_ACTION_SLTP = 6
        mock_mt5.TRADE_ACTION_MODIFY = 7
        mock_mt5.TRADE_ACTION_REMOVE = 8
        mock_mt5.TRADE_ACTION_CLOSE_BY = 10
        
        # Order time/filling constants
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 2
        
        # Copy ticks flags
        mock_mt5.COPY_TICKS_ALL = 1

        yield mock_mt5
