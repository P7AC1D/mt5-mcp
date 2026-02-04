"""Tests for MCP server functionality."""

import pytest

from mcp_server_mt5.tools import get_all_tools, handle_tool_call
from mcp_server_mt5.resources import register_resources, handle_resource_read


class TestToolRegistration:
    """Tests for tool registration."""

    def test_get_all_tools(self):
        """Test that all tools are registered."""
        tools = get_all_tools()

        # Check we have tools from each category
        tool_names = [t.name for t in tools]

        assert "get_account_info" in tool_names
        assert "get_symbols" in tool_names
        assert "get_symbol_tick" in tool_names
        assert "get_ohlc_bars" in tool_names
        assert "get_positions" in tool_names
        assert "get_pending_orders" in tool_names
        assert "send_order" in tool_names
        assert "get_history_deals" in tool_names

    def test_send_order_has_destructive_hint(self):
        """Test that send_order is marked as destructive."""
        tools = get_all_tools()
        send_order = next(t for t in tools if t.name == "send_order")

        assert send_order.annotations is not None
        assert send_order.annotations.destructiveHint is True
        assert send_order.annotations.idempotentHint is False

    def test_tools_have_descriptions(self):
        """Test that all tools have descriptions."""
        tools = get_all_tools()

        for tool in tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 20, f"Tool {tool.name} description too short"

    def test_tools_have_input_schemas(self):
        """Test that all tools have input schemas."""
        tools = get_all_tools()

        for tool in tools:
            assert tool.inputSchema is not None, f"Tool {tool.name} missing inputSchema"
            assert tool.inputSchema.get("type") == "object"


class TestResourceRegistration:
    """Tests for resource registration."""

    def test_register_resources(self):
        """Test that all resources are registered."""
        resources = register_resources()

        uris = [str(r.uri) for r in resources]

        assert "mt5://account/info" in uris
        assert "mt5://symbols" in uris
        assert "mt5://symbols/%7Bsymbol%7D/tick" in uris  # URL-encoded {symbol}
        assert "mt5://symbols/%7Bsymbol%7D/info" in uris
        assert "mt5://positions" in uris
        assert "mt5://orders" in uris

    def test_resources_have_metadata(self):
        """Test that all resources have proper metadata."""
        resources = register_resources()

        for resource in resources:
            assert resource.name, f"Resource {resource.uri} missing name"
            assert resource.description, f"Resource {resource.uri} missing description"
            assert resource.mimeType == "application/json"


class TestToolHandling:
    """Tests for tool call handling."""

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, mock_mt5_client):
        """Test handling of unknown tool name."""
        client, _ = mock_mt5_client

        with pytest.raises(ValueError) as exc_info:
            await handle_tool_call(client, "unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_get_account_info(self, mock_mt5_client, mock_account_info):
        """Test handling get_account_info tool."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.account_info.return_value = mock_account_info

        result = await handle_tool_call(client, "get_account_info", {})

        assert result["balance"] == 10000.0
        assert result["equity"] == 10500.0


class TestResourceHandling:
    """Tests for resource read handling."""

    @pytest.mark.asyncio
    async def test_handle_account_resource(self, mock_mt5_client, mock_account_info):
        """Test reading account info resource."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.account_info.return_value = mock_account_info

        result = await handle_resource_read(client, "mt5://account/info")

        assert result["balance"] == 10000.0

    @pytest.mark.asyncio
    async def test_handle_symbol_tick_resource(
        self, mock_mt5_client, mock_tick, mock_symbol_info
    ):
        """Test reading symbol tick resource."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_info_tick.return_value = mock_tick

        result = await handle_resource_read(client, "mt5://symbols/EURUSD/tick")

        assert result["bid"] == 1.10000
        assert result["ask"] == 1.10010

    @pytest.mark.asyncio
    async def test_handle_unknown_resource(self, mock_mt5_client):
        """Test handling of unknown resource URI."""
        client, _ = mock_mt5_client

        from mcp_server_mt5.mt5_client import MT5Error

        with pytest.raises(MT5Error) as exc_info:
            await handle_resource_read(client, "mt5://unknown/resource")

        assert "Unknown resource" in str(exc_info.value)
