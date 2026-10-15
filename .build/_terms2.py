# -*- coding: utf-8 -*-
"""术语终检第二轮（仅修正非"替换表/引用评审原文"语境的残留）。"""
import os
import io

B = os.path.dirname(os.path.abspath(__file__))

FIX = {
    "prd-1.md": [("5 个 Agent 全部可调用；两大模块可用", "3 个领域 Agent + 编排器 + 风险控制服务全部可调用；两大模块可用")],
    "prd-5.md": [("风险预警 Agent", "风险控制服务")],
    "add-loop.md": [("§13.5", "§12.9")],
}

for name, pairs in FIX.items():
    p = os.path.join(B, name)
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("fixed", name)