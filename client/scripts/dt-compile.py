# -*- coding: utf-8 -*-
"""触发微信开发者工具编译，让模拟器进入可交互状态。

为什么需要它：automator 的 evaluate 在「项目尚未编译 / 模拟器停在欢迎页」时会永久挂起。
实测仅靠 Ctrl+B 不足以把项目真正编译进模拟器，必须先真实点击工具栏的
「编译」圆形箭头按钮（这一步同时会把项目加载进 IDE 的资源管理器与编辑器）。

用法：python scripts/dt-compile.py [窗口标题关键字]
退出码：0 已触发；1 未找到窗口。
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


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
    keyword = sys.argv[1] if len(sys.argv) > 1 else "mp-weixin"
    ms = find_window(keyword)
    if not ms:
        print(f"[dt-compile] no window matches {keyword!r}")
        sys.exit(1)
    hwnd, title = ms[0]
    print(f"[dt-compile] window: {title!r}")

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.6)
    user32.ShowWindow(hwnd, 6)
    time.sleep(0.3)
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.8)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.5)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left

    # 1) 真实点击工具栏「编译」圆形箭头按钮（窗口右上角，距右边缘约 54px、距顶约 60px）
    cx, cy = rect.left + (w - 54), rect.top + 60
    user32.SetCursorPos(cx, cy)
    time.sleep(0.15)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    print(f"[dt-compile] clicked toolbar compile at ({w - 54},60)")
    time.sleep(1.2)

    # 2) 再补一次 Ctrl+B，覆盖点击未命中或菜单态的情况
    VK_CONTROL, VK_B, KEYUP = 0x11, 0x42, 0x0002
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_B, 0, 0, 0)
    time.sleep(0.08)
    user32.keybd_event(VK_B, 0, KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)
    print("[dt-compile] ctrl+b sent")
    sys.exit(0)


if __name__ == "__main__":
    main()
