"""Resource path resolution that works both in development and in a PyInstaller bundle."""

import os
import sys


def resource_root():
    """Project root in development, the unpacked bundle folder when frozen."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(*parts):
    """Absolute path of a file inside the ``assets`` folder."""
    return os.path.join(resource_root(), 'assets', *parts)
