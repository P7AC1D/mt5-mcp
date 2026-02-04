"""Market data tools for prices, symbols, and historical data."""

from datetime import datetime
from typing import Any

import MetaTrader5 as mt5
from mcp.types import Tool

from ..mt5_client import MT5Client

# Timeframe mapping
TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

MARKET_DATA_TOOLS: list[Tool] = [
    Tool(
        name="get_symbols",
        description=(
            "Get list of available trading symbols. Optionally filter by group pattern "
            "(e.g., '*USD*' for USD pairs, 'Forex*' for forex symbols)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "description": "Filter pattern for symbol groups (e.g., '*USD*', 'Forex*')",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_symbol_info",
        description=(
            "Get detailed specification for a trading symbol including digits, lot size, "
            "tick size, margin requirements, trading hours, and contract specifications."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD', 'BTCUSD')",
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_symbol_tick",
        description=(
            "Get current market tick for a symbol including bid, ask, last price, "
            "and volume. Use this to check current prices before trading."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD', 'BTCUSD')",
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_ohlc_bars",
        description=(
            "Get OHLC (Open, High, Low, Close) candlestick bars from a starting position. "
            "Position 0 is the current incomplete bar. Use for technical analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD')",
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"],
                    "description": "Chart timeframe",
                },
                "start_pos": {
                    "type": "integer",
                    "description": "Starting bar position (0 = current bar)",
                    "default": 0,
                },
                "count": {
                    "type": "integer",
                    "description": "Number of bars to retrieve",
                    "default": 100,
                },
            },
            "required": ["symbol", "timeframe"],
        },
    ),
    Tool(
        name="get_ohlc_bars_range",
        description=(
            "Get OHLC candlestick bars for a specific date/time range. "
            "Useful for backtesting or analyzing specific time periods."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD')",
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"],
                    "description": "Chart timeframe",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format (e.g., '2024-01-01T00:00:00')",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format (e.g., '2024-01-31T23:59:59')",
                },
            },
            "required": ["symbol", "timeframe", "date_from", "date_to"],
        },
    ),
    Tool(
        name="get_ticks_range",
        description=(
            "Get tick-by-tick data for a specific date/time range. "
            "Provides detailed bid/ask/last prices with millisecond precision."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g., 'EURUSD')",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date/time in ISO format",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date/time in ISO format",
                },
            },
            "required": ["symbol", "date_from", "date_to"],
        },
    ),
]


async def handle_market_data_tool(
    client: MT5Client,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Handle market data tool calls."""

    if name == "get_symbols":
        symbols = await client.get_symbols(group=arguments.get("group"))
        # Return simplified list
        return [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "path": s.get("path", ""),
                "spread": s.get("spread"),
                "digits": s.get("digits"),
                "trade_mode": s.get("trade_mode"),
            }
            for s in symbols
        ]

    if name == "get_symbol_info":
        info = await client.get_symbol_info(arguments["symbol"])
        # Return useful trading information
        return {
            "name": info.get("name"),
            "description": info.get("description"),
            "path": info.get("path"),
            "currency_base": info.get("currency_base"),
            "currency_profit": info.get("currency_profit"),
            "currency_margin": info.get("currency_margin"),
            "digits": info.get("digits"),
            "point": info.get("point"),
            "tick_size": info.get("trade_tick_size"),
            "tick_value": info.get("trade_tick_value"),
            "volume_min": info.get("volume_min"),
            "volume_max": info.get("volume_max"),
            "volume_step": info.get("volume_step"),
            "spread": info.get("spread"),
            "spread_float": info.get("spread_float"),
            "trade_mode": info.get("trade_mode"),
            "margin_initial": info.get("margin_initial"),
            "margin_maintenance": info.get("margin_maintenance"),
            "session_open": info.get("session_open"),
            "session_close": info.get("session_close"),
        }

    if name == "get_symbol_tick":
        tick = await client.get_symbol_tick(arguments["symbol"])
        return {
            "symbol": arguments["symbol"],
            "time": tick.get("time"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "last": tick.get("last"),
            "volume": tick.get("volume"),
            "spread": round((tick.get("ask", 0) - tick.get("bid", 0)) * 100000, 1),  # Approximate pips
        }

    if name == "get_ohlc_bars":
        timeframe_str = arguments["timeframe"]
        timeframe = TIMEFRAMES.get(timeframe_str)
        if timeframe is None:
            raise ValueError(f"Invalid timeframe: {timeframe_str}")

        return await client.get_ohlc_bars(
            symbol=arguments["symbol"],
            timeframe=timeframe,
            start_pos=arguments.get("start_pos", 0),
            count=arguments.get("count", 100),
        )

    if name == "get_ohlc_bars_range":
        timeframe_str = arguments["timeframe"]
        timeframe = TIMEFRAMES.get(timeframe_str)
        if timeframe is None:
            raise ValueError(f"Invalid timeframe: {timeframe_str}")

        date_from = datetime.fromisoformat(arguments["date_from"])
        date_to = datetime.fromisoformat(arguments["date_to"])

        return await client.get_ohlc_bars_range(
            symbol=arguments["symbol"],
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to,
        )

    if name == "get_ticks_range":
        date_from = datetime.fromisoformat(arguments["date_from"])
        date_to = datetime.fromisoformat(arguments["date_to"])

        return await client.get_ticks_range(
            symbol=arguments["symbol"],
            date_from=date_from,
            date_to=date_to,
        )

    raise ValueError(f"Unknown market data tool: {name}")
