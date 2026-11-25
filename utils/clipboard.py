"""System clipboard access without spawning any subprocess.

Spawning ``clip.exe`` / ``powershell`` from a windowed (fullscreen) game flashes a console window,
steals focus from the game, and ``clip`` mangles UTF-16 text without a BOM. On Windows the clipboard
is therefore accessed directly through the Win32 API; elsewhere ``pygame.scrap`` is used.
"""

import sys
import time

import pygame

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_OPEN_RETRIES = 10


def _win32():
    """Win32 function prototypes (handles are pointer sized: never rely on ctypes' int default)."""
    import ctypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    c_void_p, c_uint, c_size_t = ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t
    kernel32.GlobalAlloc.restype, kernel32.GlobalAlloc.argtypes = c_void_p, [c_uint, c_size_t]
    kernel32.GlobalLock.restype, kernel32.GlobalLock.argtypes = c_void_p, [c_void_p]
    kernel32.GlobalUnlock.argtypes = [c_void_p]
    kernel32.GlobalFree.argtypes = [c_void_p]
    user32.OpenClipboard.argtypes = [c_void_p]
    user32.SetClipboardData.restype, user32.SetClipboardData.argtypes = c_void_p, [c_uint, c_void_p]
    user32.GetClipboardData.restype, user32.GetClipboardData.argtypes = c_void_p, [c_uint]
    return ctypes, user32, kernel32


def _open_clipboard(user32):
    """The clipboard can be briefly locked by another program: retry a few times."""
    for _ in range(_OPEN_RETRIES):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.01)
    return False


def _win_copy(text):
    ctypes, user32, kernel32 = _win32()
    data = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        return False
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not _open_clipboard(user32):
        kernel32.GlobalFree(handle)
        return False
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True  # the system owns the memory now
    finally:
        user32.CloseClipboard()


def _win_paste():
    ctypes, user32, kernel32 = _win32()
    if not _open_clipboard(user32):
        return ""
    try:
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def copy_text(text):
    """Put ``text`` in the clipboard. Returns True on success."""
    try:
        if sys.platform == "win32":
            return _win_copy(text)
        pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
        return True
    except Exception as e:
        print(f"[CLIPBOARD] copy failed: {e}")
        return False


def paste_text():
    """Text currently in the clipboard ('' if none or on error)."""
    try:
        if sys.platform == "win32":
            return _win_paste().strip()
        pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        return raw.decode("utf-8", errors="ignore").rstrip("\x00").strip() if raw else ""
    except Exception as e:
        print(f"[CLIPBOARD] paste failed: {e}")
        return ""
