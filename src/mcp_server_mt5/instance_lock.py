"""OS-backed single-instance lock, automatically released on process exit."""

import os
from pathlib import Path
from typing import BinaryIO


class InstanceLock:
    # Native operations may outlive a failed ASGI app/lifespan. Keep fail-closed
    # handles alive even if that app is garbage-collected. Only process exit
    # releases these retained locks; never launch a second owner in this process.
    _retained_locks: list["InstanceLock"] = []

    def retain(self) -> None:
        self.retained = True
        self._retained_locks.append(self)

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.stream: BinaryIO | None = None
        self.retained = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Windows permits locking past EOF. Initialize only AFTER acquiring
            # the byte lock: reading another owner's locked byte raises before
            # the normal duplicate-lock handler and can leak the open handle.
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
                stream.flush()
        except OSError:
            stream.close()
            raise RuntimeError(f"Another server holds the instance lock: {self.path}") from None
        self.stream = stream
        return self

    def __exit__(self, *args):
        if self.stream and not self.retained:
            self.stream.close()
            self.stream = None
