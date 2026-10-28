"""Capture the WeChat DevTools window off-screen via PrintWindow (survives occlusion)."""
import sys
import ctypes
from ctypes import wintypes
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def find_window(substr):
    found = []

    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if substr in buf.value:
            found.append((h, buf.value))
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def capture(hwnd, out_path):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError('bad window size')

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bmp)

    PW_RENDERFULLCONTENT = 2
    ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    class BIHDR(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
            ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
            ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
            ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
            ('biClrImportant', wintypes.DWORD),
        ]

    bmi = BITMAPINFO = (BIHDR * 1)()
    bmi[0].biSize = ctypes.sizeof(BIHDR)
    bmi[0].biWidth = w
    bmi[0].biHeight = -h
    bmi[0].biPlanes = 1
    bmi[0].biBitCount = 32
    bmi[0].biCompression = 0

    buf_len = w * h * 4
    buf = (ctypes.c_char * buf_len)()
    gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi[0]), 0)

    img = Image.frombytes('RGBA', (w, h), bytes(buf), 'raw', 'BGRA').convert('RGB')
    img.save(out_path)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    return ok, img.size


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'capture.png'
    matches = find_window('微信开发者工具')
    if not matches:
        matches = find_window('mp-weixin')
    if not matches:
        raise SystemExit('DevTools window not found')
    hwnd, title = matches[0]
    print('window', hwnd, title)
    print(capture(hwnd, out))
