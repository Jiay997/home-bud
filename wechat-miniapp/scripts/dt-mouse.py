# -*- coding: utf-8 -*-
"""DevTools 调试器面板操作小工具（临时）：置前窗口 + 鼠标拖拽/点击。

用法：
  python scripts/dt-mouse.py drag <x1> <y1> <x2> <y2>   # 窗口内相对坐标拖拽
  python scripts/dt-mouse.py click <x> <y>              # 窗口内相对坐标点击
"""
import ctypes
import sys
import time
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


def find_window(keyword: str):
    matches = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lp):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, b, n + 1)
                if keyword in b.value:
                    matches.append((hwnd, b.value))
        return True

    user32.EnumWindows(cb, 0)
    return matches


def main():
    mode, args = sys.argv[1], [int(v) for v in sys.argv[2:]]
    matches = find_window('mp-weixin')
    if not matches:
        print('no window')
        sys.exit(1)
    hwnd = matches[0][0]
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.8)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    ox, oy = rect.left, rect.top
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)

    def move(x, y):
        user32.SetCursorPos(ox + x, oy + y)
        time.sleep(0.05)

    if mode == 'drag':
        x1, y1, x2, y2 = args
        move(x1, y1)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        steps = 12
        for i in range(1, steps + 1):
            move(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        print(f'drag ({x1},{y1})->({x2},{y2}) from origin ({ox},{oy})')
    elif mode == 'wheel':
        x, y, delta = args
        move(x, y)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta * 120, 0)
        print(f'wheel at ({x},{y}) delta={delta} from origin ({ox},{oy})')
    elif mode == 'click':
        x, y = args
        move(x, y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        print(f'click ({x},{y}) from origin ({ox},{oy})')


if __name__ == '__main__':
    main()
