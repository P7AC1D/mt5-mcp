"""MCP Resources for passive MT5 data access."""

import re
from typing import Any

from mcp.types import Resource

from .mt5_client import MT5Client, MT5Error


def register_resources() -> list[Resource]:
    """Register all MT5 resources for passive polling."""
    return [
        Resource(
            uri="mt5://account/info",
            name="Account Information",
            description="Trading account balance, equity, margin, and status",
            mimeType="application/json",
        ),
        Resource(
            uri="mt5://symbols",
            name="Trading Symbols",
            description="List of all available trading symbols",
            mimeType="application/json",
        ),
        Resource(
            uri="mt5://symbols/{symbol}/tick",
            name="Symbol Tick",
            description="Current bid/ask/last price for a trading symbol",
            mimeType="application/json",
        ),
        Resource(
            uri="mt5://symbols/{symbol}/info",
            name="Symbol Information",
            description="Detailed specification for a trading symbol",
            mimeType="application/json",
        ),
        Resource(
            uri="mt5://positions",
            name="Open Positions",
            description="All currently open trading positions",
            mimeType="application/json",
        ),
        Resource(
            uri="mt5://orders",
            name="Pending Orders",
            description="All pending (unfilled) trading orders",
            mimeType="application/json",
        ),
    ]


async def handle_resource_read(client: MT5Client, uri: str) -> Any:
    """Handle reading an MT5 resource by URI."""

    # Account info
    if uri == "mt5://account/info":
        return await client.get_account_info()

    # Symbols list
    if uri == "mt5://symbols":
        symbols = await client.get_symbols()
        # Return simplified list for overview
        return [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "path": s.get("path", ""),
                "visible": s.get("visible", False),
            }
            for s in symbols
        ]

    # Symbol tick - mt5://symbols/{symbol}/tick
    tick_match = re.match(r"mt5://symbols/([^/]+)/tick", uri)
    if tick_match:
        symbol = tick_match.group(1)
        return await client.get_symbol_tick(symbol)

    # Symbol info - mt5://symbols/{symbol}/info
    info_match = re.match(r"mt5://symbols/([^/]+)/info", uri)
    if info_match:
        symbol = info_match.group(1)
        return await client.get_symbol_info(symbol)

    # Positions
    if uri == "mt5://positions":
        positions = await client.get_positions()
        return {
            "count": len(positions),
            "positions": positions,
        }

    # Orders
    if uri == "mt5://orders":
        orders = await client.get_orders()
        return {
            "count": len(orders),
            "orders": orders,
        }

    raise MT5Error(f"Unknown resource URI: {uri}")
