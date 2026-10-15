# -*- coding: utf-8 -*-
"""V1.4 收尾：改名、引用同步、归档 V1.3。"""
import io, os, glob

ROOT = r"D:\HomeBud"
D = os.path.join(ROOT, "docs")
log = []

# ---- 1. 改名（内容已是新版本号）----
ren = [
    (os.path.join(D, "02-基线", "家伴-UI原型描述_V1.2.md"), os.path.join(D, "02-基线", "家伴-UI原型描述_V1.3.md")),
    (os.path.join(D, "04-工程", "家伴-架构设计文档_V1.0.md"), os.path.join(D, "04-工程", "家伴-架构设计文档_V1.1.md")),
    (os.path.join(D, "04-工程", "家伴-数据模型文档_V1.0.md"), os.path.join(D, "04-工程", "家伴-数据模型文档_V1.1.md")),
]
for a, b in ren:
    if os.path.exists(a) and not os.path.exists(b):
        os.rename(a, b)
        log.append("RENAME %s -> %s" % (os.path.basename(a), os.path.basename(b)))
    else:
        log.append("SKIP   rename %s (存在=%s)" % (os.path.basename(a), os.path.exists(a)))

# ---- 2. 归档 PRD V1.3 ----
src = os.path.join(D, "02-基线", "家伴-PRD_V1.3.md")
dst = os.path.join(D, "99-归档", "家伴-PRD_V1.3.md")
if os.path.exists(src) and not os.path.exists(dst):
    os.rename(src, dst)
    log.append("ARCHIVE 家伴-PRD_V1.3.md -> docs/99-归档/")
else:
    log.append("SKIP   archive V1.3 (存在=%s)" % os.path.exists(src))

# ---- 3. 引用同步（不动 99-归档 与 05-审核）----
pairs = [
    ("家伴-UI原型描述_V1.2.md", "家伴-UI原型描述_V1.3.md"),
    ("家伴-架构设计文档_V1.0.md", "家伴-架构设计文档_V1.1.md"),
    ("家伴-数据模型文档_V1.0.md", "家伴-数据模型文档_V1.1.md"),
]
targets = []
for pat in ["02-基线/*.md", "03-设计/*.md", "04-工程/*.md", "06-机构方向/*.md", "07-竞品调研/*.md"]:
    targets += glob.glob(os.path.join(D, pat))
targets.append(os.path.join(ROOT, "README.md"))
tot = 0
for p in targets:
    t = io.open(p, encoding="utf-8").read()
    orig = t
    for a, b in pairs:
        t = t.replace(a, b)
    if t != orig:
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        tot += 1
        log.append("REFS   %s" % os.path.relpath(p, ROOT))
log.append("引用已更新的文件数：%d" % tot)

print("\n".join(log))
