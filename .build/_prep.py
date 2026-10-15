# -*- coding: utf-8 -*-
"""V1.2 组装前处理：① 第 12 章编号迁移；② 拆分 add-arch-block.md；③ 校验。"""
import glob
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# ---------- ① 第 12 章迁移：新 12.1/12.2 让位，旧 12.1~12.6 → 12.3~12.8
SEC = [("### 12.6 ", "### 12.@8 "), ("### 12.5 ", "### 12.@7 "), ("### 12.4 ", "### 12.@6 "),
       ("### 12.3 ", "### 12.@5 "), ("### 12.2 ", "### 12.@4 "), ("### 12.1 ", "### 12.@3 ")]
REF = [("§12.6", "§12.@8"), ("§12.5", "§12.@7"), ("§12.4", "§12.@6"),
       ("§12.3", "§12.@5"), ("§12.2", "§12.@4"), ("§12.1", "§12.@3")]

# 需要参与迁移的文件（不含 add-kb / add-assess，它们的 12.1/12.2 是新的）
TARGETS = [os.path.join(B, f) for f in
           ("prd-1.md", "prd-2.md", "prd-3.md", "prd-4.md", "prd-5.md",
            "add-protocol.md", "add-compliance.md", "add-events.md", "add-loop.md", "add-refund.md")]

for p in TARGETS:
    if not os.path.exists(p):
        continue
    s = read(p)
    o = s
    for a, b in SEC + REF:
        s = s.replace(a, b)
    s = s.replace("@", "")
    if s != o:
        write(p, s)
        print("ch12 migrated:", os.path.basename(p))

# add-refund 改挂到 12.9（与商业化同章）
p = os.path.join(B, "add-refund.md")
s = read(p)
s = s.replace("## 13.5 会员与退款边界", "### 12.9 会员与退款边界")
write(p, s)
print("add-refund.md -> 12.9")

# ---------- ② 拆分 add-arch-block.md（含 7.1 / 7.9 / 6.17 三节）
p = os.path.join(B, "add-arch-block.md")
s = read(p)
i1 = s.index("## 7.1 架构分层与命名")
i9 = s.index("## 7.9 风险拦截与申诉状态机")
i6 = s.index("## 6.17 超范围拒答口径")
write(os.path.join(B, "sec-71.md"), s[i1:i9])
write(os.path.join(B, "sec-79.md"), s[i9:i6])
write(os.path.join(B, "sec-617.md"), s[i6:])
print("split add-arch-block.md -> sec-71 / sec-79 / sec-617")

# ---------- ③ 校验第 12 章标题
print("\n-- ch12 headings --")
for f in sorted(glob.glob(os.path.join(B, "*.md"))):
    for m in re.finditer(r"^### 12\.\d+ .*$", read(f), re.M):
        print("  %-20s %s" % (os.path.basename(f), m.group(0)[:70]))