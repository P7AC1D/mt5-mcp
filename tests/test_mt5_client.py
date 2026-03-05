"""Tests for MT5 client wrapper."""

from datetime import datetime

import pytest

from mcp_server_mt5.mt5_client import MT5Client, MT5Error


class TestMT5ClientInitialization:
    """Tests for MT5 client initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_mt5_module, mock_settings):
        """Test successful MT5 initialization."""
        mock_mt5_module.initialize.return_value = True

        client = MT5Client(mock_settings)
        result = await client.initialize()

        assert result is True
        mock_mt5_module.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self, mock_mt5_module, mock_settings):
        """Test MT5 initialization failure."""
        mock_mt5_module.initialize.return_value = False
        mock_mt5_module.last_error.return_value = (-1, "Connection failed")

        client = MT5Client(mock_settings)

        with pytest.raises(MT5Error) as exc_info:
            await client.initialize()

        assert "initialization failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_mt5_module, mock_settings):
        """Test MT5 shutdown."""
        mock_mt5_module.initialize.return_value = True

        client = MT5Client(mock_settings)
        await client.initialize()
        await client.shutdown()

        mock_mt5_module.shutdown.assert_called_once()


class TestMT5ClientAccountInfo:
    """Tests for account info retrieval."""

    @pytest.mark.asyncio
    async def test_get_account_info(self, mock_mt5_client, mock_account_info):
        """Test getting account information."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.account_info.return_value = mock_account_info

        info = await client.get_account_info()

        assert info["login"] == 12345678
        assert info["balance"] == 10000.0
        assert info["equity"] == 10500.0

    @pytest.mark.asyncio
    async def test_get_account_info_not_initialized(self, mock_settings):
        """Test account info fails when not initialized."""
        client = MT5Client(mock_settings)

        with pytest.raises(MT5Error) as exc_info:
            await client.get_account_info()

        assert "not initialized" in str(exc_info.value)


class TestMT5ClientSymbols:
    """Tests for symbol operations."""

    @pytest.mark.asyncio
    async def test_get_symbol_info(self, mock_mt5_client, mock_symbol_info):
        """Test getting symbol information."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_select.return_value = True

        info = await client.get_symbol_info("EURUSD")

        assert info["name"] == "EURUSD"
        assert info["digits"] == 5

    @pytest.mark.asyncio
    async def test_get_symbol_tick(self, mock_mt5_client, mock_tick, mock_symbol_info):
        """Test getting symbol tick."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_info_tick.return_value = mock_tick

        tick = await client.get_symbol_tick("EURUSD")

        assert tick["bid"] == 1.10000
        assert tick["ask"] == 1.10010

    @pytest.mark.asyncio
    async def test_auto_select_symbol(self, mock_mt5_client, mock_symbol_info, mock_tick):
        """Test that symbols are auto-selected when needed."""
        client, mock_mt5 = mock_mt5_client

        # Symbol not visible initially
        not_visible_info = mock_symbol_info._replace(visible=False)
        mock_mt5.symbol_info.return_value = not_visible_info
        mock_mt5.symbol_select.return_value = True
        mock_mt5.symbol_info_tick.return_value = mock_tick

        await client.get_symbol_tick("EURUSD")

        # Should have called symbol_select to add to MarketWatch
        mock_mt5.symbol_select.assert_called_with("EURUSD", True)


class TestMT5ClientPositions:
    """Tests for position operations."""

    @pytest.mark.asyncio
    async def test_get_positions(self, mock_mt5_client, mock_position):
        """Test getting open positions."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = [mock_position]

        positions = await client.get_positions()

        assert len(positions) == 1
        assert positions[0]["symbol"] == "EURUSD"
        assert positions[0]["profit"] == 50.0

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, mock_mt5_client):
        """Test getting positions when none exist."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = None

        positions = await client.get_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_get_positions_count(self, mock_mt5_client):
        """Test getting positions count."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_total.return_value = 5

        count = await client.get_positions_total()

        assert count == 5


class TestMT5ClientLogin:
    """Tests for login functionality."""

    @pytest.mark.asyncio
    async def test_login_success(self, mock_mt5_client):
        """Test successful login."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.login.return_value = True

        result = await client.login(
            login=99999999,
            password="pass123",
            server="TestServer-Demo",
        )

        assert result is True
        mock_mt5.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_failure(self, mock_mt5_client):
        """Test failed login."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.login.return_value = False

        with pytest.raises(MT5Error, match="Login failed"):
            await client.login(
                login=99999999,
                password="wrong",
                server="TestServer-Demo",
            )

    @pytest.mark.asyncio
    async def test_login_with_timeout(self, mock_mt5_client):
        """Test login with custom timeout."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.login.return_value = True

        await client.login(
            login=99999999,
            password="pass123",
            server="TestServer-Demo",
            timeout=30000,
        )

        call_kwargs = mock_mt5.login.call_args[1]
        assert call_kwargs["timeout"] == 30000


class TestMT5ClientTerminalInfo:
    """Tests for terminal info retrieval."""

    @pytest.mark.asyncio
    async def test_get_terminal_info(self, mock_mt5_client, mock_terminal_info):
        """Test getting terminal information."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.terminal_info.return_value = mock_terminal_info

        info = await client.get_terminal_info()

        assert info["connected"] is True
        assert info["build"] == 4150
        assert info["company"] == "MetaQuotes"

    @pytest.mark.asyncio
    async def test_get_terminal_info_failure(self, mock_mt5_client):
        """Test terminal info failure."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.terminal_info.return_value = None

        with pytest.raises(MT5Error, match="Failed to get terminal info"):
            await client.get_terminal_info()


class TestMT5ClientMarketDepth:
    """Tests for market depth operations."""

    @pytest.mark.asyncio
    async def test_market_book_add(self, mock_mt5_client, mock_symbol_info):
        """Test subscribing to market depth."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.market_book_add.return_value = True

        result = await client.market_book_add("EURUSD")

        assert result is True
        mock_mt5.market_book_add.assert_called_once_with("EURUSD")

    @pytest.mark.asyncio
    async def test_market_book_add_failure(self, mock_mt5_client, mock_symbol_info):
        """Test failed market depth subscription."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.market_book_add.return_value = False

        with pytest.raises(MT5Error, match="Failed to subscribe"):
            await client.market_book_add("EURUSD")

    @pytest.mark.asyncio
    async def test_market_book_get(self, mock_mt5_client, mock_book_entries):
        """Test getting market depth data."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.market_book_get.return_value = mock_book_entries

        entries = await client.market_book_get("EURUSD")

        assert len(entries) == 4
        assert entries[0]["price"] == 1.10005

    @pytest.mark.asyncio
    async def test_market_book_release(self, mock_mt5_client):
        """Test unsubscribing from market depth."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.market_book_release.return_value = True

        result = await client.market_book_release("EURUSD")

        assert result is True
        mock_mt5.market_book_release.assert_called_once_with("EURUSD")


class TestMT5ClientOHLCBarsFrom:
    """Tests for copy_rates_from wrapper."""

    @pytest.mark.asyncio
    async def test_get_ohlc_bars_from(self, mock_mt5_client, mock_symbol_info):
        """Test getting bars from a start date."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info

        import numpy as np
        mock_rates = np.array(
            [(1704067200, 1.1, 1.102, 1.098, 1.101, 500, 8, 100)],
            dtype=[
                ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8"),
            ],
        )
        mock_mt5.copy_rates_from.return_value = mock_rates

        bars = await client.get_ohlc_bars_from(
            symbol="EURUSD",
            timeframe=1,
            date_from=datetime(2024, 1, 1),
            count=100,
        )

        assert len(bars) == 1
        assert bars[0]["open"] == 1.1
        assert bars[0]["close"] == 1.101


class TestMT5ClientTicksFrom:
    """Tests for copy_ticks_from wrapper."""

    @pytest.mark.asyncio
    async def test_get_ticks_from(self, mock_mt5_client, mock_symbol_info):
        """Test getting ticks from a start date."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info

        import numpy as np
        mock_ticks = np.array(
            [(1704067200, 1.1, 1.1001, 1.1, 100, 1704067200000, 0, 100.0)],
            dtype=[
                ("time", "i8"), ("bid", "f8"), ("ask", "f8"), ("last", "f8"),
                ("volume", "i8"), ("time_msc", "i8"), ("flags", "i4"), ("volume_real", "f8"),
            ],
        )
        mock_mt5.copy_ticks_from.return_value = mock_ticks

        ticks = await client.get_ticks_from(
            symbol="EURUSD",
            date_from=datetime(2024, 1, 1),
            count=1000,
        )

        assert len(ticks) == 1
        assert ticks[0]["bid"] == 1.1
        assert ticks[0]["ask"] == 1.1001


class TestMT5ClientSelectSymbol:
    """Tests for explicit symbol selection."""

    @pytest.mark.asyncio
    async def test_select_symbol_enable(self, mock_mt5_client):
        """Test adding a symbol to MarketWatch."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_select.return_value = True

        result = await client.select_symbol("EURUSD", True)

        assert result is True
        mock_mt5.symbol_select.assert_called_with("EURUSD", True)
        assert "EURUSD" in client._selected_symbols

    @pytest.mark.asyncio
    async def test_select_symbol_disable(self, mock_mt5_client):
        """Test removing a symbol from MarketWatch."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_select.return_value = True
        client._selected_symbols.add("EURUSD")

        result = await client.select_symbol("EURUSD", False)

        assert result is True
        assert "EURUSD" not in client._selected_symbols

    @pytest.mark.asyncio
    async def test_select_symbol_failure(self, mock_mt5_client):
        """Test failed symbol selection."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_select.return_value = False

        with pytest.raises(MT5Error, match="Failed to select"):
            await client.select_symbol("INVALID", True)
