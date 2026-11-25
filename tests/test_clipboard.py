"""Clipboard round trip (Windows only: other platforms need a display server)."""

import sys

import pytest

from utils import clipboard

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Win32 clipboard")


def test_copy_paste_round_trip_keeps_exact_text():
    saved = clipboard.paste_text()
    try:
        for text in ("192.168.0.9", "10.0.0.1, 100.64.0.2", "accentué é ü 日本"):
            assert clipboard.copy_text(text)
            assert clipboard.paste_text() == text
    finally:
        if saved:
            clipboard.copy_text(saved)
