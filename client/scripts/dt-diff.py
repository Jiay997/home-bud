# -*- coding: utf-8 -*-
"""比较两张同尺寸截图的差异比例（用于「点击后 UI 是否真的变了」的客观证据）。

弹层/对话框往往渲染在子组件里，页面数据层看不到 visible 字段，
因此用像素差异作为补充信号。

用法: python scripts/dt-diff.py <a.png> <b.png>
输出: 差异像素占比，如 0.1304（尺寸不同直接输出 1.0000）
"""
import sys

from PIL import Image, ImageChops

a = Image.open(sys.argv[1]).convert('L')
b = Image.open(sys.argv[2]).convert('L')
if a.size != b.size:
    print('1.0000')
    sys.exit(0)

diff = ImageChops.difference(a, b)
hist = diff.histogram()
total = a.size[0] * a.size[1]
# 忽略 <=8 的轻微噪声（抗锯齿/字体渲染抖动）
changed = sum(hist[9:])
print(f'{changed / total:.4f}')
