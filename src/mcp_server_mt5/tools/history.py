"""Historical trading data tools."""

from datetime import datetime, timedelta
from typing import Any

from mcp.types import Tool

from ..mt5_client import MT5Client

HISTORY_TOOLS: list[Tool] = [
    Tool(
        name="get_history_orders",
        description=(
            "Get historical orders for a date range. Includes filled, canceled, and expired orders. "
            "Can filter by symbol, order ticket, or position ticket."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format (e.g., '2024-01-01T00:00:00')",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format (e.g., '2024-01-31T23:59:59')",
                },
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol name",
                },
                "ticket": {
                    "type": "integer",
                    "description": "Filter by specific order ticket",
                },
                "position": {
                    "type": "integer",
                    "description": "Filter by position ticket (get all orders for a position)",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_history_deals",
        description=(
            "Get historical deals/trades for a date range. Deals are the actual executed trades "
            "(entries, exits, balance operations). Can filter by symbol, deal ticket, or position ticket."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format",
                },
                "symbol": {
                    "type": "string",
                    "description": "Filter by symbol name",
                },
                "ticket": {
                    "type": "integer",
                    "description": "Filter by specific deal ticket",
                },
                "position": {
                    "type": "integer",
                    "description": "Filter by position ticket (get all deals for a position)",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_history_orders_count",
        description=(
            "Get the total number of historical orders in a date range. "
            "Defaults to the last 30 days if no dates are provided."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_history_deals_count",
        description=(
            "Get the total number of historical deals in a date range. "
            "Defaults to the last 30 days if no dates are provided."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format",
                },
            },
            "required": [],
        },
    ),
]


def _get_default_date_range() -> tuple[datetime, datetime]:
    """Get default date range (last 30 days)."""
    date_to = datetime.now()
    date_from = date_to - timedelta(days=30)
    return date_from, date_to


def _parse_dates(arguments: dict[str, Any]) -> tuple[datetime, datetime]:
    """Parse date arguments or use defaults."""
    if "date_from" in arguments and "date_to" in arguments:
        return (
            datetime.fromisoformat(arguments["date_from"]),
            datetime.fromisoformat(arguments["date_to"]),
        )
    return _get_default_date_range()


def _get_deal_type_name(deal_type: int | None) -> str:
    """Convert deal type integer to readable name."""
    type_names = {
        0: "BUY",
        1: "SELL",
        2: "BALANCE",
        3: "CREDIT",
        4: "CHARGE",
        5: "CORRECTION",
        6: "BONUS",
        7: "COMMISSION",
        8: "COMMISSION_DAILY",
        9: "COMMISSION_MONTHLY",
        10: "COMMISSION_AGENT_DAILY",
        11: "COMMISSION_AGENT_MONTHLY",
        12: "INTEREST",
        13: "BUY_CANCELED",
        14: "SELL_CANCELED",
        15: "DIVIDEND",
        16: "DIVIDEND_FRANKED",
        17: "TAX",
    }
    return type_names.get(deal_type, f"UNKNOWN({deal_type})")


def _get_deal_entry_name(entry: int | None) -> str:
    """Convert deal entry type to readable name."""
    entry_names = {
        0: "IN",
        1: "OUT",
        2: "INOUT",
        3: "OUT_BY",
    }
    return entry_names.get(entry, f"UNKNOWN({entry})")


def _get_order_state_name(state: int | None) -> str:
    """Convert order state integer to readable name."""
    state_names = {
        0: "STARTED",
        1: "PLACED",
        2: "CANCELED",
        3: "PARTIAL",
        4: "FILLED",
        5: "REJECTED",
        6: "EXPIRED",
        7: "REQUEST_ADD",
        8: "REQUEST_MODIFY",
        9: "REQUEST_CANCEL",
    }
    return state_names.get(state, f"UNKNOWN({state})")


async def handle_history_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle history-related tool calls."""

    if name == "get_history_orders":
        date_from, date_to = _parse_dates(arguments)

        orders = await client.get_history_orders(
            date_from=date_from,
            date_to=date_to,
            symbol=arguments.get("symbol"),
            ticket=arguments.get("ticket"),
            position=arguments.get("position"),
        )

        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "count": len(orders),
            "orders": [
                {
                    "ticket": o.get("ticket"),
                    "symbol": o.get("symbol"),
                    "type": o.get("type"),
                    "state": _get_order_state_name(o.get("state")),
                    "volume_initial": o.get("volume_initial"),
                    "volume_current": o.get("volume_current"),
                    "price_open": o.get("price_open"),
                    "price_current": o.get("price_current"),
                    "price_stoplimit": o.get("price_stoplimit"),
                    "sl": o.get("sl"),
                    "tp": o.get("tp"),
                    "time_setup": o.get("time_setup"),
                    "time_done": o.get("time_done"),
                    "position_id": o.get("position_id"),
                    "comment": o.get("comment"),
                    "magic": o.get("magic"),
                }
                for o in orders
            ],
        }

    if name == "get_history_deals":
        date_from, date_to = _parse_dates(arguments)

        deals = await client.get_history_deals(
            date_from=date_from,
            date_to=date_to,
            symbol=arguments.get("symbol"),
            ticket=arguments.get("ticket"),
            position=arguments.get("position"),
        )

        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "count": len(deals),
            "deals": [
                {
                    "ticket": d.get("ticket"),
                    "order": d.get("order"),
                    "symbol": d.get("symbol"),
                    "type": _get_deal_type_name(d.get("type")),
                    "entry": _get_deal_entry_name(d.get("entry")),
                    "volume": d.get("volume"),
                    "price": d.get("price"),
                    "profit": d.get("profit"),
                    "swap": d.get("swap"),
                    "commission": d.get("commission"),
                    "fee": d.get("fee"),
                    "time": d.get("time"),
                    "position_id": d.get("position_id"),
                    "comment": d.get("comment"),
                    "magic": d.get("magic"),
                }
                for d in deals
            ],
        }

    if name == "get_history_orders_count":
        date_from, date_to = _parse_dates(arguments)
        count = await client.get_history_orders_total(date_from, date_to)
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "count": count,
        }

    if name == "get_history_deals_count":
        date_from, date_to = _parse_dates(arguments)
        count = await client.get_history_deals_total(date_from, date_to)
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "count": count,
        }

    raise ValueError(f"Unknown history tool: {name}")
