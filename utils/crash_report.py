"""Crash reporting for the windowed executable (which has no console to show errors in).

Every uncaught exception (main thread or server/network threads) and every native crash is written
to ``crash.log`` in the user data folder; on Windows a message box shows where the log is.
"""

import datetime
import faulthandler
import os
import sys
import threading
import traceback

_log_file = None


def log_path():
    from storage.saves import get_folder_save
    return os.path.join(get_folder_save(), "crash.log")


def _write(title, details):
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} {title} ===\n{details}\n")
    except OSError:
        pass


def _show_message(text):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Echo - error", 0x10)  # MB_ICONERROR
    except Exception:
        pass


def install():
    """Route uncaught exceptions and native crashes to ``crash.log``."""
    global _log_file
    try:
        _log_file = open(log_path(), "a", encoding="utf-8")
        faulthandler.enable(file=_log_file)  # segfaults and fatal errors
    except OSError:
        pass

    def on_exception(exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        _write("uncaught exception", details)
        if not issubclass(exc_type, KeyboardInterrupt):
            _show_message(f"The game crashed:\n\n{exc_type.__name__}: {exc}\n\nDetails: {log_path()}")
        sys.__excepthook__(exc_type, exc, tb)

    def on_thread_exception(args):
        details = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _write(f"exception in thread {args.thread.name if args.thread else '?'}", details)

    sys.excepthook = on_exception
    threading.excepthook = on_thread_exception
