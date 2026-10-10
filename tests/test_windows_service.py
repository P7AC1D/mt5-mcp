"""Test the native SCM adapter without connecting to the SCM or MT5."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="pywin32 adapter")


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    import servicemanager
    import win32serviceutil

    from mcp_server_mt5 import windows_service

    states, errors = [], []
    monkeypatch.setattr(win32serviceutil.ServiceFramework, "__init__", lambda self, args: None)
    monkeypatch.setattr(
        win32serviceutil.ServiceFramework,
        "ReportServiceStatus",
        lambda self, state, **kwargs: states.append(state),
    )
    monkeypatch.setattr(servicemanager, "LogErrorMsg", errors.append)
    monkeypatch.setattr(windows_service.ServiceConfig, "load", lambda path: object())
    host = windows_service.service_class(tmp_path / "service.json")(["MT5-MCP"])
    return windows_service, host, states, errors


def test_scm_stop_and_shutdown_are_graceful_signals(adapter):
    _, host, _, _ = adapter
    host.SvcStop()
    assert host.stop_requested.is_set()
    host.stop_requested.clear()
    host.SvcShutdown()
    assert host.stop_requested.is_set()


def test_scm_success_only_reports_running_after_runtime_started(adapter, monkeypatch):
    import win32service

    module, host, states, errors = adapter

    async def run(config, stop, report):
        assert states == [win32service.SERVICE_START_PENDING]
        report("running")
        host.SvcStop()
        report("stop_pending")

    monkeypatch.setattr(module, "run_service", run)
    host.SvcRun()
    assert states[1] == win32service.SERVICE_RUNNING
    assert states[-1] == win32service.SERVICE_STOP_PENDING
    assert not errors


def test_scm_failure_raises_for_native_recovery_without_secret_output(adapter, monkeypatch):
    module, host, states, errors = adapter

    async def fail(*args):
        raise ValueError("secret-credential-must-not-reach-eventlog")

    monkeypatch.setattr(module, "run_service", fail)
    with pytest.raises(RuntimeError, match="inspect protected logs") as error:
        host.SvcRun()
    assert "secret-credential" not in str(error.value)
    assert len(errors) == 1
    assert "secret-credential" not in errors[0]


def test_validation_error_does_not_echo_configuration_secrets(adapter, monkeypatch):
    module, _, _, _ = adapter
    monkeypatch.setattr(sys, "argv", ["service", "--config", "C:\\service.json", "--validate"])

    def invalid(path):
        raise ValueError("secret-from-malformed-configuration")

    monkeypatch.setattr(module.ServiceConfig, "load", invalid)
    with pytest.raises(SystemExit) as error:
        module.main()
    assert "secret-from-malformed" not in str(error.value)
    assert "validation failed" in str(error.value)
