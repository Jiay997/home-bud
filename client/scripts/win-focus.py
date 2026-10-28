# -*- coding: utf-8 -*-
"""把微信开发者工具窗口强制置前（供 miniprogram-automator 截图使用）。

Windows 前台锁会让后台进程的 SetForegroundWindow 静默失败，
这里用三板斧：minimize+restore → AttachThreadInput → 模拟 ALT 键。

用法：python scripts/win-focus.py [窗口标题关键字]
退出码：0 已置前；3 未能置前。
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def find_window(keyword: str):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lp):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, b, n + 1)
                if keyword in b.value:
                    out.append((hwnd, b.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "mp-weixin"
    matches = find_window(keyword)
    if not matches:
        print(f"[win-focus] no window matches {keyword!r}")
        sys.exit(1)
    hwnd, title = matches[0]
    print(f"[win-focus] window: {title!r}")

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.8)

    # 1) minimize + restore
    user32.ShowWindow(hwnd, 6)
    time.sleep(0.4)
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.8)

    # 2) attach thread input
    if user32.GetForegroundWindow() != hwnd:
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None)
        cur_tid = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(cur_tid, fg_tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(cur_tid, fg_tid, False)
        time.sleep(0.4)

    # 3) ALT key hack
    if user32.GetForegroundWindow() != hwnd:
        VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.4)

    ok = user32.GetForegroundWindow() == hwnd
    print(f"[win-focus] foreground: {ok}")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
