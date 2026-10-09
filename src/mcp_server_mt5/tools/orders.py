"""Order management tools including trade execution."""

from typing import Any

from mcp.types import Tool, ToolAnnotations

from .. import constants as mt5
from ..mt5_client import MT5Client
from ..validation import parse_utc

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
        input_schema={
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
        name="get_orders",
        description=(
            "Get all pending (unfilled) orders. Optionally filter by symbol or ticket number."
        ),
        input_schema={
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
        input_schema={
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
        input_schema={
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
        input_schema={
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
        input_schema={
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
            destructive_hint=True,
            idempotent_hint=False,
        ),
    ),
    Tool(
        name="cancel_order",
        description=(
            "⚠️ CANCEL a pending order by its ticket number. "
            "Only works on unfilled pending orders (limit/stop orders)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "Pending order ticket number to cancel",
                },
            },
            "required": ["order_id"],
        },
        annotations=ToolAnnotations(
            destructive_hint=True,
            idempotent_hint=False,
        ),
    ),
    Tool(
        name="modify_order",
        description=(
            "⚠️ MODIFY a pending order's price, stop loss, take profit, or expiration. "
            "Only works on unfilled pending orders (limit/stop orders)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "Pending order ticket number to modify",
                },
                "price": {
                    "type": "number",
                    "description": "New order price",
                },
                "sl": {
                    "type": "number",
                    "description": "New stop loss price (0 to remove)",
                },
                "tp": {
                    "type": "number",
                    "description": "New take profit price (0 to remove)",
                },
                "expiration": {
                    "type": "string",
                    "description": "New expiration date/time in ISO format (e.g., '2025-12-31T23:59:59')",
                },
            },
            "required": ["order_id"],
        },
        annotations=ToolAnnotations(
            destructive_hint=True,
            idempotent_hint=True,
        ),
    ),
    Tool(
        name="get_pending_orders_count",
        description="Get the total number of pending (unfilled) orders.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


async def handle_order_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle order-related tool calls."""

    if name in ("get_pending_orders", "get_orders"):
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

    if name == "cancel_order":
        order_id = arguments["order_id"]
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order_id,
        }
        result = await client.send_order(request)
        success = result.get("retcode") in (10008, 10009, 10010)
        return {
            "success": success,
            "retcode": result.get("retcode"),
            "retcode_description": RETURN_CODES.get(result.get("retcode"), "Unknown"),
            "order": result.get("order"),
            "comment": result.get("comment"),
        }

    if name == "modify_order":
        order_id = arguments["order_id"]

        # Fetch the order to get current values
        orders = await client.get_orders(ticket=order_id)
        if not orders:
            raise ValueError(f"Pending order with ticket {order_id} not found")
        order = orders[0]

        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": order_id,
            "symbol": order.get("symbol"),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "price": float(arguments.get("price", order.get("price_open", 0.0))),
            "sl": float(arguments.get("sl", order.get("sl", 0.0))),
            "tp": float(arguments.get("tp", order.get("tp", 0.0))),
        }

        if "expiration" in arguments:
            request["expiration"] = int(parse_utc(arguments["expiration"]).timestamp())
            request["type_time"] = mt5.ORDER_TIME_SPECIFIED

        result = await client.send_order(request)
        success = result.get("retcode") in (10008, 10009, 10010)
        return {
            "success": success,
            "retcode": result.get("retcode"),
            "retcode_description": RETURN_CODES.get(result.get("retcode"), "Unknown"),
            "order": result.get("order"),
            "comment": result.get("comment"),
        }

    if name == "get_pending_orders_count":
        count = await client.get_orders_total()
        return {"count": count}

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
    return type_names.get(order_type if order_type is not None else -1, f"UNKNOWN({order_type})")


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
    if arguments.get("price"):
        request["price"] = float(arguments["price"])

    # Add stop loss if specified
    if arguments.get("sl"):
        request["sl"] = float(arguments["sl"])

    # Add take profit if specified
    if arguments.get("tp"):
        request["tp"] = float(arguments["tp"])

    # Add position ticket for modifications
    if arguments.get("position"):
        request["position"] = int(arguments["position"])

    # Add order ticket for pending order modifications
    if arguments.get("order"):
        request["order"] = int(arguments["order"])

    return request
