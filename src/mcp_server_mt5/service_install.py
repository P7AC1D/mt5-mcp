"""Explicit administrative registration; never starts the service or touches ACLs."""

import argparse
import subprocess
import sys
from pathlib import Path

from .windows_service import SERVICE_NAME


def register_service(python: str, config: str, api) -> None:
    command = subprocess.list2cmdline(
        [
            python,
            "-I",
            "-m",
            "mcp_server_mt5.windows_service",
            "--config",
            config,
        ]
    )
    manager = api.OpenSCManager(None, None, api.SC_MANAGER_CONNECT | api.SC_MANAGER_CREATE_SERVICE)
    service = None
    try:
        # DELETE is a standard access right, not a service-specific permission.
        access = api.SERVICE_CHANGE_CONFIG | api.SERVICE_QUERY_CONFIG | 0x00010000
        service = api.CreateService(
            manager,
            SERVICE_NAME,
            "MetaTrader 5 MCP",
            access,
            api.SERVICE_WIN32_OWN_PROCESS,
            api.SERVICE_AUTO_START,
            api.SERVICE_ERROR_NORMAL,
            command,
            None,
            0,
            None,
            "NT SERVICE\\MT5-MCP",
            None,
        )
        api.ChangeServiceConfig2(
            service,
            api.SERVICE_CONFIG_DESCRIPTION,
            "Native MT5 MCP; validate Session 0 before relying on boot availability",
        )
        api.ChangeServiceConfig2(
            service,
            api.SERVICE_CONFIG_FAILURE_ACTIONS,
            {
                "ResetPeriod": 86400,
                "RebootMsg": None,
                "Command": None,
                "Actions": [
                    (api.SC_ACTION_RESTART, 60000),
                    (api.SC_ACTION_RESTART, 120000),
                    (api.SC_ACTION_RESTART, 300000),
                ],
            },
        )
        api.ChangeServiceConfig2(service, api.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG, True)
    except Exception:
        if service is not None:
            try:
                api.DeleteService(service)
            except Exception:
                raise RuntimeError(
                    "Incomplete MT5-MCP registration remains; inspect SCM before reboot"
                ) from None
        raise
    finally:
        if service is not None:
            api.CloseServiceHandle(service)
        api.CloseServiceHandle(manager)


def main():
    parser = argparse.ArgumentParser(description="Explicit native MT5-MCP registration")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--register", action="store_true", required=True)
    args = parser.parse_args()
    if not args.config.is_absolute():
        parser.error("--config must be an absolute path")
    import win32service

    try:
        register_service(sys.executable, str(args.config), win32service)
    except Exception as error:
        print(
            f"Service registration failed ({type(error).__name__}, "
            f"Windows error {getattr(error, 'winerror', 'unavailable')}); inspect SCM state",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print("Registered MT5-MCP with Automatic startup/recovery; service NOT STARTED")


if __name__ == "__main__":
    main()
