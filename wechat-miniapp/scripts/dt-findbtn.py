# -*- coding: utf-8 -*-
"""在 DevTools 窗口截图中定位「重新连接」按钮（鼠尾草绿实心胶囊）。

用法: python scripts/dt-findbtn.py <window_shot.png>
输出: "<cx> <cy>" 窗口内相对坐标（供 dt-mouse.py click 使用）；未找到输出 "none"
"""
import sys

from PIL import Image

TARGET = (126, 145, 131)
TOL = 40

img = Image.open(sys.argv[1]).convert('RGB')
w, h = img.size
px = img.load()

hits = []
for y in range(0, h, 2):
    for x in range(int(w * 0.5), w, 2):
        r, g, b = px[x, y]
        if abs(r - TARGET[0]) + abs(g - TARGET[1]) + abs(b - TARGET[2]) < TOL:
            hits.append((x, y))

if not hits:
    print('none')
    sys.exit(0)

ys = sorted({y for _, y in hits})
bands = []
cur = [ys[0]]
for y in ys[1:]:
    if y - cur[-1] <= 8:
        cur.append(y)
    else:
        bands.append(cur)
        cur = [y]
bands.append(cur)

best = None
for band in bands:
    lo, hi = band[0], band[-1]
    pts = [(x, y) for x, y in hits if lo <= y <= hi]
    xs = [x for x, _ in pts]
    width = max(xs) - min(xs)
    if len(pts) >= 200 and width >= 150:
        if best is None or len(pts) > best[0]:
            best = (len(pts), min(xs), max(xs), lo, hi)

if best is None:
    print('none')
    sys.exit(0)

_, x0, x1, y0, y1 = best
cx = (x0 + x1) // 2
cy = (y0 + y1) // 2
print(f'{cx} {cy}  # bbox=({x0},{y0})-({x1},{y1})')
