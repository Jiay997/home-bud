# -*- coding: utf-8 -*-
"""分级决策首批模板（RQ-06 §3.6.3 五类模板，Q-49 默认「保守从严」口径）。

五类模板：

1. `fever` 婴幼儿发热（分月龄档：<3 月 / 3–6 月 / 6 月+，阈值与热程组合判定）
2. `vomit` 呕吐腹泻（脱水观察项；血便 / 胆汁样呕吐直 🔴）
3. `trauma` 外伤（动物致伤走 F8.5 第 4 类硬拦截，不入分级；跌落碰撞按部位与意识状态）
4. `ingestion` 误食（有毒物走 F8.5 第 6 类硬拦截；低危物品观察档）
5. `pet_acute` 宠物急症观察（食欲 / 精神 / 排泄观察项 + 红旗）

**规则口径声明**：以下规则为「保守从严」默认实现，阈值为研发按公开儿科/兽医
科普共识取保守值，**须经育儿 / 宠物专家逐条书面确认后替换**
（PRD §7.2 门禁「分级决策规则上线评审」、Q-49）。确认动作在后台
`POST /admin/triage-rules/{rule_id}/review` 留痕（写 `expert_signoff`）。

字段语义（`conditions`）：

- `any_keywords`：命中任一即视为症状条件满足；
- `all_keywords`：全部命中才满足（用于组合症状，如「呕吐 + 胆汁」）；
- `none_keywords`：出现任一即否决该规则（用于误食低危与有毒物的区分）；
- `temp_min` / `temp_max`：体温（℃）区间，左闭右开；
- `duration_min_hours`：症状持续小时数下限；
- `mental_state`：`normal`（精神反应正常）/ `poor`（嗜睡、萎靡、叫不醒）。

档位判定由服务端规则引擎执行（毫秒级），模型只负责观察项文案与追问理解，
**不得改写档位**（PRD §3.6.3「判定位置」）。
"""
from typing import Any, Dict, List

# 场景识别关键词（用于在风险放行后判定问题属于哪一类分级模板）
SCENE_KEYWORDS: Dict[str, List[str]] = {
    "fever": [
        "发烧", "发热", "体温", "低烧", "高烧", "烧到", "℃", "度",
        "抽搐", "惊厥", "翻白眼",
    ],
    "vomit": [
        "呕吐", "吐了", "吐奶", "腹泻", "拉稀", "拉肚子", "脱水", "水样便", "血便",
    ],
    "trauma": [
        "摔了", "摔下", "跌落", "磕到", "撞到", "碰伤", "淤青", "肿包", "外伤",
    ],
    "ingestion": [
        "误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口",
    ],
    "pet_acute": [
        "不吃", "不喝", "不食", "精神差", "精神萎靡", "拉稀", "呕吐", "腹泻",
        "抽搐", "呼吸费力", "出血", "站不起来", "急症", "尿不出", "躲起来",
    ],
}

# 领域 → 可用场景（儿童不起宠物急症模板，宠物不起儿科模板，避免跨域误判）
SCENES_BY_DOMAIN: Dict[str, List[str]] = {
    "child": ["fever", "vomit", "trauma", "ingestion"],
    "pet": ["pet_acute", "ingestion"],
}

# 场景顺序（同分时按此顺序优先：越靠前越保守）
SCENE_ORDER = ["pet_acute", "fever", "vomit", "trauma", "ingestion"]

# 档位元信息（服务端下发，前端不得硬编码文案）
LEVEL_META: Dict[str, Dict[str, str]] = {
    "red": {
        "label": "建议立即就医",
        "color": "danger",
        "icon": "🔴",
        "action_hint": "请尽快前往就近医疗机构；无法自行前往时拨打急救电话。",
    },
    "yellow": {
        "label": "建议尽快评估",
        "color": "warning",
        "icon": "🟡",
        "action_hint": "建议在 24 小时内由医生或有资质机构评估；期间按观察项记录变化。",
    },
    "green": {
        "label": "可居家观察",
        "color": "success",
        "icon": "🟢",
        "action_hint": "可按观察项居家照护；出现升级红旗任一项即按 🔴 处理。",
    },
}

# 通用免责（三档均附着，NFR-C2）
COMMON_DISCLAIMERS = [
    "本工具仅提供养育科普参考，不构成诊断或治疗建议。",
    "本工具不能替代面诊；如对状况判断不确定，请及时就医。",
]

# 绿档强制附加声明（AC-RQ06-4：必须附「随时可再次提问 / 不能替代面诊」）
GREEN_DISCLAIMERS = [
    "观察期间可随时再次提问；本工具不能替代面诊。",
    "不出现就医指征不代表可以排除疾病，请以线下医生判断为准。",
]

# 夜间提示（AC-RQ06-7）
NIGHT_NOTICE_NON_GREEN = (
    "夜间就医提示：目前处于夜间时段（22:00–6:00），如需就诊请优先选择设有"
    "急诊的机构；必要时拨打急救电话。"
)
NIGHT_NOTICE_GREEN = (
    "夜间提示：如无法安抚或症状在夜间加重，仍建议就医，不要等到白天。"
)

# 信息不足态（AC-RQ06-1 边界：不给档位，给需要补充的关键信息）
MISSING_INFO_PROMPT = [
    "体温读数（如 38.2℃）与测量方式",
    "症状开始时间与持续时长",
    "精神状态（能否正常互动、是否嗜睡或叫不醒）",
    "是否伴随其他症状（呕吐、皮疹、呼吸急促、拒食等）",
]

# ---------------------------------------------------------------------------
# 首批规则条目（seed 用；每条即一个 triage_rule 行）
# ---------------------------------------------------------------------------
TRIAGE_RULES: List[Dict[str, Any]] = [
    # ---------------- 1. 婴幼儿发热 ----------------
    {
        "rule_id": "fever_infant_lt3m",
        "scene": "fever",
        "domain": "child",
        "title": "3 月龄以下婴儿发热（≥37.5℃）必须立即就医",
        "age_min_months": 0,
        "age_max_months": 2,
        "conditions": {
            "any_keywords": ["发烧", "发热", "体温", "低烧", "高烧", "烧到"],
            "temp_min": 37.5,
        },
        "level": "red",
        "priority": 1000,
        "basis": "3 月龄以下婴儿免疫防御不完善，任何发热均按急症处理（保守从严）。",
        "observations": [
            "就诊前记录体温读数与测量时间",
            "记录喂奶量与小便次数",
        ],
        "escalation_flags": [
            "体温 ≥38.0℃",
            "拒奶、精神萎靡或叫不醒",
            "呼吸急促、口唇发绀",
        ],
        "contraindications": [
            "不要自行给 3 月龄以下婴儿使用退热药",
            "不要用酒精擦浴或冰水降温",
        ],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板 / 儿科发热分诊共识（保守口径）",
    },
    {
        "rule_id": "fever_3_6m_high",
        "scene": "fever",
        "domain": "child",
        "title": "3–6 月龄婴儿高热（≥38.5℃）按急症处理",
        "age_min_months": 3,
        "age_max_months": 5,
        "conditions": {
            "any_keywords": ["发烧", "发热", "体温", "高烧", "烧到"],
            "temp_min": 38.5,
        },
        "level": "red",
        "priority": 900,
        "basis": "小月龄婴儿高热可能提示严重细菌感染，建议立即就医。",
        "observations": ["记录体温曲线（每 2 小时一次）", "观察奶量与精神状态"],
        "escalation_flags": ["体温 ≥39.0℃", "抽搐", "精神萎靡、拒奶"],
        "contraindications": ["不要自行使用抗生素", "不要捂汗退热"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "fever_convulsion",
        "scene": "fever",
        "domain": "child",
        "title": "发热伴抽搐 / 惊厥 / 翻白眼（热性惊厥）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["抽搐", "惊厥", "翻白眼", "四肢抽动", "双眼上翻"],
        },
        "level": "red",
        "priority": 990,
        "basis": "热性惊厥需现场处置与就医评估，任何一轮追问出现抽搐均按 🔴 处理。",
        "observations": [
            "记录抽搐开始时间与持续时长",
            "记录抽搐时表现（双眼上翻、四肢抽动、口吐白沫）",
            "记录抽搐后精神恢复情况",
        ],
        "escalation_flags": [
            "抽搐超过 5 分钟",
            "抽搐后意识未恢复",
            "24 小时内再次抽搐",
        ],
        "contraindications": [
            "抽搐时不要按压肢体或往口中塞任何东西",
            "不要在抽搐时喂水喂药",
            "不要掐人中或强行束缚",
        ],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（热性惊厥处置）",
    },
    {
        "rule_id": "fever_poor_mental_state",
        "scene": "fever",
        "domain": "child",
        "title": "发热伴精神反应差 / 抽搐 / 呼吸困难",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["发烧", "发热", "体温", "低烧", "高烧", "烧到"],
            "mental_state": "poor",
        },
        "level": "red",
        "priority": 950,
        "basis": "发热伴精神反应差、抽搐或呼吸困难属就医指征，不进入居家观察。",
        "observations": ["记录抽搐持续时长与表现（是否双眼上翻、四肢抽动）"],
        "escalation_flags": ["抽搐超过 5 分钟", "意识不清", "呼吸费力"],
        "contraindications": ["抽搐时不要强行按压肢体或往口中塞东西"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "fever_child_high",
        "scene": "fever",
        "domain": "child",
        "title": "6 月龄以上高热（≥39.0℃）建议尽快评估",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["发烧", "发热", "体温", "高烧", "烧到"],
            "temp_min": 39.0,
        },
        "level": "yellow",
        "priority": 700,
        "basis": "高热伴不适建议 24 小时内由医生评估，不建议单纯居家硬扛。",
        "observations": [
            "每 2–4 小时记录一次体温",
            "记录饮水 / 排尿次数（判断脱水）",
            "记录精神状态与进食量",
        ],
        "escalation_flags": [
            "体温持续 ≥39.5℃ 超过 24 小时",
            "出现皮疹、颈项强直、抽搐",
            "尿量明显减少或哭时无泪",
        ],
        "contraindications": ["不要交替叠加多种退热药", "不要用酒精擦浴"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "fever_older_low_normal_state",
        "scene": "fever",
        "domain": "child",
        "title": "6 月龄以上低热且精神反应正常",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["发烧", "发热", "体温", "低烧", "烧到"],
            "temp_min": 37.3,
            "temp_max": 38.5,
            "mental_state": "normal",
        },
        "level": "green",
        "priority": 600,
        "basis": "低热且精神、进食、活动正常者可按观察项居家照护。",
        "observations": [
            "每 4 小时测一次体温并记录",
            "少量多次补充水分",
            "观察 24–48 小时的体温走势",
            "记录是否出现新症状（皮疹、呕吐、咳嗽加重）",
        ],
        "escalation_flags": [
            "体温升到 ≥38.5℃ 或持续超过 48 小时",
            "精神变差、拒食、尿量明显减少",
            "出现抽搐、呼吸困难、皮疹",
        ],
        "contraindications": [
            "不要捂汗",
            "不要自行使用抗生素",
            "不要以「摸额头不烫」替代体温计测量",
        ],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "fever_default",
        "scene": "fever",
        "domain": "child",
        "title": "发热但信息不足以定档（保守给评估档）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {"any_keywords": ["发烧", "发热", "体温", "低烧", "高烧", "烧到"]},
        "level": "yellow",
        "priority": 100,
        "basis": "未给出体温读数或精神状态，按保守口径建议尽快评估。",
        "observations": ["先补测体温并记录", "记录精神状态与饮水排尿"],
        "escalation_flags": ["任何抽搐、呼吸困难或叫不醒"],
        "contraindications": ["不要在没有体温读数的情况下自行加药"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    # ---------------- 2. 呕吐腹泻 ----------------
    {
        "rule_id": "vomit_blood_or_bile",
        "scene": "vomit",
        "domain": "child",
        "title": "呕吐物含血或胆汁样（黄绿色）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["呕吐", "吐了", "吐奶"],
            "all_keywords": [],
            "any_of_groups": [
                ["血", "吐血", "血丝"],
                ["胆汁", "黄绿色", "绿色"],
                ["血便", "便血"],
            ],
        },
        "level": "red",
        "priority": 980,
        "basis": "胆汁样呕吐、血性呕吐物或血便属急症指征，需立即就医。",
        "observations": ["留存呕吐物照片供医生判断（不用于本工具）", "记录呕吐次数与量"],
        "escalation_flags": ["反复呕吐无法进水", "腹部明显胀痛", "精神萎靡"],
        "contraindications": ["不要自行使用止吐药", "不要强行喂水喂食"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "vomit_dehydration",
        "scene": "vomit",
        "domain": "child",
        "title": "呕吐腹泻伴脱水指征",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["呕吐", "腹泻", "拉稀", "拉肚子", "吐了"],
            "any_of_groups": [
                ["脱水", "尿少", "无尿", "哭时无泪", "口干", "眼窝凹陷", "精神萎靡"],
            ],
        },
        "level": "red",
        "priority": 940,
        "basis": "出现脱水指征时口服补液通常不足以纠正，需就医评估。",
        "observations": ["记录最近 6 小时小便次数", "记录每次呕吐 / 腹泻量与时间"],
        "escalation_flags": ["6 小时无小便", "嗜睡", "皮肤弹性差"],
        "contraindications": ["不要只喂白水而不补充电解质", "不要自行使用止泻药"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "vomit_repeated",
        "scene": "vomit",
        "domain": "child",
        "title": "反复呕吐（≥3 次）但无脱水与血性表现",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["呕吐", "吐了", "吐奶"],
            "any_of_groups": [["三次", "3次", "四次", "多次", "反复", "好几次", "好多次"]],
        },
        "level": "yellow",
        "priority": 560,
        "basis": "反复呕吐需评估脱水风险，保守口径建议尽快由医生评估。",
        "observations": [
            "记录每次呕吐时间与量",
            "少量多次补充口服补液盐",
            "记录小便次数（每 6 小时至少 1 次）",
        ],
        "escalation_flags": [
            "呕吐物带血或呈黄绿色",
            "6 小时以上无小便、哭时无泪",
            "精神萎靡、叫不醒",
        ],
        "contraindications": ["不要自行使用止吐药", "不要强行大量喂水"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    {
        "rule_id": "vomit_mild",
        "scene": "vomit",
        "domain": "child",
        "title": "轻度呕吐或腹泻、精神尚可",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["呕吐", "吐了", "腹泻", "拉稀", "拉肚子"],
            "mental_state": "normal",
        },
        "level": "green",
        "priority": 500,
        "basis": "无脱水与血性表现、精神尚可者可按观察项居家照护。",
        "observations": [
            "少量多次口服补液盐",
            "记录呕吐 / 排便次数与性状",
            "记录小便次数（每 6 小时至少 1 次）",
            "观察精神状态与进食意愿",
        ],
        "escalation_flags": [
            "出现血便或呕吐物带血 / 胆汁样",
            "6 小时以上无小便、哭时无泪",
            "精神萎靡、叫不醒",
            "持续呕吐超过 12 小时无法进水",
        ],
        "contraindications": ["不要自行使用止泻药或抗生素", "不要强迫进食"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "vomit_default",
        "scene": "vomit",
        "domain": "child",
        "title": "呕吐 / 腹泻信息不足（保守给评估档）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {"any_keywords": ["呕吐", "吐了", "吐奶", "腹泻", "拉稀", "拉肚子", "脱水"]},
        "level": "yellow",
        "priority": 100,
        "basis": "缺少精神状态、尿量与呕吐物性状信息，按保守口径建议尽快评估。",
        "observations": ["补充记录呕吐物性状与小便次数"],
        "escalation_flags": ["血性 / 胆汁样呕吐物", "无尿", "精神萎靡"],
        "contraindications": ["不要自行使用止吐药"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    # ---------------- 3. 外伤 ----------------
    {
        "rule_id": "trauma_head_consciousness",
        "scene": "trauma",
        "domain": "child",
        "title": "跌落碰撞后意识改变 / 呕吐 / 嗜睡",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["摔了", "摔下", "跌落", "磕到", "撞到", "肿包", "碰伤"],
            "any_of_groups": [
                ["昏迷", "失去意识", "叫不醒", "嗜睡", "翻白眼"],
                ["呕吐", "喷射性呕吐"],
                ["出血不止", "大量出血"],
            ],
        },
        "level": "red",
        "priority": 970,
        "basis": "头部外伤后出现意识改变、呕吐或活动性出血属急症指征。",
        "observations": ["记录受伤时间、高度与着地部位", "持续观察 24 小时意识状态"],
        "escalation_flags": ["再次呕吐", "一侧肢体无力", "瞳孔不等大"],
        "contraindications": ["不要摇晃或抬起孩子头部", "不要自行服用止痛药掩盖症状"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "trauma_minor",
        "scene": "trauma",
        "domain": "child",
        "title": "轻度磕碰、精神反应正常",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["摔了", "摔下", "跌落", "磕到", "撞到", "淤青", "肿包", "碰伤"],
            "mental_state": "normal",
        },
        "level": "green",
        "priority": 520,
        "basis": "轻度磕碰、无意识改变与持续出血者可按观察项居家照护。",
        "observations": [
            "受伤 24 小时内冷敷肿包（每次 10–15 分钟）",
            "观察 48 小时内意识、精神与进食变化",
            "记录是否出现呕吐或异常哭闹",
        ],
        "escalation_flags": [
            "出现呕吐、嗜睡或叫不醒",
            "肿包迅速增大或明显压痛",
            "活动受限或一侧肢体不用",
        ],
        "contraindications": ["24 小时内不要热敷或揉搓肿包", "不要自行服用止痛药掩盖症状"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "trauma_default",
        "scene": "trauma",
        "domain": "child",
        "title": "外伤信息不足（保守给评估档）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["摔了", "摔下", "跌落", "磕到", "撞到", "碰伤", "淤青", "肿包", "外伤"]
        },
        "level": "yellow",
        "priority": 100,
        "basis": "缺少受伤部位、高度与意识状态信息，按保守口径建议尽快评估。",
        "observations": ["补充记录受伤高度、着地部位与当时反应"],
        "escalation_flags": ["意识改变", "反复呕吐", "出血不止"],
        "contraindications": ["不要揉搓受伤部位"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    # ---------------- 4. 误食（有毒物走 F8.5 第 6 类硬拦截） ----------------
    {
        "rule_id": "ingestion_hazard_flag",
        "scene": "ingestion",
        "domain": "any",
        "title": "误食高风险物品（电池 / 磁铁 / 药物 / 清洁剂）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口"],
            "any_of_groups": [
                ["纽扣电池", "电池", "磁铁", "磁珠"],
                ["药", "药片", "药水", "退烧药", "布洛芬", "对乙酰氨基酚"],
                ["清洁剂", "消毒液", "农药", "洗洁精", "洗衣液"],
                ["干燥剂", "樟脑", "烟油", "电子烟"],
            ],
        },
        "level": "red",
        "priority": 990,
        "basis": "高风险物品误食可能造成化学损伤、梗阻或中毒，需立即就医。",
        "observations": ["带上误食物品的包装或说明书前往医院", "记录误食量与时间"],
        "escalation_flags": ["流涎、灼痛、呕吐", "呼吸困难", "精神萎靡"],
        "contraindications": [
            "不要催吐（腐蚀性物品催吐会二次损伤）",
            "不要自行喂水、喂奶或喂食中和",
        ],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "ingestion_low_risk",
        "scene": "ingestion",
        "domain": "child",
        "title": "误食低危物品（纸 / 少量食物碎屑）观察档",
        "age_min_months": 6,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口"],
            "any_of_groups": [["纸", "纸巾", "饼干", "饭粒", "水果", "蔬菜", "面包"]],
            "none_keywords": [
                "电池", "磁铁", "药", "清洁剂", "消毒液", "农药", "干燥剂",
                "樟脑", "烟油", "电子烟",
            ],
        },
        "level": "green",
        "priority": 540,
        "basis": "低危物品少量误食、无呛咳与呼吸困难者可按观察项居家照护。",
        "observations": [
            "观察有无呛咳、流涎、呕吐与腹痛",
            "观察 24–48 小时排便情况",
            "记录误食物品与大致量",
        ],
        "escalation_flags": [
            "出现呛咳、呼吸困难或声音嘶哑",
            "反复呕吐、腹痛或腹胀",
            "出现电池 / 磁铁 / 药物 / 清洁剂误食",
        ],
        "contraindications": ["不要自行催吐", "不要用大量水强行冲服"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板",
    },
    {
        "rule_id": "ingestion_default",
        "scene": "ingestion",
        "domain": "child",
        "title": "误食物品不明（保守给评估档）",
        "age_min_months": 0,
        "age_max_months": 83,
        "conditions": {
            "any_keywords": ["误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口"]
        },
        "level": "yellow",
        "priority": 100,
        "basis": "误食物品或剂量不明，按保守口径建议尽快评估。",
        "observations": ["确认误食物品名称与剂量", "带上包装前往医院"],
        "escalation_flags": ["流涎、灼痛、呕吐、呼吸困难"],
        "contraindications": ["不要催吐", "不要自行喂水稀释"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    # ---------------- 4b. 宠物误食（有毒物走 F8.5 第 6 类硬拦截） ----------------
    {
        "rule_id": "pet_ingestion_low_risk",
        "scene": "ingestion",
        "domain": "pet",
        "title": "宠物误食低危物品（纸 / 少量主食 / 蔬果）观察档",
        "age_min_months": 0,
        "age_max_months": 9999,
        "conditions": {
            "any_keywords": ["误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口"],
            "any_of_groups": [["纸", "纸巾", "狗粮", "猫粮", "饭粒", "水果", "蔬菜", "面包", "草"]],
            "none_keywords": [
                "巧克力", "葡萄", "洋葱", "木糖醇", "百合", "清洁剂", "消毒液",
                "农药", "老鼠药", "药片", "电池", "磁铁",
            ],
        },
        "level": "green",
        "priority": 540,
        "basis": "低危物品少量误食、无呕吐与精神异常者可按观察项居家照护。",
        "observations": [
            "记录误食物品与大致量",
            "观察 24–48 小时的进食、排便与精神状态",
            "保证充足饮水",
        ],
        "escalation_flags": [
            "出现呕吐、腹泻或拒食",
            "精神萎靡、站立困难",
            "误食物品属于巧克力 / 葡萄 / 洋葱 / 木糖醇 / 药物 / 清洁剂",
        ],
        "contraindications": ["不要自行催吐", "不要自行投喂人用药物"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（宠物误食观察）",
    },
    {
        "rule_id": "pet_ingestion_default",
        "scene": "ingestion",
        "domain": "pet",
        "title": "宠物误食物品不明（保守给评估档）",
        "age_min_months": 0,
        "age_max_months": 9999,
        "conditions": {
            "any_keywords": ["误食", "误服", "吃下去", "吞了", "咽下", "吃了", "尝了一口"]
        },
        "level": "yellow",
        "priority": 100,
        "basis": "误食物品或剂量不明，按保守口径建议 24 小时内由兽医评估。",
        "observations": ["确认误食物品名称与大致量", "带上包装前往宠物医院"],
        "escalation_flags": ["呕吐、流涎、抽搐、呼吸费力"],
        "contraindications": ["不要自行催吐", "不要自行投喂人用药物"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（保守从严）",
    },
    # ---------------- 5. 宠物急症观察 ----------------
    {
        "rule_id": "pet_acute_red",
        "scene": "pet_acute",
        "domain": "pet",
        "title": "宠物急症表现（抽搐 / 呼吸费力 / 大量出血 / 无法站立）",
        "age_min_months": 0,
        "age_max_months": 9999,
        "conditions": {
            "any_keywords": ["抽搐", "惊厥", "呼吸费力", "张口呼吸", "喘不上气", "大出血", "血流不止",
                             "出血不止", "无法站立", "瘫痪", "站不起来", "叫不醒", "昏迷", "排尿困难",
                             "尿不出", "不吃", "不喝", "精神差", "拉稀", "呕吐", "腹泻"],
            "any_of_groups": [
                ["抽搐", "惊厥"],
                ["呼吸费力", "张口呼吸", "喘不上气"],
                ["大出血", "血流不止", "出血不止"],
                ["无法站立", "瘫痪", "站不起来"],
                ["叫不醒", "昏迷"],
                ["排尿困难", "尿不出"],
            ],
        },
        "level": "red",
        "priority": 980,
        "basis": "上述表现为宠物急症指征，需尽快前往宠物急诊机构。",
        "observations": ["记录发作时间与持续时长", "拍摄发作视频供兽医判断（不用于本工具）"],
        "escalation_flags": ["症状持续超过 5 分钟", "意识丧失", "牙龈发白"],
        "contraindications": ["不要自行投喂人用药物", "不要强行喂食喂水"],
        "disclaimers": COMMON_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（宠物急症观察）",
    },
    {
        "rule_id": "pet_acute_yellow",
        "scene": "pet_acute",
        "domain": "pet",
        "title": "宠物持续不食 / 呕吐 / 精神差（24 小时内观察）",
        "age_min_months": 0,
        "age_max_months": 9999,
        "conditions": {
            "any_keywords": ["不吃", "不喝", "不食", "精神差", "精神萎靡", "呕吐", "拉稀",
                             "腹泻", "软便", "嗜睡", "躲起来"]
        },
        "level": "yellow",
        "priority": 700,
        "basis": "持续不食、呕吐或精神差提示可能存在问题，建议 24 小时内评估。",
        "observations": [
            "记录饮水量与进食量",
            "记录呕吐 / 排便次数与性状",
            "观察是否躲藏、拒触、呼吸频率变化",
        ],
        "escalation_flags": [
            "出现抽搐、呼吸费力、大量出血",
            "超过 24 小时完全不进食不饮水",
            "呕吐超过 3 次或多日腹泻",
        ],
        "contraindications": ["不要自行投喂人用止吐药或抗生素", "不要强行改变饮食"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（宠物急症观察）",
    },
    {
        "rule_id": "pet_behavior_mild",
        "scene": "pet_acute",
        "domain": "pet",
        "title": "宠物轻度行为 / 食欲波动（观察档）",
        "age_min_months": 0,
        "age_max_months": 9999,
        "conditions": {
            "any_keywords": ["不吃", "不喝", "挑食", "没胃口", "精神差", "软便", "偶尔呕吐",
                             "不太吃", "食欲下降"]
        },
        "level": "green",
        "priority": 520,
        "basis": "轻度食欲或行为波动且无急症表现者可按观察项居家照护。",
        "observations": [
            "记录 24 小时进食量与饮水量",
            "观察排便性状与次数",
            "记录活动量与互动反应",
        ],
        "escalation_flags": [
            "超过 24 小时完全不吃不喝",
            "呕吐 / 腹泻次数增加",
            "出现抽搐、呼吸费力、站立困难",
        ],
        "contraindications": ["不要用零食替代主粮", "不要自行用药"],
        "disclaimers": COMMON_DISCLAIMERS + GREEN_DISCLAIMERS,
        "source_ref": "Q-49 默认模板（宠物急症观察）",
    },
]
