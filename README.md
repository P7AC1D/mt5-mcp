# MCP Server for MetaTrader 5

For boot startup and failure recovery through the native Windows Service Control
Manager, see [Windows service deployment](docs/windows-service.md). Registration,
service-identity/profile provisioning and Session 0 acceptance are explicit steps;
the installer does not start MT5 automatically during setup.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
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

- Python 3.11+
- MetaTrader 5 terminal installed (Windows only - MT5 API limitation)
- MT5 account credentials

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/P7AC1D/mt5-mcp.git
cd mt5-mcp

# Install with uv
uv sync --locked
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

### Running the Server (HTTP)

```bash
uv run --locked mcp-server-mt5 --transport http --env-file /absolute/path/to/.env
```

Connect current clients to `http://127.0.0.1:8000/mcp`. The official MCP SDK
2.3.0 serves MCP 2026-07-28 and compatible older Streamable HTTP clients.
`GET /healthz` is process liveness; `GET /readyz` is cached terminal readiness
(503 while disconnected, stopping or overdue). Readiness is probed every 5 seconds.

HTTP now defaults to loopback. Non-loopback binding requires `MT5_HTTP_TOKEN`
and explicitly configured `MT5_ALLOWED_HOSTS`; keep DNS-rebinding/Origin checks
and terminate TLS at a trusted reverse proxy. Every protected request needs
`Authorization: Bearer <token>`. This private shared-token mode does not implement
OAuth discovery; clients requiring MCP OAuth need an appropriate authenticated
gateway. No firewall, credential, or network changes happen automatically.

For an existing SSE-only client such as Aurum, temporarily set
`MT5_LEGACY_SSE=true` or add `--legacy-sse`. This retains `/sse` and `/messages/`
with the same security checks and one shared terminal owner. Existing client URLs
must remain `/sse` until that client supports Streamable HTTP. Both transports can
run concurrently. See [migration and compatibility](docs/modernization.md),
especially the required client error handling and no-retry rule for trades.

For reliable Windows startup, versioned updates and rollback, follow
[Windows deployment](docs/windows-deployment.md). An interactive logon task is
not a boot-before-login Windows service. Do not enable automatic Windows login.

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

### Python MCP Client

```python
from mcp.client import Client

async with Client("http://127.0.0.1:8000/mcp") as client:
    result = await client.call_tool("get_positions", {})
    if result.is_error:
        raise RuntimeError(result.structured_content)
    print(result.structured_content)
```

Use an authenticated HTTP transport for a token-protected endpoint. The bundled
`test_client.py` accepts its token only from `MT5_HTTP_TOKEN` and performs reads.

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
- `send_order` - Execute a trade order ⚠️ (the calling application must enforce authorization)

### History
- `get_history_orders` - Get historical orders
- `get_history_deals` - Get historical deals/trades

## Available Resources

Resources provide passive data access for polling. The two `{symbol}` URLs are
advertised separately by `resources/templates/list`:

- `mt5://account/info` - Account information
- `mt5://symbols` - List of trading symbols
- `mt5://symbols/{symbol}/tick` - Current price tick for a symbol
- `mt5://symbols/{symbol}/info` - Symbol specification
- `mt5://positions` - Open positions
- `mt5://orders` - Pending orders

## Safety Considerations

- All 33 tool names and successful JSON text payloads are preserved. Structured
  output is added; array payloads use `structuredContent.result` while their text
  remains a JSON array. Tool errors have `isError=true`; empty results differ from
  failed reads. Resource failures use protocol errors.
- Native MT5 calls run on one dedicated owner thread. HTTP requests are concurrent,
  but terminal operations (including compound closes/modifications) are serialized.
  Never start multiple ASGI workers or connect another owner to the same terminal.
- Account/broker identity is pinned at startup and checked before tool operations
  and order submission. `login` remains registered but is disabled unless
  `MT5_ALLOW_ACCOUNT_SWITCH=true`. Queued requests cannot cross account changes.
- Cancelling or timing out a dispatched order does not undo it. Never retry a trade
  automatically. Reconcile terminal orders/deals and the local operation journal.
- An overdue native call blocks new admission. Shutdown never overlaps it. A hung
  extension may require deliberate process recovery after reconciling trades;
  threads cannot safely kill native calls. No automatic order replay or account
  reconnect occurs.
- Trading annotations are client hints, not server-side confirmation or risk
  limits. Keep authorization and position/loss controls in the calling application.
- Tests use injected fake APIs, including on Windows. No live order is needed for
  smoke tests. Live MT5 behavior must be validated separately on Windows.

## Development

```bash
# Install dev dependencies
uv sync --locked --extra dev

# Run tests and quality checks (Linux/macOS use injected native APIs)
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked pyright

# Run with MCP Inspector for debugging
npx @modelcontextprotocol/inspector uv run mcp-server-mt5
```

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) before submitting a pull request.

## Security

For security concerns, please see [SECURITY.md](SECURITY.md). **Never commit real credentials** — use `.env` files with the provided `.env.example` as a template.

## License

MIT License — see [LICENSE](LICENSE) for details.
