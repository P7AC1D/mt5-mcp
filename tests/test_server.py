"""Tests for MCP server functionality."""

from collections import namedtuple

import pytest

from mcp_server_mt5.tools import get_all_tools, handle_tool_call
from mcp_server_mt5.resources import register_resources, handle_resource_read


class TestToolRegistration:
    """Tests for tool registration."""

    def test_get_all_tools(self):
        """Test that all tools are registered."""
        tools = get_all_tools()
        tool_names = [t.name for t in tools]

        # Account tools
        assert "get_account_info" in tool_names
        assert "get_terminal_info" in tool_names
        assert "login" in tool_names

        # Market data tools
        assert "get_symbols" in tool_names
        assert "get_symbol_tick" in tool_names
        assert "get_ohlc_bars" in tool_names
        assert "get_ohlc_bars_from" in tool_names
        assert "get_ticks_from" in tool_names
        assert "select_symbol" in tool_names
        assert "get_symbols_count" in tool_names

        # Market depth tools
        assert "market_book_subscribe" in tool_names
        assert "market_book_get" in tool_names
        assert "market_book_unsubscribe" in tool_names

        # Position tools
        assert "get_positions" in tool_names
        assert "close_position" in tool_names
        assert "modify_position" in tool_names

        # Order tools
        assert "get_pending_orders" in tool_names
        assert "get_pending_orders_count" in tool_names
        assert "send_order" in tool_names
        assert "cancel_order" in tool_names
        assert "modify_order" in tool_names

        # History tools
        assert "get_history_deals" in tool_names
        assert "get_history_orders" in tool_names
        assert "get_history_orders_count" in tool_names
        assert "get_history_deals_count" in tool_names

    def test_send_order_has_destructive_hint(self):
        """Test that send_order is marked as destructive."""
        tools = get_all_tools()
        send_order = next(t for t in tools if t.name == "send_order")

        assert send_order.annotations is not None
        assert send_order.annotations.destructiveHint is True
        assert send_order.annotations.idempotentHint is False

    def test_destructive_tools_have_annotations(self):
        """Test that all destructive tools are properly annotated."""
        tools = get_all_tools()
        destructive_tool_names = [
            "send_order", "close_position", "modify_position",
            "cancel_order", "modify_order", "login",
        ]
        for tool_name in destructive_tool_names:
            tool = next(t for t in tools if t.name == tool_name)
            assert tool.annotations is not None, f"{tool_name} missing annotations"
            assert tool.annotations.destructiveHint is True, f"{tool_name} not marked destructive"

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


class TestClosePositionTool:
    """Tests for close_position tool."""

    @pytest.mark.asyncio
    async def test_close_buy_position(self, mock_mt5_client, mock_position, mock_tick, mock_symbol_info):
        """Test closing a BUY position (should sell at bid)."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = [mock_position]  # type=0 (BUY)
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_info_tick.return_value = mock_tick

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=999, deal=888, volume=0.1,
            price=1.10000, bid=1.10000, ask=1.10010, comment="", request_id=1,
        )

        result = await handle_tool_call(client, "close_position", {"ticket": 123456})

        assert result["success"] is True
        # Verify the order was sent with SELL type (opposite of BUY) at bid
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["type"] == 1  # ORDER_TYPE_SELL
        assert sent_request["price"] == mock_tick.bid
        assert sent_request["position"] == 123456

    @pytest.mark.asyncio
    async def test_close_sell_position(self, mock_mt5_client, mock_sell_position, mock_tick, mock_symbol_info):
        """Test closing a SELL position (should buy at ask)."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = [mock_sell_position]  # type=1 (SELL)
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_info_tick.return_value = mock_tick

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=999, deal=888, volume=0.5,
            price=1.10010, bid=1.10000, ask=1.10010, comment="", request_id=1,
        )

        result = await handle_tool_call(client, "close_position", {"ticket": 789012})

        assert result["success"] is True
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["type"] == 0  # ORDER_TYPE_BUY
        assert sent_request["price"] == mock_tick.ask

    @pytest.mark.asyncio
    async def test_close_position_partial(self, mock_mt5_client, mock_position, mock_tick, mock_symbol_info):
        """Test partial close of a position."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = [mock_position]
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.symbol_info_tick.return_value = mock_tick

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=999, deal=888, volume=0.05,
            price=1.10000, bid=1.10000, ask=1.10010, comment="", request_id=1,
        )

        result = await handle_tool_call(
            client, "close_position", {"ticket": 123456, "volume": 0.05}
        )

        assert result["success"] is True
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["volume"] == 0.05

    @pytest.mark.asyncio
    async def test_close_position_not_found(self, mock_mt5_client):
        """Test closing a position that doesn't exist."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await handle_tool_call(client, "close_position", {"ticket": 999999})


class TestModifyPositionTool:
    """Tests for modify_position tool."""

    @pytest.mark.asyncio
    async def test_modify_position_sl_tp(self, mock_mt5_client, mock_position):
        """Test modifying SL and TP on a position."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.positions_get.return_value = [mock_position]

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=0, deal=0, volume=0,
            price=0, bid=0, ask=0, comment="", request_id=1,
        )

        result = await handle_tool_call(
            client, "modify_position", {"ticket": 123456, "sl": 1.08500, "tp": 1.12000}
        )

        assert result["success"] is True
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["action"] == 6  # TRADE_ACTION_SLTP
        assert sent_request["sl"] == 1.08500
        assert sent_request["tp"] == 1.12000


class TestCancelOrderTool:
    """Tests for cancel_order tool."""

    @pytest.mark.asyncio
    async def test_cancel_pending_order(self, mock_mt5_client):
        """Test canceling a pending order."""
        client, mock_mt5 = mock_mt5_client

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=555, deal=0, volume=0,
            price=0, bid=0, ask=0, comment="", request_id=1,
        )

        result = await handle_tool_call(client, "cancel_order", {"order_id": 555})

        assert result["success"] is True
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["action"] == 8  # TRADE_ACTION_REMOVE
        assert sent_request["order"] == 555


class TestModifyOrderTool:
    """Tests for modify_order tool."""

    @pytest.mark.asyncio
    async def test_modify_pending_order(self, mock_mt5_client):
        """Test modifying a pending order."""
        client, mock_mt5 = mock_mt5_client

        from tests.conftest import OrderInfo
        mock_order = OrderInfo(
            ticket=555, symbol="EURUSD", type=2, volume_initial=0.1,
            volume_current=0.1, price_open=1.08000, price_current=1.10000,
            sl=1.07000, tp=1.09000, time_setup=0, time_expiration=0,
            comment="", magic=0,
        )
        mock_mt5.orders_get.return_value = [mock_order]

        OrderResult = namedtuple(
            "OrderResult",
            ["retcode", "order", "deal", "volume", "price", "bid", "ask", "comment", "request_id"],
        )
        mock_mt5.order_send.return_value = OrderResult(
            retcode=10009, order=555, deal=0, volume=0,
            price=0, bid=0, ask=0, comment="", request_id=1,
        )

        result = await handle_tool_call(
            client, "modify_order",
            {"order_id": 555, "price": 1.07500, "sl": 1.06500, "tp": 1.08500},
        )

        assert result["success"] is True
        sent_request = mock_mt5.order_send.call_args[0][0]
        assert sent_request["action"] == 7  # TRADE_ACTION_MODIFY
        assert sent_request["price"] == 1.07500
        assert sent_request["sl"] == 1.06500
        assert sent_request["tp"] == 1.08500

    @pytest.mark.asyncio
    async def test_modify_order_not_found(self, mock_mt5_client):
        """Test modifying a non-existent order."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.orders_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await handle_tool_call(
                client, "modify_order", {"order_id": 999999, "price": 1.0}
            )


class TestMarketDepthTools:
    """Tests for market depth tools."""

    @pytest.mark.asyncio
    async def test_market_book_subscribe(self, mock_mt5_client, mock_symbol_info):
        """Test subscribing to market depth."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_info.return_value = mock_symbol_info
        mock_mt5.market_book_add.return_value = True

        result = await handle_tool_call(
            client, "market_book_subscribe", {"symbol": "EURUSD"}
        )

        assert result["subscribed"] is True
        assert result["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_market_book_get(self, mock_mt5_client, mock_book_entries):
        """Test getting market depth data."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.market_book_get.return_value = mock_book_entries

        result = await handle_tool_call(
            client, "market_book_get", {"symbol": "EURUSD"}
        )

        assert result["count"] == 4
        assert result["entries"][0]["type"] == "BUY"
        assert result["entries"][2]["type"] == "SELL"

    @pytest.mark.asyncio
    async def test_market_book_unsubscribe(self, mock_mt5_client):
        """Test unsubscribing from market depth."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.market_book_release.return_value = True

        result = await handle_tool_call(
            client, "market_book_unsubscribe", {"symbol": "EURUSD"}
        )

        assert result["unsubscribed"] is True


class TestTerminalInfoTool:
    """Tests for terminal info tool."""

    @pytest.mark.asyncio
    async def test_get_terminal_info(self, mock_mt5_client, mock_terminal_info):
        """Test getting terminal info via tool."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.terminal_info.return_value = mock_terminal_info

        result = await handle_tool_call(client, "get_terminal_info", {})

        assert result["connected"] is True
        assert result["build"] == 4150
        assert result["company"] == "MetaQuotes"


class TestLoginTool:
    """Tests for login tool."""

    @pytest.mark.asyncio
    async def test_login_success(self, mock_mt5_client):
        """Test successful login via tool."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.login.return_value = True

        result = await handle_tool_call(
            client, "login",
            {"login": 99999999, "password": "pass", "server": "Demo"},
        )

        assert result["success"] is True
        assert result["login"] == 99999999


class TestHistoryCountTools:
    """Tests for history count tools."""

    @pytest.mark.asyncio
    async def test_get_history_orders_count(self, mock_mt5_client):
        """Test getting history orders count."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.history_orders_total.return_value = 42

        result = await handle_tool_call(client, "get_history_orders_count", {})

        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_get_history_deals_count(self, mock_mt5_client):
        """Test getting history deals count."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.history_deals_total.return_value = 100

        result = await handle_tool_call(client, "get_history_deals_count", {})

        assert result["count"] == 100


class TestSelectSymbolTool:
    """Tests for select_symbol tool."""

    @pytest.mark.asyncio
    async def test_select_symbol(self, mock_mt5_client):
        """Test selecting a symbol in MarketWatch."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_select.return_value = True

        result = await handle_tool_call(
            client, "select_symbol", {"symbol": "EURUSD", "enable": True}
        )

        assert result["status"] == "success"
        assert result["action"] == "added to"

    @pytest.mark.asyncio
    async def test_deselect_symbol(self, mock_mt5_client):
        """Test removing a symbol from MarketWatch."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbol_select.return_value = True
        client._selected_symbols.add("EURUSD")

        result = await handle_tool_call(
            client, "select_symbol", {"symbol": "EURUSD", "enable": False}
        )

        assert result["action"] == "removed from"


class TestGetSymbolsCountTool:
    """Tests for get_symbols_count tool."""

    @pytest.mark.asyncio
    async def test_get_symbols_count(self, mock_mt5_client):
        """Test getting total symbols count."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.symbols_total.return_value = 500

        result = await handle_tool_call(client, "get_symbols_count", {})

        assert result["count"] == 500


class TestGetPendingOrdersCountTool:
    """Tests for get_pending_orders_count tool."""

    @pytest.mark.asyncio
    async def test_get_pending_orders_count(self, mock_mt5_client):
        """Test getting pending orders count."""
        client, mock_mt5 = mock_mt5_client
        mock_mt5.orders_total.return_value = 3

        result = await handle_tool_call(client, "get_pending_orders_count", {})

        assert result["count"] == 3


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
