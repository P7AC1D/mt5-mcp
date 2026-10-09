"""Bounded, cancellation-safe ownership of the synchronous MT5 extension.

Cancellation can prevent queued work. It cannot stop a native call that has
started: the owner retains that job until it finishes and never replays it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import queue
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import MT5Error

logger = logging.getLogger(__name__)


@dataclass
class Job:
    call: Callable[[], Any]
    name: str
    deadline: float
    mutating: bool = False
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    future: concurrent.futures.Future = field(default_factory=concurrent.futures.Future)


class TerminalOwner:
    """One daemon thread, one bounded queue, no native-call overlap."""

    def __init__(self, *, queue_size: int, timeout: float, journal_file: Path | None):
        self.timeout = timeout
        self.queue: queue.Queue[Job] = queue.Queue(maxsize=queue_size)
        self.journal_file = journal_file
        self._accepting = True
        self._closing = threading.Event()
        self._closed = threading.Event()
        self._state_lock = threading.Lock()
        self._active: Job | None = None
        self._finalizer: Callable[[], Any] | None = None
        self._close_error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="mt5-terminal-owner", daemon=True)
        self.thread.start()

    def _is_stalled(self) -> bool:
        return self._active is not None and time.monotonic() >= self._active.deadline

    @property
    def status(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "accepting": self._accepting,
                "stalled": self._is_stalled(),
                "queued": self.queue.qsize(),
                "active": self._active is not None,
                "closed": self._closed.is_set(),
            }

    def _journal(self, job: Job, state: str, result: Any = None) -> None:
        if not job.mutating or self.journal_file is None:
            return
        record = {
            "operation_id": job.operation_id,
            "operation": job.name,
            "state": state,
            "time": time.time(),
        }
        if state == "completed":
            record["result"] = result
        # Arguments (especially login credentials) are deliberately never written.
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, default=str, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    async def submit(self, call: Callable[[], Any], *, name: str, mutating: bool = False) -> Any:
        with self._state_lock:
            if not self._accepting or self._is_stalled():
                raise MT5Error(
                    "Terminal owner is stopping or awaiting an overdue native operation.",
                    kind="unavailable",
                )
            job = Job(call, name, time.monotonic() + self.timeout, mutating)
            try:
                self.queue.put_nowait(job)
            except queue.Full:
                raise MT5Error(
                    "MT5 request queue is full. No operation was started.", kind="busy"
                ) from None
        future = asyncio.wrap_future(job.future)
        # Consume eventual failures even if the original request is gone.
        future.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=self.timeout)
        except asyncio.CancelledError:
            if not job.future.cancel():
                logger.warning(
                    "Request cancelled while operation %s is running; outcome must be reconciled",
                    job.operation_id,
                )
            raise
        except TimeoutError:
            cancelled = job.future.cancel()
            if not cancelled and job.future.done():
                return job.future.result()
            raise MT5Error(
                "Request deadline exceeded. "
                + (
                    "Queued operation was not started."
                    if cancelled
                    else "Native operation may have completed. Do not retry a trade; reconcile its outcome first."
                ),
                kind="deadline_exceeded",
                operation_id=job.operation_id,
                outcome_unknown=not cancelled and mutating,
            ) from None

    def _run(self) -> None:
        try:
            while not self._closing.is_set():
                try:
                    job = self.queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    with self._state_lock:
                        if self._closing.is_set():
                            if not job.future.done():
                                job.future.set_exception(
                                    MT5Error("Server stopped before dispatch.", kind="unavailable")
                                )
                            continue
                        if not job.future.set_running_or_notify_cancel():
                            continue
                        if time.monotonic() >= job.deadline:
                            job.future.set_exception(
                                MT5Error(
                                    "Queued request expired before execution.",
                                    kind="deadline_exceeded",
                                )
                            )
                            continue
                        self._active = job
                    # A journal failure BEFORE dispatch fails closed, so no trade is sent.
                    self._journal(job, "started")
                    result = job.call()
                    try:
                        self._journal(job, "completed", result)
                    except Exception:
                        logger.exception(
                            "Could not persist completed operation %s", job.operation_id
                        )
                        raise MT5Error(
                            "Native operation completed but its audit result could not be persisted; reconcile before retrying.",
                            kind="journal_error",
                            operation_id=job.operation_id,
                            outcome_unknown=job.mutating,
                        ) from None
                    job.future.set_result(result)
                except Exception as error:
                    if isinstance(error, MT5Error) and error.operation_id is None:
                        error.operation_id = job.operation_id
                    if not job.future.done():
                        job.future.set_exception(error)
                finally:
                    with self._state_lock:
                        self._active = None
                    self.queue.task_done()
            # Stop means queued work will not run; the active call has finished.
            while True:
                try:
                    job = self.queue.get_nowait()
                except queue.Empty:
                    break
                if not job.future.done():
                    job.future.set_exception(
                        MT5Error("Server stopped before dispatch.", kind="unavailable")
                    )
                self.queue.task_done()
            if self._finalizer is not None:
                self._finalizer()
        except BaseException as error:
            self._close_error = error
            logger.error("Terminal owner stopped with %s", type(error).__name__)
        finally:
            self._closed.set()

    async def close(self, finalizer: Callable[[], Any], timeout: float) -> None:
        with self._state_lock:
            self._accepting = False
            if not self._closing.is_set():
                self._finalizer = finalizer
                self._closing.set()
        deadline = time.monotonic() + timeout
        # Do not occupy asyncio's default executor with an unkillable join().
        while not self._closed.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        if not self._closed.is_set():
            raise MT5Error(
                "Shutdown timed out waiting for a native call. No overlapping shutdown was started; reconcile trades before restart.",
                kind="shutdown_timeout",
                outcome_unknown=True,
            )
        if self._close_error:
            raise MT5Error("Native shutdown failed.", kind="shutdown_failed") from self._close_error
