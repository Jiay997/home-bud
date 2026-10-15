# -*- coding: utf-8 -*-
"""第二轮交叉引用修正（一次性）。"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))

# 各文件中仍然指向「旧编号」的引用 → 新编号
# 新编号真值：7.1 架构 / 7.2 Agent 清单 / 7.3 输出契约 / 7.4 中枢→前端 /
#            7.5 响应协议 / 7.6 调度 / 7.7 延迟 / 7.8 降级 / 7.9 申诉 /
#            7.10 汇总 / 7.11 冲突 / 7.12 检索 / 7.13 成本
RULES = {
    "add-protocol.md": [("（§7.9）", "（§7.8）")],
    "add-events.md": [("§7.10", "§7.13"), ("§7.6", "§7.7")],
    "add-kb.md": [("§7.8", "§7.11")],
}


def main():
    for name, pairs in RULES.items():
        p = os.path.join(B, name)
        s = io.open(p, encoding="utf-8").read()
        before = s
        for a, b in pairs:
            s = s.replace(a, b)
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        print("%-20s changed=%s" % (name, s != before))

    # 汇总校验：输出所有 add-* 中的 §7.x 引用
    import glob
    for p in sorted(glob.glob(os.path.join(B, "add-*.md"))):
        s = io.open(p, encoding="utf-8").read()
        refs = sorted(set(re.findall(r"§7\.\d+(?:\.\d+)?", s)))
        print("  %-20s %s" % (os.path.basename(p), refs))


if __name__ == "__main__":
    main()