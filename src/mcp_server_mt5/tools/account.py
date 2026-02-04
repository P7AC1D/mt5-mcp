"""Account information tools."""

from typing import Any

from mcp.types import Tool

from ..mt5_client import MT5Client

ACCOUNT_TOOLS: list[Tool] = [
    Tool(
        name="get_account_info",
        description=(
            "Get current trading account information including balance, equity, "
            "margin, free margin, margin level, profit/loss, and account settings. "
            "Use this to check account status before placing trades."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


async def handle_account_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle account-related tool calls."""
    if name == "get_account_info":
        info = await client.get_account_info()
        # Return a subset of useful fields with descriptions
        return {
            "login": info.get("login"),
            "name": info.get("name"),
            "server": info.get("server"),
            "currency": info.get("currency"),
            "balance": info.get("balance"),
            "equity": info.get("equity"),
            "profit": info.get("profit"),
            "margin": info.get("margin"),
            "margin_free": info.get("margin_free"),
            "margin_level": info.get("margin_level"),
            "leverage": info.get("leverage"),
            "trade_mode": info.get("trade_mode"),
            "limit_orders": info.get("limit_orders"),
            "trade_allowed": info.get("trade_allowed"),
            "trade_expert": info.get("trade_expert"),
        }

    raise ValueError(f"Unknown account tool: {name}")
