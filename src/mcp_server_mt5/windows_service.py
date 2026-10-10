"""Native SCM entry point, launched by an absolute venv python.exe -I -m.

No install/debug/start convenience command: importing or validating this module
does not open MT5. Registration is separate and explicit in Install-Mt5Service.ps1.
"""

import argparse
import asyncio
import threading
from pathlib import Path

from .service_runtime import ServiceConfig, run_service, service_settings

SERVICE_NAME = "MT5-MCP"


def service_class(config_path: Path):
    import servicemanager
    import win32service
    import win32serviceutil

    class MT5Service(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = "MetaTrader 5 MCP"

        def __init__(self, args):
            super().__init__(args)
            self.stop_requested = threading.Event()
            self.last_state = None

        def SvcStop(self):
            self.stop_requested.set()

        def SvcShutdown(self):
            self.SvcStop()

        def report(self, state):
            statuses = {
                "start_pending": win32service.SERVICE_START_PENDING,
                "running": win32service.SERVICE_RUNNING,
                "stop_pending": win32service.SERVICE_STOP_PENDING,
            }
            # Pending reports advance SCM checkpoints; RUNNING needs no heartbeat.
            if state != "running" or state != self.last_state:
                self.ReportServiceStatus(statuses[state], waitHint=10000)
                self.last_state = state

        def SvcRun(self):
            try:
                self.report("start_pending")
                config = ServiceConfig.load(config_path)
                asyncio.run(run_service(config, self.stop_requested, self.report))
                self.report("stop_pending")
                # pywin32 reports STOPPED/0 after a normal return. Exceptions are
                # reported as nonzero STOPPED, enabling SCM failure actions.
            except Exception as error:
                servicemanager.LogErrorMsg(
                    f"MT5-MCP service failed ({type(error).__name__}); inspect protected logs"
                )
                raise RuntimeError("MT5-MCP service failed; inspect protected logs") from None

    return MT5Service


def main():
    parser = argparse.ArgumentParser(description="Native MT5 MCP Windows service host")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--validate", action="store_true", help="Validate files/settings only")
    args = parser.parse_args()
    if args.validate:
        try:
            config = ServiceConfig.load(args.config)
            settings = service_settings(config)
            # Constructing an app validates remote authentication/hosts but does not
            # enter its lifespan, initialize MT5 or bind a listening socket.
            from .server import create_http_app

            create_http_app(settings, host=config.host, mt5_path_override=str(config.terminal_path))
        except Exception as error:
            # Settings-validation exceptions can include input values. Never echo
            # them into an installer transcript or task output.
            raise SystemExit(
                f"Service validation failed ({type(error).__name__}); check protected configuration locally"
            ) from None
        print("Service configuration validated; no terminal connection or listener started")
        return
    import servicemanager

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(service_class(args.config))
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    main()
