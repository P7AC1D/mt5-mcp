"""_NativeClient._call must not pass an empty keyword dict to MetaTrader5.

MetaTrader5's C functions treat ``f(request, **{})`` as keywords present and fail
with (-2, "Unnamed arguments not allowed") before reaching the terminal. A Python
mock cannot tell ``f(x)`` from ``f(x, **{})``, so the real package is used. The
test never calls ``initialize``: without a terminal connection the expected error
is "No IPC connection", which proves the request got past argument parsing.
"""

import sys

import pytest

from mcp_server_mt5._native import _NativeClient
from mcp_server_mt5.config import MT5Settings
from mcp_server_mt5.errors import MT5Error

mt5 = pytest.importorskip("MetaTrader5") if sys.platform == "win32" else None

pytestmark = pytest.mark.skipif(mt5 is None, reason="needs the MetaTrader5 package on Windows")


@pytest.mark.parametrize("name", ["order_check", "order_send"])
def test_order_request_reaches_the_terminal_connection_step(tmp_path, name):
    settings = MT5Settings(
        _env_file=None,
        journal_file=tmp_path / "journal.jsonl",
        lock_file=tmp_path / "server.lock",
    )
    client = _NativeClient(settings, mt5)

    with pytest.raises(MT5Error) as error:
        client._call(name, {})

    assert "Unnamed arguments not allowed" not in str(error.value)
