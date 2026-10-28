# -*- coding: utf-8 -*-
"""分级决策包（RQ-06「先拦、再分档、后回答」的「分档」层）。

模块清单：
- `templates`：首批 5 类分级模板（发热 / 呕吐 / 外伤 / 误食 / 宠物急症），
  规则条目化、文案「保守从严」，作为 `triage_rule` 表的种子与引擎兜底；
- `engine`：毫秒级规则引擎（场景识别 → 信号提取 → 条件匹配 → 档位裁决），
  输出 `triage` 契约对象（`level` / `rule_hits` / `observations` /
  `escalation_flags` / `disclaimers`），并保证不出现确定性结论表述。
"""
