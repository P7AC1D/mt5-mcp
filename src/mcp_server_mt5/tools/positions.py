"""Position management tools."""

from typing import Any

from mcp.types import Tool

from ..mt5_client import MT5Client

POSITION_TOOLS: list[Tool] = [
    Tool(
        name="get_positions",
        description=(
            "Get all open trading positions. Optionally filter by symbol or ticket number. "
            "Returns position details including entry price, current profit, volume, and type."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol name (e.g., 'EURUSD')",
                },
                "ticket": {
                    "type": "integer",
                    "description": "Filter by specific position ticket number",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_positions_count",
        description="Get the total number of open positions.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


async def handle_position_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle position-related tool calls."""

    if name == "get_positions":
        positions = await client.get_positions(
            symbol=arguments.get("symbol"),
            ticket=arguments.get("ticket"),
        )
        return {
            "count": len(positions),
            "positions": [
                {
                    "ticket": p.get("ticket"),
                    "symbol": p.get("symbol"),
                    "type": "BUY" if p.get("type") == 0 else "SELL",
                    "volume": p.get("volume"),
                    "price_open": p.get("price_open"),
                    "price_current": p.get("price_current"),
                    "sl": p.get("sl"),
                    "tp": p.get("tp"),
                    "profit": p.get("profit"),
                    "swap": p.get("swap"),
                    "commission": p.get("commission"),
                    "time": p.get("time"),
                    "comment": p.get("comment"),
                    "magic": p.get("magic"),
                }
                for p in positions
            ],
        }

    if name == "get_positions_count":
        count = await client.get_positions_total()
        return {"count": count}

    raise ValueError(f"Unknown position tool: {name}")
