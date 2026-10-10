"""Real SDK/HTTP protocol tests against an injected fake terminal."""

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from unittest.mock import Mock

import httpx
import httpx2
import pytest
import uvicorn
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from mcp_server_mt5.config import MT5Settings
from mcp_server_mt5.errors import MT5Error
from mcp_server_mt5.instance_lock import InstanceLock
from mcp_server_mt5.mt5_client import MT5Client
from mcp_server_mt5.resources import handle_resource_read, register_resource_templates
from mcp_server_mt5.server import create_http_app, create_server
from mcp_server_mt5.validation import parse_utc


def configuration(tmp_path, **kwargs):
    return MT5Settings(
        _env_file=None,
        lock_file=tmp_path / "lock",
        journal_file=tmp_path / "operations.jsonl",
        **kwargs,
    )


@pytest.fixture
def api(mock_account_info, mock_terminal_info):
    api = Mock()
    api.initialize.return_value = True
    api.shutdown.return_value = None
    api.account_info.return_value = mock_account_info
    api.terminal_info.return_value = mock_terminal_info
    api.positions_get.return_value = ()
    api.positions_total.return_value = 0
    api.last_error.return_value = (-42, "fake failure")
    return api


@asynccontextmanager
async def running_http(settings, api):
    app = create_http_app(settings, client_factory=lambda s: MT5Client(s, api=api))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on", access_log=False))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(3):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Server failed to start")
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 4)
        sock.close()


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
async def test_http_current_and_legacy_clients(tmp_path, api, mode):
    async with running_http(configuration(tmp_path), api) as url:
        async with Client(
            streamable_http_client(url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False)),
            mode=mode,
        ) as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 33
            result = await client.call_tool("get_positions", {})
            assert not result.is_error
            assert result.structured_content == {"count": 0, "positions": []}
            assert json.loads(result.content[0].text) == result.structured_content
            resources = await client.list_resources()
            assert len(resources.resources) == 4
            templates = await client.list_resource_templates()
            assert len(templates.resource_templates) == 2
            assert all("{" not in r.uri for r in resources.resources)
            content = await client.read_resource("mt5://positions")
            assert json.loads(content.contents[0].text)["count"] == 0
        # Reconnect is a fresh client, with the same single terminal owner.
        async with Client(
            streamable_http_client(url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False)),
            mode=mode,
        ) as client:
            assert not (await client.call_tool("get_positions_count", {})).is_error
    api.initialize.assert_called_once()
    api.shutdown.assert_called_once()


async def test_two_clients_concurrent_calls(tmp_path, api):
    async with running_http(configuration(tmp_path), api) as url:
        async with (
            Client(
                streamable_http_client(
                    url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False)
                )
            ) as a,
            Client(
                streamable_http_client(
                    url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False)
                )
            ) as b,
        ):
            results = await asyncio.gather(
                *[(a if i % 2 else b).call_tool("get_positions_count", {}) for i in range(20)]
            )
            assert all(r.structured_content == {"count": 0} for r in results)
    assert api.positions_total.call_count == 20
    api.initialize.assert_called_once()


async def test_real_protocol_errors_and_input_validation(tmp_path, api):
    server = create_server(configuration(tmp_path), client_factory=lambda s: MT5Client(s, api=api))
    async with Client(server) as client:
        api.positions_get.return_value = None
        result = await client.call_tool("get_positions", {})
        assert result.is_error and result.structured_content["error_code"] == -42
        with pytest.raises(MCPError):
            await client.read_resource("mt5://unknown/resource")
        for arguments in (
            {"count": -1, "symbol": "EURUSD", "timeframe": "M1"},
            {"count": 100001, "symbol": "EURUSD", "timeframe": "M1"},
        ):
            result = await client.call_tool("get_ohlc_bars", arguments)
            assert result.is_error
        api.copy_rates_from_pos.assert_not_called()


async def test_auth_host_origin_and_body_limits(tmp_path, api):
    settings = configuration(tmp_path, http_token="test-token-only", max_request_bytes=1024)
    async with running_http(settings, api) as url:
        async with httpx.AsyncClient(trust_env=False) as http:
            assert (await http.get(url + "/healthz")).status_code == 200
            assert (await http.get(url + "/readyz")).status_code == 401
            headers = {
                "Authorization": "Bearer test-token-only",
                "Accept": "application/json, text/event-stream",
            }
            assert (await http.get(url + "/readyz", headers=headers)).status_code == 200
            bad_host = await http.post(
                url + "/mcp", headers={**headers, "Host": "evil.example"}, json={}
            )
            assert bad_host.status_code in (400, 421)
            bad_origin = await http.post(
                url + "/mcp", headers={**headers, "Origin": "https://evil.example"}, json={}
            )
            assert bad_origin.status_code == 403
            huge = await http.post(url + "/mcp", headers=headers, json={"data": "x" * 2048})
            assert huge.status_code == 413


def test_non_loopback_requires_explicit_security(tmp_path):
    with pytest.raises(ValueError, match="MT5_HTTP_TOKEN"):
        create_http_app(configuration(tmp_path), host="0.0.0.0")
    with pytest.raises(ValueError, match="MT5_ALLOWED_HOSTS"):
        create_http_app(configuration(tmp_path, http_token="test-token-only"), host="0.0.0.0")


def test_instance_lock_rejects_duplicates_and_releases(tmp_path):
    with InstanceLock(tmp_path / "lock"):
        with pytest.raises(RuntimeError, match="Another server"):
            with InstanceLock(tmp_path / "lock"):
                pass
    with InstanceLock(tmp_path / "lock"):
        pass


@pytest.mark.parametrize(
    "uri",
    [
        "mt5://symbols/EURUSD/tick/extra",
        "mt5://symbols/EUR%2fUSD/info",
        "mt5://symbols/%7Bsymbol%7D/tick",
    ],
)
async def test_resource_uris_are_anchored_and_validated(uri):
    with pytest.raises(MT5Error):
        await handle_resource_read(Mock(), uri)


def test_templates_and_naive_dates_are_utc():
    assert len(register_resource_templates()) == 2
    assert parse_utc("2026-01-01T00:00:00").utcoffset().total_seconds() == 0
    assert parse_utc("2026-01-01T02:00:00+02:00").hour == 0


async def test_legacy_sse_client_shares_owner_with_modern_client(tmp_path, api):
    from mcp.client.sse import sse_client

    async with running_http(configuration(tmp_path, legacy_sse=True), api) as url:
        async with Client(
            sse_client(
                url + "/sse",
                httpx_client_factory=lambda **kw: httpx2.AsyncClient(trust_env=False, **kw),
            ),
            mode="legacy",
        ) as legacy:
            async with Client(
                streamable_http_client(
                    url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False)
                )
            ) as modern:
                a, b = await asyncio.gather(
                    legacy.call_tool("get_positions_count", {}),
                    modern.call_tool("get_positions_count", {}),
                )
                assert a.structured_content == b.structured_content == {"count": 0}
    api.initialize.assert_called_once()
    api.shutdown.assert_called_once()


async def test_initial_readiness_detects_disconnected_terminal(tmp_path, api):
    api.terminal_info.return_value = api.terminal_info.return_value._replace(connected=False)
    async with running_http(configuration(tmp_path), api) as url:
        async with httpx.AsyncClient(trust_env=False) as http:
            assert (await http.get(url + "/healthz")).status_code == 200
            assert (await http.get(url + "/readyz")).status_code == 503


@pytest.mark.parametrize("retcode", [10012, 10031])
async def test_broker_timeout_and_connection_results_are_uncertain(tmp_path, api, retcode):
    result = Mock()
    result._asdict.return_value = {"retcode": retcode}
    api.order_send.return_value = result
    server = create_server(configuration(tmp_path), client_factory=lambda s: MT5Client(s, api=api))
    async with Client(server) as client:
        response = await client.call_tool("cancel_order", {"order_id": 42})
        assert response.is_error
        assert response.structured_content["outcome_unknown"]
        assert response.structured_content["retcode"] == retcode
    api.order_send.assert_called_once()


def test_retained_instance_lock_survives_app_garbage_collection(tmp_path):
    import gc

    lock = InstanceLock(tmp_path / "lock")
    lock.__enter__()
    lock.retain()
    lock.__exit__()
    del lock
    gc.collect()
    with pytest.raises(RuntimeError, match="Another server"):
        with InstanceLock(tmp_path / "lock"):
            pass
    # Test-only cleanup, after proving the process-lifetime registry retained it.
    retained = InstanceLock._retained_locks.pop()
    retained.retained = False
    retained.__exit__()


async def test_unexpected_probe_failure_cannot_skip_shutdown(tmp_path, api):
    terminal = api.terminal_info.return_value
    def terminal_info():
        if api.terminal_info.call_count == 1:
            return terminal
        raise RuntimeError("fake native failure")

    api.terminal_info.side_effect = terminal_info
    server = create_server(
        configuration(tmp_path, readiness_interval=0.02),
        client_factory=lambda s: MT5Client(s, api=api),
    )
    async with server.lifespan(server) as client:
        async with asyncio.timeout(1):
            while client.status["ready"]:
                await asyncio.sleep(0.005)
        assert not client.status["ready"]
    api.shutdown.assert_called_once()
    assert client.status["closed"] and not client.status["accepting"]
    with InstanceLock(tmp_path / "lock"):
        pass


async def test_liveness_remains_responsive_during_blocked_native_read(tmp_path, api):
    import threading

    started, release = threading.Event(), threading.Event()

    def blocked():
        started.set()
        release.wait(2)
        return 0

    api.positions_total.side_effect = blocked
    async with running_http(configuration(tmp_path), api) as url:
        async with Client(
            streamable_http_client(url + "/mcp", http_client=httpx2.AsyncClient(trust_env=False))
        ) as client:
            task = asyncio.create_task(client.call_tool("get_positions_count", {}))
            try:
                async with asyncio.timeout(1):
                    while not started.is_set():
                        await asyncio.sleep(0.005)
                async with httpx.AsyncClient(trust_env=False) as http:
                    response = await asyncio.wait_for(http.get(url + "/healthz"), 0.5)
                    assert response.status_code == 200
                assert not task.done()
            finally:
                release.set()
                await task


async def test_sdk_rejects_mismatched_modern_routing_headers(tmp_path, api):
    from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY

    async with running_http(configuration(tmp_path), api) as url:
        async with httpx.AsyncClient(trust_env=False) as http:
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_positions_count",
                    "arguments": {},
                    "_meta": {
                        PROTOCOL_VERSION_META_KEY: "2026-07-28",
                        CLIENT_CAPABILITIES_META_KEY: {},
                    },
                },
            }
            headers = {
                "Accept": "application/json, text/event-stream",
                "mcp-protocol-version": "2026-07-28",
                "mcp-method": "tools/call",
                "mcp-name": "wrong_tool_name",
            }
            response = await http.post(url + "/mcp", headers=headers, json=body)
            assert response.status_code == 400
            assert "error" in response.json()
    api.positions_total.assert_not_called()
