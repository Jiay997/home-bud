# -*- coding: utf-8 -*-
"""种子数据脚本：初始化业务运行所需的基础数据（幂等）。

覆盖 spec「首次初始化」Scenario：
- 后台账号 5 个（admin/operator/support/expert_child/expert_pet）
- 词库条目（高危/敏感 + 药名剂量正则配置 + 拟人化文案合规词表 RQ-02）
- 危机渠道占位（除 110 外号码留空，不编造号码；V3.1 补类目/地域/服务时段）
- 知识库样例条目（育儿/宠物各 ≥6 条 published；V3.1 补「来源等级」）
- 气质测评 16 题（4 维×4 题，04/08/12/16 反向，双题干变体，合成演示数据）
- 商品（会员月卡 19.9 元 = 19_900_000 micro，platform_scope 排除 ios）
- 文案 ID（DISCLAIMER_V1 等 11 个）
- 系统开关（5 个入口紧急下线）
- V3.1 新增：分级规则 21 条（RQ-06 首批 5 类模板）、轻工具 3 个（RQ-12）、
  专题包 3 套（RQ-13/RQ-14）、订阅偏好默认关闭（RQ-08 需用户开启）

用法：python scripts/seed_data.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.crypto import encrypt_field, sha256_hex  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    AdminUser,
    AppUser,
    ConfigVersion,
    ConsentRecord,
    CrisisChannel,
    KbEntry,
    LexiconTerm,
    Product,
    RiskRuleConfig,
    TextVersion,
    ToolItem,
    TopicPack,
    TriageRule,
)

NOW = datetime.now(timezone.utc)

# ---------- 文案 ID 清单（UI 文档 §8：11 个文案 ID） ----------
TEXTS = [
    ("DISCLAIMER_V1", "本内容由 AI 生成，仅作养育参考，不构成医疗建议，不能替代医生、心理咨询师、学校教师或执业兽医的判断。如有疑问请咨询专业人士。"),
    ("AI_GEN_LABEL_V1", "AI 生成内容"),
    ("REFUSAL_AGE_V1", "该问题超出 0-6 岁育儿与猫狗饲养范围，建议咨询相关专业机构。"),
    ("CRISIS_CHANNELS_V1", "如果您或孩子正处于危险中，请立即联系以下渠道获得帮助。"),
    ("QUOTA_RULE_V1", "免费用户每日可用 {limit} 次问答，次日 0 点恢复；会员不受限制。"),
    ("REFUND_NOTICE_V1", "虚拟内容一经解锁，非质量问题不支持退款。购买前请确认。"),
    ("CHILD_CONSENT_V1", "我们将收集儿童的昵称、出生日期、过敏项等信息，仅用于提供分龄养育建议，加密存储、不用于训练模型，您可随时撤回同意。"),
    ("GUARDIAN_DECLARATION_V1", "我确认我是该儿童的监护人，所填写信息真实、必要。"),
    ("RISK_BLOCK_V1", "已停止生成回答。"),
    ("APPEAL_NOTICE_V1", "如认为本次拦截属于误判，可提交申诉，我们将在 24 小时内复核。"),
    ("READONLY_V1", "会员已到期，历史内容转为只读。"),
]

# ---------- 危机渠道占位（号码除 110 外留空：不得编造号码，PRD 红线） ----------
# V3.1 RQ-03 §3.3.3 字段扩展：(code, name, phone, category, region,
# service_hours, applicable_categories)
CRISIS_CHANNELS = [
    ("police", "报警求助", "110", "police", "全国", "7×24", ["child_abuse", "child_selfharm"]),
    ("minor_protection", "未成年人保护热线", "", "minor_protection", "全国", "工作日 9:00–17:00",
     ["child_abuse", "harmful_to_minor"]),
    ("psych_hotline", "心理援助热线", "", "psychological", "全国", "以官方公布时段为准",
     ["child_selfharm", "depression"]),
    ("fever_emergency", "儿科急症就诊", "", "pediatric_emergency", "全国", "以机构公布时段为准",
     ["high_fever", "medicine_dosage", "risk_unavailable"]),
    ("pet_emergency", "宠物急症就诊", "", "pet_emergency", "全国", "以机构公布时段为准",
     ["pet_poison", "pet_bleeding"]),
    ("rabies_clinic", "犬伤处置门诊/疾控中心", "", "pediatric_emergency", "全国",
     "以机构公布时段为准", ["animal_bite"]),
]

# ---------- 拟人化文案合规词表（RQ-02 / NFR-C14 类型 anthropomorphic） ----------
# 词表真源在 `app/compliance/copy_scan.FORBIDDEN_PHRASES`（合规包自身不参与
# 文案扫描，避免「词表含词条」自证违规）；此处仅入库供后台与 CI 共用。
# 入库后**不参与**输入侧风险拦截（见 risk/service.py 的 anthropomorphic 过滤）。
from app.compliance.copy_scan import FORBIDDEN_PHRASES as ANTHROPOMORPHIC_TERMS  # noqa: E402

# ---------- V3.1 专题包（RQ-13 / RQ-14） ----------
# 诚实口径：示例内容以 `draft` 落库、专家会签字段留空 —— 交叉主题包必须
# 育儿 + 宠物专家**双签**后才能上架（AC-RQ13-1），播种阶段不得伪造签署。
# 运营在后台 `/admin/topics` 补签后会签字段并置 status=on 即可上架。
TOPIC_PACKS = [
    {
        "topic_code": "topic_pregnancy_pet",
        "title": "孕期 + 养宠共存指南",
        "domain": "cross",
        "summary": "弓形虫风险的真实口径、孕期日常接触边界、产前准备与环境调整。",
        "price_micro": 9_900_000,
        "product_code": "member_monthly",
        "redflag_first": True,
        "redflag_blocks": [
            {
                "key": "redflags",
                "title": "先看红旗",
                "content": (
                    "孕期出现发热、皮疹、淋巴结肿大，或接触猫砂后不适，请就医并告知医生养宠情况；"
                    "**本内容不替代产检与医生判断**。"
                ),
            }
        ],
        "content_blocks": [
            {
                "key": "physiological_check",
                "title": "先排查生理风险",
                "content": "弓形虫主要经未煮熟的肉类与土壤传播，规范清理猫砂（每日、戴手套、事后洗手）可显著降低风险。",
            },
            {
                "key": "behavior_cause",
                "title": "孕期宠物行为变化",
                "content": "家庭成员作息改变、气味变化可能让猫狗出现黏人或回避行为，属常见适应反应。",
            },
            {
                "key": "action_plan",
                "title": "可执行方案",
                "content": "1) 猫砂每日清理并交由非孕妇成员；2) 产前布置婴儿房让宠物提前适应；3) 保持疫苗与驱虫周期。",
            },
        ],
        "review_child_signoff": None,
        "review_pet_signoff": None,
        "status": "draft",
    },
    {
        "topic_code": "topic_bite_aftercare",
        "title": "孩子被猫抓狗咬之后",
        "domain": "cross",
        "summary": "暴露分级、24 小时内犬伤门诊流程、回家后的安抚与居家观察。",
        "price_micro": 9_900_000,
        "product_code": "member_monthly",
        "redflag_first": True,
        "redflag_blocks": [
            {
                "key": "redflags",
                "title": "先看这一条（红旗前置）",
                "content": (
                    "**动物致伤属狂犬病暴露风险**：立即用肥皂水与流动清水交替冲洗伤口 ≥15 分钟，"
                    "碘伏消毒，并**24 小时内前往犬伤门诊 / 疾控中心**评估是否需要疫苗与免疫球蛋白。"
                    "以下安抚与共居内容在就医引导之后。"
                ),
            }
        ],
        "content_blocks": [
            {
                "key": "physiological_check",
                "title": "先排查生理原因（暴露分级）",
                "content": "Ⅰ 级：接触/喂养，无破损；Ⅱ 级：轻咬、无出血抓伤；Ⅲ 级：单处或多处贯穿性咬伤、破损皮肤被舔。Ⅱ/Ⅲ 级均需就医评估。",
            },
            {
                "key": "behavior_cause",
                "title": "为什么会发生",
                "content": "多数抓咬发生在宠物进食、睡眠被打扰、被抱姿不当或疼痛时，属应激反应而非「性格坏」。",
            },
            {
                "key": "action_plan",
                "title": "事后安抚与居家改造",
                "content": "1) 先处理孩子的情绪，不斥责、不强迫接触；2) 设置宠物独处安全区；3) 教孩子「不打扰进食与睡觉」；4) 记录疫苗与驱虫周期。",
            },
        ],
        "review_child_signoff": None,
        "review_pet_signoff": None,
        "status": "draft",
    },
    {
        "topic_code": "topic_pet_behavior_line",
        "title": "宠物行为内容线：拆家 / 乱尿 / 护食 / 分离焦虑",
        "domain": "behavior",
        "summary": "先排查生理与发情因素，再做行为成因科普与分场景方案，红旗固定在结构前部。",
        "price_micro": 12_900_000,
        "product_code": "member_monthly",
        "redflag_first": True,
        "redflag_blocks": [
            {
                "key": "redflags",
                "title": "红旗：何时需要就医而不是训练",
                "content": (
                    "出现排尿困难、尿中带血、频繁呕吐、拒食超过 24 小时、突发攻击性升高或认知障碍表现，"
                    "请先就医排查疾病，**不要把病当行为问题训**。"
                ),
            }
        ],
        "content_blocks": [
            {
                "key": "physiological_check",
                "title": "先排查生理原因",
                "content": "疼痛、泌尿系统疾病、发情期、甲状腺问题与认知衰退都会表现为行为变化。",
            },
            {
                "key": "behavior_cause",
                "title": "行为成因科普",
                "content": "拆家常与分离焦虑、运动量不足相关；乱尿需先排除泌尿疾病；护食多与资源竞争焦虑有关。",
            },
            {
                "key": "action_plan",
                "title": "分龄 / 分场景可执行方案",
                "content": "1) 建立固定排泄点与奖励反馈；2) 分离脱敏从 30 秒开始逐步延长；3) 护食训练用「靠近即加餐」替代抢夺。",
            },
        ],
        "review_child_signoff": None,
        "review_pet_signoff": None,
        "status": "draft",
    },
]

# ---------- 词库种子（高危/敏感；词条密文存储） ----------
LEXICON = [
    # (词, 类型, 策略, 类别码)
    ("虐待儿童", "risk", "block", "child_abuse"),
    ("打孩子打到出血", "risk", "block", "child_abuse"),
    ("自杀", "risk", "block", "child_selfharm"),
    ("自残", "risk", "block", "child_selfharm"),
    ("高烧惊厥", "risk", "block", "high_fever"),
    ("热性惊厥", "risk", "block", "high_fever"),
    # 急症独立词条（D1 修复）：原词库只收「高烧惊厥/热性惊厥」等复合短语，
    # 口语化短句（「宝宝突然抽搐了怎么办」）一级不命中，导致急症类问题被
    # 正常生成正文。补齐独立急症词后，「命中即阻断 / 正文为空 / 不计次」
    # 对口语表达同样成立；类别归入 high_fever（后台口径「儿童急症类」，
    # 渠道卡为「儿科急症就诊」）。
    ("抽搐", "risk", "block", "high_fever"),
    ("惊厥", "risk", "block", "high_fever"),
    ("窒息", "risk", "block", "high_fever"),
    ("噎住", "risk", "block", "high_fever"),
    ("呛奶", "risk", "block", "high_fever"),
    ("溺水", "risk", "block", "high_fever"),
    ("烫伤", "risk", "block", "high_fever"),
    ("烧伤", "risk", "block", "high_fever"),
    ("呼吸困难", "risk", "block", "high_fever"),
    ("叫不醒", "risk", "block", "high_fever"),
    ("翻白眼", "risk", "block", "high_fever"),
    ("被狗咬了出血", "risk", "block", "animal_bite"),
    ("被猫抓伤出血", "risk", "block", "animal_bite"),
    ("狂犬病暴露", "risk", "block", "animal_bite"),
    ("宠物中毒", "risk", "block", "pet_poison"),
    ("大出血", "risk", "block", "pet_bleeding"),
    ("严重抑郁", "risk", "block", "depression"),
    ("想死", "risk", "block", "child_selfharm"),
    ("退烧药剂量", "sensitive", "rewrite", "medicine_dosage"),
    ("抗生素用量", "sensitive", "rewrite", "medicine_dosage"),
    ("确诊", "sensitive", "rewrite", "diagnosis"),
    ("治愈", "sensitive", "rewrite", "efficacy"),
    ("包治百病", "sensitive", "rewrite", "efficacy"),
    ("算命", "sensitive", "rewrite", "fortune"),
    ("天生注定", "sensitive", "rewrite", "fortune"),
]

# ---------- 风险规则配置（双阈值 + 模式正则） ----------
RISK_CONFIGS = [
    ("two_level_threshold", {"gray_low": 0.5, "gray_high": 0.8}),
    ("medicine_dosage_pattern", {
        "pattern": r"(布洛芬|对乙酰氨基酚|阿莫西林|头孢|退烧药|抗生素)[^。]{0,10}(剂量|用量|mg|毫升|ml|片)",
        "category_code": "medicine_dosage",
        "action": "block_or_rewrite",
    }),
    ("diagnosis_pattern", {
        "pattern": r"(确诊|诊断为)[^。]{0,20}(自闭|多动|抑郁|焦虑)",
        "action": "rewrite",
    }),
    ("efficacy_pattern", {
        "pattern": r"(保证|包治|根治|治愈)[^。]{0,10}(病|症|障碍)",
        "action": "rewrite",
    }),
    # 急症模式（D1 修复）：与 app/risk/engine.py DEFAULT_PATTERNS 保持一致，
    # 落库后可在后台「词库维护 - 风险规则配置」直接调整正则；
    # exclude_if 按语境消歧（宠物急症不误判为儿童急症）
    ("acute_emergency_pattern", {
        "pattern": (
            r"(抽搐|惊厥|窒息|噎住|噎到|呛奶|呛到|溺水|"
            r"烫伤|烧伤|呼吸困难|喘不上气|叫不醒|翻白眼|失去意识)"
        ),
        "category_code": "high_fever",
        "exclude_if": r"(狗|犬|猫|宠物|汪|喵)",
        "action": "block",
    }),
    ("medicine_ingestion_pattern", {
        "pattern": (
            r"(误食|误服|吞下|咽下|当糖吃)[^。]{0,12}"
            r"(药|药片|胶囊|药水|退烧药|布洛芬|对乙酰氨基酚|消毒液|清洁剂|农药)"
            r"|(药片|胶囊|药水|退烧药|布洛芬|对乙酰氨基酚|消毒液|清洁剂|农药|纽扣电池)"
            r"[^。]{0,12}(误食|误服|吞下|咽下|吃下去|吃了)"
        ),
        "category_code": "medicine_dosage",
        "exclude_if": r"(狗|犬|猫|宠物|汪|喵)",
        "action": "block_or_rewrite",
    }),
]

# ---------- 知识库样例条目（育儿/宠物各 6 条 published；内容为演示性科普） ----------
KB_ENTRIES = [
    # 育儿 6 条
    ("kb_child_sleep_01", "child", "育儿", "sleep_training", "睡眠", "1-3y", None, None,
     "1-3 岁幼儿睡眠引导要点",
     "固定睡前程序（洗澡-抚触-讲故事-关灯）有助于建立睡眠联想；就寝时间建议在 20:30-21:30 之间；白天小睡 1-2 次，总时长 1.5-3 小时。夜醒时先观察 1-2 分钟再介入，避免立即抱起形成依赖。",
     "适用于 12-36 月龄、无发热等急性症状的幼儿", [], "support"),
    ("kb_child_sleep_02", "child", "育儿", "sleep_training", "睡眠", "0-6m", None, None,
     "0-6 月婴儿夜醒应对",
     "此阶段夜醒属正常生理现象，胃容量小需要夜间喂养；建议识别饥饿性哭声与不适性哭声；白天光线充足、夜间暗光，帮助建立昼夜节律。",
     "适用于 0-6 月龄健康新生儿；早产儿按矫正月龄", [], "support"),
    ("kb_child_feed_01", "child", "育儿", "feeding", "喂养与辅食", "6-12m", None, None,
     "辅食添加基本原则",
     "满 6 月龄起添加辅食，首选强化铁米粉；每次只引入一种新食物，观察 2-3 天有无过敏；由稀到稠、由少到多循序渐进；1 岁前不建议添加盐、糖与蜂蜜。",
     "适用于满 6 月龄、已排除食物过敏史的婴儿", [], "support"),
    ("kb_child_safety_01", "child", "育儿", "safety_prevention", "安全与意外预防", "1-3y", None, None,
     "家庭环境安全隐患排查",
     "1-3 岁是跌落、误吞高发期：家具边角加装防撞条、抽屉上锁、小物件（纽扣电池、药片）放置于 1.5 米以上；浴室地面防滑；插座加保护盖。",
     "适用于已学会爬行或行走的幼儿家庭", [], "support"),
    ("kb_child_emotion_01", "child", "育儿", "emotion", "情绪与社交", "3-6y", None, None,
     "幼儿情绪 tantrum 应对",
     "3-6 岁幼儿情绪爆发常见于需求未满足：先共情命名情绪（你现在很生气），再设定边界（打人不可以），最后给选择权（先收积木还是先洗手）。",
     "适用于 3-6 岁典型发展幼儿；频繁自伤或伤人请咨询专业人士", [], "support"),
    ("kb_child_health_01", "child", "育儿", "health_monitor", "生长发育", "0-6m", None, None,
     "婴儿体温观察区间",
     "腋温 36.0-37.2 ℃ 为常见区间；3 月龄以下婴儿体温 ≥38.0 ℃ 属于需及时就医的情形；观察精神状态比单次体温更重要。",
     "适用于 0-6 月龄婴儿的日常体温观察", [], "conditional"),
    # 宠物 6 条
    ("kb_pet_cat_feed_01", "pet", "宠物", "cat_feeding", "喂养", None, "adult", "cat",
     "成年猫喂养频次与体重管理",
     "成年猫建议每日定时喂食 2-3 次；以体重 4kg 成猫为例，干粮每日总量约 50-60g（以包装推荐为准）；肥胖猫需在兽医指导下减重；随时提供清洁饮水。",
     "适用于 1-7 岁已绝育或未绝育家养猫", [], "support"),
    ("kb_pet_cat_behavior_01", "pet", "宠物", "cat_behavior", "行为解读", None, "adult", "cat",
     "猫哈气与低吼的含义",
     "哈气、低吼、飞机耳是猫的防御信号，表示感到威胁需要空间；此时不建议强行抚摸或惩罚；应移除刺激源、给予躲避空间，待其放松后再互动。",
     "适用于应激初期；若伴随拒食超过 24 小时请就医", [], "support"),
    ("kb_pet_dog_feed_01", "pet", "宠物", "dog_feeding", "喂养", None, "adult", "dog",
     "成年犬喂养要点",
     "成年犬每日喂食 1-2 次，避免剧烈运动前后 1 小时进食（降低胃扭转风险）；巧克力、葡萄、洋葱、木糖醇对犬有毒，务必收好；饮水常备。",
     "适用于 1-7 岁健康成年犬", [], "support"),
    ("kb_pet_dog_behavior_01", "pet", "宠物", "dog_behavior", "行为解读", None, "adult", "dog",
     "犬护食行为解读",
     "护食是犬的资源保护本能：进食时低吼是警告信号，不应打骂（会加剧焦虑）；可通过（进餐时保持距离-逐步脱敏-交换高价值零食）的方式改善。",
     "适用于无攻击史的家养犬；出现咬人请咨询专业训犬师", [], "conditional"),
    ("kb_pet_child_01", "pet", "宠物", "child_pet_interaction", "儿童与宠物共处", None, "adult", None,
     "幼儿与猫狗同处的安全边界",
     "学步期幼儿与宠物互动必须全程有成人监护；不给宠物喂食、不拉尾巴、不打扰进食与睡觉的宠物；观察宠物回避信号（哈气、甩尾、躲闪）并及时分开；抓咬伤后立即就医处理。",
     "适用于有 0-6 岁儿童且饲养猫/狗的家庭", [], "support"),
    ("kb_pet_health_01", "pet", "宠物", "health_monitor", "健康观察", None, "junior", None,
     "幼宠疫苗接种区间参考",
     "幼猫幼犬首针疫苗通常在 6-8 周龄，之后按兽医安排间隔接种；疫苗未完成前避免外出接触陌生动物；驱虫方案请遵兽医建议。",
     "适用于 <1 岁幼猫幼犬；具体接种计划以执业兽医意见为准", [], "conditional"),
]

# ---------- 科普全书 / 每日一则小知识（内容源自 docs/09-知识库 的公开指南与机构资料） ----------
# 约定：
# - topic_key 统一为 daily_science_{category}，category ∈ infant / toddler / pet / family；
# - 仅本清单会被 C 端知识科普接口读取，避免测试探针或演示条目进入每日推荐；
# - 每条必须带可读来源、source_level 与适用前提，不写诊断、处方或用药剂量。
PUBLIC_SCIENCE_ENTRIES = [
    # 母婴（0–12 月龄）6 条
    {
        "kb_id": "kb_science_infant_01",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "回应性照护",
        "age_band": "0-3y",
        "pet_stage": None,
        "species": None,
        "title": "回应性照护不是「一哭就抱」",
        "content": "先观察宝宝的眼神、表情、动作、声音和手势，判断是在表达饥饿、困倦、无聊还是需要安抚，再及时、恰当地回应。回应性照护的关键是看见信号并回应，不是固定延迟，也不是每次都用同一种方式。",
        "preconditions": "0–36 月龄健康儿童日常照护；早产儿按矫正月龄观察。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_infant_02",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "喂养与辅食",
        "age_band": "6-24m",
        "pet_stage": None,
        "species": None,
        "title": "辅食第一口，优先富铁食物",
        "content": "满 6 月龄开始添加辅食。6 月龄后母乳提供的铁仅约占需要量的 5%，辅食应每天包含富铁动物性食物（如肉泥、肝泥）或强化铁米粉；只加蛋黄而不加肉类，补铁量往往不够。",
        "preconditions": "6–24 月龄、已开始添加辅食的婴幼儿；食物过敏或患病时遵医嘱。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《婴幼儿营养喂养评估服务指南（试行）》（2024）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_infant_03",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "喂养与辅食",
        "age_band": "6-12m",
        "pet_stage": None,
        "species": None,
        "title": "6–12 月龄奶量参考",
        "content": "6 月龄约 800–1000 毫升/日（5–6 次），8 月龄约 700–800 毫升/日（4–5 次），12 月龄约 600–700 毫升/日（2–3 次）。奶量逐步下降的同时，辅食种类和量要同步增加。",
        "preconditions": "足月健康婴儿；具体奶量需结合生长曲线与医生建议。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《婴幼儿营养喂养评估服务指南（试行）》（2024）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_infant_04",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "视屏管理",
        "age_band": "0-3y",
        "pet_stage": None,
        "species": None,
        "title": "0–3 岁视屏：能不接触就不接触",
        "content": "0–3 岁婴幼儿不接触任何形式的视屏类产品；2 岁以上如使用，每天累计不超过 1 小时、单次不超过 20 分钟。2024 年服务指南口径更严格：6–18 月龄任何视屏使用都视为养育风险。",
        "preconditions": "0–36 月龄；需家庭共同执行，不以视屏替代陪伴。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）及《婴幼儿早期发展服务指南（试行）》（2024）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_infant_05",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "日常护理与睡眠",
        "age_band": "0-12m",
        "pet_stage": None,
        "species": None,
        "title": "睡眠环境与自主入睡",
        "content": "卧室安静、空气新鲜，温度 20–25℃；白天不过度遮光，夜晚睡后熄灯，卧室不放电视等视屏产品。婴儿期每天总睡眠约 12–17 小时；识别睡眠信号，培养自主入睡，避免长期抱睡、摇睡。",
        "preconditions": "0–12 月龄家庭睡眠照护；患病期间按医生建议调整。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_infant_06",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_infant",
        "topic_category": "亲子交流与玩耍",
        "age_band": "0-12m",
        "pet_stage": None,
        "species": None,
        "title": "亲子交流从「面对面」开始",
        "content": "0–1 月多注视眼睛、温柔说话；1–3 月微笑、模仿宝宝的声音；3–6 月多俯卧抬头、伸手抓握不同质地玩具；6–9 月回应名字、玩躲猫猫。交流与玩耍的重点是陪伴和互动，不是提前训练。",
        "preconditions": "0–12 月龄；玩具需适龄并由成人全程看护。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《婴幼儿早期发展服务指南（试行）》附件 3《亲子交流与玩耍要点》（2024）",
        "source_level": "guide",
    },
    # 幼儿（1–6 岁）6 条
    {
        "kb_id": "kb_science_toddler_01",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "情绪与管教",
        "age_band": "1-6y",
        "pet_stage": None,
        "species": None,
        "title": "情绪爆发：先共情，再设边界",
        "content": "需求未被满足时，先帮孩子命名情绪（「你现在很生气」），再明确边界（「打人不可以」），最后给出有限选择（「先收积木还是先洗手」）。共情不等于让步，规则要稳定一致。",
        "preconditions": "1–6 岁典型发展儿童；频繁自伤或伤人需咨询专业人士。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "AAP《Effective Discipline to Raise Healthy Children》（2018）及国家卫健委养育照护指南（2022）",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_toddler_02",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "情绪与管教",
        "age_band": "1-6y",
        "pet_stage": None,
        "species": None,
        "title": "不打不骂也能管教",
        "content": "用正向强化（做到就具体表扬）、提前预告（再过 5 分钟收玩具）、转移注意和自然后果替代打骂。AAP 立场文件指出，体罚与儿童攻击性行为增加相关，且长期效果有限；语言羞辱、威胁同样不建议。",
        "preconditions": "一般家庭日常管教；涉及虐待或家庭暴力应寻求专业保护。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "AAP《Effective Discipline to Raise Healthy Children》（Sege & Siegel，2018）",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_toddler_03",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "安全与意外预防",
        "age_band": "1-3y",
        "pet_stage": None,
        "species": None,
        "title": "家庭安全排查从「小物件」开始",
        "content": "1–3 岁是跌落、误吞高发期。家具尖角加防撞条，抽屉和柜门上锁，纽扣电池、药片、小零件放到幼儿够不到的高处；浴室防滑，插座加保护盖，窗户装锁，水桶水盆加盖。",
        "preconditions": "有 1–3 岁幼儿的家庭；急救操作需接受正规培训。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）·伤害预防",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_toddler_04",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "身体活动",
        "age_band": "1-6y",
        "pet_stage": None,
        "species": None,
        "title": "幼儿每天至少 3 小时身体活动",
        "content": "幼儿每天身体活动不少于 3 小时，其中户外活动至少 2 小时；避免久坐超过 1 小时。天气不适时可减少户外，但应保持室内活动和亲子游戏。",
        "preconditions": "1–6 岁健康儿童；运动能力受限者遵医嘱。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《婴幼儿早期发展服务指南（试行）》附件 3（2024）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_toddler_05",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "亲子阅读",
        "age_band": "0-6y",
        "pet_stage": None,
        "species": None,
        "title": "亲子阅读比识字卡更重要",
        "content": "每天一起看绘本、讲故事、说儿歌，并围绕画面提问、讨论。早期学习应融入日常交流和玩耍，重点是回应、语言输入和亲子关系，而不是提前进行学业训练。",
        "preconditions": "0–6 岁；按孩子注意力长度调整，不强迫坐下听完。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）·交流与玩耍",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_toddler_06",
        "kb_kind": "child",
        "domain": "child",
        "topic_key": "daily_science_toddler",
        "topic_category": "危重症识别",
        "age_band": "0-3y",
        "pet_stage": None,
        "species": None,
        "title": "这些呼吸信号要立即就医",
        "content": "安静状态下，2–12 月龄呼吸超过 50 次/分、2–3 岁超过 40 次/分，或出现鼻翼扇动、胸凹陷、呼吸暂停伴口唇发紫，应立即就医或呼叫急救。家长直觉「情况不对」也应就医。",
        "preconditions": "仅作危重识别与转介提示，不替代急救培训与临床诊断。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "国家卫健委《3岁以下婴幼儿健康养育照护指南（试行）》（2022）·危重症识别",
        "source_level": "guide",
    },
    # 宠物（猫狗科学饲养）6 条
    {
        "kb_id": "kb_science_pet_01",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "喂养与营养",
        "age_band": None,
        "pet_stage": "adult",
        "species": None,
        "title": "营养是宠物的「第五生命体征」",
        "content": "每次健康评估都应看体重、体况评分（BCS）、肌肉状况评分（MCS）和饮食史，异常时再做扩展评估。只看体重会漏掉肌肉流失；体况和肌肉应同时记录。",
        "preconditions": "犬猫；具体热量与处方粮选择需兽医或营养师个体化。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "WSAVA《Global Nutrition Guidelines》（2011）",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_pet_02",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "喂养与营养",
        "age_band": None,
        "pet_stage": "adult",
        "species": None,
        "title": "全价粮与补充性粮不是一回事",
        "content": "标签写「全价（complete）」表示该产品应满足对应生命阶段的全部营养需要；补充性食品不能作为唯一主食。选粮时看生命阶段、营养分析、企业资质与饲喂试验证据，而不是只看广告。",
        "preconditions": "犬猫；中国家庭还需符合国内宠物饲料标签与卫生规定。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "FEDIAF《Nutritional Guidelines for Complete and Complementary Pet Food》（2025）",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_pet_03",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "行为解读",
        "age_band": None,
        "pet_stage": "adult",
        "species": "cat",
        "title": "猫哈气、低吼是在说「请退后」",
        "content": "哈气、低吼、飞机耳、瞳孔放大都是猫的防御信号，表示它感到威胁、需要空间。此时不要强行抱起或惩罚，应移除刺激源、提供躲藏处，等它放松后再互动。",
        "preconditions": "家养猫日常互动；若伴随拒食超过 24 小时或呼吸异常请就医。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "AAHA/AAFP《2021 Feline Life Stage Guidelines》",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_pet_04",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "行为解读",
        "age_band": None,
        "pet_stage": "adult",
        "species": "dog",
        "title": "犬护食：不打骂，做脱敏",
        "content": "护食是犬的资源保护本能。进食时低吼是警告信号，打骂会加剧焦虑。可从保持距离开始，逐步靠近，并用更高价值的零食交换，配合「放下」训练；出现咬人应找专业训犬师或兽医行为师。",
        "preconditions": "无攻击史的家养犬；有咬伤史需专业评估。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "AAHA《2019 Canine Life Stage Guidelines》·行为管理",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_pet_05",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "寄生虫防控",
        "age_band": None,
        "pet_stage": "junior",
        "species": None,
        "title": "幼犬幼猫驱虫从 2 周龄开始",
        "content": "幼犬幼猫应从约 2 周龄开始驱虫，每 2 周一次，直到进入常规广谱寄生虫控制；成年犬猫建议按风险全年驱虫。具体药物、频次与粪检计划由兽医制定。",
        "preconditions": "幼年犬猫；早产、体弱或患病幼宠需兽医个体化。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CAPC 寄生虫防控指南系列（持续更新）",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_pet_06",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_pet",
        "topic_category": "环境丰容",
        "age_band": None,
        "pet_stage": "adult",
        "species": "cat",
        "title": "给猫一个「能躲起来」的家",
        "content": "环境丰容不是多买玩具，而是提供躲藏处、垂直空间、抓挠区、分散的食水与猫砂盆，并保持作息可预测。猫友好、低应激的互动方式应贯穿日常照护与就医。",
        "preconditions": "家养猫；多猫家庭需增加资源点位，减少竞争。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "AAHA/AAFP《2021 Feline Life Stage Guidelines》",
        "source_level": "guide",
    },
    # 家庭共处（孩子 + 宠物）6 条
    {
        "kb_id": "kb_science_family_01",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "儿童与宠物共处",
        "age_band": None,
        "pet_stage": None,
        "species": None,
        "title": "学步期和宠物互动，成人要全程在场",
        "content": "0–6 岁儿童与猫狗互动必须全程有成人监护；不拉尾巴、不抢食、不打扰进食和睡觉的宠物；看到哈气、甩尾、躲闪等回避信号及时分开。抓咬伤后立即处理并就医评估。",
        "preconditions": "有 0–6 岁儿童且饲养猫狗的家庭。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CDC《Healthy Pets, Healthy People》及 AAHA/AAFP 猫狗生命阶段指南",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_family_02",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "家庭卫生",
        "age_band": None,
        "pet_stage": None,
        "species": None,
        "title": "接触宠物后，用肥皂和清水洗手",
        "content": "接触宠物、清理粪便或户外活动后，用肥皂和清水洗手，饭前也要洗。宠物粪便及时清理，沙坑不用时加盖，教育孩子不食土、不把玩具放嘴里。",
        "preconditions": "所有养宠家庭；儿童、孕妇和免疫低下人群重点执行。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CDC《Healthy Pets, Healthy People》·蛔虫防控",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_family_03",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "家庭卫生",
        "age_band": None,
        "pet_stage": None,
        "species": None,
        "title": "防蛔虫不只靠给宠物驱虫",
        "content": "儿童防弓首蛔虫的关键包括：宠物定期驱虫与粪检、即时清理粪便、覆盖沙坑、洗手、不食土，以及不喂宠物未处理生肉。单靠一次驱虫不能替代环境与卫生措施。",
        "preconditions": "有儿童的家庭；具体驱虫方案由兽医制定。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CAPC 寄生虫防控指南与 CDC 家庭卫生建议",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_family_04",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "动物致伤",
        "age_band": None,
        "pet_stage": None,
        "species": None,
        "title": "宠物抓咬伤：先处理暴露，再谈安抚",
        "content": "被猫狗抓咬后，立即用流动清水和肥皂冲洗伤口，尽快前往犬伤门诊或疾控中心评估狂犬病暴露风险，通常应在 24 小时内完成评估与处置。不要先观察、拖延或自行包扎了事。",
        "preconditions": "任何动物致伤；免疫史与伤口分级由医务人员判断。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "中国疾控中心《狂犬病暴露预防处置工作规范（2023 年版）》",
        "source_level": "guide",
    },
    {
        "kb_id": "kb_science_family_05",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "人兽共患",
        "age_band": None,
        "pet_stage": None,
        "species": None,
        "title": "人兽共患病可以管理，不必直接弃养",
        "content": "弓形虫、蛔虫、钩虫、猫抓病等风险可通过驱虫、疫苗、环境清洁、洗手和避免高风险接触来降低。孕妇、婴幼儿和免疫低下人群需要重点防护，但多数情况下无需因此弃养宠物。",
        "preconditions": "一般养宠家庭；免疫低下者需咨询医生与兽医。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CDC《Healthy Pets, Healthy People》与 Kirk's Current Veterinary Therapy 人兽共患病综述",
        "source_level": "institution",
    },
    {
        "kb_id": "kb_science_family_06",
        "kb_kind": "pet",
        "domain": "pet",
        "topic_key": "daily_science_family",
        "topic_category": "孕期防护",
        "age_band": None,
        "pet_stage": None,
        "species": "cat",
        "title": "猫砂盆与孕妇：把风险说清楚",
        "content": "弓形虫主要通过摄入被污染的食物、土壤或猫粪传播。孕妇和免疫低下者应避免直接处理猫砂；如必须处理，戴手套、事后洗手，猫砂盆每天清理。不给猫喂生肉，也能降低感染风险。",
        "preconditions": "孕妇、备孕或免疫低下人群；具体筛查与防护遵医嘱。",
        "contraindications": [],
        "source_type": "literature_rewrite",
        "source_ref": "CDC《Healthy Pets, Healthy People》·弓形虫防护",
        "source_level": "institution",
    },
]

# ---------- 气质测评 16 题（合成演示数据！PRD §12.2 冻结结构，题目内容为占位） ----------
# 维度代码：ACT 活动水平 / APP 趋近-退缩 / ADP 适应性 / EMO 情绪强度
ASSESSMENT_QUESTIONS = [
    # (q_no, dimension, is_reverse, stem_0_12m, stem_1_6y)
    (1, "ACT", False, "宝宝醒着时手脚不停挥舞踢动", "孩子跑跳活动时很难安静下来"),
    (2, "ACT", False, "换尿布时宝宝总是扭动不停", "孩子坐着吃饭时也常常扭来扭去"),
    (3, "ACT", False, "宝宝吃奶时动作幅度很大", "孩子走路总是一路小跑"),
    (4, "ACT", True, "宝宝安静地躺着看东西能持续一阵", "孩子能安静坐着听完一个短故事"),
    (5, "APP", False, "陌生人靠近时宝宝会哭闹退缩", "见到陌生大人时孩子会躲到家长身后"),
    (6, "APP", False, "宝宝对新玩具要先观察很久才碰", "孩子进新环境要先抱一会儿才肯下地"),
    (7, "APP", False, "宝宝对新的声音光线表现敏感抗拒", "孩子拒绝尝试没见过的食物"),
    (8, "APP", True, "宝宝能较快接受新的洗澡流程", "孩子到新游乐场能很快开始玩"),
    (9, "ADP", False, "更换喂养方式后宝宝要哭闹好几天", "换新奶粉或新餐具孩子要闹好几天"),
    (10, "ADP", False, "作息打乱后宝宝要很久才恢复规律", "旅行回来后孩子作息要乱好几天"),
    (11, "ADP", False, "换新环境睡觉宝宝明显不安", "搬家或换床后孩子入睡明显变难"),
    (12, "ADP", True, "宝宝对日常小变化没什么反应", "临时改变计划孩子也能接受"),
    (13, "EMO", False, "宝宝饿或困时哭声激烈很难安抚", "需求没被满足时孩子大哭大闹很难哄"),
    (14, "EMO", False, "宝宝高兴时手舞足蹈反应强烈", "孩子开心时又蹦又叫特别兴奋"),
    (15, "EMO", False, "宝宝不适时的哭闹声特别响亮", "孩子生气时会摔东西或大声喊叫"),
    (16, "EMO", True, "宝宝大部分时间情绪平和", "孩子平时情绪比较平稳温和"),
]

# 5 点李克特选项（1=完全不符合 ... 5=完全符合）
LIKERT_OPTIONS = ["完全不符合", "比较不符合", "不确定", "比较符合", "完全符合"]


def seed(db: Session) -> None:
    """执行种子数据写入（幂等：按唯一键判重跳过）。

    Args:
        db: 数据库会话。

    Raises:
        Exception: 种子写入失败时抛出（事务回滚）。
    """
    # 1. 文案版本
    for text_id, content in TEXTS:
        exists = db.query(TextVersion).filter_by(text_id=text_id, version="V1").first()
        if not exists:
            db.add(TextVersion(
                text_id=text_id, version="V1", content=content,
                effective_at=NOW, requires_reconsent=False,
            ))

    # 2. 危机渠道（police 有公开号码 110；其余一律留空占位）
    for code, name, phone, category, region, hours, scope in CRISIS_CHANNELS:
        exists = db.query(CrisisChannel).filter_by(channel_code=code).first()
        if not exists:
            db.add(CrisisChannel(
                channel_code=code, channel_name=name,
                phone_number=phone if phone else None,  # 未确认号码留空
                script="请告知对方您的位置与当前情况。",
                category_scope=scope, status="placeholder" if not phone else "active",
                next_review_due_at=NOW + timedelta(days=90),
                category=category, region=region, service_hours=hours,
                verified_by="seed（未人工拨测）" if phone else None,
                verified_at=None,
            ))
        else:
            # 存量库补齐 V3.1 列（不覆盖运营已维护的字段）
            changed = False
            if not getattr(exists, "category", None):
                exists.category = category
                changed = True
            if not getattr(exists, "region", None):
                exists.region = region
                changed = True
            if getattr(exists, "service_hours", None) is None:
                exists.service_hours = hours
                changed = True
            if changed:
                db.flush()

    # 2.1 拟人化文案合规词表（RQ-02：类型 anthropomorphic，不参与风险拦截）
    for term in ANTHROPOMORPHIC_TERMS:
        th = sha256_hex(term)
        exists = db.query(LexiconTerm).filter_by(term_hash=th).first()
        if not exists:
            db.add(LexiconTerm(
                term_hash=th, term_enc=encrypt_field(term),
                lexicon_type="anthropomorphic", strategy="rewrite",
                category_code="anthropomorphic",
            ))

    # 3. 词库（term_hash 去重；词条密文存储）
    for term, ltype, strategy, category in LEXICON:
        th = sha256_hex(term)
        exists = db.query(LexiconTerm).filter_by(term_hash=th).first()
        if not exists:
            db.add(LexiconTerm(
                term_hash=th, term_enc=encrypt_field(term),
                lexicon_type=ltype, strategy=strategy, category_code=category,
            ))

    # 4. 风险规则配置
    for key, value in RISK_CONFIGS:
        exists = db.query(RiskRuleConfig).filter_by(config_key=key).first()
        if not exists:
            db.add(RiskRuleConfig(config_key=key, config_value=value, effective_at=NOW))

    # 5. 知识库条目
    for row in KB_ENTRIES:
        (kb_id, kind, domain, topic_key, topic_cat, age_band, pet_stage, species,
         title, content, preconditions, contra, stance) = row
        exists = db.query(KbEntry).filter_by(kb_id=kb_id).first()
        if not exists:
            db.add(KbEntry(
                kb_id=kb_id, kb_kind=kind, domain=domain, topic_key=topic_key,
                topic_category=topic_cat, age_band=age_band, pet_stage=pet_stage,
                species=species, title=title, content=content,
                preconditions=preconditions, contraindications=contra, stance=stance,
                source_type="literature_rewrite", source_ref="demo://seed-data",
                # RQ-07 信任条：来源等级 DR-10（示例条目按「学术文献」标注）
                source_level="academic",
                status="published", version=1, published_at=NOW,
                next_review_due_at=NOW + timedelta(days=365),
            ))

    # 5.1 科普全书 / 每日一则小知识专用条目（C 端只读取 daily_science_* 主题键）
    for raw in PUBLIC_SCIENCE_ENTRIES:
        exists = db.query(KbEntry).filter_by(kb_id=raw["kb_id"]).first()
        if not exists:
            db.add(KbEntry(
                kb_id=raw["kb_id"], kb_kind=raw["kb_kind"], domain=raw["domain"],
                topic_key=raw["topic_key"], topic_category=raw["topic_category"],
                age_band=raw["age_band"], pet_stage=raw["pet_stage"],
                species=raw["species"], title=raw["title"], content=raw["content"],
                preconditions=raw["preconditions"],
                contraindications=raw["contraindications"],
                stance="support",
                source_type=raw["source_type"], source_ref=raw["source_ref"],
                source_level=raw["source_level"],
                status="published", version=1, published_at=NOW,
                next_review_due_at=NOW + timedelta(days=365),
            ))

    # 6. 气质测评题库（题干存 assessment_pool 类 kb_entry，content 为 JSON 字符串）
    for q_no, dim, reverse, stem_baby, stem_child in ASSESSMENT_QUESTIONS:
        kb_id = f"kb_question_{q_no:02d}"
        exists = db.query(KbEntry).filter_by(kb_id=kb_id).first()
        if not exists:
            import json

            db.add(KbEntry(
                kb_id=kb_id, kb_kind="assessment_pool", domain="育儿",
                topic_key=f"temperament_{dim.lower()}",
                topic_category="气质测评题库",
                title=f"气质测评题 {q_no:02d}（{dim} 维度）",
                content=json.dumps({
                    "q_no": q_no, "dimension": dim, "reverse": reverse,
                    "stem_0_12m": stem_baby, "stem_1_6y": stem_child,
                    "options": LIKERT_OPTIONS,
                }, ensure_ascii=False),
                preconditions="合成演示数据：真实题库未定稿（PRD Q-08），仅用于联调",
                source_type="expert_original", source_ref="demo://question-bank-synthetic",
                status="published", version=1, published_at=NOW,
            ))

    # 7. 商品（19.9 元 = 19_900_000 micro；platform_scope 不含 ios）
    if not db.query(Product).filter_by(product_code="member_monthly").first():
        db.add(Product(
            product_code="member_monthly", name="Babe宝伴会员月卡",
            price_micro=19_900_000, duration_days=30,
            platform_scope=["android", "web"],
            entitlements=["深度养育方案", "月度养育计划", "宠物长期规划", "家庭复合方案"],
        ))

    # 8. 系统开关（5 个入口紧急下线，默认全部开）
    entry_switches = [
        ("switch.entry.child", "育儿问答入口"),
        ("switch.entry.pet", "宠物问答入口"),
        ("switch.entry.family", "家庭综合问答入口"),
        ("switch.entry.assessment", "气质测评入口"),
        ("switch.entry.member", "会员购买入口"),
    ]
    for key, name in entry_switches:
        exists = db.query(ConfigVersion).filter_by(
            config_type="switch", config_key=key, version=1
        ).first()
        if not exists:
            db.add(ConfigVersion(
                config_type="switch", config_key=key,
                snapshot={"enabled": True, "name": name},
                effective_at=NOW, reason="seed: init entries",
            ))

    # 9. 演示 C 端用户（openid 为占位密文；uid 必须是合法 UUID）
    demo_uid = "00000000-0000-0000-0000-000000000001"
    if not db.query(AppUser).filter_by(user_uid=demo_uid).first():
        db.add(AppUser(user_uid=demo_uid, wx_openid_enc=encrypt_field("demo-openid")))
        db.flush()
        demo_user = db.query(AppUser).filter_by(user_uid=demo_uid).first()
        # 基础同意默认已签（方便演示直接进入）
        db.add(ConsentRecord(
            user_id=demo_user.id, consent_type="base", consent_version="V1",
            guardian_verified=False,
        ))

    # 10. V3.1 分级规则（RQ-06 首批 5 类模板，Q-49 默认「保守从严」口径）
    from app.triage import templates as triage_templates

    for raw in triage_templates.TRIAGE_RULES:
        exists = db.query(TriageRule).filter_by(rule_id=raw["rule_id"]).first()
        if exists is None:
            db.add(TriageRule(
                rule_id=raw["rule_id"], scene=raw["scene"], domain=raw["domain"],
                title=raw["title"], age_min_months=raw["age_min_months"],
                age_max_months=raw["age_max_months"], conditions=raw["conditions"],
                level=raw["level"], priority=raw["priority"], basis=raw.get("basis"),
                observations=raw.get("observations"),
                escalation_flags=raw.get("escalation_flags"),
                contraindications=raw.get("contraindications"),
                disclaimers=raw.get("disclaimers"), source_ref=raw.get("source_ref"),
                status="active", version=1,
            ))

    # 11. V3.1 轻工具（RQ-12；内容来自知识资产，kb_refs 可追溯）
    from app.services.tool_service import BUILTIN_TOOLS

    for raw in BUILTIN_TOOLS:
        exists = db.query(ToolItem).filter_by(tool_code=raw["tool_code"]).first()
        if exists is None:
            db.add(ToolItem(
                tool_code=raw["tool_code"], title=raw["title"],
                tool_type=raw["tool_type"], domain=raw["domain"],
                summary=raw["summary"], kb_refs=raw["kb_refs"],
                content=raw["content"], sort_order=raw["sort_order"], status="on",
            ))

    # 12. V3.1 专题包（RQ-13 交叉主题 / RQ-14 宠物行为内容线）
    for raw in TOPIC_PACKS:
        exists = db.query(TopicPack).filter_by(topic_code=raw["topic_code"]).first()
        if exists is None:
            db.add(TopicPack(**raw))

    # 13. 品牌更名收尾（缺陷 N1）：存量库商品名残留旧品牌自动纠正
    for product in db.query(Product).all():
        if product.name and "小光景" in product.name:
            product.name = product.name.replace("小光景", "Babe宝伴")

    db.commit()
    try:
        from app.services.retriever import Retriever

        patched = Retriever().ensure_embeddings(db)
        print(f"[seed_data] embeddings ensured: {patched} entries")
        # 10.1 Milvus 向量索引重建（best-effort）：主通道就绪时全量重灌
        # jiaban_kb_entries 集合（真实/确定性嵌入经 embed_client 分发）；
        # 不可用静默跳过
        from app.services import rag_index

        if rag_index.available():
            written = rag_index.reindex_all(db)
            print(f"[seed_data] rag index reindexed: {written} entries to Milvus")
        else:
            print("[seed_data] Milvus unavailable, retrieval falls back to hashing path")
    except Exception as exc:  # noqa: BLE001 — 向量补算失败不阻断种子流程
        print(f"[seed_data] ensure_embeddings skipped: {exc}")


def seed_admins(db: Session) -> None:
    """写入后台账号种子（幂等；密码统一 Admin@123456，生产必须修改）。

    Args:
        db: 数据库会话。

    Raises:
        Exception: 写入失败抛出。
    """
    admins = [
        ("admin", "系统超管", "super_admin", None),
        ("operator", "内容运营", "operator", None),
        ("support", "客服专员", "support", None),
        ("expert_child", "育儿专家", "expert_child", "child"),
        ("expert_pet", "宠物专家", "expert_pet", "pet"),
    ]
    for username, display, role, scope in admins:
        if not db.query(AdminUser).filter_by(username=username).first():
            db.add(AdminUser(
                username=username, display_name=display, role=role,
                password_hash=hash_password("Admin@123456"),
                phone_enc=encrypt_field("13800000000"),
                domain_scope=scope,
                temp_auth_expire_at=NOW + timedelta(days=3650),  # 专家授权 10 年（演示）
            ))
    db.commit()
    print("[seed_data] admin accounts ready (password: Admin@123456)")


if __name__ == "__main__":
    session = get_session_factory()()
    try:
        seed_admins(session)
        seed(session)
    finally:
        session.close()
