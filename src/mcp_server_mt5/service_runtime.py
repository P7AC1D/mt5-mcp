"""SCM-independent lifecycle. Importing this module never connects to MT5."""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import MT5Settings, get_settings

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=1, ge=1, le=1)
    env_file: Path
    terminal_path: Path
    runtime_root: Path
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("env_file", "terminal_path", "runtime_root")
    @classmethod
    def absolute_local_path(cls, value: Path) -> Path:
        if not value.is_absolute() or str(value).startswith("\\\\"):
            raise ValueError("Service paths must be absolute local paths")
        return value

    @classmethod
    def load(cls, path: Path) -> ServiceConfig:
        if not path.is_absolute():
            raise ValueError("Service configuration path must be absolute")
        config = cls.model_validate_json(path.read_text(encoding="utf-8-sig"))
        for item in (config.env_file, config.terminal_path):
            if not item.is_file():
                raise ValueError("Required service input file is missing")
        if not config.runtime_root.is_dir():
            raise ValueError("Service runtime directory has not been provisioned")
        return config


def service_settings(config: ServiceConfig) -> MT5Settings:
    settings = get_settings(str(config.env_file))
    if settings.expected_login is None or not settings.expected_server:
        raise ValueError("Service requires expected_login and expected_server account pins")
    if settings.allow_account_switch:
        raise ValueError("Service does not permit automatic account switching")
    if (settings.login is not None and settings.login != settings.expected_login) or (
        settings.server is not None and settings.server != settings.expected_server
    ):
        raise ValueError("Configured credentials must match service account pins")
    settings.path = str(config.terminal_path)
    settings.lock_file = config.runtime_root / "run" / "server.lock"
    settings.journal_file = config.runtime_root / "run" / "orders.jsonl"
    settings.log_file = config.runtime_root / "logs" / "server.log"
    return settings


async def run_controlled_server(
    server,
    stop: threading.Event,
    report: Callable[[str], None],
    unsafe_shutdown: Callable[[], bool],
    *,
    poll_interval: float = 0.25,
) -> None:
    """Ask Uvicorn to drain; never force-kill an uncertain native operation.

    A retained application lock means the owner could still be using MT5. Stay
    alive/STOP_PENDING, retaining that lock, instead of allowing SCM replacement.
    This is intentionally not an automatic hung-native-call recovery mechanism.
    """
    if stop.is_set():
        return
    task = asyncio.create_task(server.serve())
    try:
        while not task.done():
            if stop.is_set():
                server.should_exit = True
                report("stop_pending")
            elif server.started:
                report("running")
            else:
                report("start_pending")
            await asyncio.sleep(poll_interval)
        if unsafe_shutdown():
            # Retrieve exceptions without allowing them to unwind the lock owner.
            if not task.cancelled():
                task.exception()
            logger.critical("Native shutdown uncertain; retaining service and lock for review")
            while True:
                report("stop_pending")
                await asyncio.sleep(poll_interval)
        await task
        if not stop.is_set():
            raise RuntimeError("HTTP server exited unexpectedly; SCM recovery is required")
        report("stop_pending")
    finally:
        # External process termination is outside graceful SCM stop. Never send
        # shutdown to a second native thread or replay any operation here.
        if not task.done():
            server.should_exit = True


async def run_service(config: ServiceConfig, stop: threading.Event, report) -> None:
    import uvicorn

    from . import configure_logging
    from .server import create_http_app

    settings = service_settings(config)
    for folder in (config.runtime_root / "run", config.runtime_root / "logs"):
        if not folder.is_dir():
            raise ValueError("Provision service run/logs directories before starting")
    configure_logging(settings, console=False)
    app = create_http_app(settings, host=config.host, mt5_path_override=str(config.terminal_path))
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.host,
            port=config.port,
            workers=1,
            access_log=False,
            log_config=None,
            timeout_graceful_shutdown=math.ceil(settings.shutdown_timeout),
        )
    )
    await run_controlled_server(
        server,
        stop,
        report,
        lambda: app.state.mt5_server.retained_lock is not None,
    )
