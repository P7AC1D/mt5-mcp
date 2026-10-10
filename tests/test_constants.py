"""On Windows, verify enum constants against the installed official wheel."""

import importlib
import sys

import pytest

from mcp_server_mt5 import constants


@pytest.mark.skipif(sys.platform != "win32", reason="Official native MT5 wheel is Windows-only")
def test_constants_match_official_native_package():
    native = importlib.import_module("MetaTrader5")
    for name in dir(constants):
        if name.isupper():
            assert getattr(constants, name) == getattr(native, name), name
