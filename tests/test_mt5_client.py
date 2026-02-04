"""Tests for MT5 client wrapper."""

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
