"""MCP Server for MetaTrader 5 API integration."""

import argparse
import asyncio
import logging
from logging.handlers import RotatingFileHandler

__version__ = "0.2.0"


def configure_logging(settings, *, verbose: bool = False, console: bool = True) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()] if console else []
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                settings.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
            )
        )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    for name in ("httpx", "httpx2", "httpcore", "httpcore2", "mcp"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    from .config import get_settings
    from .server import serve, serve_http

    parser = argparse.ArgumentParser(
        description="MCP Server for MetaTrader 5",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mt5-path", default=None)
    parser.add_argument(
        "--env-file", default=None, help="Explicit .env path; otherwise .env in working directory"
    )
    parser.add_argument(
        "--legacy-sse",
        action="store_true",
        help="Also enable legacy /sse and /messages/ compatibility",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    settings = get_settings(args.env_file)
    if args.legacy_sse:
        settings.legacy_sse = True
    configure_logging(settings, verbose=args.verbose)
    if args.transport == "http":
        asyncio.run(serve_http(args.host, args.port, args.mt5_path, settings))
    else:
        asyncio.run(serve(args.mt5_path, settings))
