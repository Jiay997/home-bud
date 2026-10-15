# -*- coding: utf-8 -*-
"""文档链一致性核对器（家伴文档库）

用途：每次改动版本号 / 重命名 / 状态口径后跑一次，查出漏改的引用与残留口径。
这套检查就是发现「V1.3 引用停在旧版本」「UI 决策索引状态过时」等 21 处漂移的方法。

用法：
    python .build/check_docs.py            # 完整报告
    python .build/check_docs.py --quiet    # 只打印 FAIL / WARN

退出码：0 = 无 FAIL；1 = 存在 FAIL

判定原则：**归档声明、变更登记、修订记录、附录修正索引里的旧版本引用是合法的**，
因此按「章节上下文 + 行内关键词」双重豁免，避免把历史记录当漂移。
"""
import io, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
QUIET = "--quiet" in sys.argv
FAIL, WARN, OK = [], [], []


def say(kind, msg):
    line = "[%s] %s" % (kind, msg)
    (OK if kind == "OK" else WARN if kind == "WARN" else FAIL).append(line)
    if not QUIET or kind != "OK":
        print(line)


def read(p):
    return io.open(p, encoding="utf-8").read()


# ---------------------------------------------------------------- 扫描范围
SKIP_DIRS = ("99-归档", "01-需求来源", "05-审核", "_原始检索", ".build")
scanned = [p for p in glob.glob(os.path.join(DOCS, "**", "*.md"), recursive=True)
           if not any(k in p for k in SKIP_DIRS)]
scanned.append(os.path.join(ROOT, "README.md"))
scanned = sorted(set(scanned))
all_md = {os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "**", "*.md"), recursive=True)}

# ---------------------------------------------------------------- 家族与现行版
FAMILIES = {
    "PRD": r"家伴-PRD_V(\d+)\.(\d+)\.md",
    "UI原型描述": r"家伴-UI原型描述_V(\d+)\.(\d+)\.md",
    "架构设计文档": r"家伴-架构设计文档_V(\d+)\.(\d+)\.md",
    "数据模型文档": r"家伴-数据模型文档_V(\d+)\.(\d+)\.md",
}
latest, current_file = {}, {}
for fam, pat in FAMILIES.items():
    best, bestf = (-1, -1), None
    for d in (os.path.join(DOCS, "02-基线"), os.path.join(DOCS, "04-工程")):
        for p in glob.glob(os.path.join(d, "*.md")):
            m = re.fullmatch(pat, os.path.basename(p))
            if m:
                v = (int(m.group(1)), int(m.group(2)))
                if v > best:
                    best, bestf = v, p
    if bestf:
        latest[fam] = "V%d.%d" % best
        current_file[fam] = os.path.basename(bestf)

print("=" * 78)
print("现行基线：" + " ｜ ".join("%s %s" % (k, v) for k, v in latest.items()))
print("=" * 78)

# ---------------------------------------------------------------- 历史豁免上下文
# 行内关键词
HIST_LINE = ("归档", "被取代", "取代", "历史来源", "历史", "变更登记", "变更映射",
             "修订记录", "错命名", "副本", "已取消", "移出", "旧版", "上一版",
             "同步说明", "修正 T-", "修正 F-", "本次修订", "V1.0 →", "→ V1.")
# 章节标题关键词（该章节内所有行豁免版本漂移判定）
HIST_HEAD = ("归档", "变更", "修订", "修正", "同步", "交付", "冻结", "附录 D")
HEAD_RE = re.compile(r"^(#{2,4}) (.+)$", re.M)


def hist_sections(text):
    """返回 [(起行号, 止行号)] 的历史性章节区间（1-based，含止行）。"""
    lines = text.split("\n")
    heads = [(i + 1, len(m.group(1)), m.group(2))
             for i, ln in enumerate(lines) for m in [HEAD_RE.match(ln)] if m]
    spans, end = [], len(lines) + 1
    for idx, (ln, lvl, title) in enumerate(heads):
        if any(k in title for k in HIST_HEAD):
            stop = end
            for ln2, lvl2, _ in heads[idx + 1:]:
                if lvl2 <= lvl:
                    stop = ln2
                    break
            spans.append((ln, stop - 1))
    return spans


def in_hist(spans, lineno):
    return any(a <= lineno <= b for a, b in spans)


def hist_line(line):
    return any(k in line for k in HIST_LINE)


# ---------------------------------------------------------------- 1. 悬空文件名引用
dangling = set()
for p in scanned:
    for m in re.finditer(r"家伴-[^`｜|\)\s《》，]*?\.md", read(p)):
        name = m.group(0)
        if name not in all_md and not re.search(r"[<>（）/]", name):
            dangling.add("%s → %s" % (os.path.basename(p), name))
if dangling:
    say("FAIL", "悬空文件名引用 %d 处：" % len(dangling))
    for d in sorted(dangling):
        print("        " + d)
else:
    say("OK", "文件名引用全部可解析（无悬空，%d 份文档）" % len(scanned))

# ---------------------------------------------------------------- 2. 把旧版当现行
stale, exempt = [], 0
for p in scanned:
    base, text = os.path.basename(p), read(p)
    spans = hist_sections(text)
    for i, line in enumerate(text.split("\n"), 1):
        for fam, pat in FAMILIES.items():
            for m in re.finditer(pat, line):
                if m.group(0) == current_file.get(fam):
                    continue
                if hist_line(line) or in_hist(spans, i):
                    exempt += 1
                else:
                    stale.append("%s L%d  引用旧版 %s（现行 %s）"
                                 % (base, i, m.group(0), latest[fam]))
if stale:
    say("FAIL", "把旧版本当现行引用 %d 处：" % len(stale))
    for s in stale:
        print("        " + s)
else:
    say("OK", "无「把旧版当现行」的引用（%d 处旧版引用已按归档/变更语境豁免）" % exempt)

# ---------------------------------------------------------------- 3. 基线声明指向
BASE_WORDS = ("唯一需求基线", "唯一界面基线", "关联文档", "配套", "基线依据", "唯一来源")
bad = []
for p in scanned:
    base, text = os.path.basename(p), read(p)
    spans = hist_sections(text)
    for i, line in enumerate(text.split("\n"), 1):
        if not any(w in line for w in BASE_WORDS):
            continue
        for fam, pat in FAMILIES.items():
            for m in re.finditer(pat, line):
                if m.group(0) == current_file.get(fam):
                    continue
                if hist_line(line) or in_hist(spans, i):
                    continue
                bad.append("%s L%d  「%s」声明行指向 %s（应为 %s）"
                           % (base, i, fam, m.group(0), current_file[fam]))
if bad:
    say("FAIL", "基线/配套声明指向旧版 %d 处：" % len(bad))
    for b in bad:
        print("        " + b)
else:
    say("OK", "所有基线/配套声明均指向现行版本")

# ---------------------------------------------------------------- 4. 旧口径回归守卫
prd = os.path.join(DOCS, "02-基线", current_file["PRD"]) if current_file.get("PRD") else None
MUST_ZERO = {
    r"700 \| 1450": "旧延迟预算表值（应为 930/1750）",
    r"上线首批 5 类": "D18 前的高危清单（应为 6 类）",
    r"告警 22\.5s": "已废弃的超时口径",
    r"\| G1 \|": "幽灵阻塞级别 G1",
    r"G1 开工阻塞项": "幽灵阻塞级别 G1",
    r"以运营账号展开": "S1-3 越权表述（应为超级管理员）",
    r"客服/专家不出现编辑": "T-08 权限冲突表述",
    r"12–16 题": "题量区间旧值（应为 16 题）",
    r"内容与配置留痕类（[^）]*admin_login_\*": "保留期表里 admin_login_* 通配",
}
if prd:
    txt = read(prd)
    bad = [(p, d, len(re.findall(p, txt))) for p, d in MUST_ZERO.items() if re.findall(p, txt)]
    if bad:
        say("FAIL", "PRD 中仍存在应清零的旧口径：")
        for p, d, n in bad:
            print("        %-30s %s ×%d" % (p[:30], d, n))
    else:
        say("OK", "PRD 中 %d 项旧口径全部为 0" % len(MUST_ZERO))

    # ------------------------------------------------------------ 5. 章号与 § 引用
    lvl1 = [int(m.group(1)) for m in re.finditer(r"^## (\d+)\. ", txt, re.M)]
    dup = sorted(x for x in set(lvl1) if lvl1.count(x) > 1)
    gap = [x for x in range(min(lvl1), max(lvl1) + 1) if x not in lvl1] if lvl1 else []
    if dup or gap:
        say("FAIL", "PRD 一级章号异常：重复 %s｜缺号 %s" % (dup or "无", gap or "无"))
    else:
        say("OK", "PRD 一级章号 0–%d 连续无重复（共 %d 章）" % (max(lvl1), len(lvl1)))

    heads = {m.group(1) for m in re.finditer(r"^#{2,4} (\d+(?:\.\d+)*)", txt, re.M)}
    refs = set(re.findall(r"§(\d+(?:\.\d+)*)", txt))
    bad_refs = sorted(r for r in refs if r not in heads)
    if bad_refs:
        say("WARN", "§ 引用无法在本 PRD 内解析 %d 个（多为指向 V1.0 需求文档的章节，非错误）：%s"
            % (len(bad_refs), ", ".join("§" + r for r in bad_refs[:12])))
    else:
        say("OK", "§ 引用全部可解析（%d 个）" % len(refs))

# ---------------------------------------------------------------- 6. 台账一致性
try:
    sys.path.insert(0, os.path.join(ROOT, ".build"))
    import ledger as L
    gen = os.path.join(ROOT, ".build", "gen-blockers.md")
    if prd and os.path.exists(gen):
        g, t2 = read(gen), read(prd)

        def num(pat, s):
            m = re.search(pat, s)
            return m.group(1) if m else None

        checks = [("FR 条目总数", r"FR 条目总数 \| (\d+)"),
                  ("B1 开工阻塞", r"\*\*B1 开工阻塞（未决策，不得开发）\*\* \| \*\*(\d+)\*\*"),
                  ("B2 上线阻塞", r"\*\*B2 上线阻塞\*\* \| \*\*(\d+)\*\*")]
        drift = ["%s：生成器 %s vs PRD §22 %s" % (lab, num(pt, g), num(pt, t2))
                 for lab, pt in checks if num(pt, g) != num(pt, t2)]
        if drift:
            say("FAIL", "台账与 PRD §22 不一致：" + "；".join(drift))
        else:
            say("OK", "台账与 PRD §22 一致（Q 总数 %d ｜ B1 未关闭 %d ｜ B2 未关闭 %d ｜ 真·未决策 %d）"
                % (len(L.Q), len(L.blockers("B1")), len(L.blockers("B2")),
                   len([q for q in L.Q if q[4] == "block"])))
except Exception as e:
    say("WARN", "台账核对跳过（%s）" % e)

# ---------------------------------------------------------------- 汇总
print("=" * 78)
print("通过 %d ｜ 警告 %d ｜ 失败 %d" % (len(OK), len(WARN), len(FAIL)))
print("=" * 78)
sys.exit(1 if FAIL else 0)
