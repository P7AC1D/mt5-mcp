"""Order management tools including trade execution."""

from typing import Any

import MetaTrader5 as mt5
from mcp.types import Tool, ToolAnnotations

from ..mt5_client import MT5Client

# Order type mapping
ORDER_TYPES = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
    "BUY_STOP_LIMIT": mt5.ORDER_TYPE_BUY_STOP_LIMIT,
    "SELL_STOP_LIMIT": mt5.ORDER_TYPE_SELL_STOP_LIMIT,
}

# Trade action mapping
TRADE_ACTIONS = {
    "DEAL": mt5.TRADE_ACTION_DEAL,
    "PENDING": mt5.TRADE_ACTION_PENDING,
    "SLTP": mt5.TRADE_ACTION_SLTP,
    "MODIFY": mt5.TRADE_ACTION_MODIFY,
    "REMOVE": mt5.TRADE_ACTION_REMOVE,
    "CLOSE_BY": mt5.TRADE_ACTION_CLOSE_BY,
}

# Return code descriptions
RETURN_CODES = {
    10009: "TRADE_RETCODE_DONE - Request completed",
    10008: "TRADE_RETCODE_PLACED - Order placed",
    10010: "TRADE_RETCODE_DONE_PARTIAL - Request partially completed",
    10006: "TRADE_RETCODE_REJECT - Request rejected",
    10007: "TRADE_RETCODE_CANCEL - Request canceled by trader",
    10004: "TRADE_RETCODE_REQUOTE - Requote",
    10013: "TRADE_RETCODE_INVALID - Invalid request",
    10014: "TRADE_RETCODE_INVALID_VOLUME - Invalid volume",
    10015: "TRADE_RETCODE_INVALID_PRICE - Invalid price",
    10016: "TRADE_RETCODE_INVALID_STOPS - Invalid stops",
    10017: "TRADE_RETCODE_TRADE_DISABLED - Trade disabled",
    10018: "TRADE_RETCODE_MARKET_CLOSED - Market closed",
    10019: "TRADE_RETCODE_NO_MONEY - Insufficient funds",
    10020: "TRADE_RETCODE_PRICE_CHANGED - Price changed",
    10021: "TRADE_RETCODE_PRICE_OFF - No prices",
    10022: "TRADE_RETCODE_INVALID_EXPIRATION - Invalid expiration",
    10023: "TRADE_RETCODE_ORDER_CHANGED - Order state changed",
    10024: "TRADE_RETCODE_TOO_MANY_REQUESTS - Too many requests",
}

ORDER_TOOLS: list[Tool] = [
    Tool(
        name="get_pending_orders",
        description=(
            "Get all pending (unfilled) orders. Optionally filter by symbol or ticket number."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol name",
                },
                "ticket": {
                    "type": "integer",
                    "description": "Filter by specific order ticket",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="calculate_margin",
        description=(
            "Calculate the required margin for a potential order. "
            "Use this to check if you have sufficient margin before placing a trade."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["BUY", "SELL"],
                    "description": "Trade direction",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol name",
                },
                "volume": {
                    "type": "number",
                    "description": "Trade volume in lots",
                },
                "price": {
                    "type": "number",
                    "description": "Entry price",
                },
            },
            "required": ["action", "symbol", "volume", "price"],
        },
    ),
    Tool(
        name="calculate_profit",
        description=(
            "Calculate the potential profit/loss for a trade at a given exit price. "
            "Use this to assess risk/reward before entering a position."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["BUY", "SELL"],
                    "description": "Trade direction",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol name",
                },
                "volume": {
                    "type": "number",
                    "description": "Trade volume in lots",
                },
                "price_open": {
                    "type": "number",
                    "description": "Entry price",
                },
                "price_close": {
                    "type": "number",
                    "description": "Exit price to calculate profit at",
                },
            },
            "required": ["action", "symbol", "volume", "price_open", "price_close"],
        },
    ),
    Tool(
        name="check_order",
        description=(
            "Validate an order before sending it. Returns margin requirements and "
            "checks if the order would be accepted. Use this before send_order."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name",
                },
                "order_type": {
                    "type": "string",
                    "enum": ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"],
                    "description": "Order type",
                },
                "volume": {
                    "type": "number",
                    "description": "Volume in lots",
                },
                "price": {
                    "type": "number",
                    "description": "Order price (use 0 for market orders)",
                },
                "sl": {
                    "type": "number",
                    "description": "Stop loss price (optional)",
                },
                "tp": {
                    "type": "number",
                    "description": "Take profit price (optional)",
                },
            },
            "required": ["symbol", "order_type", "volume", "price"],
        },
    ),
    Tool(
        name="send_order",
        description=(
            "⚠️ EXECUTE A REAL TRADE ORDER. This will place an actual order on your trading account. "
            "Use check_order first to validate. Supports market orders, limit orders, and stop orders. "
            "Can also modify existing positions (SL/TP) or close positions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["DEAL", "PENDING", "SLTP", "MODIFY", "REMOVE", "CLOSE_BY"],
                    "description": "Trade action: DEAL for market orders, PENDING for limit/stop orders, SLTP to modify stops",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol name",
                },
                "order_type": {
                    "type": "string",
                    "enum": ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"],
                    "description": "Order type",
                },
                "volume": {
                    "type": "number",
                    "description": "Volume in lots",
                },
                "price": {
                    "type": "number",
                    "description": "Order price (0 for market orders uses current price)",
                },
                "sl": {
                    "type": "number",
                    "description": "Stop loss price (optional)",
                },
                "tp": {
                    "type": "number",
                    "description": "Take profit price (optional)",
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
                "position": {
                    "type": "integer",
                    "description": "Position ticket (for closing/modifying existing positions)",
                },
                "order": {
                    "type": "integer",
                    "description": "Order ticket (for modifying/removing pending orders)",
                },
            },
            "required": ["action", "symbol", "order_type", "volume"],
        },
        # Mark as destructive - clients should prompt for confirmation
        annotations=ToolAnnotations(
            destructiveHint=True,
            idempotentHint=False,
        ),
    ),
]


async def handle_order_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle order-related tool calls."""

    if name == "get_pending_orders":
        orders = await client.get_orders(
            symbol=arguments.get("symbol"),
            ticket=arguments.get("ticket"),
        )
        return {
            "count": len(orders),
            "orders": [
                {
                    "ticket": o.get("ticket"),
                    "symbol": o.get("symbol"),
                    "type": _get_order_type_name(o.get("type")),
                    "volume_initial": o.get("volume_initial"),
                    "volume_current": o.get("volume_current"),
                    "price_open": o.get("price_open"),
                    "price_current": o.get("price_current"),
                    "sl": o.get("sl"),
                    "tp": o.get("tp"),
                    "time_setup": o.get("time_setup"),
                    "time_expiration": o.get("time_expiration"),
                    "comment": o.get("comment"),
                    "magic": o.get("magic"),
                }
                for o in orders
            ],
        }

    if name == "calculate_margin":
        action = mt5.ORDER_TYPE_BUY if arguments["action"] == "BUY" else mt5.ORDER_TYPE_SELL
        margin = await client.calculate_margin(
            action=action,
            symbol=arguments["symbol"],
            volume=arguments["volume"],
            price=arguments["price"],
        )
        return {
            "symbol": arguments["symbol"],
            "action": arguments["action"],
            "volume": arguments["volume"],
            "price": arguments["price"],
            "margin_required": margin,
        }

    if name == "calculate_profit":
        action = mt5.ORDER_TYPE_BUY if arguments["action"] == "BUY" else mt5.ORDER_TYPE_SELL
        profit = await client.calculate_profit(
            action=action,
            symbol=arguments["symbol"],
            volume=arguments["volume"],
            price_open=arguments["price_open"],
            price_close=arguments["price_close"],
        )
        return {
            "symbol": arguments["symbol"],
            "action": arguments["action"],
            "volume": arguments["volume"],
            "price_open": arguments["price_open"],
            "price_close": arguments["price_close"],
            "potential_profit": profit,
        }

    if name == "check_order":
        request = _build_order_request(arguments, for_check=True)
        result = await client.check_order(request)
        return {
            "valid": result.get("retcode") == 0,
            "retcode": result.get("retcode"),
            "retcode_description": RETURN_CODES.get(result.get("retcode"), "Unknown"),
            "balance": result.get("balance"),
            "equity": result.get("equity"),
            "margin": result.get("margin"),
            "margin_free": result.get("margin_free"),
            "margin_level": result.get("margin_level"),
            "comment": result.get("comment"),
            "request": result.get("request"),
        }

    if name == "send_order":
        request = _build_order_request(arguments, for_check=False)
        result = await client.send_order(request)

        success = result.get("retcode") in (10008, 10009, 10010)
        return {
            "success": success,
            "retcode": result.get("retcode"),
            "retcode_description": RETURN_CODES.get(result.get("retcode"), "Unknown"),
            "order": result.get("order"),
            "deal": result.get("deal"),
            "volume": result.get("volume"),
            "price": result.get("price"),
            "bid": result.get("bid"),
            "ask": result.get("ask"),
            "comment": result.get("comment"),
            "request_id": result.get("request_id"),
        }

    raise ValueError(f"Unknown order tool: {name}")


def _get_order_type_name(order_type: int | None) -> str:
    """Convert order type integer to readable name."""
    type_names = {
        0: "BUY",
        1: "SELL",
        2: "BUY_LIMIT",
        3: "SELL_LIMIT",
        4: "BUY_STOP",
        5: "SELL_STOP",
        6: "BUY_STOP_LIMIT",
        7: "SELL_STOP_LIMIT",
    }
    return type_names.get(order_type, f"UNKNOWN({order_type})")


def _build_order_request(arguments: dict[str, Any], for_check: bool) -> dict[str, Any]:
    """Build MT5 order request from tool arguments."""
    order_type = ORDER_TYPES.get(arguments["order_type"])
    if order_type is None:
        raise ValueError(f"Invalid order type: {arguments['order_type']}")

    action = TRADE_ACTIONS.get(arguments.get("action", "DEAL"), mt5.TRADE_ACTION_DEAL)

    request = {
        "action": action,
        "symbol": arguments["symbol"],
        "volume": float(arguments["volume"]),
        "type": order_type,
        "deviation": arguments.get("deviation", 20),
        "magic": arguments.get("magic", 0),
        "comment": arguments.get("comment", "")[:31],  # Max 31 chars
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Add price if specified
    if "price" in arguments and arguments["price"]:
        request["price"] = float(arguments["price"])

    # Add stop loss if specified
    if "sl" in arguments and arguments["sl"]:
        request["sl"] = float(arguments["sl"])

    # Add take profit if specified
    if "tp" in arguments and arguments["tp"]:
        request["tp"] = float(arguments["tp"])

    # Add position ticket for modifications
    if "position" in arguments and arguments["position"]:
        request["position"] = int(arguments["position"])

    # Add order ticket for pending order modifications
    if "order" in arguments and arguments["order"]:
        request["order"] = int(arguments["order"])

    return request
