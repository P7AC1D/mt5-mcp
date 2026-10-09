"""Market Depth (DOM / Order Book) tools."""

from typing import Any

from mcp.types import Tool

from ..mt5_client import MT5Client

# Book entry type labels
BOOK_TYPES = {
    1: "SELL",
    2: "BUY",
    3: "SELL_MARKET",
    4: "BUY_MARKET",
}

MARKET_DEPTH_TOOLS: list[Tool] = [
    Tool(
        name="market_book_subscribe",
        description=(
            "Subscribe to Market Depth (DOM / order book) updates for a symbol. "
            "Must be called before market_book_get. Unsubscribe when no longer needed."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to subscribe to (e.g., 'EURUSD')",
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market_book_get",
        description=(
            "Get current Market Depth (DOM / order book) entries for a symbol. "
            "Returns price levels with volumes and types (BUY/SELL). "
            "Requires a prior market_book_subscribe call for the symbol."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD')",
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market_book_unsubscribe",
        description=(
            "Unsubscribe from Market Depth (DOM / order book) updates for a symbol. "
            "Call this when you no longer need depth data to free resources."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to unsubscribe from (e.g., 'EURUSD')",
                },
            },
            "required": ["symbol"],
        },
    ),
]


async def handle_market_depth_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle market depth tool calls."""

    if name == "market_book_subscribe":
        symbol = arguments["symbol"]
        await client.market_book_add(symbol)
        return {"subscribed": True, "symbol": symbol}

    if name == "market_book_get":
        symbol = arguments["symbol"]
        entries = await client.market_book_get(symbol)
        return {
            "symbol": symbol,
            "count": len(entries),
            "entries": [
                {
                    "type": BOOK_TYPES.get(e.get("type"), f"UNKNOWN({e.get('type')})"),
                    "price": e.get("price"),
                    "volume": e.get("volume"),
                    "volume_real": e.get("volume_real"),
                }
                for e in entries
            ],
        }

    if name == "market_book_unsubscribe":
        symbol = arguments["symbol"]
        await client.market_book_release(symbol)
        return {"unsubscribed": True, "symbol": symbol}

    raise ValueError(f"Unknown market depth tool: {name}")
