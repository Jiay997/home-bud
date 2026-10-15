# -*- coding: utf-8 -*-
"""V1.2 术语与交叉引用终检修正（一次性）。"""
import glob
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))

# 1) 源文件级替换（台账是附录的唯一来源，必须一起改）
FIX = {
    "ledger.py": [
        ("异常场景处理见 §13.5", "异常场景处理见 §12.9"),
        ("退款政策另见 §13.5", "退款政策另见 §12.9"),
        ("AS-21 / §13.5 / FR-J4", "AS-21 / §12.9 / FR-J4"),
        ("§13.5 会员与退款边界", "§12.9 会员与退款边界"),
    ],
    "add-api.md": [("§13.5.3", "§12.9.3"), ("§13.5", "§12.9")],
    "prd-1.md": [("附录 C 中 G1/G2 项", "附录 C.1 阻塞项摘要")],
    "prd-3.md": [
        ("风险预警 Agent", "风险控制服务"),
        ("5 个 Agent 全部可调用", "3 个领域 Agent 全部可调用"),
    ],
    "prd-2.md": [
        ("模块 L：风险预警（最高优先级，独立运行）", "模块 L：风险控制与预警（最高优先级，独立运行）"),
    ],
}

for name, pairs in FIX.items():
    p = os.path.join(B, name)
    if not os.path.exists(p):
        print("skip(missing)", name)
        continue
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("fixed", name)

# 2) 术语残留扫描（只看 PRD 源文件，不看历史文档）
print("\n-- 术语残留 --")
for f in sorted(glob.glob(os.path.join(B, "prd-*.md")) + glob.glob(os.path.join(B, "add-*.md"))):
    s = io.open(f, encoding="utf-8").read()
    hits = []
    for t in ("5 个 Agent", "风险预警 Agent", "§13.5", "G1/G2 项"):
        n = s.count(t)
        if n:
            hits.append("%s×%d" % (t, n))
    if hits:
        print("  %-20s %s" % (os.path.basename(f), ", ".join(hits)))