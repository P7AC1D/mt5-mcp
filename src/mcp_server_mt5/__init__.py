"""MCP Server for MetaTrader 5 API integration."""

import argparse
import asyncio
import logging

from .server import serve, serve_http

__version__ = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Main entry point for the MCP MT5 server."""
    parser = argparse.ArgumentParser(
        description="MCP Server for MetaTrader 5 trading platform",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol: stdio (local) or http (remote/network)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind HTTP server (use 0.0.0.0 for all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP server",
    )
    parser.add_argument(
        "--mt5-path",
        type=str,
        default=None,
        help="Path to MT5 terminal executable (overrides MT5_PATH env var)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.transport == "http":
        asyncio.run(serve_http(
            host=args.host,
            port=args.port,
            mt5_path_override=args.mt5_path,
        ))
    else:
        asyncio.run(serve(mt5_path_override=args.mt5_path))


if __name__ == "__main__":
    main()
