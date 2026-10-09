"""Safety tests; every native call is fake and no trading terminal is used."""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mcp_server_mt5.config import MT5Settings
from mcp_server_mt5.errors import MT5Error
from mcp_server_mt5.mt5_client import MT5Client
from mcp_server_mt5.owner import TerminalOwner
from mcp_server_mt5.tools import handle_tool_call


async def wait_event(event):
    async with asyncio.timeout(2):
        while not event.is_set():
            await asyncio.sleep(0.005)


def settings(tmp_path, **kwargs):
    return MT5Settings(
        _env_file=None,
        journal_file=tmp_path / "journal.jsonl",
        lock_file=tmp_path / "server.lock",
        **kwargs,
    )


def fake_api():
    api = Mock()
    api.initialize.return_value = True
    api.shutdown.return_value = None
    api.account_info.return_value = SimpleNamespace(login=123, server="Demo")
    api.last_error.return_value = (-42, "native failure")
    return api


async def test_all_native_calls_have_one_thread_and_error_affinity(tmp_path):
    api = fake_api()
    threads = []

    def record(result):
        def call(*args, **kwargs):
            threads.append(threading.get_ident())
            return result

        return call

    api.initialize.side_effect = record(True)
    api.account_info.side_effect = record(SimpleNamespace(login=123, server="Demo"))
    api.positions_get.side_effect = record(None)
    api.last_error.side_effect = record((-42, "native failure"))
    api.shutdown.side_effect = record(None)
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    results = await asyncio.gather(
        *(client.get_positions() for _ in range(8)), return_exceptions=True
    )
    assert all(isinstance(r, MT5Error) and r.error_code == -42 for r in results)
    await client.shutdown()
    assert len(set(threads)) == 1
    assert threads[0] != threading.get_ident()


async def test_queue_backpressure_and_queued_cancellation(tmp_path):
    owner = TerminalOwner(queue_size=1, timeout=2, journal_file=None)
    started, release = threading.Event(), threading.Event()
    calls = []

    def block():
        started.set()
        release.wait(2)

    first = asyncio.create_task(owner.submit(block, name="active"))
    await wait_event(started)
    queued = asyncio.create_task(owner.submit(lambda: calls.append("queued"), name="queued"))
    await asyncio.sleep(0.01)
    with pytest.raises(MT5Error) as error:
        await owner.submit(lambda: None, name="full")
    assert error.value.kind == "busy"
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    release.set()
    await first
    await owner.close(lambda: None, 1)
    assert calls == []


async def test_cancel_running_job_keeps_owner_and_persists_completion(tmp_path):
    path = tmp_path / "journal.jsonl"
    owner = TerminalOwner(queue_size=3, timeout=2, journal_file=path)
    started, release = threading.Event(), threading.Event()
    calls = []

    def trade():
        calls.append("start")
        started.set()
        release.wait(2)
        calls.append("finish")
        return {"order": 123, "success": True}

    active = asyncio.create_task(owner.submit(trade, name="send_order", mutating=True))
    await wait_event(started)
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active
    after = asyncio.create_task(owner.submit(lambda: calls.append("after"), name="read"))
    await asyncio.sleep(0.02)
    assert calls == ["start"]
    release.set()
    await after
    await owner.close(lambda: calls.append("shutdown"), 1)
    assert calls == ["start", "finish", "after", "shutdown"]
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["state"] for r in records] == ["started", "completed"]
    assert records[0]["operation_id"] == records[1]["operation_id"]
    assert records[1]["result"]["order"] == 123


async def test_active_timeout_fails_closed_without_replay_and_recovers(tmp_path):
    owner = TerminalOwner(queue_size=3, timeout=0.08, journal_file=tmp_path / "journal")
    started, release, done = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def trade():
        calls.append(1)
        started.set()
        release.wait(2)
        done.set()

    active = asyncio.create_task(owner.submit(trade, name="send_order", mutating=True))
    await wait_event(started)
    with pytest.raises(MT5Error) as error:
        await active
    assert error.value.outcome_unknown and error.value.operation_id
    assert owner.status["stalled"]
    with pytest.raises(MT5Error, match="overdue"):
        await owner.submit(lambda: calls.append(2), name="retry", mutating=True)
    release.set()
    await wait_event(done)
    await asyncio.sleep(0.01)
    assert await owner.submit(lambda: 7, name="read") == 7
    await owner.close(lambda: None, 1)
    assert calls == [1]


async def test_shutdown_waits_for_active_and_cancels_queued(tmp_path):
    owner = TerminalOwner(queue_size=3, timeout=2, journal_file=None)
    started, release = threading.Event(), threading.Event()
    calls = []

    def block():
        started.set()
        release.wait(2)
        calls.append("finish")

    active = asyncio.create_task(owner.submit(block, name="active"))
    await wait_event(started)
    queued = asyncio.create_task(owner.submit(lambda: calls.append("queued"), name="queued"))
    await asyncio.sleep(0.01)
    with pytest.raises(MT5Error) as error:
        await owner.close(lambda: calls.append("shutdown"), 0.02)
    assert error.value.kind == "shutdown_timeout"
    assert calls == []
    release.set()
    await active
    with pytest.raises(MT5Error, match="stopped before"):
        await queued
    await owner.close(lambda: None, 1)
    assert calls == ["finish", "shutdown"]


async def test_compound_close_keeps_reads_and_order_together(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    calls = []
    started, release = threading.Event(), threading.Event()

    def positions(*args, **kwargs):
        calls.append("positions")
        started.set()
        release.wait(2)
        p = Mock()
        p._asdict.return_value = {"type": 0, "symbol": "EURUSD", "volume": 1}
        return (p,)

    api.positions_get.side_effect = positions
    api.symbol_info.return_value = SimpleNamespace(visible=True)
    tick = Mock()
    tick._asdict.return_value = {"bid": 1.1, "ask": 1.2}
    api.symbol_info_tick.side_effect = lambda *a: (calls.append("tick"), tick)[1]
    result = Mock()
    result._asdict.return_value = {"retcode": 10009, "order": 99}
    api.order_send.side_effect = lambda *a: (calls.append("order"), result)[1]
    api.orders_total.side_effect = lambda: (calls.append("other"), 0)[1]
    close = asyncio.create_task(handle_tool_call(client, "close_position", {"ticket": 12}))
    await wait_event(started)
    other = asyncio.create_task(handle_tool_call(client, "get_pending_orders_count", {}))
    await asyncio.sleep(0.01)
    release.set()
    await asyncio.gather(close, other)
    await client.shutdown()
    assert calls == ["positions", "tick", "order", "other"]
    api.order_send.assert_called_once()


async def test_account_mismatch_blocks_trade(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    api.account_info.return_value = SimpleNamespace(login=999, server="Demo")
    with pytest.raises(MT5Error) as error:
        await client.send_order({"symbol": "EURUSD"})
    assert error.value.kind == "account_mismatch"
    api.order_send.assert_not_called()
    await client.shutdown()


async def test_account_switch_disabled_by_default(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    with pytest.raises(MT5Error) as error:
        await client.login(999, "do-not-log", "Other")
    assert error.value.kind == "forbidden"
    api.login.assert_not_called()
    assert "do-not-log" not in (tmp_path / "journal.jsonl").read_text()
    await client.shutdown()


async def test_journal_failure_prevents_native_dispatch(tmp_path):
    owner = TerminalOwner(queue_size=1, timeout=1, journal_file=tmp_path)
    called = Mock()
    with pytest.raises(IsADirectoryError):
        await owner.submit(called, name="send_order", mutating=True)
    called.assert_not_called()
    await owner.close(lambda: None, 1)


@pytest.mark.parametrize("method", ["get_positions", "get_orders", "get_symbols"])
async def test_empty_tuple_is_success_but_none_is_failure(tmp_path, method):
    api = fake_api()
    native = {
        "get_positions": "positions_get",
        "get_orders": "orders_get",
        "get_symbols": "symbols_get",
    }[method]
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    getattr(api, native).return_value = ()
    assert await getattr(client, method)() == []
    getattr(api, native).return_value = None
    with pytest.raises(MT5Error) as error:
        await getattr(client, method)()
    assert error.value.error_code == -42
    await client.shutdown()


@pytest.mark.parametrize("failure", [None, RuntimeError("native exception")])
async def test_native_order_failure_is_uncertain_after_dispatch(tmp_path, failure):
    api = fake_api()
    api.order_send.side_effect = failure if isinstance(failure, Exception) else None
    api.order_send.return_value = None
    client = MT5Client(settings(tmp_path), api=api)
    await client.initialize()
    with pytest.raises(MT5Error) as error:
        await client.send_order({"symbol": "EURUSD"})
    assert error.value.outcome_unknown
    assert "reconcile" in str(error.value).lower()
    api.order_send.assert_called_once()
    await client.shutdown()


async def test_failed_initial_account_pin_never_allows_trade(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path, expected_login=999), api=api)
    with pytest.raises(MT5Error) as error:
        await client.initialize()
    assert error.value.kind == "account_mismatch"
    with pytest.raises(MT5Error, match="not initialized"):
        await client.send_order({})
    api.order_send.assert_not_called()
    await client.shutdown()


async def test_account_epoch_rejects_previously_queued_trade(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path, allow_account_switch=True), api=api)
    await client.initialize()
    started, release = threading.Event(), threading.Event()

    def block():
        started.set()
        release.wait(2)
        return 0

    api.positions_total.side_effect = block

    def login(**kwargs):
        api.account_info.return_value = SimpleNamespace(login=999, server="Other")
        return True

    api.login.side_effect = login
    first = asyncio.create_task(client.get_positions_total())
    await wait_event(started)
    switch = asyncio.create_task(client.login(999, "not-recorded", "Other"))
    await asyncio.sleep(0.01)
    trade = asyncio.create_task(client.send_order({}))
    await asyncio.sleep(0.01)
    release.set()
    await asyncio.gather(first, switch)
    with pytest.raises(MT5Error) as error:
        await trade
    assert error.value.kind == "account_changed"
    api.order_send.assert_not_called()
    await client.shutdown()


async def test_shutdown_is_atomic_with_queue_dispatch(tmp_path):
    import queue

    owner = TerminalOwner(queue_size=3, timeout=2, journal_file=None)
    entered, release = threading.Event(), threading.Event()

    class PausingQueue(queue.Queue):
        def get(self, *args, **kwargs):
            if kwargs.get("block", True):
                entered.set()
                release.wait(2)
            return super().get(*args, **kwargs)

    owner.queue = PausingQueue(3)
    await wait_event(entered)
    called = Mock()
    pending = asyncio.create_task(owner.submit(called, name="send_order", mutating=True))
    await asyncio.sleep(0.01)
    close = asyncio.create_task(owner.close(lambda: None, 1))
    await asyncio.sleep(0.01)
    release.set()
    with pytest.raises(MT5Error, match="stopped before"):
        await pending
    await close
    called.assert_not_called()


async def test_result_limit_is_explicit_error(tmp_path):
    api = fake_api()
    client = MT5Client(settings(tmp_path, max_rows=1), api=api)
    await client.initialize()
    api.positions_get.return_value = (Mock(), Mock())
    with pytest.raises(MT5Error) as error:
        await client.get_positions()
    assert error.value.kind == "result_too_large"
    await client.shutdown()


async def test_login_must_verify_requested_identity(tmp_path):
    api = fake_api()
    api.login.return_value = True  # Native success alone is insufficient.
    client = MT5Client(settings(tmp_path, allow_account_switch=True), api=api)
    await client.initialize()
    with pytest.raises(MT5Error) as error:
        await client.login(999, "not-recorded", "Other")
    assert error.value.kind == "account_mismatch"
    with pytest.raises(MT5Error, match="not initialized"):
        await client.send_order({})
    api.order_send.assert_not_called()
    await client.shutdown()
