"""Main MCP server implementation for MT5."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from .config import get_settings
from .mt5_client import MT5Client, MT5Error
from .resources import register_resources, handle_resource_read
from .tools import get_all_tools, handle_tool_call

logger = logging.getLogger(__name__)

# Global client instance for use by tools and resources
_client: MT5Client | None = None


def get_client() -> MT5Client:
    """Get the MT5 client instance."""
    if _client is None:
        raise MT5Error("MT5 client not initialized")
    return _client


@asynccontextmanager
async def mt5_lifespan(mt5_path_override: str | None = None) -> AsyncIterator[MT5Client]:
    """Async context manager for MT5 connection lifecycle."""
    global _client

    settings = get_settings()
    client = MT5Client(settings)

    try:
        await client.initialize(path_override=mt5_path_override)
        _client = client
        yield client
    finally:
        await client.shutdown()
        _client = None


def _create_server() -> Server:
    """Create and configure the MCP server instance."""
    server = Server("mcp-mt5")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available MT5 tools."""
        return get_all_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool invocation."""
        try:
            client = get_client()
            result = await handle_tool_call(client, name, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except MT5Error as e:
            logger.error(f"MT5 error in tool {name}: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e), "error_code": e.error_code}))]
        except Exception as e:
            logger.exception(f"Error in tool {name}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available MT5 resources."""
        return register_resources()

    @server.read_resource()
    async def read_resource(uri) -> str:
        """Read an MT5 resource."""
        # Convert AnyUrl to string if needed
        uri_str = str(uri)
        try:
            client = get_client()
            result = await handle_resource_read(client, uri_str)
            return json.dumps(result, indent=2, default=str)
        except MT5Error as e:
            logger.error(f"MT5 error reading resource {uri_str}: {e}")
            return json.dumps({"error": str(e), "error_code": e.error_code})
        except Exception as e:
            logger.exception(f"Error reading resource {uri_str}")
            return json.dumps({"error": str(e)})

    return server


async def serve(mt5_path_override: str | None = None) -> None:
    """Run the MCP server with STDIO transport (local)."""
    server = _create_server()

    async with mt5_lifespan(mt5_path_override):
        logger.info("Starting MCP MT5 server (stdio)...")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


async def serve_http(
    host: str = "0.0.0.0",
    port: int = 8000,
    mt5_path_override: str | None = None,
) -> None:
    """Run the MCP server with HTTP+SSE transport for remote access."""
    import uvicorn

    server = _create_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection."""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
        return Response()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        """Starlette lifespan for MT5 connection."""
        async with mt5_lifespan(mt5_path_override):
            logger.info(f"MCP MT5 server (HTTP) running on http://{host}:{port}")
            logger.info(f"Connect clients to: http://{host}:{port}/sse")
            yield

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            # Mount the SSE transport's handle_post_message as an ASGI app
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=lifespan,
    )

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()
