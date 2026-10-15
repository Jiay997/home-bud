# -*- coding: utf-8 -*-
"""V1.2 一致性自检：编号闭合、交叉引用、术语、三态词汇、机器生成区块校验。"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)
PRD = os.path.join(ROOT, "docs", "02-基线", "家伴-PRD_V1.2.md")

s = io.open(PRD, encoding="utf-8").read()
lines = s.split("\n")

print("== 1. 规模 ==")
print("   lines=%d  chars=%d" % (len(lines), len(s)))

print("\n== 2. 章节完整性 ==")
chaps = re.findall(r"^## (\d+)\. (.+)$", s, re.M)
nums = [int(c[0]) for c in chaps]
print("   章数=%d  编号序列连续=%s" % (len(chaps), nums == list(range(0, max(nums) + 1))))
missing = [n for n in range(0, max(nums) + 1) if n not in nums]
print("   缺章:", missing or "无")

print("\n== 3. FR / NFR 编号闭合 ==")
fr_def = set(re.findall(r"^\| (FR-[A-Z]\d+) \|", s, re.M))
fr_used = set(re.findall(r"FR-[A-Z]\d+", s))
print("   FR 定义（§6.16 台账）=%d  全文出现=%d  未定义引用=%s"
      % (len(fr_def), len(fr_used), sorted(fr_used - fr_def) or "无"))
nfr_def = set(re.findall(r"^\| \**?(NFR-\d+\.\d+)\**? \|", s, re.M))
nfr_used = set(re.findall(r"NFR-\d+\.\d+", s))
print("   NFR 定义=%d  未定义引用=%s" % (len(nfr_def), sorted(nfr_used - nfr_def) or "无"))

print("\n== 4. AS / D / Q 编号闭合 ==")
for pre, label in (("AS", "AS"), ("D", "D"), ("Q", "Q")):
    d = set(re.findall(r"^\| (" + pre + r"-\d+) \|", s, re.M))
    u = set(re.findall(pre + r"-\d+", s))
    print("   %-3s 定义=%3d  未定义引用=%s" % (label, len(d), sorted(u - d) or "无"))

print("\n== 5. CG 编号闭合 ==")
cg_def = set(re.findall(r"^\| (CG\d+) \|", s, re.M))
cg_used = set(re.findall(r"CG\d+", s))
print("   CG 定义=%d  未定义引用=%s" % (len(cg_def), sorted(cg_used - cg_def) or "无"))

print("\n== 6. 章节交叉引用有效性 ==")
refs = set(re.findall(r"§(\d+(?:\.\d+)?)", s))
bad = []
EXTERNAL = {"2.29", "3.5", "3.7", "3.10", "3.11", "3.12", "3.13", "2.7"}
for r in sorted(refs):
    pat = re.compile(r"^#{2,4}\s+" + re.escape(r) + r"(?!\.\d)(?:\.|\s)", re.M)
    if not pat.search(s) and r not in EXTERNAL:
        bad.append(r)
print("   引用总数=%d  本文档悬空=%s" % (len(refs), bad or "无"))
print("   （排除项：V1.0 章节号 / UI 文档 §2.7 / 审核意见条号，属外部引用）")

print("\n== 7. 三态词汇与禁用措辞 ==")
for t in ("已决策，可开发", "有默认方案，可开发但需记录风险", "未决策，不得开发"):
    print("   %-22s %d" % (t, s.count(t)))
body = "\n".join(lines[:3700])   # 正文（不含附录/闭环表/阻塞摘要）
print("   正文中『待确认』=%d（仅允许出现在编号约定/变更映射/闭环对照处）" % body.count("待确认"))
print("   正文中『待拍板』=%d" % body.count("待拍板"))
print("   ⚠️ 出现=%d（§0.3 要求正文 0）" % body.count("⚠️"))

print("\n== 8. 术语一致性 ==")
for t, expect in (("风险预警 Agent", "仅允许出现在术语替换表/变更映射/闭环对照"),
                  ("5 个 Agent", "仅允许出现在术语替换表/变更映射/闭环对照")):
    hits = [i + 1 for i, l in enumerate(lines) if t in l]
    print("   %-16s %d 处 行号=%s" % (t, len(hits), hits[:8]))

print("\n== 9. 机器生成区块 ==")
for marker in ("§6.16", "附录 C.1", "## 22. 当前阻塞项摘要"):
    print("   %-24s 存在=%s" % (marker, marker.lstrip("§") in s or marker in s))
blk = re.search(r"B1 开工阻塞.*?\*\*(\d+)\*\*", s)
print("   B1 数量（摘要）=%s" % (blk.group(1) if blk else "?"))

print("\n== 10. 需求变更映射完整性 ==")
tot = 0
for g in ("继承", "修改", "删除", "新增", "废弃"):
    m = re.search(r"^#### " + g + r"（(\d+) 项）", s, re.M)
    n = int(m.group(1)) if m else 0
    tot += n
    print("   %-4s %d 条" % (g, n))
print("   合计 %d 条" % tot)

print("\n== 11. 接口与埋点规模 ==")
print("   API 条数=%d（C=%d, A=%d）" % (
    len(re.findall(r"^\| API-[CA]-\d+", s, re.M)),
    len(re.findall(r"^\| API-C-\d+", s, re.M)),
    len(re.findall(r"^\| API-A-\d+", s, re.M))))
print("   埋点事件行数=%d" % len(re.findall(r"^\| `[a-z_]+` \|", s, re.M)))

print("\n== 12. 禁用词（用词规范示例，需人工确认） ==")
for w in ("心理诊断", "包提分", "算命", "天生注定", "代做作业", "性格永久判定", "信效度"):
    n = s.count(w)
    if n:
        print("   %-8s %d" % (w, n))