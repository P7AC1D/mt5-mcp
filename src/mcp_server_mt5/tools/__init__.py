"""MT5 MCP Tools - organized by category."""

from typing import Any

from mcp.types import Tool

from ..mt5_client import MT5Client
from .account import ACCOUNT_TOOLS, handle_account_tool
from .history import HISTORY_TOOLS, handle_history_tool
from .market_data import MARKET_DATA_TOOLS, handle_market_data_tool
from .orders import ORDER_TOOLS, handle_order_tool
from .positions import POSITION_TOOLS, handle_position_tool

__all__ = ["get_all_tools", "handle_tool_call"]


def get_all_tools() -> list[Tool]:
    """Get all registered MT5 tools."""
    return [
        *ACCOUNT_TOOLS,
        *MARKET_DATA_TOOLS,
        *POSITION_TOOLS,
        *ORDER_TOOLS,
        *HISTORY_TOOLS,
    ]


# Map tool names to their handlers
_TOOL_HANDLERS = {
    # Account tools
    "get_account_info": ("account", handle_account_tool),
    # Market data tools
    "get_symbols": ("market_data", handle_market_data_tool),
    "get_symbol_info": ("market_data", handle_market_data_tool),
    "get_symbol_tick": ("market_data", handle_market_data_tool),
    "get_ohlc_bars": ("market_data", handle_market_data_tool),
    "get_ohlc_bars_range": ("market_data", handle_market_data_tool),
    "get_ticks_range": ("market_data", handle_market_data_tool),
    # Position tools
    "get_positions": ("positions", handle_position_tool),
    "get_positions_count": ("positions", handle_position_tool),
    # Order tools
    "get_pending_orders": ("orders", handle_order_tool),
    "calculate_margin": ("orders", handle_order_tool),
    "calculate_profit": ("orders", handle_order_tool),
    "check_order": ("orders", handle_order_tool),
    "send_order": ("orders", handle_order_tool),
    # History tools
    "get_history_orders": ("history", handle_history_tool),
    "get_history_deals": ("history", handle_history_tool),
}


async def handle_tool_call(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Route tool call to appropriate handler."""
    if name not in _TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {name}")

    _, handler = _TOOL_HANDLERS[name]
    return await handler(client, name, arguments)
