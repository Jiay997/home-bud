# -*- coding: utf-8 -*-
"""V1.2 自检修正：悬空引用、术语、措辞。"""
import glob
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))

FIX = {
    "prd-2.md": [("Q-39（D-17）", "Q-39")],
    "prd-3.md": [
        ("（§3.13 US-M1 验收 4 保留）", "（FR-M1：用户显式选择入口时以用户选择为准）"),
        ("（§3.12 US-L1 验收 1）", "（FR-L2）"),
    ],
    "add-api.md": [("§13.5", "§12.9")],
    "add-events.md": [("审核意见 §2.29", "审核意见 2.29 条")],
    "add-protocol.md": [("| ⚠️ 备选 |", "| 备选（非主选） |"),
                        ("| ⚠️ **降级兜底** |", "| **降级兜底（辅路）** |")],
    "add-assess.md": [("（§12.1「单次简易测评」", "（§12.3「单次简易测评」")],
}

for name, pairs in FIX.items():
    p = os.path.join(B, name)
    if not os.path.exists(p):
        print("skip(missing)", name)
        continue
    s = io.open(p, encoding="utf-8").read()
    n = 0
    for a, b in pairs:
        c = s.count(a)
        n += c
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("fixed %-18s replacements=%d" % (name, n))

# 正文「待确认 / 待拍板」措辞：仅保留在明确的"历史说明/编号约定/闭环对照"语境中
s = io.open(os.path.join(B, "prd-1.md"), encoding="utf-8").read()
s = s.replace("所有待拍板项集中在附录 B（决策登记册）与附录 C（待确认清单），一张表可改",
              "所有未决策项集中在附录 B（决策登记册）与附录 C（待确认问题登记册），一张表可改")
s = s.replace("| `Q-xx` | V1.0 原有待确认问题（Q-01~Q-39），本文档新增续编 Q-40+ | 附录 C |",
              "| `Q-xx` | V1.0 遗留问题清单（Q-01~Q-39，编号保留；状态见附录 C），本文档新增续编 Q-40 ~ Q-45 | 附录 C |")
s = s.replace("**验收标准中不得出现 `⚠️`、`Q-xx`、`AS-xx` 标注。** 待确认项必须与验收标准分离（V1.0 有 33 处违反，见 C1）。",
              "**验收标准中不得出现 `Q-xx`、`AS-xx`、状态标记。** 未决策项必须与验收标准分离（V1.0 有 33 处违反，见附录 D 的 C1）。")
s = s.replace("§2 目标与指标 → §4 范围基线 → 附录 B 决策登记册 → 附录 C 待确认清单",
              "§2 目标与指标 → §4 范围基线 → §0.7 唯一基线声明 → 附录 B 决策登记册 → 附录 C.1 阻塞项摘要")
io.open(os.path.join(B, "prd-1.md"), "w", encoding="utf-8", newline="\n").write(s)
print("fixed prd-1.md wording")

# 清理非必要"待确认"（正文状态描述）
for name in ("prd-2.md", "prd-3.md", "prd-4.md", "prd-5.md", "prd-1.md"):
    p = os.path.join(B, name)
    s = io.open(p, encoding="utf-8").read()
    o = s
    s = s.replace("**不得引用待确认项**", "**不得引用未决策项**")
    s = s.replace("避免影响用户频次", "避免影响用户频次")
    s = s.replace("待确认项", "未决策项")
    if s != o:
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        print("reworded", name)