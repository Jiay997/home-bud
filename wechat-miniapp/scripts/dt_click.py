"""Bring DevTools to front and click at window-relative coords."""
import sys
import time
import ctypes
from ctypes import wintypes

u = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


def find_hwnd():
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        if u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(h, b, 256)
            if '微信开发者工具' in b.value:
                found.append(h)
        return True

    u.EnumWindows(proc(cb), 0)
    if not found:
        raise SystemExit('DevTools window not found')
    return found[0]


HWND = find_hwnd()


def restore():
    u.ShowWindow(HWND, 9)
    u.SetForegroundWindow(HWND)
    r = wintypes.RECT()
    u.GetWindowRect(HWND, ctypes.byref(r))
    return r


def click(x, y):
    time.sleep(0.6)
    u.SetCursorPos(POINT(x, y))
    time.sleep(0.25)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    u.mouse_event(0x0004, 0, 0, 0, 0)


if __name__ == '__main__':
    args = sys.argv[1:]
    maximize = bool(args) and args[0] == '--max'
    if maximize:
        args = args[1:]
    u.ShowWindow(HWND, 3 if maximize else 9)
    u.SetForegroundWindow(HWND)
    time.sleep(1.2)
    r = wintypes.RECT()
    u.GetWindowRect(HWND, ctypes.byref(r))
    print('window', r.left, r.top, r.right, r.bottom)
    for pair in args:
        wx, wy = pair.split(',')
        click(r.left + int(wx), r.top + int(wy))
        print('clicked', pair)
        time.sleep(0.5)
