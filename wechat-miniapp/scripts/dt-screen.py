# -*- coding: utf-8 -*-
"""全屏抓取（可包含弹出菜单/独立弹出窗口），裁剪到 DevTools 窗口范围。

PrintWindow 抓不到菜单栏弹出层，此脚本用 ImageGrab 屏幕抓取替代。

用法:
  python scripts/dt-screen.py <out.png> [click_x,click_y] [margin]

click_x,click_y: 可选，窗口内相对坐标，先点击再截图（等待 1s）。
margin: 可选，向外扩展像素（默认 60，便于看到窗口边缘）。
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

from PIL import ImageGrab

user32 = ctypes.windll.user32


def find_window(keyword):
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
    out = sys.argv[1]
    click = None
    margin = 0
    for a in sys.argv[2:]:
        if "," in a:
            click = tuple(int(v) for v in a.split(","))
        else:
            margin = int(a)

    ms = find_window('mp-weixin')
    if not ms:
        print('no window')
        sys.exit(1)
    hwnd, title = ms[0]
    print('window:', title)

    user32.ShowWindow(hwnd, 6)
    time.sleep(0.3)
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.5)
    HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
    SWP_NOSIZE, SWP_NOMOVE = 0x1, 0x2
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.8)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print('rect:', rect.left, rect.top, rect.right, rect.bottom)

    if click:
        ox, oy = rect.left, rect.top
        x, y = ox + click[0], oy + click[1]
        user32.SetCursorPos(x, y)
        time.sleep(0.1)
        user32.mouse_event(0x2, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x4, 0, 0, 0, 0)
        time.sleep(1.0)

    img = ImageGrab.grab(all_screens=True)
    img = img.crop((rect.left - margin, rect.top - margin, rect.right + margin, rect.bottom + margin))
    img = img.convert('RGB')
    img.save(out)
    print('saved', out, img.size)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)


if __name__ == '__main__':
    main()
