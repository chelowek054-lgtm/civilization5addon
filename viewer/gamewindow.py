"""The Civ 5 game window (Windows only): find it, tell whether it runs in
exclusive fullscreen (nothing can stay above it then) and turn the windowed
game into borderless fullscreen so the overlay can sit on top of it.

Civ 5 has no borderless mode of its own: "windowed" at screen size still has
a title bar and frame. Removing them is what tools like Borderless Gaming do;
it changes nothing in the game itself and is undone when the game restarts.
"""
import ctypes
import os
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
GAME_EXES = ("civilizationv_dx11.exe", "civilizationv_dx9.exe", "civilizationv.exe",
             "civilizationv_tablet.exe")

WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
WS_SYSMENU, WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00080000, 0x00020000, 0x00010000
FRAME = WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX


def _exe_of(hwnd):
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def find_game():
    """(hwnd, exe name) of the visible Civ 5 main window, or (None, None)."""
    if not IS_WIN:
        return None, None
    found = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):   # no owner: main window
            exe = _exe_of(hwnd)
            if exe in GAME_EXES:
                found.append((hwnd, exe))
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else (None, None)


def exclusive_fullscreen(exe, user_dir):
    """True if the game's graphics settings say FullScreen = 1."""
    ini = "GraphicsSettingsDX9.ini" if exe and "dx9" in exe else "GraphicsSettingsDX11.ini"
    try:
        with open(os.path.join(user_dir, ini), encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip().lower() == "fullscreen":
                    return value.strip() == "1"
    except OSError:
        pass
    return False


def make_borderless(hwnd):
    """Strip the frame and fill the monitor the window is on. Returns True if changed."""
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, -16)
    if not style & WS_CAPTION:
        return False
    user32.SetWindowLongW(hwnd, -16, style & ~FRAME)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
    r = mi.rcMonitor
    # SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOACTIVATE
    user32.SetWindowPos(hwnd, 0, r.left, r.top, r.right - r.left, r.bottom - r.top, 0x0020 | 0x0004 | 0x0010)
    return True
