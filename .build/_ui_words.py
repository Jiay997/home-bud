# -*- coding: utf-8 -*-
"""UI §8 表格中的残留措辞改为三态词汇（§11/§12 索引处的说明性提及保留）。"""
import io
import os

B = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(B, "ui-2.md")
s = io.open(p, encoding="utf-8").read()

PAIRS = [
    ("（具体数值待确认 Q-22）", "（具体数值为 **有默认方案，可开发但需记录风险**，见 Q-22）"),
    ("（推荐值待拍板）", "（默认值；**有默认方案，可开发但需记录风险**）"),
    ("为待确认项（Q-22），默认按", "为 **有默认方案，可开发但需记录风险**（Q-22），默认按"),
    ("| 14 | 所有待确认项已标注编号，未在界面上编造数值 |",
     "| 14 | 所有未决策项已按三态标注，且未在界面上编造数值（未决策内容留占位） |"),
]
n = 0
for a, b in PAIRS:
    c = s.count(a)
    n += c
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("replacements=%d" % n)