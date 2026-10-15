# -*- coding: utf-8 -*-
"""从 ledger.py 生成 PRD 的决策类章节，杜绝手工维护导致的数量与状态漂移。

生成物：
  gen-fr-status.md   §6.16 FR 决策状态与可开发边界
  gen-appendix.md    附录 A/B/C（AS 假定基线 / D 决策登记册 / Q 待确认清单 + 阻塞项摘要）
  gen-changes.md     §0.6 需求变更映射表（继承/修改/删除/新增/废弃）
  gen-blockers.md    文末「当前阻塞项摘要」（机器统计，禁止手写）
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as L  # noqa: E402


def w(name, text):
    p = os.path.join(HERE, name)
    io.open(p, "w", encoding="utf-8", newline="\n").write(text.rstrip("\n") + "\n")
    print("wrote %-20s %5d lines" % (name, text.count("\n") + 1))


def tbl(head, rows):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def state_cell(code):
    lab = L.LABEL[code]
    mark = {"dev": "🟢", "risk": "🟡", "block": "🔴", "removed": "⬜", "已关闭": "⬜"}[code]
    return "%s %s" % (mark, lab)


# ---------------------------------------------------------------- §6.16
def fr_status():
    c = L.fr_counts()
    rows = []
    for num, name, st, boundary, dep in L.FR:
        rows.append([num, name, state_cell(st), boundary, dep])
    head = ["编号", "条目", "决策状态", "可开发边界 / 未决部分", "关联编号"]
    text = """### 6.16 FR 决策状态与可开发边界

> **本节由 `ledger.py` 自动生成**（`gen.py`），禁止手工编辑。任何状态变化只能改台账，然后重新生成——这是防止「待确认」一码多义、以及防止阻塞项数量与正文不一致的机制。

**统计（机器计数）**：共 %d 条 FR｜🟢 已决策，可开发 **%d**｜🟡 有默认方案，可开发但需记录风险 **%d**｜🔴 未决策，不得开发 **%d**（部分条目只有局部未决）｜⬜ 已移出 / 已删除 **%d**。

**读法**：🔴 不等于整条不能开工。绝大多数 🔴 条目是「**机制可开发、内容或数值不得定稿**」，其可开发边界写在第四列；只有该列同时写着"未决"的部分才禁止开发。

%s
""" % (len(L.FR), c.get("dev", 0), c.get("risk", 0), c.get("block", 0), c.get("removed", 0), tbl(head, rows))
    w("gen-fr-status.md", text)


# ---------------------------------------------------------------- 附录 A/B/C
def appendix():
    a_rows = [[a[0], a[1], a[2], a[3], state_cell(a[4])] for a in L.AS]
    a_head = ["编号", "假定内容", "来源", "责任方", "决策状态"]

    d_rows = [[d[0], d[1], d[2], d[3], state_cell(d[4])] for d in L.D]
    d_head = ["编号", "议题", "本文档采纳结论", "决策人", "决策状态"]

    q_rows = [[q[0], q[1], q[2], q[3], state_cell(q[4])] for q in L.Q]
    q_head = ["编号", "问题摘要", "阻塞级别", "落点", "决策状态"]

    qc = L.q_counts()
    sc = L.q_status_counts()
    b1 = L.blockers("B1")
    b2 = L.blockers("B2")
    b3 = L.blockers("B3")
    # 语义修正（V1.4）：附录 C 表头统计「全部项」，附录 C.1 统计「未关闭项」。
    # 原实现让两处标签同名却给出 8 与 5 两个数，属生成器自身的语义 bug。
    open_total = len(b1) + len(b2) + len(b3)
    block_total = len([q for q in L.Q if q[4] == "block"])

    def blist(items):
        if not items:
            return "（无）"
        return "、".join("%s（%s）" % (i[0], i[1][:22]) for i in items)

    text = """### 附录 A：假定基线登记册（AS）

> 由台账自动生成。**判定标准**：🟢 可直接按此开发；🟡 按默认值开发但必须把风险写进 §14.1；🔴 该项对应的产品行为不得定稿（若条目本身给出了可开发边界，边界内仍可开发）。

%s

### 附录 B：决策登记册（D）

> 由台账自动生成。本表记录**本文档已采纳的结论**与仍需拍板的项；"决策人"列是该结论的最终责任人。🟢 项如需推翻，须走变更流程并回填 §0.6。

%s

### 附录 C：待确认问题登记册（Q）

**阻塞级别定义（与 §0.3 三态严格对应）**

| 级别 | 含义 | 与三态的关系 | 全部项 | 未关闭 |
| --- | --- | --- | --- | --- |
| **B1 开工阻塞** | 未决策，不得开发 | 对应 🔴 未决策，不得开发 | %d | **%d** |
| **B2 上线阻塞** | 可开发，但不得上线 | 对应 🔴 或 🟡 | %d | **%d** |
| **B3 运营参数待定** | 有默认方案，灰度期可调 | 对应 🟡 或 🟢 | %d | **%d** |
| 已关闭 | 已给结论，编号保留 | 对应 🟢 或 ⬜ | %d | — |

> **读法（V1.4 修正）**：「全部项」包含已有默认结论的 🟡/🟢 条目；「**未关闭**」才是仍压着开工/上线的条目。原实现两列同名却给出不同数（B3 一处 8、一处 5），属生成器语义 bug，现已拆列。

**状态分布（机器计数）**：🟢 %d｜🟡 %d｜🔴 %d｜⬜ %d。

%s

#### 附录 C.1 当前阻塞项摘要（**机器生成，禁止手写**）

> 本节取代 V1.1 正文中的人工表述（原文写"仍有 4 项阻塞"与附录实际条目数不符）。以下数字由 `ledger.py` 统计，正文任何位置引用阻塞项数量时必须引用本节。

| 类别 | 未关闭数量 | 清单 |
| --- | --- | --- |
| **B1 开工阻塞** | **%d** | %s |
| **B2 上线阻塞** | **%d** | %s |
| **B3 运营参数** | %d | %s |

> 上表只列**未关闭**项。其中状态为 🔴「未决策，不得开发」的共 **%d 项**，其余为 🟡「有默认方案，可开发但需记录风险」——**🟡 不阻塞编码起步**，只要求在 §14.1 登记风险。

**开工判据（V1.4 修订：外部依赖与开发解耦）**

1. **全部 B1 项已有明确结论或已写明"可开发边界"**：🟢/🟡 项可直接开工；剩余 🔴 项须满足"可开发边界已写明且不阻塞编码起步"（当前仅剩 3 项，均为外部事实确认，见 §23.3）。
2. §0.5 基线声明已由业务方签字（**签字前可开发，但不得对外发布**）。
3. §12.1 知识库"来源与版权"结论未出前：**代码可开发，内容不得上架**。
4. §11.11 模型供应商清单未定前：**按 §23.2 抽象层起步**（`Provider` 接口 + 配置白名单 + 未登记拒绝启动）。

> **V1.4 的政策变化**：原判据要求"全部 B1 项关闭"，把**外部事实确认**与**编码起步**绑死，导致项目在等法务/等签约期间完全停摆。V1.4 改为**外部依赖与开发并行**——外部结论到达后只改配置（模型白名单、渠道清单、专家签字状态、知识库上架许可），不改架构。

**上线判据**：全部 **B1 + B2** 项关闭，且 §11.8 上线前置合规检查表全绿。

#### 附录 C.2 已关闭编号（保留编号，不再计入阻塞）

%s
""" % (
        tbl(a_head, a_rows),
        tbl(d_head, d_rows),
        qc.get("B1", 0), len(b1), qc.get("B2", 0), len(b2), qc.get("B3", 0), len(b3), qc.get("已关闭", 0),
        sc.get("dev", 0), sc.get("risk", 0), sc.get("block", 0), sc.get("removed", 0),
        tbl(q_head, q_rows),
        len(b1), blist(b1),
        len(b2), blist(b2),
        len(b3), blist(b3),
        block_total,
        "、".join("%s" % q[0] for q in L.Q if q[2] == "已关闭") or "（无）",
    )
    w("gen-appendix.md", text)


# ---------------------------------------------------------------- §0.6 变更映射
def changes():
    groups = ["继承", "修改", "删除", "新增", "废弃"]
    parts = []
    for g in groups:
        rows = [[c[1], c[2], c[3], c[4]] for c in L.CHANGES if c[0] == g]
        if not rows:
            continue
        parts.append("#### %s（%d 项）\n\n%s" % (
            g, len(rows), tbl(["对象 / 编号", "V1.0 / V1.1 原状", "V1.2 现状", "依据"], rows)))
    text = """### 0.6 需求变更映射（相对 V1.0 与 V1.1）

> 由台账自动生成。**这张表是判断"某个老编号还算不算数"的唯一依据**：凡出现在「废弃」与「删除」两组的编号，任何文档、代码注释、测试用例都不得再引用。

""" + "\n\n".join(parts) + "\n"
    w("gen-changes.md", text)


# ---------------------------------------------------------------- 文末摘要
def blockers():
    qc = L.q_counts()
    b1, b2 = L.blockers("B1"), L.blockers("B2")
    b3 = L.blockers("B3")
    fc = L.fr_counts()
    text = """> **本节由 `ledger.py` 机器生成，禁止手写。** 任何位置引用阻塞项数量时必须以本节为准；正文其余各处只允许写"见文末阻塞项摘要"。

| 维度 | 数量 |
| --- | --- |
| FR 条目总数 | %d |
| 🟢 已决策，可开发 | %d |
| 🟡 有默认方案，可开发但需记录风险 | %d |
| 🔴 未决策，不得开发 | %d |
| ⬜ 已移出 / 已删除 | %d |
| **B1 开工阻塞（未决策，不得开发）** | **%d** |
| **B2 上线阻塞** | **%d** |
| B3 运营参数（全部 / 未关闭） | %d / **%d** |
| 已关闭编号 | %d |

**B1 开工阻塞清单（%d 项）**：%s

**B2 上线阻塞清单（%d 项）**：%s

**结论**：当前**不具备正式开工条件**，也不具备上线条件。可立即开工的范围是全部 🟢 条目 + 🟡 条目的默认值路径 + 🔴 条目中已在 §6.16 注明"可开发"的机制部分（例如风险流水线、工单状态机、配置化阈值——均不含最终数值与内容）。
""" % (
        len(L.FR), fc.get("dev", 0), fc.get("risk", 0), fc.get("block", 0), fc.get("removed", 0),
        len(b1), len(b2), qc.get("B3", 0), len(b3), qc.get("已关闭", 0),
        len(b1), "、".join(q[0] for q in b1),
        len(b2), "、".join(q[0] for q in b2),
    )
    w("gen-blockers.md", text)


if __name__ == "__main__":
    fr_status()
    appendix()
    changes()
    blockers()