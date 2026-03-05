# MCP Server for MetaTrader 5

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

A Python-based [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides AI assistants like Claude with access to the MetaTrader 5 trading platform for market analysis and trade management.

## Features

- **Market Data Access**: Real-time prices, OHLC bars, tick data, and symbol information
- **Account Management**: Account balance, equity, margin status
- **Position Tracking**: View open positions and pending orders
- **Trade Execution**: Place, modify, and close trades (with safety annotations)
- **Historical Data**: Access trade history and deal records
- **MCP Resources**: Passive polling endpoints for account, positions, and market data

## Requirements

- Python 3.10+
- MetaTrader 5 terminal installed (Windows only - MT5 API limitation)
- MT5 account credentials

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/P7AC1D/mt5-mcp.git
cd mt5-mcp

# Install with uv
uv sync
```

### Using pip

```bash
pip install -e .
```

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your MT5 credentials:
   ```env
   MT5_LOGIN=12345678
   MT5_PASSWORD=your_password
   MT5_SERVER=MetaQuotes-Demo
   ```

## Usage

### Running the Server (Local - STDIO)

```bash
# Default: STDIO transport for local use
mcp-server-mt5

# Or using Python module
python -m mcp_server_mt5

# Or using uv
uv run mcp-server-mt5
```

### Running the Server (Remote - HTTP)

For remote access over the network (e.g., from another machine):

```bash
# Start HTTP server on all interfaces, port 8000
mcp-server-mt5 --transport http --port 8000

# Or specify a different host/port
mcp-server-mt5 --transport http --host 0.0.0.0 --port 9000
```

**Windows Firewall**: Allow the port through Windows Firewall:
```powershell
netsh advfirewall firewall add rule name="MCP MT5" dir=in action=allow protocol=tcp localport=8000
```

Clients connect to: `http://<server-ip>:8000/sse`

### Claude Desktop Configuration (Local)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mt5": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/Code/mt5-mcp",
        "run",
        "mcp-server-mt5"
      ],
      "env": {
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "your_password",
        "MT5_SERVER": "MetaQuotes-Demo"
      }
    }
  }
}
```

### VS Code MCP Configuration (Local)

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "mt5": {
      "command": "uv",
      "args": ["--directory", "C:/Code/mt5-mcp", "run", "mcp-server-mt5"],
      "env": {
        "MT5_LOGIN": "${env:MT5_LOGIN}",
        "MT5_PASSWORD": "${env:MT5_PASSWORD}",
        "MT5_SERVER": "${env:MT5_SERVER}"
      }
    }
  }
}
```

### Remote Access from Another Machine

When the server is running with `--transport http`, clients on other machines can connect:

**Python MCP Client:**
```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async with sse_client("http://<server-ip>:8000/sse") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        # Call tools...
```

**MCP Inspector (for testing):**
```bash
npx @modelcontextprotocol/inspector http://<server-ip>:8000/sse
```

## Available Tools

### Account
- `get_account_info` - Get account balance, equity, margin, and trading conditions

### Market Data
- `get_symbols` - List available trading symbols
- `get_symbol_info` - Get detailed symbol specification
- `get_symbol_tick` - Get current bid/ask prices
- `get_ohlc_bars` - Get OHLC candlestick data
- `get_ohlc_bars_range` - Get OHLC data for a date range
- `get_ticks_range` - Get tick data for a date range

### Positions
- `get_positions` - Get all open positions
- `get_positions_count` - Get number of open positions

### Orders
- `get_pending_orders` - Get all pending orders
- `calculate_margin` - Calculate required margin for an order
- `calculate_profit` - Calculate potential profit/loss
- `check_order` - Validate an order before sending
- `send_order` - Execute a trade order ⚠️ (requires confirmation)

### History
- `get_history_orders` - Get historical orders
- `get_history_deals` - Get historical deals/trades

## Available Resources

Resources provide passive data access for polling:

- `mt5://account/info` - Account information
- `mt5://symbols` - List of trading symbols
- `mt5://symbols/{symbol}/tick` - Current price tick for a symbol
- `mt5://symbols/{symbol}/info` - Symbol specification
- `mt5://positions` - Open positions
- `mt5://orders` - Pending orders

## Safety Considerations

- Trade execution tools (`send_order`) are marked with `destructiveHint=True` to prompt for user confirmation
- Always use a demo account for testing
- The server logs all trading operations for audit purposes
- Consider implementing additional safeguards (position limits, daily loss limits) for production use

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
pytest

# Run with MCP Inspector for debugging
npx @modelcontextprotocol/inspector uv run mcp-server-mt5
```

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) before submitting a pull request.

## Security

For security concerns, please see [SECURITY.md](SECURITY.md). **Never commit real credentials** — use `.env` files with the provided `.env.example` as a template.

## License

MIT License — see [LICENSE](LICENSE) for details.
