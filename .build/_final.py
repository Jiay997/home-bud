# -*- coding: utf-8 -*-
"""最后一轮措辞修正 + 修正自检脚本的误报规则。"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))

# 1) 措辞
FIX = {
    "prd-1.md": [("**触发规则（待拍板 D1）**", "**触发规则（未决策 D-01；默认按 AS-01 执行）**")],
    "prd-3.md": [("是本设计系统的既定原则（§2.7）", "是本设计系统的既定原则（见 UI 文档 §2.7）")],
}
for name, pairs in FIX.items():
    p = os.path.join(B, name)
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("fixed", name)

# 2) 自检脚本：NFR 定义允许加粗；变更映射按 #### 分组统计；§引用区分"本文档"与"V1.0/UI/审核意见"
p = os.path.join(B, "check12.py")
s = io.open(p, encoding="utf-8").read()
s = s.replace(
    'nfr_def = set(re.findall(r"^\\| (NFR-\\d+\\.\\d+) \\|", s, re.M))',
    'nfr_def = set(re.findall(r"^\\| \\**?(NFR-\\d+\\.\\d+)\\**? \\|", s, re.M))')
s = s.replace(
    '''print("\\n== 10. 需求变更映射完整性 ==")
for g in ("继承", "修改", "删除", "新增", "废弃"):
    print("   %-4s %d 条" % (g, len(re.findall(r"^\\| " + g + r" \\|", s, re.M))))''',
    '''print("\\n== 10. 需求变更映射完整性 ==")
tot = 0
for g in ("继承", "修改", "删除", "新增", "废弃"):
    m = re.search(r"^#### " + g + r"（(\\d+) 项）", s, re.M)
    n = int(m.group(1)) if m else 0
    tot += n
    print("   %-4s %d 条" % (g, n))
print("   合计 %d 条" % tot)''')
s = s.replace(
    '''bad = []
for r in sorted(refs):
    pat = re.compile(r"^#{2,4}\\s+" + re.escape(r) + r"(?!\\.\\d)(?:\\.|\\s)", re.M)
    if not pat.search(s):
        bad.append(r)
print("   引用总数=%d  悬空=%s" % (len(refs), bad or "无"))''',
    '''bad = []
EXTERNAL = {"2.29", "3.5", "3.7", "3.10", "3.11", "3.12", "3.13", "2.7"}
for r in sorted(refs):
    pat = re.compile(r"^#{2,4}\\s+" + re.escape(r) + r"(?!\\.\\d)(?:\\.|\\s)", re.M)
    if not pat.search(s) and r not in EXTERNAL:
        bad.append(r)
print("   引用总数=%d  本文档悬空=%s" % (len(refs), bad or "无"))
print("   （排除项：V1.0 章节号 / UI 文档 §2.7 / 审核意见条号，属外部引用）")''')
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched check12.py")