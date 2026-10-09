"""MCP SDK v2 server: concurrent protocol requests, one exclusive MT5 owner."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from typing import Any, cast

import anyio
from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.runner import serve_dual_era_loop
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    ReadResourceRequestParams,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
)
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .config import MT5Settings, get_settings
from .errors import MT5Error
from .instance_lock import InstanceLock
from .mt5_client import MT5Client
from .resources import handle_resource_read, register_resource_templates, register_resources
from .tools import get_all_tools, handle_tool_call
from .validation import validate_arguments

logger = logging.getLogger(__name__)
VERSION = "0.2.0"


class MT5Server(Server[MT5Client]):
    health_routes: list[Route]
    active_client: MT5Client | None = None
    retained_lock: InstanceLock | None = None


class BearerMiddleware:
    """Preconfigured shared-token protection for private deployments, not OAuth."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] != "/healthz":
            headers = dict(scope["headers"])
            supplied = headers.get(b"authorization", b"").decode("latin-1")
            if not hmac.compare_digest(supplied, "Bearer " + self.token):
                response = JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _tool_result(payload: Any, *, error: bool = False) -> CallToolResult:
    # Preserve legacy JSON text, and expose machine-readable structured output.
    serializable = json.loads(json.dumps(payload, default=str, allow_nan=False))
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(serializable, indent=2))],
        structured_content=serializable
        if isinstance(serializable, dict)
        else {"result": serializable},
        is_error=error,
    )


def create_server(
    settings: MT5Settings | None = None,
    *,
    client_factory: Callable[[MT5Settings], MT5Client] = MT5Client,
    mt5_path_override: str | None = None,
) -> MT5Server:
    settings = settings or get_settings()
    registry = {tool.name: tool for tool in get_all_tools()}
    state: dict[str, Any] = {"client": None}

    @asynccontextmanager
    async def lifespan(base_server: Server[MT5Client]):
        server = cast(MT5Server, base_server)
        with InstanceLock(settings.lock_file) as instance_lock:
            client = client_factory(settings)
            state["client"] = client
            server.active_client = client
            probe_task = None
            try:
                await client.initialize(path_override=mt5_path_override)

                async def probe():
                    while True:
                        await asyncio.sleep(settings.readiness_interval)
                        try:
                            info = await client.transaction(
                                lambda owner: owner.get_terminal_info(), name="readiness"
                            )
                            client._ready = bool(info.get("connected", False))
                        except Exception:
                            client._ready = False
                            logger.warning("Terminal readiness probe failed")

                probe_task = asyncio.create_task(probe())
                yield client
            finally:
                try:
                    if probe_task:
                        probe_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await probe_task
                finally:
                    try:
                        # Probe errors/cancellation must never skip owner draining.
                        # Shield AnyIO shutdown cancellation, retaining the OS lock
                        # if any other interruption prevents verified shutdown.
                        with anyio.CancelScope(shield=True):
                            await client.shutdown()
                    except BaseException:
                        instance_lock.retain()
                        server.retained_lock = instance_lock
                        raise
                    finally:
                        state["client"] = None
                        server.active_client = None

    async def list_tools(ctx, params):
        return ListToolsResult(tools=list(registry.values()))

    async def call_tool(ctx: ServerRequestContext[MT5Client], params: CallToolRequestParams):
        name, arguments = params.name, params.arguments or {}
        if name not in registry:
            raise MCPError(-32602, "Unknown tool")
        try:
            validate_arguments(registry[name].input_schema, arguments, settings)
            result = await handle_tool_call(ctx.lifespan_context, name, arguments)
            if isinstance(result, dict) and result.get("retcode") in {10012, 10031}:
                result = {
                    **result,
                    "outcome_unknown": True,
                    "error": "Broker timeout or connection failure; reconcile before retrying.",
                }
            return _tool_result(
                result, error=isinstance(result, dict) and result.get("success") is False
            )
        except MT5Error as error:
            logger.warning(
                "Tool %s failed (%s), operation=%s", name, error.kind, error.operation_id
            )
            return _tool_result(error.payload(), error=True)
        except (ValueError, KeyError, TypeError) as error:
            # Avoid serializing submitted passwords or unexpected native objects.
            return _tool_result(
                {
                    "error": str(error)
                    if isinstance(error, ValueError)
                    else "Invalid tool arguments",
                    "kind": "invalid_arguments",
                },
                error=True,
            )
        except Exception:
            logger.error("Unexpected failure in tool %s", name)
            return _tool_result(
                {"error": "Unexpected server error", "kind": "internal_error"}, error=True
            )

    async def list_resources(ctx, params):
        return ListResourcesResult(resources=register_resources())

    async def list_templates(ctx, params):
        return ListResourceTemplatesResult(resource_templates=register_resource_templates())

    async def read_resource(
        ctx: ServerRequestContext[MT5Client], params: ReadResourceRequestParams
    ):
        try:
            payload = await ctx.lifespan_context.transaction(
                lambda owner: handle_resource_read(owner, str(params.uri)), name="read_resource"
            )
            return ReadResourceResult(
                contents=[
                    TextResourceContents(
                        uri=params.uri,
                        mime_type="application/json",
                        text=json.dumps(payload, default=str, allow_nan=False),
                    )
                ]
            )
        except MT5Error as error:
            raise MCPError(-32002, str(error), error.payload()) from None

    async def health(request: Request):
        return JSONResponse({"status": "alive", "version": VERSION})

    async def ready(request: Request):
        client = state["client"]
        status = client.status if client else {"ready": False}
        return JSONResponse(status, status_code=200 if status["ready"] else 503)

    server = MT5Server(
        "mcp-mt5",
        version=VERSION,
        lifespan=lifespan,
        get_tool_input_schema=lambda name: (
            registry[name].input_schema if name in registry else None
        ),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_list_resource_templates=list_templates,
        on_read_resource=read_resource,
    )
    # Public app factory owns the SDK's lifespan; do not mount it without entering
    # session_manager.run() in an outer application's lifespan.
    server.health_routes = [Route("/healthz", health), Route("/readyz", ready)]
    return server


def create_http_app(
    settings: MT5Settings | None = None,
    *,
    host: str = "127.0.0.1",
    client_factory: Callable[[MT5Settings], MT5Client] = MT5Client,
    mt5_path_override: str | None = None,
):
    settings = settings or get_settings()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        if not settings.http_token:
            raise ValueError(
                "Non-loopback HTTP requires MT5_HTTP_TOKEN and explicit allowed hosts/origins. Use a TLS reverse proxy."
            )
        if settings.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]:
            raise ValueError("Set MT5_ALLOWED_HOSTS explicitly for non-loopback access.")
    server = create_server(
        settings, client_factory=client_factory, mt5_path_override=mt5_path_override
    )
    app = server.streamable_http_app(
        host=host,
        json_response=False,
        stateless_http=False,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
        ),
        max_request_body_size=settings.max_request_bytes,
        max_sessions=settings.max_sessions,
        session_idle_timeout=settings.session_idle_timeout,
        custom_starlette_routes=server.health_routes,
    )
    if settings.legacy_sse:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
        )
        sse = SseServerTransport(
            "/messages/",
            security_settings=security,
            max_request_body_size=settings.max_request_bytes,
        )
        slots = asyncio.Semaphore(settings.max_sessions)

        class LegacySSEApp:
            async def __call__(self, scope, receive, send):
                if slots.locked():
                    await JSONResponse({"error": "Session limit reached"}, status_code=503)(
                        scope, receive, send
                    )
                    return
                async with slots:
                    try:
                        with anyio.fail_after(settings.legacy_sse_max_seconds):
                            async with sse.connect_sse(scope, receive, send) as streams:
                                if server.active_client is None:
                                    return
                                await serve_dual_era_loop(
                                    server,
                                    *streams,
                                    lifespan_state=server.active_client,
                                    init_options=server.create_initialization_options(),
                                )
                    except TimeoutError:
                        logger.info("Legacy SSE session lifetime expired")

        app.router.routes.extend(
            [
                Route("/sse", LegacySSEApp(), methods=["GET"]),
                Mount("/messages/", app=sse.handle_post_message),
            ]
        )
    if settings.http_token:
        app.add_middleware(BearerMiddleware, token=settings.http_token.get_secret_value())
    return app


async def serve(mt5_path_override: str | None = None, settings: MT5Settings | None = None) -> None:
    server = create_server(settings, mt5_path_override=mt5_path_override)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def serve_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    mt5_path_override: str | None = None,
    settings: MT5Settings | None = None,
) -> None:
    import uvicorn

    app = create_http_app(settings, host=host, mt5_path_override=mt5_path_override)
    await uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, workers=1, access_log=False, log_config=None)
    ).serve()
