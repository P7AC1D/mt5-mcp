"""No SCM operations: verify registration, recovery and cleanup through a fake API."""

import subprocess
from unittest.mock import Mock

import pytest

from mcp_server_mt5.service_install import register_service


def api():
    fake = Mock()
    for index, name in enumerate(
        (
            "SC_MANAGER_CONNECT",
            "SC_MANAGER_CREATE_SERVICE",
            "SERVICE_CHANGE_CONFIG",
            "SERVICE_QUERY_CONFIG",
            "DELETE",
            "SERVICE_WIN32_OWN_PROCESS",
            "SERVICE_AUTO_START",
            "SERVICE_ERROR_NORMAL",
            "SERVICE_CONFIG_DESCRIPTION",
            "SERVICE_CONFIG_FAILURE_ACTIONS",
            "SERVICE_CONFIG_FAILURE_ACTIONS_FLAG",
            "SC_ACTION_RESTART",
        ),
        1,
    ):
        setattr(fake, name, index)
    fake.OpenSCManager.return_value = "manager"
    fake.CreateService.return_value = "new-service"
    return fake


def test_register_quotes_paths_and_sets_virtual_identity_auto_recovery():
    fake = api()
    python, config = r"C:\Program Files\Python\python.exe", r"C:\Service Root\service.json"
    register_service(python, config, fake)
    args = fake.CreateService.call_args.args
    assert args[5] == fake.SERVICE_AUTO_START
    assert args[7] == subprocess.list2cmdline(
        [
            python,
            "-I",
            "-m",
            "mcp_server_mt5.windows_service",
            "--config",
            config,
        ]
    )
    assert args[-2:] == ("NT SERVICE\\MT5-MCP", None)
    changes = {call.args[1]: call.args[2] for call in fake.ChangeServiceConfig2.call_args_list}
    assert changes[fake.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG] is True
    assert changes[fake.SERVICE_CONFIG_FAILURE_ACTIONS]["Actions"] == [
        (fake.SC_ACTION_RESTART, 60000),
        (fake.SC_ACTION_RESTART, 120000),
        (fake.SC_ACTION_RESTART, 300000),
    ]
    fake.StartService.assert_not_called()
    fake.DeleteService.assert_not_called()


def test_partial_registration_removes_only_new_registration():
    fake = api()
    fake.ChangeServiceConfig2.side_effect = OSError("failed")
    with pytest.raises(OSError):
        register_service(r"C:\python.exe", r"C:\service.json", fake)
    fake.DeleteService.assert_called_once_with("new-service")
    assert fake.CloseServiceHandle.call_count == 2


def test_existing_service_error_never_deletes_existing_registration():
    fake = api()
    fake.CreateService.side_effect = OSError("already exists")
    with pytest.raises(OSError):
        register_service(r"C:\python.exe", r"C:\service.json", fake)
    fake.DeleteService.assert_not_called()
    fake.CloseServiceHandle.assert_called_once_with("manager")
