# -*- coding: utf-8 -*-
"""UI V1.2 最后两处措辞与流程图修正。"""
import io
import os

B = os.path.dirname(os.path.abspath(__file__))


def fix(name, pairs):
    p = os.path.join(B, name)
    s = io.open(p, encoding="utf-8").read()
    n = 0
    for a, b in pairs:
        c = s.count(a)
        n += c
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("%-12s replacements=%d" % (name, n))


# §0.3 读法：⚠️ 段落改为"决策依赖"
fix("ui-1.md", [
    ("6. `> ⚠️` 段落为**待确认事项**，必须在开发前由对应责任人拍板（编号指向 PRD 附录 B/C）。",
     "6. `<20>` 段落为**决策依赖**：只说明该页依赖哪些未决策项与默认方案，**不阻塞页面结构开发**；完整清单集中在 §11 决策依赖索引，状态词汇与 PRD §0.3 一致。"),
    ("`> ⚠️` 为待确认事项。", "`<20>` 为决策依赖（见 §11 决策依赖索引）。"),
])

# §7.4 申诉时序图：与 §7.9 状态机对齐
fix("ui-2.md", [
    ('A->>U: 会话内标记「该问题已放行，内容仍为科普参考」',
     'A->>U: SC-13 显示「已受理 + 受理编号 + 预计复核时限」，不自动回会话'),
    ('K-->>U: 复核结果（放行 / 维持拦截，含理由）',
     'K-->>U: 复核结果（放行 / 维持拦截，含理由）'),
    ('alt 放行\n        A->>U: SC-13 显示「已受理 + 受理编号 + 预计复核时限」，不自动回会话\n    end',
     'alt 复核通过（仅软类别）\n        A->>U: SC-13 显示「该问题已放行，请在 24 小时内重新提交」\n        U->>A: 用户主动回会话重新提交（重新走完整链路，含风险扫描）\n    else 维持拦截或硬类别\n        A->>U: 显示渠道清单；硬类别不提供「继续提问」出口\n    end'),
])