# -*- coding: utf-8 -*-
"""V1.2 收尾修正（一次性）：删除被替换的旧章节 + 修正重编号后的交叉引用 + 补头部基线声明。"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# 1) 删除 prd-3.md 中被 add-protocol.md 替换的旧 §7.7 / §7.8
p3 = os.path.join(B, "prd-3.md")
s = read(p3)
start = s.index("### 7.7 端到端延迟预算表")
end = s.index("### 7.10 汇总实现规格")
removed = s[start:end]
s = s[:start] + s[end:]
write(p3, s)
print("removed %d chars (old 7.7/7.8) from prd-3.md" % len(removed))

# 2) 修正交叉引用
FIX = {
    "add-events.md": [
        ("性能口径唯一权威＝§7.5", "性能口径唯一权威＝§7.7"),
        ("＋§7.10 |", "＋§7.13 |"),
        ("超时率 >5% 告警）＋§7.6", "超时率 >5% 告警）＋§7.7"),
        ("§7.5 阶段 8", "§7.7 阶段 8"),
    ],
    "add-kb.md": [
        ("§7.9", "§7.12"),
        ("§7.8 / AS-18", "§7.11 / AS-18"),
        ("| §7.8 |", "| §7.11 |"),
    ],
    "add-compliance.md": [("（§7.12）", "（§7.13）")],
    "add-protocol.md": [
        ("见 §7.4.5", "见 §7.5.5"),
        ("§7.7 安全 Agent 失败", "§7.8 安全 Agent 失败"),
    ],
    "add-arch-block.md": [("§7.12 成本测算", "§7.13 成本测算")],
}
for name, pairs in FIX.items():
    p = os.path.join(B, name)
    s = read(p)
    for a, b in pairs:
        if a not in s:
            print("  WARN not found in %s: %s" % (name, a))
        s = s.replace(a, b)
    write(p, s)
    print("fixed", name)

# 3) prd-3.md 章首补一句架构说明（第 7 章已被重构）
p3s = read(p3)
p3s = p3s.replace(
    "## 7. 多智能体能力规格\n",
    "## 7. 多智能体能力规格\n\n"
    "> **本章结构在 V1.2 被重构**：新增 §7.1 架构分层（术语澄清）、§7.5 问答响应协议、"
    "§7.7 延迟预算表、§7.8 降级矩阵、§7.9 风险拦截与申诉状态机；原 §7.1/7.2/7.3 顺延为 "
    "§7.2/7.3/7.4，原 §7.4 顺延为 §7.6。术语替换见 §7.1.3。\n",
    1,
)
write(p3, p3s)
print("annotated prd-3.md")