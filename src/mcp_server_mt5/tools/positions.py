"""Position management tools."""

from typing import Any

import MetaTrader5 as mt5
from mcp.types import Tool, ToolAnnotations

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
    Tool(
        name="close_position",
        description=(
            "⚠️ CLOSE an open trading position by ticket number. Sends a market order in the "
            "opposite direction to close the position. Supports partial close via the volume parameter. "
            "Uses the current bid (for closing BUY) or ask (for closing SELL) price."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket": {
                    "type": "integer",
                    "description": "Position ticket number to close",
                },
                "volume": {
                    "type": "number",
                    "description": "Volume to close in lots. If omitted, closes the full position.",
                },
                "deviation": {
                    "type": "integer",
                    "description": "Maximum price deviation in points (default: 20)",
                    "default": 20,
                },
                "magic": {
                    "type": "integer",
                    "description": "Expert Advisor ID (magic number) for tracking",
                    "default": 0,
                },
                "comment": {
                    "type": "string",
                    "description": "Order comment (max 31 characters)",
                    "default": "",
                },
            },
            "required": ["ticket"],
        },
        annotations=ToolAnnotations(
            destructiveHint=True,
            idempotentHint=False,
        ),
    ),
    Tool(
        name="modify_position",
        description=(
            "⚠️ MODIFY the Stop Loss and/or Take Profit of an open position. "
            "Set sl or tp to 0 to remove an existing stop level."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket": {
                    "type": "integer",
                    "description": "Position ticket number to modify",
                },
                "sl": {
                    "type": "number",
                    "description": "New stop loss price (0 to remove)",
                },
                "tp": {
                    "type": "number",
                    "description": "New take profit price (0 to remove)",
                },
            },
            "required": ["ticket"],
        },
        annotations=ToolAnnotations(
            destructiveHint=True,
            idempotentHint=True,
        ),
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

    if name == "close_position":
        ticket = arguments["ticket"]

        # Fetch the position to get symbol, type, and volume
        positions = await client.get_positions(ticket=ticket)
        if not positions:
            raise ValueError(f"Position with ticket {ticket} not found")
        position = positions[0]

        position_type = position.get("type")  # 0=BUY, 1=SELL
        symbol = position.get("symbol")
        full_volume = position.get("volume")
        close_volume = arguments.get("volume", full_volume)

        # Determine opposite order type and price
        if position_type == 0:  # BUY position → close with SELL at bid
            close_type = mt5.ORDER_TYPE_SELL
            tick = await client.get_symbol_tick(symbol)
            price = tick["bid"]
        else:  # SELL position → close with BUY at ask
            close_type = mt5.ORDER_TYPE_BUY
            tick = await client.get_symbol_tick(symbol)
            price = tick["ask"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(close_volume),
            "type": close_type,
            "price": price,
            "position": ticket,
            "deviation": arguments.get("deviation", 20),
            "magic": arguments.get("magic", 0),
            "comment": arguments.get("comment", "")[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = await client.send_order(request)
        success = result.get("retcode") in (10008, 10009, 10010)
        return {
            "success": success,
            "retcode": result.get("retcode"),
            "order": result.get("order"),
            "deal": result.get("deal"),
            "volume": result.get("volume"),
            "price": result.get("price"),
            "comment": result.get("comment"),
        }

    if name == "modify_position":
        ticket = arguments["ticket"]

        # Fetch the position to get its symbol
        positions = await client.get_positions(ticket=ticket)
        if not positions:
            raise ValueError(f"Position with ticket {ticket} not found")
        position = positions[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.get("symbol"),
            "position": ticket,
            "sl": float(arguments.get("sl", position.get("sl", 0.0))),
            "tp": float(arguments.get("tp", position.get("tp", 0.0))),
        }

        result = await client.send_order(request)
        success = result.get("retcode") in (10008, 10009, 10010)
        return {
            "success": success,
            "retcode": result.get("retcode"),
            "order": result.get("order"),
            "comment": result.get("comment"),
        }

    raise ValueError(f"Unknown position tool: {name}")
