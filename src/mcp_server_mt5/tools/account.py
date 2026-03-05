"""Account information tools."""

from typing import Any

from mcp.types import Tool, ToolAnnotations

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
    Tool(
        name="get_terminal_info",
        description=(
            "Get MT5 terminal information including build number, connection status, "
            "trade permissions, DLL usage, paths, and company/server details."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="login",
        description=(
            "⚠️ LOG IN to a different trading account. Switches the active trading account "
            "on the connected MT5 terminal. Requires account number, password, and server."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "login": {
                    "type": "integer",
                    "description": "Trading account number",
                },
                "password": {
                    "type": "string",
                    "description": "Trading account password",
                },
                "server": {
                    "type": "string",
                    "description": "Trade server name (e.g., 'MetaQuotes-Demo')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Connection timeout in milliseconds (default: 60000)",
                },
            },
            "required": ["login", "password", "server"],
        },
        annotations=ToolAnnotations(
            destructiveHint=True,
            idempotentHint=False,
        ),
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

    if name == "get_terminal_info":
        info = await client.get_terminal_info()
        return {
            "connected": info.get("connected"),
            "trade_allowed": info.get("trade_allowed"),
            "tradeapi_disabled": info.get("tradeapi_disabled"),
            "dlls_allowed": info.get("dlls_allowed"),
            "email_enabled": info.get("email_enabled"),
            "ftp_enabled": info.get("ftp_enabled"),
            "notifications_enabled": info.get("notifications_enabled"),
            "community_account": info.get("community_account"),
            "community_balance": info.get("community_balance"),
            "build": info.get("build"),
            "maxbars": info.get("maxbars"),
            "ping_last": info.get("ping_last"),
            "retransmission": info.get("retransmission"),
            "company": info.get("company"),
            "name": info.get("name"),
            "language": info.get("language"),
            "path": info.get("path"),
            "data_path": info.get("data_path"),
            "commondata_path": info.get("commondata_path"),
        }

    if name == "login":
        await client.login(
            login=arguments["login"],
            password=arguments["password"],
            server=arguments["server"],
            timeout=arguments.get("timeout"),
        )
        return {"success": True, "login": arguments["login"], "server": arguments["server"]}

    raise ValueError(f"Unknown account tool: {name}")
