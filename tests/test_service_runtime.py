"""Service control tests: no SCM registration or real terminal initialization."""

import asyncio
import json
import threading

import pytest

from mcp_server_mt5.service_runtime import ServiceConfig, run_controlled_server


class FakeServer:
    def __init__(self, *, fail_start=False, retained=False):
        self.started = False
        self.should_exit = False
        self.fail_start = fail_start
        self.retained = retained
        self.entered = False
        self.drained = False

    async def serve(self):
        self.entered = True
        if self.fail_start:
            return
        self.started = True
        while not self.should_exit:
            await asyncio.sleep(0)
        await asyncio.sleep(0.01)
        self.drained = True


async def test_stop_waits_for_server_drain_and_reports_running():
    server, stop, states = FakeServer(), threading.Event(), []

    def report(state):
        states.append(state)
        if state == "running":
            stop.set()

    await run_controlled_server(server, stop, report, lambda: False, poll_interval=0.001)
    assert server.drained
    assert "running" in states
    assert states[-1] == "stop_pending"


async def test_stop_before_start_never_initializes_terminal():
    server, stop = FakeServer(), threading.Event()
    stop.set()
    await run_controlled_server(server, stop, lambda _: None, lambda: False)
    assert not server.entered


async def test_failed_start_is_failure_for_scm_recovery():
    with pytest.raises(RuntimeError, match="unexpectedly"):
        await run_controlled_server(
            FakeServer(fail_start=True),
            threading.Event(),
            lambda _: None,
            lambda: False,
            poll_interval=0.001,
        )


async def test_uncertain_shutdown_holds_service_in_stop_pending():
    server, stop, states = FakeServer(), threading.Event(), []

    def report(state):
        states.append(state)
        if state == "running":
            stop.set()

    task = asyncio.create_task(
        run_controlled_server(
            server,
            stop,
            report,
            lambda: True,
            poll_interval=0.001,
        )
    )
    await asyncio.sleep(0.05)
    assert server.drained
    assert not task.done()  # Never reports a clean stop / permits automatic overlap.
    assert states[-1] == "stop_pending"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def config_payload(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    env = tmp_path / "server.env"
    env.write_text("", encoding="utf-8")
    terminal = tmp_path / "terminal64.exe"
    terminal.write_text("fake", encoding="utf-8")
    return dict(
        schema_version=1,
        env_file=str(env),
        terminal_path=str(terminal),
        runtime_root=str(root),
        host="127.0.0.1",
        port=8000,
    )


def test_config_requires_explicit_existing_paths(tmp_path):
    payload = config_payload(tmp_path)
    config_file = tmp_path / "service.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    config = ServiceConfig.load(config_file)
    assert config.runtime_root == tmp_path / "runtime"
    payload["env_file"] = "relative.env"
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="absolute"):
        ServiceConfig.load(config_file)


def test_config_rejects_unknown_fields_and_bad_port(tmp_path):
    payload = config_payload(tmp_path)
    with pytest.raises(ValueError):
        ServiceConfig(**(payload | {"password": "never-in-service-json"}))
    with pytest.raises(ValueError):
        ServiceConfig(**(payload | {"port": 0}))


def test_service_settings_pin_runtime_and_require_account_identity(tmp_path):
    config = ServiceConfig(**config_payload(tmp_path))
    from mcp_server_mt5.service_runtime import service_settings

    with pytest.raises(ValueError, match="expected_login"):
        service_settings(config)
    config.env_file.write_text(
        "MT5_EXPECTED_LOGIN=123\nMT5_EXPECTED_SERVER=Demo\nMT5_LOCK_FILE=untrusted.lock\n",
        encoding="utf-8",
    )
    settings = service_settings(config)
    assert settings.lock_file == config.runtime_root / "run" / "server.lock"
    assert settings.journal_file == config.runtime_root / "run" / "orders.jsonl"
    assert settings.log_file == config.runtime_root / "logs" / "server.log"
    assert not settings.allow_account_switch


def test_service_rejects_account_switch(tmp_path):
    config = ServiceConfig(**config_payload(tmp_path))
    config.env_file.write_text(
        "MT5_EXPECTED_LOGIN=123\nMT5_EXPECTED_SERVER=Demo\nMT5_ALLOW_ACCOUNT_SWITCH=true\n",
        encoding="utf-8",
    )
    from mcp_server_mt5.service_runtime import service_settings

    with pytest.raises(ValueError, match="account switching"):
        service_settings(config)


def test_service_rejects_credentials_for_a_different_pinned_account(tmp_path):
    config = ServiceConfig(**config_payload(tmp_path))
    config.env_file.write_text(
        "MT5_EXPECTED_LOGIN=123\nMT5_EXPECTED_SERVER=Demo\nMT5_LOGIN=456\n",
        encoding="utf-8",
    )
    from mcp_server_mt5.service_runtime import service_settings

    with pytest.raises(ValueError, match="account pins"):
        service_settings(config)
