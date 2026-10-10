"""Async public client backed by one cancellation-safe terminal owner."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable, Coroutine
from typing import Any

try:
    mt5 = importlib.import_module("MetaTrader5")
except ModuleNotFoundError:
    mt5 = None  # The actual adapter is Windows-only; tests inject an implementation.

from ._native import _NativeClient
from .config import MT5Settings
from .errors import MT5Error
from .owner import TerminalOwner

__all__ = ["MT5Client", "MT5Error"]


class _OwnerView:
    """Async-shaped adapter used only inside a complete owner-thread transaction."""

    def __init__(self, native: _NativeClient):
        self.native = native

    def __getattr__(self, name: str) -> Any:
        method = getattr(self.native, name)

        async def invoke(*args: Any, **kwargs: Any) -> Any:
            return method(*args, **kwargs)

        return invoke


class MT5Client:
    def __init__(self, settings: MT5Settings | None = None, *, api: Any = None):
        self.settings = settings or MT5Settings()
        self._native = _NativeClient(self.settings, api if api is not None else mt5)
        self._owner = TerminalOwner(
            queue_size=self.settings.queue_size,
            timeout=self.settings.request_timeout,
            journal_file=self.settings.journal_file,
        )
        self._ready = False
        self._closed = False

    @property
    def _initialized(self) -> bool:
        return self._ready

    @property
    def _selected_symbols(self) -> set[str]:
        return self._native._selected_symbols

    @property
    def status(self) -> dict[str, Any]:
        state = self._owner.status
        return {
            **state,
            "ready": self._ready
            and self._native._initialized
            and state["accepting"]
            and not state["stalled"],
        }

    async def initialize(self, path_override: str | None = None) -> bool:
        def initialize_and_check():
            result = self._native.initialize(path_override)
            return result, self._native.get_terminal_info()

        result, info = await self._owner.submit(initialize_and_check, name="initialize")
        self._ready = bool(info.get("connected", False))
        return result

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._ready = False
        await self._owner.close(self._native.shutdown, self.settings.shutdown_timeout)
        self._closed = True

    async def transaction(
        self, call: Callable[[Any], Coroutine[Any, Any, Any]], *, name: str, mutating: bool = False
    ) -> Any:
        generation = self._native.account_generation

        def execute() -> Any:
            if generation != self._native.account_generation:
                raise MT5Error(
                    "Account changed after this request was queued. Review the account before submitting again.",
                    kind="account_changed",
                )
            self._native.verify_account()
            # All await points inside handlers resolve on this owner, so account
            # checks/read-modify-write/error capture form one indivisible job.
            return asyncio.run(call(_OwnerView(self._native)))

        return await self._owner.submit(execute, name=name, mutating=mutating)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        method = getattr(self._native, name)

        async def invoke(*args: Any, **kwargs: Any) -> Any:
            generation = self._native.account_generation

            def execute():
                if generation != self._native.account_generation:
                    raise MT5Error(
                        "Account changed after this request was queued.", kind="account_changed"
                    )
                return method(*args, **kwargs)

            return await self._owner.submit(
                execute, name=name, mutating=name in {"send_order", "login"}
            )

        return invoke
